# SPDX-License-Identifier: LGPL-3.0-or-later
"""Pruebas del sistema de actualizaciones (sin internet: servidor local)."""
import hashlib
import http.server
import io
import os
import sys
import tarfile
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from npm import updater  # noqa: E402


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


class UpdaterTest(unittest.TestCase):
    def test_versions(self):
        self.assertTrue(updater.newer("3.10.0", "3.9.9"))
        self.assertTrue(updater.newer("v4.0.0", "3.99.99"))
        self.assertFalse(updater.newer("3.3.0", "3.3.0"))
        self.assertFalse(updater.newer("3.2.1", "3.3.0"))

    def _release(self, body="### Añadido\n- Algo nuevo"):
        return {"tag_name": "v9.0.0", "body": body, "html_url": "x", "prerelease": False, "draft": False,
                "published_at": "2026-10-20T00:00:00Z", "assets": []}

    def test_pick_latest_and_beta(self):
        data = [dict(self._release(), tag_name="v3.4.0"),
                dict(self._release(), tag_name="v3.5.0", prerelease=True),
                dict(self._release(), tag_name="v9.9.9", draft=True),
                dict(self._release(), tag_name="estudio-v99.0.0")]     # otro programa: se ignora
        with mock.patch("json.load", return_value=data), mock.patch.object(updater, "_open"):
            self.assertEqual(updater.fetch_latest(False).version, "3.4.0")
            self.assertEqual(updater.fetch_latest(True).version, "3.5.0")

    def test_skip_and_important(self):
        rel = updater.Release(self._release())
        upd = {"skip": "9.0.0", "beta": False}
        with mock.patch.object(updater, "fetch_latest", return_value=rel):
            self.assertIsNone(updater.check(upd, "3.3.0"))
            self.assertIsNotNone(updater.check(upd, "3.3.0", manual=True))
        imp = updater.Release(self._release("<!-- importante -->\n### Corregido\n- Fallo grave"))
        self.assertTrue(imp.important)
        with mock.patch.object(updater, "fetch_latest", return_value=imp):
            self.assertIsNotNone(updater.check(upd, "3.3.0"))
        self.assertEqual(imp.notes_lines(), [("Corregido", "Fallo grave")])

    def test_download_verify_and_install_linux(self):
        root = tempfile.mkdtemp()
        # paquete de Linux falso, como el que publica GitHub Actions
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            data = b"#!/bin/sh\necho nueva\n"
            info = tarfile.TarInfo("NumpadMacros/NumpadMacros")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        pkg = buf.getvalue()
        with open(os.path.join(root, "NumpadMacros-Linux.tar.gz"), "wb") as f:
            f.write(pkg)
        good = hashlib.sha256(pkg).hexdigest()
        with open(os.path.join(root, "SHA256SUMS.txt"), "w") as f:
            f.write(f"{good}  NumpadMacros-Linux.tar.gz\n")
        handler = lambda *a, **k: _Quiet(*a, directory=root, **k)  # noqa: E731
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        rel = updater.Release(dict(self._release(), assets=[
            {"name": "NumpadMacros-Linux.tar.gz", "browser_download_url": base + "/NumpadMacros-Linux.tar.gz",
             "size": len(pkg)},
            {"name": "SHA256SUMS.txt", "browser_download_url": base + "/SHA256SUMS.txt", "size": 80}]))
        try:
            with mock.patch.object(updater, "platform_key", return_value="linux"):
                seen = []
                path = updater.download(rel, lambda d, t: seen.append(d))
                self.assertTrue(seen and seen[-1] == len(pkg))
                # instalar sobre un "programa" viejo
                exe = os.path.join(root, "app", "NumpadMacros")
                os.makedirs(os.path.dirname(exe))
                with open(exe, "w") as f:
                    f.write("vieja")
                with mock.patch.object(sys, "executable", exe):
                    updater.install_linux(path)
                with open(exe, "rb") as f:
                    self.assertIn(b"nueva", f.read())
                self.assertTrue(os.path.exists(exe + ".anterior"))
                self.assertTrue(os.access(exe, os.X_OK))
                # huella que no coincide -> se rechaza y se borra
                with open(os.path.join(root, "SHA256SUMS.txt"), "w") as f:
                    f.write("0" * 64 + "  NumpadMacros-Linux.tar.gz\n")
                with self.assertRaises(updater.UpdateError):
                    updater.download(rel)
        finally:
            srv.shutdown()

    @unittest.skipUnless(sys.platform.startswith("linux"), "rutas de Linux")
    def test_estudio_check_and_install_linux(self):
        root = tempfile.mkdtemp()
        home = os.path.join(root, "home")
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            for name, data in (("EstudioTemas/EstudioTemas-NumpadMacros", b"#!/bin/sh\necho estudio\n"),
                               ("EstudioTemas/icon-estudio.png", b"no-es-png")):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        pkg = buf.getvalue()
        files = {"EstudioTemas-Linux.tar.gz": pkg}
        files["SHA256SUMS.txt"] = (f"{hashlib.sha256(pkg).hexdigest()}  EstudioTemas-Linux.tar.gz\n").encode()
        for name, data in files.items():
            with open(os.path.join(root, name), "wb") as f:
                f.write(data)
        handler = lambda *a, **k: _Quiet(*a, directory=root, **k)  # noqa: E731
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        assets = [{"name": n, "browser_download_url": f"{base}/{n}", "size": len(d)} for n, d in files.items()]
        # el Estudio tiene sus propias Releases («estudio-v…»), aparte de las de Numpad Macros
        est_data = dict(self._release(), tag_name="estudio-v1.2.0", assets=assets)
        app_data = dict(self._release(), assets=[])
        rel = updater.Release(est_data)
        env = {"HOME": home, "XDG_DATA_HOME": os.path.join(home, "datos"),
               "XDG_CONFIG_HOME": os.path.join(home, "config")}
        try:
            with mock.patch.dict(os.environ, env), mock.patch.object(updater, "platform_key", return_value="linux"), \
                    mock.patch("npm.desktop_linux.refresh"), \
                    mock.patch.object(updater, "_releases", return_value=[app_data, est_data]):
                # no instalado: no hay nada que actualizar, ni aunque la opción esté activa
                self.assertIsNone(updater.estudio_installed())
                self.assertEqual(updater.check_all({"estudio": True}, "9.0.0")[1:], (None, None))
                self.assertEqual(updater.estudio_version(rel), "1.2.0")
                exe = updater.install_estudio(rel, "1.2.0")
                self.assertEqual(exe, os.path.join(home, ".local", "bin", "estudio-temas"))
                self.assertTrue(os.access(exe, os.X_OK))
                self.assertEqual(updater.estudio_installed(), (exe, "1.2.0"))
                self.assertTrue(os.path.isfile(os.path.join(env["XDG_DATA_HOME"], "applications",
                                                            "estudio-temas-numpad-macros.desktop")))
                # al día -> nada; versión vieja anotada -> se ofrece la nueva
                self.assertEqual(updater.check_all({"estudio": True}, "9.0.0"), (None, None, None))
                with open(exe + ".version", "w") as f:
                    f.write("1.1.1\n")
                app, est_rel, ver = updater.check_all({"estudio": True}, "9.0.0")
                self.assertIsNone(app)
                self.assertEqual(est_rel.tag, "estudio-v1.2.0")
                self.assertEqual(ver, "1.2.0")
                self.assertEqual(updater.fetch_latest_estudio().version, "1.2.0")
                # con la opción apagada solo se busca Numpad Macros
                app, est_rel, ver = updater.check_all({"estudio": False}, "8.0.0")
                self.assertEqual((app.version, est_rel, ver), ("9.0.0", None, None))
                # una Release de Numpad Macros no es del Estudio (aunque trajera el archivo)
                self.assertEqual(updater.estudio_version(updater.Release(dict(app_data, assets=assets))), "")
                # la elección del instalador de Linux se lee una sola vez
                os.makedirs(os.path.join(env["XDG_CONFIG_HOME"], "NumpadMacros"))
                with open(os.path.join(env["XDG_CONFIG_HOME"], "NumpadMacros", updater.CHOICE_FILE), "w") as f:
                    f.write("1\n")
                self.assertTrue(updater.take_installer_choice())
                self.assertIsNone(updater.take_installer_choice())
        finally:
            srv.shutdown()

    def test_changelog_bundled(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        from npm import __version__
        versions = updater.read_changelog(os.path.join(here, "CHANGELOG.md"))
        self.assertTrue(versions)
        # la versión del programa debe tener sus novedades (o estar en «Sin publicar»)
        with open(os.path.join(here, "CHANGELOG.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(any(v["version"] == __version__ for v in versions) or "[Sin publicar]" in text)


class LoudnessTest(unittest.TestCase):
    def test_lufs_and_compressor(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy no instalado")
        from npm import loudness as ld
        t = np.arange(48000 * 2) / 48000
        x = (0.1 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
        lufs = ld.measure(np, np.stack([x, x], 1))
        self.assertAlmostEqual(lufs, -20.0, delta=0.6)       # referencia de la norma
        self.assertIsNone(ld.measure(np, np.zeros((48000, 2), np.float32)))
        self.assertEqual(ld.norm_gain_db(-30, -16), 12.0)     # tope de +12 dB
        comp = ld.Compressor(np)
        loud = np.ones((480, 2), np.float32) * 1.5
        for _ in range(20):
            out = comp.process(loud.copy(), -18, 3, -1)
        self.assertLessEqual(float(np.max(np.abs(out))), ld.db_to_lin(-1) + 1e-6)
        self.assertGreater(comp.gr_db, 1)


if __name__ == "__main__":
    unittest.main()


class DesktopLinuxTest(unittest.TestCase):
    def test_menu_entry_and_icons(self):
        from npm import desktop_linux
        tmp = tempfile.mkdtemp()
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": tmp}), mock.patch.object(desktop_linux, "refresh"):
            icon = os.path.join(here, "assets", "icon.png")
            self.assertTrue(desktop_linux.install("numpad-macros", "Numpad Macros", "x", "/opt/nm bin", icon,
                                                  "NumpadMacros"))
            with open(os.path.join(tmp, "applications", "numpad-macros.desktop"), encoding="utf-8") as f:
                text = f.read()
            self.assertIn("StartupWMClass=NumpadMacros", text)
            self.assertIn('Exec="/opt/nm bin"', text)
            self.assertIn("Icon=numpad-macros", text)
            for s in desktop_linux.SIZES:
                self.assertTrue(os.path.isfile(os.path.join(tmp, "icons", "hicolor", f"{s}x{s}", "apps",
                                                            "numpad-macros.png")))
            # sin cambios: no vuelve a escribir
            self.assertFalse(desktop_linux.install("numpad-macros", "Numpad Macros", "x", "/opt/nm bin", icon,
                                                   "NumpadMacros"))
            # icono nuevo (otra versión): se vuelve a copiar
            other = os.path.join(here, "assets", "icon-estudio.png")
            self.assertTrue(desktop_linux.install("numpad-macros", "Numpad Macros", "x", "/opt/nm bin", other,
                                                  "NumpadMacros"))
