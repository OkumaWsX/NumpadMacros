# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Botonera propia: reproduce archivos de audio por tus audífonos y por un
micrófono virtual, para que te escuchen en Discord, OBS o el juego.

- Windows y macOS: mezclador propio (sounddevice). El micrófono virtual es un
  dispositivo de audio aparte: VB-Cable en Windows ("CABLE Input") o BlackHole
  en macOS. Opcionalmente mezcla tu micrófono real, así hablas y suenan los
  efectos por el mismo micrófono virtual.
- Linux: usa PipeWire/PulseAudio. El programa crea él mismo el micrófono
  virtual "NumpadMacros-Mic" (y lo quita al cerrar).

En todos los sistemas la mezcla la hace el propio programa (clase _Bus):
iguala el volumen de los sonidos (LUFS), aplica el compresor/limitador y
mide los niveles que muestran los medidores de la ventana.
"""
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
from collections import deque

from . import loudness as ld

SR = 48000
AUDIO_EXT = (".mp3", ".wav", ".ogg", ".flac", ".opus", ".aiff", ".aif")

# Qué pasa al pulsar una tecla cuyo sonido ya está sonando
PLAY_MODES = [
    ("overlap", "Superponer (cada pulsación suena encima)"),
    ("restart", "Reiniciar (vuelve a empezar)"),
    ("toggle", "Alternar (pulsa para sonar, pulsa otra vez para detener)"),
    ("hold", "Mientras se mantiene (suena solo con la tecla apretada)"),
]


def clean_env():
    """Entorno para lanzar programas del sistema desde la app empaquetada.
    PyInstaller cambia LD_LIBRARY_PATH y eso rompe pactl/pw-play/pkexec."""
    env = os.environ.copy()
    if getattr(sys, "frozen", False):
        orig = env.pop("LD_LIBRARY_PATH_ORIG", None)
        if orig is not None:
            env["LD_LIBRARY_PATH"] = orig
        else:
            env.pop("LD_LIBRARY_PATH", None)
    return env


class SoundboardError(RuntimeError):
    pass


def title_of(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def make_soundboard(settings: dict):
    if sys.platform.startswith("linux"):
        return PipeWireBoard(settings)
    return MixerBoard(settings)




# ============================================================================ mezcla común
BLOCK = 480                   # 10 ms: tamaño de bloque al escribir por tubería (Linux)
MAX_VOICES = 16


class _Voice:
    __slots__ = ("data", "pos", "gain", "tag")

    def __init__(self, data, gain, tag):
        self.data, self.pos, self.gain, self.tag = data, 0, gain, tag


class _Bus:
    """Una salida (audífonos o micrófono virtual): mezcla las voces, aplica el
    compresor/limitador y mide el nivel para los medidores."""

    def __init__(self, np, settings, mic_feed=None):
        self.np = np
        self.settings = settings
        self.voices: list[_Voice] = []
        self.lock = threading.Lock()
        self.mic_feed = mic_feed
        self.comp = ld.Compressor(np)
        self.level = (-math.inf, -math.inf, 0.0, False)   # rms dB, pico dB, compresión dB, saturó
        self._sat_until = 0.0
        self.closed = False          # la salida se detuvo (por inactividad): no acepta voces
        self.idle_since = time.monotonic()

    def render(self, frames, out=None):
        np = self.np
        if out is None:
            out = np.zeros((frames, 2), dtype=np.float32)
        else:
            out.fill(0)
        if not self.voices and self.mic_feed is None:     # silencio: casi sin gastar procesador
            now = time.monotonic()
            self.comp.gr_db = 0.0
            self.comp.gain = 1.0
            self.level = (-math.inf, -math.inf, 0.0, now < self._sat_until)
            return out
        with self.lock:
            keep = []
            for v in self.voices:
                n = min(frames, len(v.data) - v.pos)
                out[:n] += v.data[v.pos:v.pos + n] * v.gain
                v.pos += n
                if v.pos < len(v.data):
                    keep.append(v)
            self.voices = keep
        if self.mic_feed is not None:
            out += self.mic_feed.read(frames)
        raw_peak = float(np.max(np.abs(out))) if frames else 0.0
        comp = self.settings.get("compressor") or {}
        now = time.monotonic()
        if comp.get("on", True):
            thr, ratio, ceil = ld.comp_params(self.settings)
            self.comp.process(out, thr, ratio, ceil)
        else:
            self.comp.gr_db = 0.0
            if raw_peak > 1.0:
                self._sat_until = now + 0.8
            np.clip(out, -1.0, 1.0, out=out)
        if raw_peak > 0:
            rms = float(np.sqrt(np.mean(out * out)))
            peak = float(np.max(np.abs(out)))
            self.level = (ld.lin_to_db(rms), ld.lin_to_db(peak), self.comp.gr_db, now < self._sat_until)
        else:
            self.level = (-math.inf, -math.inf, 0.0, now < self._sat_until)
        return out

    def add(self, data, gain, tag=None) -> bool:
        """False si la salida ya se cerró (hay que abrir otra)."""
        with self.lock:
            if self.closed:
                return False
            if len(self.voices) >= MAX_VOICES:
                self.voices.pop(0)
            self.voices.append(_Voice(data, gain, tag))
            self.idle_since = time.monotonic()
            return True

    def close_if_idle(self, seconds) -> bool:
        """Cierra la salida si lleva `seconds` en silencio. True si se cerró."""
        with self.lock:
            if self.voices or self.mic_feed is not None:
                self.idle_since = time.monotonic()
                return False
            if time.monotonic() - self.idle_since < seconds:
                return False
            self.closed = True
            return True

    def has(self, tag) -> bool:
        with self.lock:
            return any(v.tag == tag for v in self.voices)

    def stop_tag(self, tag):
        with self.lock:
            self.voices = [v for v in self.voices if v.tag != tag]

    def progress(self) -> dict:
        """{etiqueta: avance 0–1} de lo que está sonando."""
        with self.lock:
            return {v.tag: v.pos / max(1, len(v.data)) for v in self.voices if v.tag}

    def clear(self):
        with self.lock:
            self.voices = []


class _MicFeed:
    """Captura el micrófono real y lo entrega en bloques al micrófono virtual."""

    def __init__(self, sd, np, device):
        self.np = np
        self.buf: deque = deque()
        self.count = 0
        self.lock = threading.Lock()
        last = None
        for ch in (1, 2):
            try:
                self.stream = sd.InputStream(samplerate=SR, channels=ch, dtype="float32",
                                             device=device, callback=self._cb, latency="low")
                break
            except Exception as e:
                last = e
        else:
            raise SoundboardError(f"No pude abrir tu micrófono: {last}")
        self.stream.start()

    def _cb(self, indata, frames, _t, _status):
        mono = indata.mean(axis=1) if indata.shape[1] > 1 else indata[:, 0]
        with self.lock:
            self.buf.append(mono.copy())
            self.count += len(mono)
            while self.count > SR // 4 and self.buf:      # no acumular más de 250 ms
                self.count -= len(self.buf.popleft())

    def read(self, frames):
        np = self.np
        out = np.zeros(frames, dtype=np.float32)
        filled = 0
        with self.lock:
            while filled < frames and self.buf:
                chunk = self.buf[0]
                take = min(frames - filled, len(chunk))
                out[filled:filled + take] = chunk[:take]
                if take < len(chunk):
                    self.buf[0] = chunk[take:]
                else:
                    self.buf.popleft()
                filled += take
                self.count -= take
        return out[:, None]

    def close(self):
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:
            pass


class _SDSink:
    """Salida por sounddevice (Windows y macOS)."""

    def __init__(self, sd, bus, device):
        self.bus = bus
        self.stream = sd.OutputStream(samplerate=SR, channels=2, dtype="float32",
                                      device=device, callback=self._cb, latency="low")
        self.stream.start()

    def _cb(self, out, frames, _t, _status):
        self.bus.render(frames, out)

    def alive(self):
        return True

    def close(self):
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:
            pass


class _PipeSink:
    """Salida por tubería a pw-cat o pacat (Linux): el programa mezcla y le
    entrega audio crudo en bloques de 10 ms mientras suena algo. Tras unos
    segundos de silencio se cierra sola (no queda un flujo abierto todo el rato)
    y se vuelve a abrir con el siguiente sonido."""
    IDLE_CLOSE = 4.0

    def __init__(self, cmd, bus):
        self.bus = bus
        self.stop = False
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, env=clean_env(), bufsize=0)
        try:                         # tubería chica = poca latencia
            import fcntl
            fcntl.fcntl(self.proc.stdin.fileno(), 1031, 16384)   # F_SETPIPE_SZ (~40 ms)
        except Exception:
            pass
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        buf = None
        try:
            while not self.stop:
                if self.bus.close_if_idle(self.IDLE_CLOSE):
                    break
                buf = self.bus.render(BLOCK, buf)
                self.proc.stdin.write(buf.tobytes())
        except (BrokenPipeError, OSError, ValueError):
            pass
        self.stop = True
        self.bus.closed = True
        try:
            self.proc.stdin.close()
        except Exception:
            pass

    def alive(self):
        return not self.stop and self.proc.poll() is None and self.thread.is_alive()

    def close(self):
        self.stop = True
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=1)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass


class _BoardBase:
    """Lo común: cargar archivos, medir su volumen, reproducir y medidores."""
    kind = ""

    def __init__(self, settings: dict):
        self.settings = settings
        self.np = self.sf = None
        self._err = None
        try:
            import numpy as np
            import soundfile as sf
            self.np, self.sf = np, sf
        except Exception as e:
            self._err = f"Faltan dependencias de audio ({e})"
        self._lock = threading.Lock()
        self._cache: dict[str, tuple] = {}
        self._cache_lock = threading.Lock()
        self._lufs: dict[str, tuple] = {}
        self.spk: _Bus | None = None
        self.mic: _Bus | None = None

    def available(self):
        return (self._err is None, self._err or "")

    # ---------------------------------------------------------------- archivos
    CACHE_BYTES = 768 * 1024 * 1024      # memoria máxima para sonidos ya decodificados

    def _decode(self, path, max_seconds=None):
        """Lee el archivo como estéreo float32 a 48 kHz (sin guardarlo en caché)."""
        np = self.np
        try:
            frames = -1
            if max_seconds:
                frames = int(self.sf.info(path).samplerate * max_seconds)
            data, sr = self.sf.read(path, dtype="float32", always_2d=True, frames=frames)
        except Exception as e:
            raise SoundboardError(f"No pude leer «{os.path.basename(path)}»: {e}")
        if data.shape[1] == 1:
            data = np.repeat(data, 2, axis=1)
        elif data.shape[1] > 2:
            data = data[:, :2]
        if sr != SR and len(data) > 1:
            n = int(round(len(data) * SR / sr))
            x_old = np.arange(len(data))
            x_new = np.linspace(0, len(data) - 1, n)
            data = np.stack([np.interp(x_new, x_old, data[:, c]) for c in range(2)],
                            axis=1).astype(np.float32)
        return np.ascontiguousarray(data)

    def _load(self, path):
        mtime = os.path.getmtime(path)
        with self._cache_lock:
            hit = self._cache.pop(path, None)
            if hit and hit[0] == mtime:
                self._cache[path] = hit          # queda como el más reciente
                return hit[1]
        data = self._decode(path)
        with self._cache_lock:
            self._cache[path] = (mtime, data)
            total = sum(d.nbytes for _m, d in self._cache.values())
            while total > self.CACHE_BYTES and len(self._cache) > 1:
                _m, old = self._cache.pop(next(iter(self._cache)))
                total -= old.nbytes
        return data

    def loudness(self, path):
        """Volumen percibido del archivo en LUFS (None si es silencio)."""
        if self._err:
            raise SoundboardError(self._err)
        mtime = os.path.getmtime(path)
        hit = self._lufs.get(path)
        if hit and hit[0] == mtime:
            return hit[1]
        cached = self._cache.get(path)
        if cached and cached[0] == mtime:
            data = cached[1]
        else:                                    # medir no llena la memoria con la biblioteca
            data = self._decode(path, ld.MAX_SECONDS)
        value = ld.measure(self.np, data)
        self._lufs[path] = (mtime, value)
        return value

    def set_known_loudness(self, path, mtime, value):
        """Medición guardada en la biblioteca (para no volver a calcularla)."""
        self._lufs[path] = (mtime, value)

    def norm_gain_db(self, path) -> float:
        if not self.settings.get("normalize", True):
            return 0.0
        try:
            return ld.norm_gain_db(self.loudness(path), self.settings.get("target_lufs", -16.0))
        except (SoundboardError, OSError):
            return 0.0

    # ---------------------------------------------------------------- salidas
    def _buses(self):
        return [b for b in (self.spk, self.mic) if b]

    def levels(self):
        """{'spk': (rms, pico, compresión, saturó) o None, 'mic': ...}"""
        return {"spk": self.spk.level if self.spk else None,
                "mic": self.mic.level if self.mic else None}

    def playing(self, tag) -> bool:
        return any(b.has(tag) for b in self._buses())

    def stop_tag(self, tag):
        for b in self._buses():
            b.stop_tag(tag)

    def progress(self) -> dict:
        out = {}
        for b in self._buses():
            for tag, p in b.progress().items():
                out[tag] = max(out.get(tag, 0.0), p)
        return out

    def stop_all(self):
        for b in self._buses():
            b.clear()

    def _ensure(self):
        raise NotImplementedError

    def play(self, path, volume=1.0, speakers=True, mic=True, tag=None, mode="overlap"):
        """Devuelve el título, o None si la tecla detuvo su sonido (modo alternar)."""
        if self._err:
            raise SoundboardError(self._err)
        if mode == "toggle" and tag and self.playing(tag):
            self.stop_tag(tag)
            return None
        if not os.path.isfile(path):
            raise SoundboardError(f"No existe el archivo «{path}»")
        data = self._load(path)
        gain = (max(0.0, float(volume)) * float(self.settings.get("volume", 1.0))
                * ld.db_to_lin(self.norm_gain_db(path)))
        with self._lock:
            try:
                self._ensure()
            except SoundboardError:
                raise
            except Exception as e:
                self._close_streams()
                raise SoundboardError(f"No pude abrir el audio: {e}")
            if tag and mode in ("restart", "hold"):
                self.stop_tag(tag)
            for _attempt in range(2):
                ok = True
                if speakers and self.spk:
                    ok = self.spk.add(data, gain, tag) and ok
                if mic and self.mic:
                    ok = self.mic.add(data, gain, tag) and ok
                if ok:
                    break
                self._ensure()                   # la salida se cerró por silencio: abrir otra
            if mic and not self.mic and not speakers:
                raise SoundboardError("Elige el micrófono virtual en la pestaña Audio")
        return title_of(path)

    def test_tone(self):
        """Pitido corto solo por los audífonos, para comprobar la salida elegida."""
        if self._err:
            raise SoundboardError(self._err)
        np = self.np
        t = np.arange(int(SR * 0.35)) / SR
        tone = (0.25 * np.sin(2 * np.pi * 880 * t) * np.minimum(1, np.minimum(t, t[::-1]) / 0.02))
        data = np.ascontiguousarray(np.stack([tone, tone], 1).astype(np.float32))
        with self._lock:
            self._ensure()
            if not (self.spk and self.spk.add(data, 1.0, "prueba")):
                self._ensure()
                if self.spk:
                    self.spk.add(data, 1.0, "prueba")

    def _close_streams(self):
        raise NotImplementedError

    def close(self):
        with self._lock:
            self._close_streams()


# ============================================================================ Windows / macOS
class MixerBoard(_BoardBase):
    kind = "mixer"
    VIRTUAL_HINTS = ("CABLE Input", "BlackHole", "VB-Audio", "Loopback")

    def __init__(self, settings: dict):
        super().__init__(settings)
        self.sd = None
        if not self._err:
            try:
                import sounddevice as sd
                self.sd = sd
            except Exception as e:   # ImportError u OSError si falta PortAudio
                self._err = f"Faltan dependencias de audio ({e})"
        self._sinks: list = []
        self._feed = None
        self._opened = None

    # ---------------------------------------------------------------- dispositivos
    def _hostapi(self):
        """En Windows hay varias APIs con los mismos dispositivos repetidos; se usa
        DirectSound, que convierte la frecuencia de muestreo sola."""
        if sys.platform != "win32":
            return None
        for i, h in enumerate(self.sd.query_hostapis()):
            if "DirectSound" in h["name"]:
                return i
        return None

    def _devices(self, kind):
        if self._err:
            return []
        api = self._hostapi()
        key = "max_output_channels" if kind == "out" else "max_input_channels"
        out = []
        for i, d in enumerate(self.sd.query_devices()):
            if d[key] > 0 and (api is None or d["hostapi"] == api):
                if d["name"] not in [n for _, n in out]:
                    out.append((i, d["name"]))
        return out

    def outputs(self):
        return [n for _, n in self._devices("out")]

    def inputs(self):
        return [n for _, n in self._devices("in")]

    def suggested_mic(self):
        for name in self.outputs():
            if any(h.lower() in name.lower() for h in self.VIRTUAL_HINTS):
                return name
        return ""

    def virtual_mic_missing(self) -> bool:
        """True si no hay ningún micrófono virtual instalado (VB-Cable/BlackHole)."""
        return not self._err and not self.suggested_mic()

    def _index(self, name, kind):
        if not name:
            return None
        for i, n in self._devices(kind):
            if n == name:
                return i
        raise SoundboardError(f"No encuentro el dispositivo «{name}»")

    def status(self):
        if self._err:
            return self._err
        mic = self.settings.get("mic_device")
        if not mic:
            return "Sin micrófono virtual: solo se escucha en tus audífonos"
        return f"Micrófono virtual: {mic}"

    # ---------------------------------------------------------------- streams
    def _ensure(self):
        s = self.settings
        want = (s.get("monitor_device", ""), s.get("mic_device", ""),
                bool(s.get("mix_mic")), s.get("mic_input", ""))
        if want == self._opened:
            return
        self._close_streams()
        np = self.np
        self.spk = _Bus(np, s)
        self._sinks.append(_SDSink(self.sd, self.spk, self._index(want[0], "out")))
        if want[1]:
            if want[2]:
                self._feed = _MicFeed(self.sd, np, self._index(want[3], "in"))
            self.mic = _Bus(np, s, self._feed)
            self._sinks.append(_SDSink(self.sd, self.mic, self._index(want[1], "out")))
        self._opened = want

    def _close_streams(self):
        for x in self._sinks + [self._feed]:
            if x is not None:
                x.close()
        self._sinks = []
        self._feed = None
        self.spk = self.mic = None
        self._opened = None

    def apply(self):
        """Reabre los dispositivos con los ajustes actuales."""
        if self._err:
            return
        with self._lock:
            self._close_streams()
            self._ensure()


# ============================================================================ Linux
class PipeWireBoard(_BoardBase):
    kind = "pipewire"
    SINK = "numpad_macros_sink"
    SRC = "numpad_macros_mic"
    MIC_LABEL = "NumpadMacros-Mic"

    def __init__(self, settings: dict):
        super().__init__(settings)
        self.player = "pw-cat" if shutil.which("pw-cat") else ("pacat" if shutil.which("pacat") else None)
        self.pactl = shutil.which("pactl")
        self._ready = False
        self._sinks: list = []
        if not self._err and (not self.pactl or not self.player):
            self._err = ("Falta PipeWire/PulseAudio (comandos pactl y pw-cat o pacat). "
                         "En Arch/CachyOS: sudo pacman -S pipewire-pulse")

    def _run(self, *args) -> str:
        # si el audio del sistema se trabó, no esperar 5 s en cada llamada (la app se congelaría)
        if time.monotonic() < getattr(self, "_hung_until", 0):
            raise SoundboardError("El audio del sistema (PipeWire) no responde.")
        try:
            r = subprocess.run([self.pactl, *args], capture_output=True, text=True, timeout=5,
                               env=clean_env())
        except subprocess.TimeoutExpired:
            self._hung_until = time.monotonic() + 30
            raise SoundboardError("El audio del sistema (PipeWire) no responde.")
        if r.returncode != 0:
            raise SoundboardError((r.stderr or r.stdout).strip() or f"pactl {args[0]} falló")
        return r.stdout

    def _modules(self):
        mods = []
        for line in self._run("list", "short", "modules").splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                mods.append((parts[0], parts[1], parts[2] if len(parts) > 2 else ""))
        return mods

    def outputs(self):
        """Salidas de audio (audífonos/parlantes) como «descripción [nombre]»."""
        if self._err:
            return []
        out = []
        try:
            data = json.loads(self._run("-f", "json", "list", "sinks"))
            for s in data:
                name = s.get("name", "")
                if not name or name == self.SINK:
                    continue
                out.append(f"{s['description']} [{name}]" if s.get("description") else name)
        except (SoundboardError, ValueError, subprocess.TimeoutExpired):
            try:
                for line in self._run("list", "short", "sinks").splitlines():
                    parts = line.split("\t")
                    if len(parts) > 1 and parts[1] != self.SINK:
                        out.append(parts[1])
            except SoundboardError:
                pass
        return out

    def inputs(self):
        """Micrófonos reales (nombre interno, descripción)."""
        if self._err:
            return []
        out = []
        try:
            data = json.loads(self._run("-f", "json", "list", "sources"))
            for s in data:
                name = s.get("name", "")
                if name.endswith(".monitor") or name == self.SRC:
                    continue
                out.append(name if not s.get("description") else f"{s['description']} [{name}]")
        except (SoundboardError, ValueError, subprocess.TimeoutExpired):
            try:
                for line in self._run("list", "short", "sources").splitlines():
                    parts = line.split("\t")
                    if len(parts) > 1 and not parts[1].endswith(".monitor") and parts[1] != self.SRC:
                        out.append(parts[1])
            except SoundboardError:
                pass
        return out

    def suggested_mic(self):
        return self.MIC_LABEL

    def virtual_mic_missing(self) -> bool:
        return False                 # en Linux se crea solo

    @staticmethod
    def _source_name(label: str) -> str:
        if label.endswith("]") and "[" in label:
            return label[label.rindex("[") + 1:-1]
        return label

    def status(self):
        if self._err:
            return self._err
        if self._ready:
            return f"Micrófono virtual «{self.MIC_LABEL}» listo: elígelo como micrófono en Discord/OBS"
        return "El micrófono virtual se crea al iniciar"

    def _setup_modules(self):
        mods = self._modules()
        have_sink = any(n == "module-null-sink" and f"sink_name={self.SINK}" in a for _, n, a in mods)
        have_src = any(n == "module-remap-source" and f"source_name={self.SRC}" in a for _, n, a in mods)
        for mid, n, a in mods:     # el loopback del mic real se rehace siempre
            if n == "module-loopback" and f"sink={self.SINK}" in a:
                self._run("unload-module", mid)
        if not have_sink:
            self._run("load-module", "module-null-sink", f"sink_name={self.SINK}",
                      "sink_properties=device.description=NumpadMacros-Salida")
        if not have_src:
            self._run("load-module", "module-remap-source", f"master={self.SINK}.monitor",
                      f"source_name={self.SRC}",
                      f"source_properties=device.description={self.MIC_LABEL}")
        if self.settings.get("mix_mic"):
            src = self._source_name(self.settings.get("mic_input", "")) or \
                self._run("get-default-source").strip()
            if src and src != self.SRC and not src.startswith(self.SINK):
                self._run("load-module", "module-loopback", f"source={src}",
                          f"sink={self.SINK}", "latency_msec=20")
        self._ready = True

    _raw_flag = None

    @classmethod
    def _pwcat_raw(cls):
        """Las versiones nuevas de pw-cat (PipeWire 1.2+) necesitan --raw para leer audio crudo
        desde la tubería; sin él intentan adivinar el formato y suena estática."""
        if cls._raw_flag is None:
            try:
                r = subprocess.run(["pw-cat", "--help"], capture_output=True, text=True, timeout=5,
                                   env=clean_env())
                cls._raw_flag = "--raw" in (r.stdout + r.stderr)
            except Exception:
                cls._raw_flag = False
        return cls._raw_flag

    def _cmd(self, target, name):
        if self.player == "pw-cat":
            cmd = ["pw-cat", "--playback"] + (["--raw"] if self._pwcat_raw() else []) + [
                "--format", "f32", "--rate", str(SR), "--channels", "2",
                "--latency", "40ms", "-P", f"{{ node.description = \"Numpad Macros ({name})\" }}"]
            if target:
                cmd += ["--target", target]
            return cmd + ["-"]
        cmd = ["pacat", "--playback", "--raw", "--format=float32le", f"--rate={SR}", "--channels=2",
               "--latency-msec=30", f"--client-name=Numpad Macros ({name})"]
        if target:
            cmd.append(f"--device={target}")
        return cmd

    def _ensure(self):
        if self._sinks and all(s.alive() for s in self._sinks):
            return
        self._close_streams()
        if not self._ready:
            self._setup_modules()
        self.spk = _Bus(self.np, self.settings)
        self.mic = _Bus(self.np, self.settings)
        spk_target = self._source_name(self.settings.get("monitor_device", "")) or None
        self._sinks = [_PipeSink(self._cmd(spk_target, "audífonos"), self.spk),
                       _PipeSink(self._cmd(self.SINK, "micrófono"), self.mic)]

    def _close_streams(self):
        for s in self._sinks:
            s.close()
        self._sinks = []
        self.spk = self.mic = None

    def apply(self):
        """Crea (o rehace) el micrófono virtual según los ajustes."""
        if self._err:
            return
        with self._lock:
            self._close_streams()
            self._setup_modules()
            self._ensure()

    def close(self):
        with self._lock:
            self._close_streams()
            if self._err:
                return
            try:
                ours = {"module-loopback": f"sink={self.SINK}",
                        "module-remap-source": f"source_name={self.SRC}",
                        "module-null-sink": f"sink_name={self.SINK}"}
                mods = self._modules()
                for kind in ours:          # en orden: loopback, micrófono, salida
                    for mid, n, a in mods:
                        if n == kind and ours[kind] in a:
                            self._run("unload-module", mid)
            except (SoundboardError, subprocess.TimeoutExpired):
                pass
            self._ready = False
