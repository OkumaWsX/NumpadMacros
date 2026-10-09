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
"""
import json
import os
import shutil
import subprocess
import sys
import threading
from collections import deque

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


# ============================================================================ Windows / macOS
class _Voice:
    __slots__ = ("data", "pos", "gain", "tag")

    def __init__(self, data, gain, tag):
        self.data, self.pos, self.gain, self.tag = data, 0, gain, tag


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


class _Output:
    def __init__(self, sd, np, device, mic_feed=None):
        self.np = np
        self.voices: list[_Voice] = []
        self.lock = threading.Lock()
        self.mic_feed = mic_feed
        self.stream = sd.OutputStream(samplerate=SR, channels=2, dtype="float32",
                                      device=device, callback=self._cb, latency="low")
        self.stream.start()

    def _cb(self, out, frames, _t, _status):
        out.fill(0)
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
        self.np.clip(out, -1.0, 1.0, out=out)

    def add(self, data, gain, tag=None):
        with self.lock:
            if len(self.voices) >= 16:
                self.voices.pop(0)
            self.voices.append(_Voice(data, gain, tag))

    def has(self, tag) -> bool:
        with self.lock:
            return any(v.tag == tag for v in self.voices)

    def stop_tag(self, tag):
        with self.lock:
            self.voices = [v for v in self.voices if v.tag != tag]

    def clear(self):
        with self.lock:
            self.voices = []

    def close(self):
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:
            pass


class MixerBoard:
    kind = "mixer"
    VIRTUAL_HINTS = ("CABLE Input", "BlackHole", "VB-Audio", "Loopback")

    def __init__(self, settings: dict):
        self.settings = settings
        self.sd = self.np = self.sf = None
        self._err = None
        try:
            import numpy as np
            import sounddevice as sd
            import soundfile as sf
            self.np, self.sd, self.sf = np, sd, sf
        except Exception as e:   # ImportError u OSError si falta PortAudio
            self._err = f"Faltan dependencias de audio ({e})"
        self._lock = threading.Lock()
        self._mon = self._mic = self._feed = None
        self._opened = None
        self._cache: dict[str, tuple] = {}

    # ---------------------------------------------------------------- dispositivos
    def available(self):
        return (self._err is None, self._err or "")

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
        self._mon = _Output(self.sd, self.np, self._index(want[0], "out"))
        if want[1]:
            feed = None
            if want[2]:
                feed = _MicFeed(self.sd, self.np, self._index(want[3], "in"))
            self._feed = feed
            self._mic = _Output(self.sd, self.np, self._index(want[1], "out"), feed)
        self._opened = want

    def _close_streams(self):
        for x in (self._mon, self._mic, self._feed):
            if x is not None:
                x.close()
        self._mon = self._mic = self._feed = None
        self._opened = None

    def apply(self):
        """Reabre los dispositivos con los ajustes actuales."""
        if self._err:
            return
        with self._lock:
            self._close_streams()
            self._ensure()

    def _load(self, path):
        np = self.np
        mtime = os.path.getmtime(path)
        hit = self._cache.get(path)
        if hit and hit[0] == mtime:
            return hit[1]
        try:
            data, sr = self.sf.read(path, dtype="float32", always_2d=True)
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
        data = np.ascontiguousarray(data)
        if len(self._cache) > 64:
            self._cache.pop(next(iter(self._cache)))
        self._cache[path] = (mtime, data)
        return data

    def _outs(self):
        return [o for o in (self._mon, self._mic) if o]

    def playing(self, tag) -> bool:
        return any(o.has(tag) for o in self._outs())

    def stop_tag(self, tag):
        with self._lock:
            for o in self._outs():
                o.stop_tag(tag)

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
        gain = float(volume) * float(self.settings.get("volume", 1.0))
        with self._lock:
            try:
                self._ensure()
            except SoundboardError:
                raise
            except Exception as e:
                self._close_streams()
                raise SoundboardError(f"No pude abrir el audio: {e}")
            if tag and mode in ("restart", "hold"):
                for o in self._outs():
                    o.stop_tag(tag)
            if speakers and self._mon:
                self._mon.add(data, gain, tag)
            if mic:
                if not self._mic:
                    if not speakers:
                        raise SoundboardError("Elige el micrófono virtual en la pestaña Audio")
                else:
                    self._mic.add(data, gain, tag)
        return title_of(path)

    def stop_all(self):
        with self._lock:
            for o in (self._mon, self._mic):
                if o:
                    o.clear()

    def close(self):
        with self._lock:
            self._close_streams()


# ============================================================================ Linux
class PipeWireBoard:
    kind = "pipewire"
    SINK = "numpad_macros_sink"
    SRC = "numpad_macros_mic"
    MIC_LABEL = "NumpadMacros-Mic"

    def __init__(self, settings: dict):
        self.settings = settings
        self.procs: list[tuple[str, subprocess.Popen]] = []
        self._lock = threading.Lock()
        self.player = "pw-play" if shutil.which("pw-play") else ("paplay" if shutil.which("paplay") else None)
        self.pactl = shutil.which("pactl")
        self._ready = False
        self._err = None
        if not self.pactl or not self.player:
            self._err = ("Falta PipeWire/PulseAudio (comandos pactl y pw-play o paplay). "
                         "En Arch/CachyOS: sudo pacman -S pipewire-pulse")

    def _run(self, *args) -> str:
        r = subprocess.run([self.pactl, *args], capture_output=True, text=True, timeout=5,
                           env=clean_env())
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

    def available(self):
        return (self._err is None, self._err or "")

    def outputs(self):
        return []

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

    def apply(self):
        """Crea (o rehace) el micrófono virtual según los ajustes."""
        if self._err:
            return
        with self._lock:
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

    @staticmethod
    def _kill(procs):
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=1)
            except subprocess.TimeoutExpired:
                p.kill()

    def playing(self, tag) -> bool:
        with self._lock:
            return any(t == tag and p.poll() is None for t, p in self.procs)

    def stop_tag(self, tag):
        with self._lock:
            mine = [p for t, p in self.procs if t == tag]
            self.procs = [(t, p) for t, p in self.procs if t != tag]
        self._kill(mine)

    def play(self, path, volume=1.0, speakers=True, mic=True, tag=None, mode="overlap"):
        """Devuelve el título, o None si la tecla detuvo su sonido (modo alternar)."""
        if self._err:
            raise SoundboardError(self._err)
        if mode == "toggle" and tag and self.playing(tag):
            self.stop_tag(tag)
            return None
        if not os.path.isfile(path):
            raise SoundboardError(f"No existe el archivo «{path}»")
        if mic and not self._ready:
            self.apply()
        if tag and mode in ("restart", "hold"):
            self.stop_tag(tag)
        v = max(0.0, float(volume) * float(self.settings.get("volume", 1.0)))
        targets = ([None] if speakers else []) + ([self.SINK] if mic else [])
        env = clean_env()
        with self._lock:
            self.procs = [(t, p) for t, p in self.procs if p.poll() is None]
            for target in targets:
                if self.player == "pw-play":
                    cmd = ["pw-play", "--volume", f"{v:.2f}"]
                    if target:
                        cmd += ["--target", target]
                else:
                    cmd = ["paplay", f"--volume={int(v * 65536)}"]
                    if target:
                        cmd.append(f"--device={target}")
                cmd.append(path)
                self.procs.append((tag, subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                                         stderr=subprocess.DEVNULL, env=env)))
        return title_of(path)

    def stop_all(self):
        with self._lock:
            procs = [p for _, p in self.procs]
            self.procs = []
        self._kill(procs)

    def close(self):
        self.stop_all()
        if self._err:
            return
        with self._lock:
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
