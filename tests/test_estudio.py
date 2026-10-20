# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Pruebas de la lógica del Estudio de Temas (sin abrir ventanas)."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools", "estudio"))
try:
    import PIL  # noqa: F401
    import logica as L  # noqa: E402
except ImportError:          # el Estudio necesita Pillow; sin él se omiten estas pruebas
    L = None


@unittest.skipIf(L is None, "Pillow no está instalado")
class LogicTest(unittest.TestCase):
    def setUp(self):
        self.base = L.builtin_themes()[0]["colores"]

    def test_builtin_themes(self):
        ts = L.builtin_themes()
        self.assertEqual(len(ts), 11)
        for t in ts:
            self.assertEqual(set(L.npt.TOKENS) - set(t["colores"]), set(), t["nombre"])

    def test_effective_mixes_with_layer_below(self):
        c = dict(self.base, bg="#000000", panel="#ffffff")
        self.assertEqual(L.effective(c, {})["panel"], "#ffffff")
        self.assertEqual(L.effective(c, {"panel": 50})["panel"], "#808080")
        self.assertEqual(L.effective(c, {"panel": 0})["panel"], "#000000")

    def test_legibility_and_fix(self):
        c = dict(self.base, text="#202020")
        states = {n: s for n, _r, _m, s in L.legibility(c, {}, {"opacidad": 100})}
        self.assertEqual(states["Texto sobre paneles"], "bad")
        changed = L.fix_legibility(c, {})
        self.assertIn("text", changed)
        states = {n: s for n, _r, _m, s in L.legibility(c, {}, {"opacidad": 100})}
        self.assertEqual(states["Texto sobre paneles"], "ok")

    def test_window_opacity_warning(self):
        rows = L.legibility(self.base, {}, {"opacidad": 55})
        self.assertEqual(rows[-1][0], "Opacidad de la ventana")
        self.assertEqual(rows[-1][3], "bad")
        self.assertNotIn("Opacidad de la ventana", [r[0] for r in L.legibility(self.base, {}, {"opacidad": 90})])

    def test_palette_from_image(self):
        pal = L.extract_palette(L.sample_image())
        self.assertGreaterEqual(len(pal), 4)
        self.assertAlmostEqual(sum(n for _c, n in pal), 1.0, places=3)
        self.assertEqual(pal, sorted(pal, key=lambda p: -p[1]))
        for dark in (True, False):
            c = L.palette_to_theme(pal, L.pick_accent(pal), dark, self.base)
            L.fix_legibility(c, {})
            self.assertEqual(L.is_dark(c), dark)
            bad = [r for r in L.legibility(c, {}, {"opacidad": 100}) if r[3] == "bad"]
            self.assertEqual(bad, [], (dark, bad))
            L.npt.validate(L.npt.Theme(name="x", author="", colors=c, kind="oscuro" if dark else "claro"))

    def test_render_slot(self):
        src = L.sample_image()
        for slot, (w, h) in L.npt.IMAGE_SLOTS.items():
            for fit in L.FITS:
                im = L.render_slot(src, slot, fit, 80, 50, 2, "#101010")
                self.assertEqual(im.size, (w, h))
        data = L.to_png(L.render_slot(src, "keys", "cover", 100, 65, 4, "#101010"))
        self.assertEqual(L.npt.image_size(data), (600, 520))
        self.assertLess(len(data), L.npt.MAX_FILE)

    def test_project_roundtrip(self):
        state = {"nombre": "Prueba", "colores": dict(self.base), "alfa": {"panel": 80},
                 "imagenes": {"logo": {"src": b"\x89PNG fake", "fit": "cover", "op": 100, "dark": 0, "blur": 0}},
                 "imagen_colores": b"abc"}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.nptproj")
            L.save_project(p, state)
            back = L.load_project(p)
        self.assertEqual(back["imagenes"]["logo"]["src"], b"\x89PNG fake")
        self.assertEqual(back["imagen_colores"], b"abc")
        self.assertEqual(back["alfa"], {"panel": 80})

    def test_slug(self):
        self.assertEqual(L.slug("Neón Tokio!"), "neon-tokio")
        self.assertEqual(L.slug("¡¡!!"), "tema")


@unittest.skipIf(L is None, "Pillow no está instalado")
class KeysTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["NPT_ESTUDIO_DIR"] = self.tmp.name
        import claves
        self.c = claves

    def tearDown(self):
        os.environ.pop("NPT_ESTUDIO_DIR", None)
        self.tmp.cleanup()

    def test_author_and_mode(self):
        self.assertEqual(self.c.mode(), "comunidad")
        self.assertFalse(self.c.has_author_key())
        k = self.c.create_author_key("@kaori")
        self.assertEqual(self.c.load_author_key().public_hex, k.public_hex)
        self.assertEqual(self.c.author_info()["nombre"], "@kaori")

    def test_import_official_backup(self):
        from unittest import mock
        off = L.npt.SigningKey.generate("oficial", "OkumaWsX")
        with self.assertRaises(L.npt.KeyFileError):          # no es la clave oficial
            self.c.import_key_file(off.to_file())
        self.assertEqual(self.c.mode(), "comunidad")
        with mock.patch.object(L.npt, "OFFICIAL_KEY", off.public_hex):
            self.assertEqual(self.c.import_key_file(off.to_file("12345678")), "oficial")
            self.assertEqual(self.c.mode(), "creador")
            self.assertTrue(self.c.official_known(self.c.official_info()))
            self.assertEqual(self.c.load_official_key("12345678").public_hex, off.public_hex)

    def test_import_publicador_pem(self):
        from unittest import mock
        from cryptography.hazmat.primitives import serialization as ser
        off = L.npt.SigningKey.generate("oficial")
        pem = off._k.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.PKCS8, ser.NoEncryption())
        with self.assertRaises(L.npt.KeyFileError):
            self.c.import_key_file(pem)
        with mock.patch.object(L.npt, "OFFICIAL_KEY", off.public_hex):
            self.assertEqual(self.c.import_key_file(pem), "oficial")
            self.assertEqual(self.c.load_official_key().public_hex, off.public_hex)


if __name__ == "__main__":
    unittest.main()
