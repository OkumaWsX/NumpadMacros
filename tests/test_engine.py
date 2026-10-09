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
    def setUp(self):
        cfg = copy.deepcopy(config.DEFAULT)
        cfg["banks"][0]["keys"]["02"] = {"type": "file", "path": "uno"}     # fila: tecla 1
        cfg["banks"][0]["keys"]["4f"] = {"type": "file", "path": "num1"}    # numpad: Num 1
        self.board = FakeBoard()
        self.e = Engine(cfg, FakeSender(), soundboard=self.board)

    def press(self, kid, mods=None):
        return self.e.main_key(kid, True, mods), self.e.main_key(kid, False, mods)

    def toggle(self):
        e = self.e
        self.assertFalse(e.main_key("1d", True))      # Ctrl
        self.assertFalse(e.main_key("38", True))      # Alt
        r = self.press("32")                          # M
        self.assertFalse(e.main_key("38", False))
        self.assertFalse(e.main_key("1d", False))
        return r

    def test_off_by_default_and_passes(self):
        self.assertEqual(self.press("02"), (False, False))   # escribe un 1 normal
        self.assertEqual(self.press("32"), (False, False))   # M sola escribe M

    def test_toggle_and_play(self):
        self.assertEqual(self.toggle(), (True, True))
        self.assertTrue(self.e.row_mode)
        self.assertEqual(self.press("02"), (True, True))      # lanza el sonido
        self.assertEqual(self.press("10"), (False, False))    # Q sigue escribiendo
        self.assertEqual(self.press("03"), (True, True))      # 2 sin acción: bloqueada
        self.toggle()
        self.assertFalse(self.e.row_mode)
        self.assertEqual(self.press("02"), (False, False))
        wait()
        self.assertEqual(self.board.played, ["uno"])

    def test_wrong_mods_do_not_toggle(self):
        self.e.main_key("1d", True)                           # solo Ctrl
        self.assertEqual(self.press("32"), (False, False))
        self.assertFalse(self.e.row_mode)
        self.e.main_key("e0:1d", True); self.e.main_key("e0:38", True)   # Ctrl+Alt derechos
        self.assertEqual(self.press("32"), (True, True))
        self.assertTrue(self.e.row_mode)

    def test_mac_mods_and_release_after_off(self):
        self.assertEqual(self.press("32", {"ctrl", "alt"}), (True, True))
        self.assertTrue(self.e.main_key("02", True, set()))
        self.e.set_row_mode(False)                             # se apaga con la tecla apretada
        self.assertTrue(self.e.main_key("02", False, set()))   # el soltar no se escapa

    def test_disabled_feature(self):
        self.e.cfg["row_mode"]["enabled"] = False
        self.assertEqual(self.toggle(), (False, False))
        self.assertFalse(self.e.row_mode)

    def test_custom_toggle(self):
        self.e.cfg["row_mode"]["toggle"] = "bloqdespl"
        self.assertEqual(self.press("46"), (True, True))
        self.assertTrue(self.e.row_mode)


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


if __name__ == "__main__":
    unittest.main()
