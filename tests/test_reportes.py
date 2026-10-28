# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
import hashlib
import http.server
import json
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class Reportes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["XDG_CONFIG_HOME"] = self.tmp.name
        os.environ["APPDATA"] = self.tmp.name
        from npm import reportes
        self.r = reportes

    def tearDown(self):
        os.environ.pop("NM_REPORT_URL", None)
        self.tmp.cleanup()

    def test_limpia_datos_personales(self):
        home = os.path.expanduser("~")
        user = os.path.basename(home)
        txt = (f"FileNotFoundError: [Errno 2] No such file: '{home}/Música/mi grabación secreta.mp3'\n"
               f'  File "/tmp/_MEI12345/npm/gui.py", line 10, in _draw\n'
               f"usuario {user} en {home}/Documentos/clave.txt")
        out = self.r.clean(txt)
        self.assertNotIn("grabación secreta", out)
        self.assertNotIn("clave.txt", out)
        self.assertIn("archivo.mp3", out)
        self.assertIn("npm/gui.py", out)               # las rutas del programa quedan
        self.assertNotIn(home, out)
        if len(user) > 2 and user.lower() not in ("root", "user", "usuario"):
            self.assertNotIn(user, out)

    def _exc(self):
        try:
            {}["no-existe"]
        except KeyError:
            return sys.exc_info()

    def test_huella_estable(self):
        a, b = self._exc(), self._exc()
        self.assertEqual(self.r.fingerprint(a[0], a[2]), self.r.fingerprint(b[0], b[2]))
        rep = self.r.build("error", a, "prueba")
        self.assertEqual(rep["tipo"], "error")
        self.assertIn("KeyError", rep["error"])
        self.assertRegex(rep["instalacion"], r"^[0-9a-f]{32}$")
        self.assertIn("Numpad Macros", self.r.as_text(rep))

    def test_prueba_de_trabajo(self):
        body = b'{"x":1}'
        n = self.r.proof_of_work(body, 12)
        h = hashlib.sha256(body + n.encode()).digest()
        self.assertLess(int.from_bytes(h, "big"), 1 << (256 - 12))

    def test_cola_y_envio(self):
        got = []

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                nonce = self.headers["X-NM-Prueba"]
                ok = int.from_bytes(hashlib.sha256(body + nonce.encode()).digest(), "big") < 1 << (256 - 18)
                got.append((json.loads(body), ok))
                self.send_response(200 if ok else 403)
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            rep = self.r.build("manual", description="se ve raro el tema", with_log=False)
            self.r._save(rep)
            self.assertEqual(self.r.flush(), (0, 1))      # sin dirección: queda en cola
            os.environ["NM_REPORT_URL"] = f"http://127.0.0.1:{srv.server_port}/reporte"
            self.assertEqual(self.r.flush(), (1, 0))
            self.assertTrue(got and got[0][1])
            self.assertEqual(got[0][0]["descripcion"], "se ve raro el tema")
        finally:
            srv.shutdown()

    def test_sin_conexion_queda_en_cola(self):
        os.environ["NM_REPORT_URL"] = "http://127.0.0.1:9/nada"
        self.r._save(self.r.build("manual", description="x", with_log=False))
        self.assertEqual(self.r.flush(), (0, 1))


if __name__ == "__main__":
    unittest.main()
