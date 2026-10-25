# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Pruebas de las piezas por plataforma con dispositivos simulados."""
import copy
import os
import stat
import sys
import tempfile
import threading
import time
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from npm import config, keys  # noqa: E402
from npm.engine import Engine  # noqa: E402


def drain(q):
    out = []
    while not q.empty():
        out.append(q.get())
    return out


class KeyMaps(unittest.TestCase):
    def test_evdev(self):
        self.assertEqual(keys.evdev_kid(71), "47")      # KEY_KP7
        self.assertEqual(keys.evdev_kid(69), "45")      # KEY_NUMLOCK
        self.assertEqual(keys.evdev_kid(96), "e0:1c")   # KEY_KPENTER
        self.assertEqual(keys.evdev_kid(98), "e0:35")   # KEY_KPSLASH
        self.assertEqual(keys.evdev_kid(117), "ev:117")
        try:
            from evdev import ecodes as e
        except ImportError:
            return
        for name in ("KP0", "KP1", "KP2", "KP3", "KP4", "KP5", "KP6", "KP7", "KP8", "KP9",
                     "KPDOT", "KPPLUS", "KPMINUS", "KPASTERISK", "KPSLASH", "KPENTER", "NUMLOCK"):
            self.assertIn(keys.evdev_kid(getattr(e, f"KEY_{name}")), keys.NUMPAD_IDS, name)

    def test_hid(self):
        got = {keys.hid_kid(u) for u in range(0x53, 0x64)}
        self.assertEqual(got, set(keys.NUMPAD_IDS))
        self.assertEqual(keys.hid_kid(0x67), "hid:67")

    def test_sender_tables_cover_choices(self):
        from npm import send_mac, send_win
        self.assertTrue(set(keys.KEY_CHOICES) <= set(keys.KEYS))
        mac_missing = set(keys.KEY_CHOICES) - set(send_mac.MAC_KEYS) - send_mac.QuartzSender.unsupported
        self.assertEqual(mac_missing, set())
        self.assertTrue(hasattr(send_win, "KeySender"))
        try:
            import evdev  # noqa: F401  (solo existe en Linux)
        except ImportError:
            return
        from npm.send_linux import _tables
        k, m = _tables()
        self.assertTrue(set(keys.KEY_CHOICES) <= set(k))
        self.assertTrue(set(keys.MODIFIERS) <= set(m))


# ------------------------------------------------------------------ botonera (mezclador)
class FakeStream:
    def __init__(self, callback=None, device=None, channels=2, **kw):
        self.callback, self.device, self.channels = callback, device, channels
        self.started = self.closed = False

    def start(self):
        self.started = True

    def stop(self):
        pass

    def close(self):
        self.closed = True


class MixerTest(unittest.TestCase):
    def setUp(self):
        try:
            import numpy as np
            import soundfile as sf
        except ImportError:
            self.skipTest("numpy/soundfile no instalados")
        self.np, self.sf = np, sf
        from npm.soundboard import MixerBoard
        streams = []

        def out_stream(**kw):
            s = FakeStream(**kw)
            streams.append(("out", s))
            return s

        def in_stream(**kw):
            s = FakeStream(**kw)
            streams.append(("in", s))
            return s
        sd = types.SimpleNamespace(
            OutputStream=out_stream, InputStream=in_stream,
            query_hostapis=lambda: [{"name": "Core Audio"}],
            query_devices=lambda: [
                {"name": "Parlantes", "max_output_channels": 2, "max_input_channels": 0, "hostapi": 0},
                {"name": "BlackHole 2ch", "max_output_channels": 2, "max_input_channels": 2, "hostapi": 0},
                {"name": "Micrófono MacBook", "max_output_channels": 0, "max_input_channels": 1, "hostapi": 0},
            ])
        self.settings = copy.deepcopy(config.DEFAULT["audio"])
        # estas pruebas revisan el ruteo: sin nivelación ni compresor
        self.settings["normalize"] = False
        self.settings["compressor"]["on"] = False
        self.board = MixerBoard(self.settings)
        self.board.sd, self.board.np, self.board.sf, self.board._err = sd, np, sf, None
        self.streams = streams
        d = tempfile.mkdtemp()
        self.wav = os.path.join(d, "beep.wav")
        t = np.arange(44100 // 2) / 44100
        sf.write(self.wav, (0.5 * np.sin(2 * np.pi * 440 * t)).astype("float32"), 44100)

    def run_cb(self, stream, frames=512):
        out = self.np.zeros((frames, 2), dtype="float32")
        stream.callback(out, frames, None, None)
        return out

    def test_devices_and_suggestion(self):
        self.assertEqual(self.board.suggested_mic(), "BlackHole 2ch")
        self.assertEqual(self.board.inputs(), ["BlackHole 2ch", "Micrófono MacBook"])

    def test_play_monitor_and_mic_with_resample(self):
        self.settings["mic_device"] = "BlackHole 2ch"
        self.assertEqual(self.board.play(self.wav, 1.0, True, True), "beep")
        outs = [s for k, s in self.streams if k == "out"]
        self.assertEqual(len(outs), 2)
        self.assertEqual(outs[1].device, 1)
        data = self.board._cache[self.wav][1]
        self.assertEqual(len(data), 24000)              # 0,5 s a 48 kHz
        a = self.run_cb(outs[0])
        b = self.run_cb(outs[1])
        self.assertGreater(abs(a).max(), 0.3)
        self.assertTrue(self.np.allclose(a, b))
        self.board.stop_all()
        self.assertEqual(abs(self.run_cb(outs[0])).max(), 0)

    def test_only_mic_line(self):
        self.settings["mic_device"] = "BlackHole 2ch"
        self.board.play(self.wav, 1.0, speakers=False, mic=True)
        mon, mic = [s for k, s in self.streams if k == "out"]
        self.assertEqual(abs(self.run_cb(mon)).max(), 0)
        self.assertGreater(abs(self.run_cb(mic)).max(), 0.3)

    def test_mic_needs_device(self):
        from npm.soundboard import SoundboardError
        with self.assertRaises(SoundboardError):
            self.board.play(self.wav, 1.0, speakers=False, mic=True)

    def test_mix_real_mic(self):
        self.settings.update(mic_device="BlackHole 2ch", mix_mic=True)
        self.board.apply()
        inp = [s for k, s in self.streams if k == "in"][0]
        mic_out = [s for k, s in self.streams if k == "out"][1]
        inp.callback(self.np.full((256, inp.channels), 0.25, dtype="float32"), 256, None, None)
        out = self.run_cb(mic_out, 256)
        self.assertTrue(self.np.allclose(out, 0.25))
        self.assertEqual(abs(self.run_cb(mic_out, 256)).max(), 0)   # sin datos nuevos: silencio

    def test_modes(self):
        mon = lambda: [s for k, s in self.streams if k == "out"][0]
        self.board.play(self.wav, tag="k", mode="overlap")
        self.board.play(self.wav, tag="k", mode="overlap")
        self.assertEqual(len(mon().callback.__self__.bus.voices), 2)
        self.board.play(self.wav, tag="k", mode="restart")
        self.assertEqual(len(mon().callback.__self__.bus.voices), 1)
        self.assertIsNone(self.board.play(self.wav, tag="k", mode="toggle"))   # detiene
        self.assertEqual(len(mon().callback.__self__.bus.voices), 0)
        self.assertEqual(self.board.play(self.wav, tag="k", mode="toggle"), "beep")  # vuelve a sonar
        self.board.stop_tag("k")
        self.assertFalse(self.board.playing("k"))

    def test_normalize_compressor_and_meters(self):
        np = self.np
        self.settings.update(normalize=True, target_lufs=-16.0)
        self.settings["compressor"]["on"] = True
        lufs = self.board.loudness(self.wav)
        self.assertAlmostEqual(lufs, -6.7, delta=1.0)          # seno de 0,5 (mono -> estéreo)
        self.assertAlmostEqual(self.board.norm_gain_db(self.wav), -16.0 - lufs, delta=0.01)
        self.board.play(self.wav, 1.0)
        out = self.run_cb([s for k, s in self.streams if k == "out"][0], 4800)
        self.assertLess(abs(out).max(), 0.3)                    # bajó al objetivo
        rms, peak, gr, sat = self.board.levels()["spk"]
        self.assertTrue(-30 < peak < 0)
        self.assertFalse(sat)
        self.settings["compressor"]["on"] = False
        self.settings["normalize"] = False
        self.board.play(self.wav, 4.0)
        self.run_cb([s for k, s in self.streams if k == "out"][0])
        self.assertTrue(self.board.levels()["spk"][3])          # saturó: se avisa
        _ = np

    def test_volume_and_clip(self):
        self.settings["volume"] = 0.5
        self.board.play(self.wav, 4.0)
        out = self.run_cb([s for k, s in self.streams if k == "out"][0])
        self.assertLessEqual(abs(out).max(), 1.0)


# ------------------------------------------------------------------ botonera (PipeWire)
@unittest.skipIf(sys.platform == "win32", "solo Unix")
class PipeWireTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.log = os.path.join(self.dir, "log")
        self.modules = os.path.join(self.dir, "modules")
        open(self.modules, "w").close()
        pactl = f"""#!/bin/sh
echo "pactl $*" >> {self.log}
case "$1" in
  list) [ "$3" = modules ] && cat {self.modules}; [ "$2" = json ] || true;;
  -f) echo '[{{"name":"alsa_input.usb","description":"Mic USB"}},{{"name":"alsa_output.monitor"}}]';;
  load-module) n=$(wc -l < {self.modules}); shift; m=$1; shift
     printf '%s\\t%s\\t%s\\n' "$((n+1))" "$m" "$*" >> {self.modules}; echo $((n+1));;
  unload-module) grep -v "^$2	" {self.modules} > {self.modules}.t; mv {self.modules}.t {self.modules};;
  get-default-source) echo alsa_input.usb;;
esac
"""
        # pw-cat falso: anota sus argumentos y guarda el audio que recibe
        play = (f"#!/bin/sh\n[ \"$1\" = --help ] && {{ echo \"  -a, --raw   Raw mode\"; exit 0; }}\n"
                f"echo \"pw-cat $*\" >> {self.log}\n"
                f"case \"$*\" in *numpad_macros_sink*) exec cat > {self.dir}/mic.raw;; "
                f"*) exec cat > {self.dir}/spk.raw;; esac\n")
        for name, body in (("pactl", pactl), ("pw-cat", play)):
            p = os.path.join(self.dir, name)
            with open(p, "w") as f:
                f.write(body)
            os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)
        self.old_path = os.environ["PATH"]
        os.environ["PATH"] = self.dir + os.pathsep + self.old_path
        from npm.soundboard import PipeWireBoard
        self.settings = copy.deepcopy(config.DEFAULT["audio"])
        self.board = PipeWireBoard(self.settings)
        try:
            import numpy as np
            import soundfile as sf
        except ImportError:
            self.skipTest("numpy/soundfile no instalados")
        self.np = np
        self.wav = os.path.join(self.dir, "x.wav")
        t = np.arange(48000) / 48000
        sf.write(self.wav, (0.5 * np.sin(2 * np.pi * 440 * t)).astype("float32"), 48000)

    def tearDown(self):
        self.board.close()
        os.environ["PATH"] = self.old_path
        # el audio falso pesa cientos de MB: no dejarlo en /tmp (pw-cat puede tardar en cerrarse)
        import shutil
        for _ in range(20):
            shutil.rmtree(self.dir, ignore_errors=True)
            if not os.path.exists(self.dir):
                break
            time.sleep(0.05)

    def lines(self):
        with open(self.log) as f:
            return f.read().splitlines()

    def test_flow(self):
        self.assertEqual(self.board.available(), (True, ""))
        self.settings["mix_mic"] = True
        self.board.apply()
        mods = open(self.modules).read()
        self.assertIn("module-null-sink", mods)
        self.assertIn("source_name=numpad_macros_mic", mods)
        self.assertIn("source=alsa_input.usb", mods)
        self.board.apply()                                # no duplica la salida ni el mic
        mods = open(self.modules).read()
        self.assertEqual(mods.count("module-null-sink"), 1)
        self.assertEqual(mods.count("module-loopback"), 1)
        self.board.play(self.wav, 0.8, True, True)
        time.sleep(0.4)
        plays = [ln for ln in self.lines() if ln.startswith("pw-cat")][-2:]   # las de la última conexión
        self.assertTrue(any("--target numpad_macros_sink" in p for p in plays))
        self.assertTrue(all("--format f32" in p for p in plays))
        self.assertTrue(all("--raw" in p for p in plays))           # PipeWire nuevo: audio crudo explícito
        mic = self.np.fromfile(os.path.join(self.dir, "mic.raw"), dtype="float32")
        self.assertGreater(abs(mic).max(), 0.05)          # el sonido llegó al micrófono virtual
        self.assertEqual(self.board.inputs(), ["Mic USB [alsa_input.usb]"])
        self.board.stop_all()
        # alternar: segunda pulsación detiene
        self.assertEqual(self.board.play(self.wav, tag="t", mode="toggle", mic=False), "x")
        self.assertTrue(self.board.playing("t"))
        self.assertIsNone(self.board.play(self.wav, tag="t", mode="toggle", mic=False))
        self.assertFalse(self.board.playing("t"))
        self.board.close()
        self.assertEqual(open(self.modules).read().strip(), "")


# ------------------------------------------------------------------ captura Linux (evdev)
class FakeDev:
    def __init__(self, path, name, vendor, product, keys_caps, extra_caps=None):
        self.path, self.name = path, name
        self.info = types.SimpleNamespace(vendor=vendor, product=product)
        self._caps = keys_caps
        self._extra = extra_caps or {}
        self._r, self._w = os.pipe()
        self.fd = self._r
        self.queue = []
        self.grabbed = False
        self.lock = threading.Lock()

    def capabilities(self):
        from evdev import ecodes as e
        return {e.EV_KEY: self._caps, **self._extra}

    def push(self, code, value, etype=None):
        from evdev import ecodes as e
        with self.lock:
            self.queue.append(types.SimpleNamespace(type=e.EV_KEY if etype is None else etype,
                                                    code=code, value=value))
        os.write(self._w, b"x")

    def read(self):
        os.read(self._r, 64)
        with self.lock:
            q, self.queue = self.queue, []
        return q

    def grab(self):
        self.grabbed = True

    def ungrab(self):
        self.grabbed = False

    def close(self):
        pass


class FakeUI:
    """Copia virtual (uinput) de un teclado tomado: anota lo que se reenvía."""
    def __init__(self, log):
        self.log, self.closed = log, False

    def write(self, etype, code, value):
        self.log.append((etype, code, value))

    def syn(self):
        from evdev import ecodes as e
        self.log.append((e.EV_SYN, 0, 0))

    def close(self):
        self.closed = True


@unittest.skipIf(sys.platform == "win32", "solo Unix")
class EvdevTest(unittest.TestCase):
    def setUp(self):
        try:
            import evdev
            from evdev import ecodes as e
        except ImportError:
            self.skipTest("evdev no instalado")
        self.e = e
        self.numpad = FakeDev("/dev/input/event7", "USB Numpad", 0x1a2c, 0x0e24, [e.KEY_KP0, e.KEY_KP7])
        self.main = FakeDev("/dev/input/event3", "HyperX Alloy", 0x0951, 0x16e6, [e.KEY_A, e.KEY_KP7])
        devs = self.devmap = {d.path: d for d in (self.numpad, self.main)}
        self._orig = (evdev.list_devices, evdev.InputDevice)
        evdev.list_devices = lambda: list(devs)
        evdev.InputDevice = lambda p: devs[p]
        from npm import send_linux
        self.emitted = []
        self._orig_emit = send_linux.emit
        send_linux.emit = lambda c, v: self.emitted.append((c, v))
        self.fwd, self.clones = [], []                  # lo reenviado por las copias virtuales

        def clone(dev):
            ui = FakeUI(self.fwd)
            self.clones.append(ui)
            return ui
        self._orig_clone = send_linux.clone
        send_linux.clone = clone
        cfg = copy.deepcopy(config.DEFAULT)
        cfg["banks"][0]["keys"]["47"] = {"type": "bank_go", "bank": 2}
        cfg["banks"][0]["keys"]["02"] = {"type": "bank_go", "bank": 2}   # fila: tecla 1
        cfg["row_mode"]["enabled"] = "row" in self._testMethodName
        if "main" not in self._testMethodName:
            cfg["hotkey"] = ""                     # sin combinación: el teclado principal no se usa
        self.engine = Engine(cfg)
        from npm.capture_linux import EvdevBackend
        self.b = EvdevBackend(self.engine, "")

    def tearDown(self):
        import evdev
        from npm import send_linux
        self.b.stop()
        evdev.list_devices, evdev.InputDevice = self._orig
        send_linux.emit = self._orig_emit
        send_linux.clone = self._orig_clone

    def wait_for(self, cond, timeout=2.0):
        end = time.time() + timeout
        while time.time() < end:
            if cond():
                return True
            time.sleep(0.02)
        return False

    def test_learn_grab_and_route(self):
        e = self.e
        self.b.start()
        self.b.learn_device(5)
        self.assertTrue(self.wait_for(lambda: len(self.b.devs) == 2))
        self.assertFalse(self.numpad.grabbed or self.main.grabbed)     # aprender no toma nada
        self.numpad.push(e.KEY_KP0, 1)
        self.assertTrue(self.wait_for(lambda: self.b.device == "1a2c:0e24:USB Numpad"))
        self.assertIn(("device", "1a2c:0e24:USB Numpad"), drain(self.engine.events))
        self.assertTrue(self.wait_for(lambda: self.numpad.grabbed))
        self.assertFalse(self.main.grabbed)                             # el teclado principal no se toca
        self.assertTrue(self.wait_for(lambda: list(self.b.devs) == [self.numpad.path]))
        # tecla con acción: se consume y cambia de banco
        self.numpad.push(e.KEY_KP7, 1)
        self.numpad.push(e.KEY_KP7, 0)
        self.assertTrue(self.wait_for(lambda: self.engine.bank == 1))
        # sin acción y sin bloquear: se devuelve al sistema por uinput
        self.engine.cfg["block_unassigned"] = False
        self.numpad.push(e.KEY_KP0, 1)
        self.numpad.push(e.KEY_KP0, 0)
        self.assertTrue(self.wait_for(lambda: self.emitted == [(e.KEY_KP0, 1), (e.KEY_KP0, 0)]))
        # pausa: suelta el grab
        self.engine.set_active(False)
        self.assertTrue(self.wait_for(lambda: not self.numpad.grabbed))
        self.engine.set_active(True)
        self.assertTrue(self.wait_for(lambda: self.numpad.grabbed))
        self.b.stop()
        self.assertFalse(self.numpad.grabbed)


    def keys(self, *seq, dev=None):
        for ev in seq:
            (dev or self.main).push(*ev)

    def fwd_keys(self):
        return [(c, v) for t, c, v in self.fwd if t == self.e.EV_KEY]

    def start_main(self):
        self.b.device = "1a2c:0e24:USB Numpad"
        self.b.start()
        self.assertTrue(self.wait_for(lambda: len(self.b.devs) == 2))     # numpad + principal

    def test_row_mode_main_keyboard(self):
        e = self.e
        self.engine.set_active(False)
        self.start_main()
        # en pausa el numpad queda libre, pero el principal se toma (para la combinación)
        self.assertTrue(self.wait_for(lambda: self.main.grabbed))
        self.assertFalse(self.numpad.grabbed)
        # escribir normal: todo se reenvía tal cual por la copia del teclado
        self.keys((e.KEY_1, 1), (e.KEY_1, 0))
        self.assertTrue(self.wait_for(lambda: self.fwd_keys() == [(e.KEY_1, 1), (e.KEY_1, 0)]))
        self.assertEqual(self.engine.bank, 0)
        self.assertEqual(self.emitted, [])                               # nada por el teclado compartido
        # Ctrl+Alt+M: el motor activa todo y la M no llega al sistema
        self.fwd.clear()
        self.keys((e.KEY_LEFTCTRL, 1), (e.KEY_LEFTALT, 1), (e.KEY_M, 1), (e.KEY_M, 2), (e.KEY_M, 0),
                  (e.KEY_LEFTALT, 0), (e.KEY_LEFTCTRL, 0))
        self.assertTrue(self.wait_for(lambda: len(self.fwd_keys()) == 4))
        self.assertEqual(self.fwd_keys(), [(e.KEY_LEFTCTRL, 1), (e.KEY_LEFTALT, 1),
                                           (e.KEY_LEFTALT, 0), (e.KEY_LEFTCTRL, 0)])   # sin toque extra
        self.assertTrue(self.engine.active)
        self.assertEqual([ev for ev in drain(self.engine.events) if ev[0] == "active_toggle"],
                         [("active_toggle", True)])                     # una sola vez (con repetición)
        self.assertTrue(self.wait_for(lambda: self.numpad.grabbed))
        # la tecla 1 lanza su acción; la Q se reenvía al sistema
        self.fwd.clear()
        self.keys((e.KEY_1, 1), (e.KEY_1, 0))
        self.assertTrue(self.wait_for(lambda: self.engine.bank == 1))
        self.keys((e.KEY_Q, 1), (e.KEY_Q, 0))
        self.assertTrue(self.wait_for(lambda: self.fwd_keys() == [(e.KEY_Q, 1), (e.KEY_Q, 0)]))
        # en pausa el principal sigue tomado y la fila vuelve a escribir
        self.engine.toggle_active()
        self.assertTrue(self.wait_for(lambda: not self.numpad.grabbed))
        self.assertTrue(self.main.grabbed)
        self.fwd.clear()
        self.keys((e.KEY_1, 1), (e.KEY_1, 0))
        self.assertTrue(self.wait_for(lambda: self.fwd_keys() == [(e.KEY_1, 1), (e.KEY_1, 0)]))
        self.b.stop()
        self.assertFalse(self.main.grabbed or self.numpad.grabbed)
        self.assertTrue(all(ui.closed for ui in self.clones))

    def test_main_forwards_every_event_type_and_high_codes(self):
        """Se reenvía todo, no solo EV_KEY: SYN, MSC (scancode), LED y teclas ≥ 249 (BTN_*, Fn)."""
        e = self.e
        self.main._caps += [e.BTN_LEFT, e.KEY_FN, e.KEY_MICMUTE + 5]
        self.start_main()
        self.assertTrue(self.wait_for(lambda: self.main.grabbed))
        seq = [(e.MSC_SCAN, 0x70004, e.EV_MSC), (e.KEY_A, 1), (e.SYN_REPORT, 0, e.EV_SYN),
               (e.KEY_FN, 1), (e.KEY_FN, 0), (e.KEY_MICMUTE + 5, 1), (e.KEY_MICMUTE + 5, 0),
               (e.LED_CAPSL, 1, e.EV_LED), (e.KEY_A, 0), (e.SYN_REPORT, 0, e.EV_SYN)]
        self.keys(*seq)
        want = [(t, c, v) for c, v, *rest in seq for t in [rest[0] if rest else e.EV_KEY]]
        self.assertTrue(self.wait_for(lambda: self.fwd == want))
        self.assertEqual(self.emitted, [])

    def test_main_pointer_devices_are_only_read(self):
        """Un teclado que también mueve un puntero (como la interfaz extra de algunos HyperX)
        no se toma: el mouse seguiría funcionando, pero la combinación igual se detecta."""
        e = self.e
        combo = FakeDev("/dev/input/event4", "HyperX Alloy Mouse", 0x0951, 0x16e6, [e.KEY_A, e.BTN_LEFT],
                        {e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL]})
        import evdev
        devs = {d.path: d for d in (self.numpad, self.main, combo)}
        evdev.list_devices = lambda: list(devs)
        evdev.InputDevice = lambda p: devs[p]
        self.engine.set_active(False)
        self.b.device = "1a2c:0e24:USB Numpad"
        self.b.start()
        self.assertTrue(self.wait_for(lambda: len(self.b.devs) == 3 and self.main.grabbed))
        time.sleep(0.15)
        self.assertFalse(combo.grabbed)
        self.keys((e.KEY_LEFTCTRL, 1), (e.KEY_LEFTALT, 1), (e.KEY_M, 1), (e.KEY_M, 0),
                  (e.KEY_LEFTALT, 0), (e.KEY_LEFTCTRL, 0), (e.REL_X, 5, e.EV_REL), dev=combo)
        self.assertTrue(self.wait_for(lambda: self.engine.active))
        self.assertEqual(self.fwd, [])                                   # el sistema ya lo recibió
        self.assertEqual(len(self.clones), 1)                            # solo el teclado tomado

    def test_main_unplug_releases_held_keys(self):
        """Desconectar con Ctrl (o la combinación) apretados: se sueltan en el motor y en el sistema."""
        e = self.e
        self.start_main()
        self.assertTrue(self.wait_for(lambda: self.main.grabbed and self.numpad.grabbed))
        self.numpad.push(e.KEY_KP0, 1)                                  # numpad: sin acción, bloqueada
        self.assertTrue(self.wait_for(lambda: "52" in self.engine._pressed))
        self.keys((e.KEY_LEFTCTRL, 1), (e.KEY_LEFTALT, 1), (e.KEY_M, 1))   # combinación apretada
        self.assertTrue(self.wait_for(lambda: self.engine._toggle_held == "32"))
        self.engine.toggle_active()                                     # (vuelve a activo)
        self.fwd.clear()

        def unplugged():
            raise OSError(19, "No such device")
        for d in (self.main, self.numpad):                              # se desconectan los dos
            self.devmap.pop(d.path)
            d.read = unplugged
            os.write(d._w, b"x")
        self.assertTrue(self.wait_for(lambda: not self.b.devs))
        self.assertEqual(sorted(c for c, v in self.fwd_keys() if v == 0), sorted([e.KEY_LEFTCTRL, e.KEY_LEFTALT]))
        self.assertTrue(self.clones[0].closed)
        self.assertEqual(self.engine._mods_down, set())                 # Ctrl/Alt no quedan pegados
        self.assertIsNone(self.engine._toggle_held)                     # la M tampoco
        self.assertEqual(self.engine._pressed, {})                      # ni la tecla del numpad
        # al volver a conectarlos, Ctrl+Alt+M funciona de inmediato
        self.assertTrue(self.engine.main_key("1d", True) is False and self.engine.main_key("38", True) is False)
        self.assertTrue(self.engine.active)
        self.assertTrue(self.engine.main_key("32", True))
        self.assertFalse(self.engine.active)

    def test_main_alt_win_combo_is_masked(self):
        """Alt+F9 (o Win+…): un toque de Ctrl antes de soltar, para que no se abra el menú."""
        e = self.e
        self.engine.cfg["hotkey"] = "alt+f9"
        self.start_main()
        self.assertTrue(self.wait_for(lambda: self.main.grabbed))
        self.keys((e.KEY_LEFTALT, 1), (e.KEY_F9, 1), (e.KEY_F9, 0), (e.KEY_LEFTALT, 0))
        self.assertTrue(self.wait_for(lambda: len(self.fwd_keys()) == 4))
        self.assertEqual(self.fwd_keys(), [(e.KEY_LEFTALT, 1), (e.KEY_LEFTCTRL, 1), (e.KEY_LEFTCTRL, 0),
                                           (e.KEY_LEFTALT, 0)])

    def test_main_without_row_and_without_uinput(self):
        """Con la fila desmarcada la combinación sigue funcionando; sin copia virtual
        el principal solo se lee (si no, dejaría de escribir) y se avisa una vez."""
        from npm import send_linux

        def broken(dev):
            raise RuntimeError("sin permisos")
        send_linux.clone = broken
        e = self.e
        self.start_main()
        self.assertTrue(self.wait_for(lambda: self.numpad.grabbed))
        self.keys((e.KEY_LEFTCTRL, 1), (e.KEY_LEFTALT, 1), (e.KEY_M, 1), (e.KEY_M, 0),
                  (e.KEY_LEFTALT, 0), (e.KEY_LEFTCTRL, 0))
        self.assertTrue(self.wait_for(lambda: not self.engine.active))
        self.assertTrue(self.wait_for(lambda: self.b.held.get(self.main.path) == set()))   # todo soltado
        evs = drain(self.engine.events)
        self.assertIn(("active_toggle", False), evs)
        self.assertEqual(sum(1 for ev in evs if ev[0] == "error" and "Teclado virtual" in ev[1]), 1)
        self.assertFalse(self.main.grabbed)
        self.assertEqual(self.emitted, [])

    def test_main_grab_failure_warns_once(self):
        def busy():
            raise OSError(16, "Device or resource busy")
        self.main.grab = busy
        self.start_main()
        self.assertTrue(self.wait_for(lambda: any(
            ev[0] == "error" and "teclado principal" in ev[1] for ev in list(self.engine.events.queue))))
        time.sleep(0.3)
        errs = [ev for ev in drain(self.engine.events) if ev[0] == "error"]
        self.assertEqual(len(errs), 1)
        self.assertIn("Otro programa", errs[0][1])
        self.assertTrue(all(ui.closed for ui in self.clones))           # la copia no queda abierta


class EngineFile(unittest.TestCase):
    def test_file_and_stop(self):
        calls = []
        board = types.SimpleNamespace(play=lambda *a, **k: calls.append(("play",) + a) or "x",
                                      stop_all=lambda: calls.append(("stop",)))
        cfg = copy.deepcopy(config.DEFAULT)
        cfg["banks"][0]["keys"]["47"] = {"type": "file", "path": "/a.mp3", "volume": 0.5,
                                         "speakers": True, "mic": False}
        cfg["banks"][0]["keys"]["48"] = {"type": "sound_stop"}
        e = Engine(cfg, None, soundboard=board)
        e.decide("47", True); e.decide("47", False)
        e.decide("48", True); e.decide("48", False)
        time.sleep(0.1)
        self.assertEqual(calls, [("play", "/a.mp3", 0.5, True, False), ("stop",)])


if __name__ == "__main__":
    unittest.main()


class LibraryTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.d, "sub"))
        self.files = []
        for name in ("b.mp3", "a.wav", "sub/c.ogg", "nota.txt"):
            p = os.path.join(self.d, name)
            open(p, "wb").close()
            self.files.append(p)
        self.cfg = copy.deepcopy(config.DEFAULT)

    def test_add_scan_search_remove(self):
        from npm import library
        found = library.scan_folder(self.d)
        self.assertEqual([os.path.basename(f) for f in found], ["a.wav", "b.mp3", "c.ogg"])
        self.assertEqual(library.add(self.cfg, found), 3)
        self.assertEqual(library.add(self.cfg, found), 0)              # sin duplicados
        self.assertEqual(library.add(self.cfg, [self.files[3]]), 0)     # no es audio
        self.assertEqual([x["title"] for x in library.search(self.cfg, "C")], ["c"])
        library.remove(self.cfg, [found[0]])
        self.assertEqual(len(self.cfg["library"]), 2)

    def test_spl_and_migration(self):
        from npm import library
        spl = os.path.join(self.d, "lista.spl")
        with open(spl, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<Soundlist>'
                    f'<Sound url="{self.files[0]}" title="Bruh" artist="Meme"/>'
                    '<Sound url="sub/c.ogg"/><Sound url=""/></Soundlist>')
        n, total = library.import_spl(self.cfg, spl)
        self.assertEqual((n, total), (2, 2))
        self.assertEqual(self.cfg["library"][0]["title"], "Meme – Bruh")
        self.assertEqual(self.cfg["library"][1]["path"], os.path.join(self.d, "sub", "c.ogg"))
        # teclas viejas de Soundpad
        cfg = copy.deepcopy(config.DEFAULT)
        cfg["banks"][0]["keys"]["47"] = {"type": "sound", "url": self.files[1], "title": "A",
                                         "index": 3, "speakers": True, "mic": False}
        cfg["banks"][0]["keys"]["48"] = {"type": "sound", "index": 4}
        self.assertEqual(library.migrate_soundpad(cfg), 2)
        k = cfg["banks"][0]["keys"]
        self.assertEqual(k["47"]["type"], "file")
        self.assertEqual(k["47"]["path"], self.files[1])
        self.assertFalse(k["47"]["mic"])
        self.assertNotIn("48", k)
        self.assertEqual(len(cfg["library"]), 1)

    def test_config_migrates_on_load(self):
        import json
        p = os.path.join(self.d, "config.json")
        with open(p, "w") as f:
            json.dump({"mode": "interception", "device_hwid": "HID\\VID_1A2C&PID_0E24",
                       "banks": [{"name": "B", "keys": {"47": {"type": "sound", "url": self.files[0],
                                                               "title": "b"}}}]}, f)
        cfg = config.load(p)
        self.assertEqual(cfg["banks"][0]["keys"]["47"]["type"], "file")
        self.assertEqual(cfg["library"][0]["path"], self.files[0])
        self.assertTrue(cfg["device"].startswith("HID"))


class PermsTest(unittest.TestCase):
    @unittest.skipIf(sys.platform == "win32", "solo Unix")
    def test_grant_uses_pkexec(self):
        from npm import linux_perms
        d = tempfile.mkdtemp()
        log = os.path.join(d, "log")
        pk = os.path.join(d, "pkexec")
        with open(pk, "w") as f:
            f.write(f'#!/bin/sh\necho "$@" > {log}\nhead -3 "$2" >> {log}\nexit 0\n')
        os.chmod(pk, 0o755)
        old = os.environ["PATH"]
        os.environ["PATH"] = d + os.pathsep + old
        try:
            ok, msg = linux_perms.grant()
        finally:
            os.environ["PATH"] = old
        self.assertTrue(ok, msg)
        with open(log) as f:
            text = f.read()
        self.assertIn("/bin/bash", text)
        self.assertIn("#!/usr/bin/env bash", text)

    def test_script_matches(self):
        from npm.linux_perms import SCRIPT
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "permisos_linux.sh"), encoding="utf-8") as f:
            self.assertEqual(f.read(), SCRIPT)
        self.assertIn('TAG+="uaccess"', SCRIPT)


class AboutTest(unittest.TestCase):
    def test_links_and_open(self):
        from unittest import mock
        from npm import about, sysutil
        self.assertEqual(about.INSTAGRAM[2], "https://www.instagram.com/okumawsx")
        self.assertEqual(about.DISCORD[2], "https://discord.gg/hcutJcBx9")
        self.assertEqual(about.DONATE, "https://ceneka.net/OkumaWsX")
        with mock.patch("webbrowser.open", return_value=True) as wo:
            self.assertTrue(sysutil.open_url(about.DONATE))
            wo.assert_called_once_with(about.DONATE, new=2)
