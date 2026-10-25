# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
import copy
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from npm import config, keys  # noqa: E402
from npm.engine import Engine  # noqa: E402


class FakeBoard:
    def __init__(self):
        self.played = []

    def play(self, path, volume, speakers, mic, tag=None, mode="overlap"):
        self.played.append(path)
        return path

    def stop_tag(self, tag):
        self.played.append("STOP " + tag)

    def stop_all(self):
        self.played.append("STOP")


class FakeSender:
    def __init__(self):
        self.log = []

    def press(self, c):
        self.log.append(("down", c))

    def release(self, c):
        self.log.append(("up", c))


def wait():
    time.sleep(0.05)


class EngineTest(unittest.TestCase):
    def make(self, **over):
        cfg = copy.deepcopy(config.DEFAULT)
        cfg.update(over)
        cfg["banks"][0]["keys"]["47"] = {"type": "file", "path": "aplausos"}
        cfg["banks"][1]["keys"]["47"] = {"type": "file", "path": "risas"}
        cfg["banks"][0]["keys"]["48"] = {"type": "keys", "combo": "ctrl+f13"}
        cfg["banks"][0]["keys"]["49"] = {"type": "file", "path": "tambor", "mode": "hold"}
        self.sp, self.snd = FakeBoard(), FakeSender()
        return Engine(cfg, self.snd, soundboard=self.sp)

    def test_sound_and_banks(self):
        e = self.make()
        self.assertTrue(e.decide("47", True))
        self.assertTrue(e.decide("47", True))   # autorepetición: no repite el sonido
        self.assertTrue(e.decide("47", False))
        self.assertTrue(e.decide("45", True))   # NumLock global -> banco siguiente
        self.assertTrue(e.decide("45", False))
        self.assertEqual(e.bank, 1)
        e.decide("47", True); e.decide("47", False)
        e.decide("45", True); e.decide("45", False)
        self.assertEqual(e.bank, 0)             # da la vuelta
        wait()
        self.assertEqual(self.sp.played, ["aplausos", "risas"])

    def test_hold_combo(self):
        e = self.make()
        e.decide("48", True); e.decide("48", True); e.decide("48", False)
        wait()
        self.assertEqual(self.snd.log, [("down", "ctrl+f13"), ("up", "ctrl+f13")])

    def test_unassigned_block_and_pass(self):
        e = self.make()
        self.assertTrue(e.decide("4c", True))
        self.assertTrue(e.decide("4c", False))
        e.cfg["block_unassigned"] = False
        self.assertFalse(e.decide("4c", True))
        self.assertFalse(e.decide("4c", False))

    def test_pause_passes_and_release_consistency(self):
        e = self.make()
        e.set_active(False)
        self.assertFalse(e.decide("47", True))
        e.set_active(True)
        self.assertFalse(e.decide("47", True))   # repetición de una tecla dejada pasar
        self.assertFalse(e.decide("47", False))  # su soltar también pasa
        self.assertFalse(e.decide("49", False))  # soltar desconocido pasa

    def test_bank_switch_while_holding(self):
        e = self.make()
        e.decide("48", True)
        e.decide("45", True); e.decide("45", False)
        e.decide("48", False)                    # suelta el combo original
        wait()
        self.assertEqual(self.snd.log[-1], ("up", "ctrl+f13"))

    def test_capture(self):
        e = self.make()
        e.capture_next = True
        self.assertTrue(e.decide("53", True))
        self.assertTrue(e.decide("53", False))
        evs = []
        while not e.events.empty():
            evs.append(e.events.get())
        self.assertIn(("captured", "53"), evs)
        wait()
        self.assertEqual(self.sp.played, [])

    def test_release_all(self):
        e = self.make()
        e.decide("48", True)
        e.release_all()
        wait()
        self.assertEqual(self.snd.log, [("down", "ctrl+f13"), ("up", "ctrl+f13")])


    def test_hold_sound_stops_on_release(self):
        e = self.make()
        e.decide("49", True); e.decide("49", True); e.decide("49", False)
        wait()
        self.assertEqual(self.sp.played, ["tambor", "STOP 49|tambor"])


class RowModeTest(unittest.TestCase):
    """Ctrl+Alt+M activa o pausa el modo macros (lo mismo que el botón ACTIVO / PAUSADO);
    la fila de números sigue a ese estado si su casilla está marcada."""
    def setUp(self):
        cfg = copy.deepcopy(config.DEFAULT)
        cfg["banks"][0]["keys"]["02"] = {"type": "file", "path": "uno"}     # fila: tecla 1
        cfg["banks"][0]["keys"]["4f"] = {"type": "file", "path": "num1"}    # numpad: Num 1
        cfg["banks"][0]["keys"]["m5"] = {"type": "file", "path": "cel"}     # tecla virtual 5
        self.board = FakeBoard()
        self.e = Engine(cfg, FakeSender(), soundboard=self.board)

    def press(self, kid, mods=None):
        return self.e.main_key(kid, True, mods), self.e.main_key(kid, False, mods)

    def combo(self, key="32", mods=("1d", "38"), repeat=0):      # 32 = M
        e = self.e
        for m in mods:
            self.assertFalse(e.main_key(m, True))
        r = [e.main_key(key, True)]
        r += [e.main_key(key, True) for _ in range(repeat)]       # autorepetición
        r.append(e.main_key(key, False))
        for m in reversed(mods):
            self.assertFalse(e.main_key(m, False))
        return r

    def toggles(self):
        """Avisos a la GUI de que la combinación ya alternó «active» (la GUI solo repinta)."""
        n = 0
        while not self.e.events.empty():
            if self.e.events.get()[0] == "active_toggle":
                n += 1
        return n

    def test_default_and_consumed(self):
        self.assertEqual(self.e.cfg["hotkey"], "ctrl+alt+m")
        self.assertIsNone(keys.busy_reason("ctrl+alt+m"))
        self.assertTrue(self.e.main_wanted())
        self.assertEqual(self.combo(), [True, True])              # la M y su soltar se consumen
        self.assertEqual(self.toggles(), 1)
        self.assertFalse(self.e.active)

    def test_engine_toggles_under_lock(self):
        """El motor cambia «active» al detectar la combinación (bajo su lock) y suelta lo
        apretado; a la GUI le llegan "active" (repintar) y "active_toggle" (aviso)."""
        self.e.cfg["banks"][0]["keys"]["03"] = {"type": "file", "path": "tambor", "mode": "hold"}
        self.assertTrue(self.e.main_key("03", True))               # sonido mientras se mantiene
        self.combo()
        self.assertFalse(self.e.active)
        self.assertEqual(self.e._pressed, {})                      # release_all
        evs = []
        while not self.e.events.empty():
            evs.append(self.e.events.get())
        self.assertIn(("active", False), evs)
        self.assertIn(("active_toggle", False), evs)
        wait()
        self.assertEqual(self.board.played, ["tambor", "STOP 03|tambor"])
        self.assertTrue(self.e.toggle_active())                    # botón / bandeja: lo mismo
        self.assertTrue(self.e.active)

    def test_row_follows_active(self):
        self.e.set_active(False)
        self.assertEqual(self.press("02"), (False, False))        # en pausa la fila escribe un 1
        self.assertEqual(self.press("32"), (False, False))        # M sola escribe M
        self.combo(); self.toggles()
        self.assertTrue(self.e.active and self.e.row_mode)
        self.assertEqual(self.press("02"), (True, True))          # lanza el sonido
        self.assertEqual(self.press("10"), (False, False))        # Q sigue escribiendo
        self.assertEqual(self.press("03"), (True, True))          # 2 sin acción: bloqueada
        self.combo(); self.toggles()
        self.assertFalse(self.e.active or self.e.row_mode)
        self.assertEqual(self.press("02"), (False, False))
        wait()
        self.assertEqual(self.board.played, ["uno"])

    def test_numpad_follows_active(self):
        self.combo(); self.toggles()                               # pausa
        self.assertFalse(self.e.decide("4f", True))                # el numpad escribe normal
        self.assertFalse(self.e.decide("4f", False))
        self.combo(); self.toggles()                               # activo otra vez
        self.assertTrue(self.e.decide("4f", True))
        self.assertTrue(self.e.decide("4f", False))
        wait()
        self.assertEqual(self.board.played, ["num1"])

    def test_works_without_row_and_while_paused(self):
        self.e.cfg["row_mode"]["enabled"] = False
        self.assertTrue(self.e.main_wanted())
        self.e.set_active(False)
        self.assertEqual(self.combo(), [True, True])
        self.assertEqual(self.toggles(), 1)
        self.assertTrue(self.e.active)
        self.assertFalse(self.e.row_mode)                          # activo, pero la fila escribe normal
        self.assertEqual(self.press("02"), (False, False))
        self.assertEqual(self.combo(), [True, True])
        self.assertEqual(self.toggles(), 1)
        self.assertFalse(self.e.active)

    def test_phone_keys_work_when_paused(self):
        self.combo(); self.toggles()
        self.assertFalse(self.e.active)
        self.e.remote_key("m5", True)
        self.e.remote_key("m5", False)
        wait()
        self.assertEqual(self.board.played, ["cel"])

    def test_wrong_mods_do_not_toggle(self):
        self.assertEqual(self.combo(mods=("1d",)), [False, False])              # solo Ctrl
        self.assertEqual(self.combo(mods=("1d", "38", "2a")), [False, False])   # Ctrl+Alt+Shift
        self.assertEqual(self.combo(mods=()), [False, False])                   # M sola escribe M
        self.assertEqual(self.toggles(), 0)
        self.assertEqual(self.combo(mods=("e0:1d", "e0:38")), [True, True])     # Ctrl+Alt derechos
        self.assertEqual(self.toggles(), 1)

    def test_mac_mods(self):
        self.assertEqual(self.press("32", {"ctrl", "alt"}), (True, True))
        self.assertEqual(self.press("32", {"ctrl"}), (False, False))
        self.assertEqual(self.toggles(), 1)

    def test_autorepeat_toggles_once(self):
        self.assertEqual(self.combo(repeat=5), [True] * 7)
        self.assertEqual(self.toggles(), 1)
        self.assertEqual(self.combo(), [True, True])              # se puede volver a usar
        self.assertEqual(self.toggles(), 1)
        self.assertTrue(self.e.active)

    def test_release_after_change_still_consumed(self):
        e = self.e
        e.main_key("1d", True); e.main_key("38", True)
        self.assertTrue(e.main_key("32", True))
        e.cfg["hotkey"] = "ctrl+alt+k"                             # se cambia con la M apretada
        self.assertTrue(e.main_key("32", False))                  # el soltar no se escapa
        self.assertFalse(e.main_key("32", True))                  # y la M ya no sirve
        self.assertFalse(e.main_key("32", False))
        self.assertTrue(e.main_key("25", True))                   # 25 = K
        self.assertTrue(e.main_key("25", False))
        self.assertEqual(self.toggles(), 2)

    def test_release_of_row_key_after_pause(self):
        self.assertTrue(self.e.main_key("02", True))
        self.e.release_all(); self.e.set_active(False)             # se pausa con la tecla apretada
        self.assertFalse(self.e.main_key("02", False))

    def test_recording_lets_keys_through(self):
        self.e.combos_off = True                                   # la GUI graba una combinación
        self.assertEqual(self.combo(), [False, False])
        self.assertEqual(self.toggles(), 0)

    def test_invalid_combo_and_phone_only(self):
        self.e.cfg["hotkey"] = "ctrl+alt+5"                        # 5 no sirve para la combinación
        self.assertFalse(self.e.main_wanted())
        self.e.set_active(False)                                   # (activo, el 5 de la fila es macro)
        self.assertEqual(self.combo(key="06"), [False, False])
        self.assertEqual(self.toggles(), 0)
        self.e.cfg["hotkey"] = "ctrl+alt+m"
        self.e.cfg["phone"]["only"] = True
        self.assertFalse(self.e.main_wanted())

    def test_custom_toggle(self):
        self.e.cfg["hotkey"] = "bloqdespl"
        self.assertEqual(self.press("46"), (True, True))
        self.assertEqual(self.toggles(), 1)
        self.e.cfg["hotkey"] = "ctrl+shift+f9"
        self.assertEqual(self.combo(key="43", mods=("1d", "2a")), [True, True])
        self.assertEqual(self.toggles(), 1)


class KeysTest(unittest.TestCase):
    def test_combo(self):
        self.assertEqual(keys.parse_combo("Ctrl+Shift+F13"), (["ctrl", "shift"], "f13"))
        self.assertEqual(keys.combo_text("ctrl+f13"), "Ctrl+F13")
        with self.assertRaises(ValueError):
            keys.parse_combo("hyper+f13")

    def test_ids(self):
        self.assertEqual(keys.key_id(0x1C, True), "e0:1c")
        self.assertEqual(len(keys.NUMPAD_IDS), 17)
        self.assertEqual(keys.key_label("47"), "Num 7")
        self.assertEqual(keys.key_label("45"), "NumLock")


class ConfigTest(unittest.TestCase):
    def test_roundtrip(self):
        import tempfile
        d = tempfile.mkdtemp()
        p = os.path.join(d, "c.json")
        cfg = config.load(p)
        cfg["banks"][0]["keys"]["47"] = {"type": "sound_stop"}
        config.save(cfg, p)
        self.assertEqual(config.load(p)["banks"][0]["keys"]["47"]["type"], "sound_stop")
        with open(p, "w") as f:
            f.write("{roto")
        from npm.capture import default_mode
        self.assertEqual(config.load(p)["mode"], default_mode())

    def test_old_config_keeps_its_combination(self):
        import json
        import tempfile
        p = os.path.join(tempfile.mkdtemp(), "c.json")
        with open(p, "w", encoding="utf-8") as f:                 # configuración de 3.5.0
            json.dump({"row_mode": {"enabled": False, "toggle": "ctrl+shift+k"}}, f)
        cfg = config.load(p)
        self.assertEqual(cfg["hotkey"], "ctrl+shift+k")           # se conserva la del usuario
        self.assertEqual(cfg["row_mode"], {"enabled": False})
        config.save(cfg, p)
        self.assertEqual(config.load(p)["hotkey"], "ctrl+shift+k")
        with open(p, "w", encoding="utf-8") as f:                 # sin combinación: la de siempre
            json.dump({"row_mode": {"enabled": True}}, f)
        self.assertEqual(config.load(p)["hotkey"], "ctrl+alt+m")
        with open(p, "w", encoding="utf-8") as f:                 # vacía (a mano): sigue desactivada
            json.dump({"row_mode": {"enabled": True, "toggle": ""}}, f)
        cfg = config.load(p)
        self.assertEqual(cfg["hotkey"], "")
        self.assertFalse(Engine(cfg).main_wanted())
        with open(p, "w", encoding="utf-8") as f:                 # la nueva manda sobre la vieja
            json.dump({"hotkey": "ctrl+alt+j", "row_mode": {"toggle": "ctrl+alt+k"}}, f)
        self.assertEqual(config.load(p)["hotkey"], "ctrl+alt+j")

if __name__ == "__main__":
    unittest.main()
