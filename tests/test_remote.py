# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Pruebas de la conexión con el celular y de las teclas F13–F24."""
import base64
import copy
import hashlib
import hmac
import json
import os
import socket
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from npm import config, remote  # noqa: E402
from npm.engine import Engine  # noqa: E402
from tests.test_engine import FakeBoard, FakeSender, wait  # noqa: E402


class Board(FakeBoard):
    def progress(self):
        return {"47|aplausos.wav": 0.5}

    def levels(self):
        return {"spk": (-20.0, -12.0, 0.0, False)}


class Phone:
    """Cliente mínimo que habla el protocolo como la app Android."""

    def __init__(self, port):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=3)
        self.buf = b""

    def send(self, **msg):
        self.s.sendall((json.dumps(msg) + "\n").encode())

    def recv(self, want=None, timeout=3):
        end = time.time() + timeout
        while time.time() < end:
            while b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                msg = json.loads(line)
                if want is None or msg.get("t") == want:
                    return msg
            try:
                chunk = self.s.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                return None
            self.buf += chunk
        return None

    def close(self):
        self.s.close()


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class RemoteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.wav = os.path.join(self.tmp, "aplausos.wav")
        open(self.wav, "wb").close()
        cfg = copy.deepcopy(config.DEFAULT)
        cfg["library"] = [{"path": self.wav, "title": "Aplausos"}]
        cfg["banks"][0]["name"] = "Stream"
        cfg["banks"][0]["keys"]["47"] = {"type": "file", "path": self.wav, "title": "Aplausos",
                                         "mode": "restart"}
        cfg["remote"] = {"port": free_port(), "bluetooth": False, "name": "PC-Prueba"}
        self.cfg = cfg
        self.board, self.snd = Board(), FakeSender()
        self.engine = Engine(cfg, self.snd, soundboard=self.board)
        self.saves = 0
        self.notes = []
        self.srv = remote.RemoteServer(cfg, self.engine, self.board, notify=lambda *w: self.notes.append(w),
                                       save=self._save, upload_dir=os.path.join(self.tmp, "subidos"))
        self.srv.start()
        self.port = cfg["remote"]["port"]

    def _save(self):
        self.saves += 1

    def tearDown(self):
        self.srv.stop()
        self.engine.stop()

    def pair(self, dev="cel-1"):
        ph = Phone(self.port)
        ph.send(t="hola", v=1, dev=dev, name="Pixel de prueba", app="1.0.0")
        reto = ph.recv("reto")
        self.assertFalse(reto["known"])
        self.assertEqual(reto["name"], "PC-Prueba")
        ph.send(t="codigo", code="0000" if self.srv.pin != "0000" else "1111")
        self.assertTrue(ph.recv("aviso")["code_wrong"])
        ph.send(t="codigo", code=self.srv.pin)
        hi = ph.recv("bienvenido")
        self.assertEqual(len(hi["token"]), 64)
        return ph, hi["token"]

    def test_pair_state_and_press(self):
        old_pin = self.srv.pin
        ph, token = self.pair()
        self.assertNotEqual(self.srv.pin, old_pin)          # el código cambia al usarse
        st = ph.recv("estado")
        self.assertEqual(st["banks"][0]["name"], "Stream")
        k = st["banks"][0]["keys"]["47"]
        self.assertEqual((k["title"], k["mode"]), ("Aplausos", "restart"))
        self.assertEqual([g["id"] for g in st["groups"]], ["numpad", "fila", "f"])
        lib = ph.recv("biblioteca")
        self.assertEqual(lib["items"][0]["lib"], remote.lib_id(self.wav))
        ph.send(t="tecla", key="47", down=True)
        ph.send(t="tecla", key="47", down=False)
        son = ph.recv("sonando")
        self.assertEqual(son["keys"], {"47": 0.5})
        self.assertEqual(son["level"], -12.0)
        self.assertIn(self.wav, self.board.played)
        ph.send(t="ping", n=7)
        self.assertEqual(ph.recv("pong")["n"], 7)
        ph.close()

    def test_reconnect_with_hmac_and_forget(self):
        ph, token = self.pair()
        ph.close()
        ph = Phone(self.port)
        ph.send(t="hola", v=1, dev="cel-1", name="Pixel de prueba")
        reto = ph.recv("reto")
        self.assertTrue(reto["known"])
        mac = hmac.new(token.encode(), reto["nonce"].encode(), hashlib.sha256).hexdigest()
        ph.send(t="prueba", mac=mac)
        hi = ph.recv("bienvenido")
        self.assertNotIn("token", hi)
        ph.close()
        # una prueba falsa se rechaza
        ph = Phone(self.port)
        ph.send(t="hola", v=1, dev="cel-1")
        ph.recv("reto")
        ph.send(t="prueba", mac="00" * 32)
        self.assertEqual(ph.recv("rechazado")["why"], "prueba")
        ph.close()
        self.srv.forget("cel-1")
        ph = Phone(self.port)
        ph.send(t="hola", v=1, dev="cel-1")
        self.assertFalse(ph.recv("reto")["known"])
        ph.close()

    def test_wrong_code_five_times(self):
        ph = Phone(self.port)
        ph.send(t="hola", v=1, dev="x")
        ph.recv("reto")
        pin = self.srv.pin
        bad = "9999" if pin != "9999" else "8888"
        for _ in range(4):
            ph.send(t="codigo", code=bad)
            ph.recv("aviso")
        ph.send(t="codigo", code=bad)
        self.assertEqual(ph.recv("rechazado")["why"], "codigo")
        self.assertNotEqual(self.srv.pin, pin)

    def test_disabled(self):
        self.cfg["remote"]["enabled"] = False
        ph = Phone(self.port)
        ph.send(t="hola", v=1, dev="x")
        self.assertEqual(ph.recv("rechazado")["why"], "desactivado")

    def test_assign_upload_and_fkeys(self):
        ph, _ = self.pair()
        ph.recv("estado")
        ph.recv("biblioteca")
        # asignar un atajo a F13 desde el celular
        ph.send(t="asignar", layer=0, key="f13", act={"type": "keys", "combo": "ctrl+shift+f16",
                                                      "color": 2})
        st = ph.recv("estado")
        self.assertEqual(st["banks"][0]["keys"]["f13"], {"type": "keys", "combo": "ctrl+shift+f16",
                                                         "color": 2})
        self.assertIn(("keys", 0, "f13"), self.notes)
        # atajo no válido
        ph.send(t="asignar", layer=0, key="48", act={"type": "keys", "combo": "nada+zz"})
        self.assertTrue(ph.recv("aviso")["bad"])
        # subir un sonido y asignarlo a la tecla 9
        data = os.urandom(300_000)
        ph.send(t="subir_ini", name="../risa rara.ogg", size=len(data), title="Risa")
        self.assertTrue(ph.recv("subida")["ok"])
        for i in range(0, len(data), 192 * 1024):
            ph.send(t="subir_parte", seq=i, data=base64.b64encode(data[i:i + 192 * 1024]).decode())
            ph.recv("subida")
        ph.send(t="subir_fin", sha256=hashlib.sha256(data).hexdigest(),
                assign={"layer": 0, "key": "49", "act": {"mode": "toggle", "volume": 1.5}})
        fin = None
        while True:
            m = ph.recv()
            if m["t"] == "subida" and m.get("fin"):
                fin = m
                break
        saved = os.path.join(self.tmp, "subidos", "risa rara.ogg")
        self.assertTrue(os.path.isfile(saved))
        with open(saved, "rb") as f:
            self.assertEqual(f.read(), data)
        act = self.cfg["banks"][0]["keys"]["49"]
        self.assertEqual((act["path"], act["mode"], act["volume"], act["title"]),
                         (saved, "toggle", 1.5, "Risa"))
        self.assertEqual(fin["lib"], remote.lib_id(saved))
        # subida con contenido distinto al anunciado
        ph.send(t="subir_ini", name="x.mp3", size=10)
        ph.recv("subida")
        ph.send(t="subir_parte", seq=0, data=base64.b64encode(b"0123456789").decode())
        ph.recv("subida")
        ph.send(t="subir_fin", sha256="00" * 32)
        self.assertFalse(ph.recv("subida")["ok"])
        # no es audio
        ph.send(t="subir_ini", name="virus.exe", size=10)
        self.assertFalse(ph.recv("subida")["ok"])
        ph.close()

    def test_discovery(self):
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        u.settimeout(2)
        u.sendto(b'{"t":"descubrir","v":1}', ("127.0.0.1", remote.UDP_PORT))
        msg = json.loads(u.recvfrom(2048)[0])
        u.close()
        self.assertEqual((msg["t"], msg["name"], msg["port"]), ("pc", "PC-Prueba", self.port))

    def test_release_on_disconnect(self):
        self.cfg["banks"][0]["keys"]["4a"] = {"type": "keys", "combo": "ctrl+f15"}
        ph, _ = self.pair()
        ph.send(t="tecla", key="4a", down=True)
        time.sleep(0.2)
        ph.close()
        time.sleep(0.3)
        self.assertEqual(self.snd.log, [("down", "ctrl+f15"), ("up", "ctrl+f15")])

    def test_qr_text(self):
        q = remote.qr_text(self.cfg, "4821")
        self.assertTrue(q.startswith("nmacros://vincular?h="))
        self.assertIn("&c=4821&n=PC-Prueba&id=", q)


class FKeyTest(unittest.TestCase):
    def make(self):
        cfg = copy.deepcopy(config.DEFAULT)
        cfg["row_mode"]["enabled"] = False
        self.board, self.snd = FakeBoard(), FakeSender()
        return Engine(cfg, self.snd, soundboard=self.board), cfg

    def test_unassigned_passes(self):
        e, cfg = self.make()
        self.assertFalse(e.fkeys_wanted())
        self.assertFalse(e.main_wanted())
        self.assertFalse(e.main_key("64", True))     # F13 (scancode de Windows) sin acción
        self.assertFalse(e.main_key("64", False))

    def test_assigned_consumed_all_platform_ids(self):
        e, cfg = self.make()
        cfg["banks"][0]["keys"]["f13"] = {"type": "file", "path": "boom"}
        cfg["global"]["f24"] = {"type": "sound_stop"}
        self.assertTrue(e.main_wanted())
        for kid in ("64", "ev:183", "f13"):          # Windows, Linux, macOS
            self.assertTrue(e.main_key(kid, True))
            self.assertTrue(e.main_key(kid, False))
        self.assertTrue(e.main_key("76", True))       # F24 en la capa Global
        self.assertTrue(e.main_key("76", False))
        wait()
        self.assertEqual(self.board.played, ["boom", "boom", "boom", "STOP"])

    def test_disabled_and_paused(self):
        e, cfg = self.make()
        cfg["banks"][0]["keys"]["f14"] = {"type": "file", "path": "boom"}
        cfg["fkeys"]["enabled"] = False
        self.assertFalse(e.main_key("65", True))
        self.assertFalse(e.main_wanted())
        cfg["fkeys"]["enabled"] = True
        e.set_active(False)
        self.assertFalse(e.main_key("65", True))      # en pausa pasa normal
        self.assertFalse(e.main_key("65", False))

    def test_capture_fkey(self):
        e, cfg = self.make()
        e.capture_next = True
        self.assertTrue(e.main_key("ev:190", True))
        self.assertEqual(e.events.get_nowait(), ("captured", "f20"))

    def test_remote_key_works_when_paused(self):
        e, cfg = self.make()
        cfg["banks"][0]["keys"]["f15"] = {"type": "file", "path": "boom", "mode": "hold"}
        e.set_active(False)
        e.remote_key("f15", True)
        e.remote_key("f15", True)                     # repetición: no duplica
        e.remote_key("f15", False)
        wait()
        self.assertEqual(self.board.played, ["boom", "STOP f15|boom"])


if __name__ == "__main__":
    unittest.main()


class BluetoothPiecesTest(unittest.TestCase):
    def test_windows_structs(self):
        import ctypes
        from npm import remote_bt as bt
        self.assertEqual(ctypes.sizeof(bt._SOCKADDR_BTH), 30)     # como en ws2bth.h
        g = bt._GUID.of(bt.SERVICE_UUID)
        self.assertEqual((g.Data1, g.Data2, g.Data3), (0x8f3c6a52, 0x5e0b, 0x4c6e))
        self.assertEqual(bytes(g.Data4), bt.SERVICE_UUID.bytes[8:])

    @unittest.skipUnless(sys.platform == "win32", "solo Windows")
    def test_windows_python_has_rfcomm(self):
        self.assertTrue(hasattr(socket, "BTPROTO_RFCOMM"))

    def test_linux_sockaddr(self):
        import ctypes
        from npm import remote_bt as bt
        self.assertEqual(ctypes.sizeof(bt._sockaddr_rc), 10)
