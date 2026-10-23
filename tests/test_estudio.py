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

    def test_animated_slot(self):
        gif = L.sample_anim("ecualizador")
        self.assertGreater(L.frame_count(gif), 1)
        for slot in ("headmid", "keys"):
            fr = L.render_slot_frames(gif, slot, L.SLOT_DEFAULTS[slot], "#101010")
            self.assertEqual(fr[0][0].size, L.npt.IMAGE_SLOTS[slot])
            data = L.encode(fr)
            self.assertEqual(L.npt.image_frames(data), len(fr))
            self.assertEqual(L.npt.image_size(data), L.npt.IMAGE_SLOTS[slot])
        # un GIF de verdad (con más de 120 cuadros) se recorta y queda animado
        import io
        from PIL import Image
        frames = [Image.new("RGB", (50, 20), (i * 2 % 256, 255 - i, 40)) for i in range(130)]
        buf = io.BytesIO()
        frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], duration=40, loop=0)
        self.assertEqual(L.source_count(buf.getvalue()), 130)
        src = L.prepare_source(buf.getvalue())
        self.assertEqual(L.frame_count(src), L.npt.MAX_FRAMES)
        self.assertEqual(L.frame_count(L.prepare_source(L.to_png(L.sample_image()))), 1)

    def test_gradient(self):
        stops = L.gradient_from_theme(self.base)
        self.assertEqual(len(stops), 3)
        for d in L.npt.GRADIENT_FROM:
            im = L.gradient_image({"colores": [["#000000", 0], ["#ffffff", 100]], "desde": d}, (40, 30))
            self.assertEqual(im.size, (40, 30))
        im = L.gradient_image({"colores": [["#000000", 0], ["#ffffff", 100]], "desde": "l"}, (100, 10))
        self.assertLess(im.getpixel((2, 5))[0], 20)
        self.assertGreater(im.getpixel((97, 5))[0], 235)
        im = L.gradient_image({"colores": [["#000000", 0], ["#ffffff", 100]], "desde": "c"}, (100, 100))
        self.assertLess(im.getpixel((50, 50))[0], 20)
        self.assertGreater(im.getpixel((1, 1))[0], 200)
        self.assertEqual(len(L.gradient_add_stop(stops)), 4)
        self.assertEqual(L.gradient_avg({"colores": [["#000000", 0], ["#ffffff", 100]]}, "#123456"), "#808080")
        r, _c, st = L.gradient_check(dict(self.base, text="#ffffff"), {},
                                     {"colores": [["#ffffff", 0], ["#000000", 100]], "desde": "t"})
        self.assertEqual(st, "bad")

    def test_sections(self):
        self.assertEqual(L.preset("normal"), {})
        f = L.focus({}, "keys")
        self.assertTrue(f["keys"]["realce"])
        self.assertEqual(f["body"]["contenido"], 55)
        rows = L.section_rows(self.base, {}, f, {}, {})
        self.assertEqual(len(rows), 6)
        self.assertTrue(any(r[5] == "warn" for r in rows))          # las atenuadas avisan
        t = L.npt.Theme(name="x", author="", colors=dict(self.base), sections=f)
        L.npt.validate(t)

    def test_preview_draws(self):
        import vista as V

        class FakeCanvas:
            def after(self, *a):
                return 1

            def after_cancel(self, *a):
                pass
        pv = V.Preview(FakeCanvas())
        pv._show = lambda: None
        e = L.effective(self.base, {})
        gif = L.sample_anim("estrellas")
        frames = lambda slot, size: (L.render_slot_frames(gif, slot, L.SLOT_DEFAULTS[slot], "#000000", size=size)  # noqa
                                     if slot in ("tabsend", "keys") else None)
        pv.draw(e, frames, gradient={"colores": [["#000000", 0], ["#334455", 100]], "desde": "b"},
                sections=L.focus({}, "body"), opacity=80, wall=True)
        im = pv.compose(250)
        self.assertEqual(im.size, (V.W, V.H))
        x1, y1, x2, y2 = V.ZONES["keys"]
        self.assertEqual(pv.tag_at(V.OX + 300 + 20, V.OY + 400, "t:"), "panel")
        pv.draw(e, frames, mode="img", sel="keys")
        self.assertEqual(pv.tag_at(V.OX + (x1 + x2) / 2, V.OY + y1 + 3, "z:"), "keys")
        self.assertEqual(pv.tag_at(V.OX + 300, V.OY + 527, "z:"), "foot")
        pv.draw(e, frames, mode="sec", sel="keys")
        self.assertEqual(pv.tag_at(V.OX + 100, V.OY + 300, "s:"), "keys")
        self.assertEqual(pv.tag_at(V.OX + 500, V.OY + 300, "s:"), "body")

    def test_preview_rescale(self):
        """Al cambiar solo el tamaño se reducen otra vez las capas: igual que dibujar todo de nuevo."""
        import vista as V

        class FakeCanvas:
            def after(self, *a):
                return 1

            def after_cancel(self, *a):
                pass
        e = L.effective(self.base, {})
        gif = L.sample_anim("estrellas")
        frames = lambda slot, size: (L.render_slot_frames(gif, slot, L.SLOT_DEFAULTS[slot], "#000000", size=size)  # noqa
                                     if slot in ("tabsend", "keys") else None)
        quick, full = V.Preview(FakeCanvas()), V.Preview(FakeCanvas())
        quick._show = full._show = lambda: None
        self.assertFalse(quick.rescale())                      # nada dibujado todavía
        quick.draw(e, frames, mode="img", sel="keys", opacity=80)
        self.assertTrue(quick.set_scale(1.3) and quick.rescale())
        full.set_scale(1.3)
        full.draw(e, frames, mode="img", sel="keys", opacity=80)
        self.assertEqual(quick.compose(160).tobytes(), full.compose(160).tobytes())
        self.assertEqual(quick.compose().size, full.size)

    def test_background_image_and_one_piece(self):
        import vista as V
        pal = L.extract_palette(L.sample_image())
        gen = L.background_from_palette(pal, True)
        img = L.from_bytes(gen)
        self.assertEqual(img.size, (1600, 1000))
        data = L.background_png(gen, 30, "#101010")
        w, h = L.npt.image_size(data)
        self.assertTrue(w <= 1920 and h <= 1200)
        self.assertLess(len(data), L.BG_LIMIT + 1)
        e = L.effective(self.base, {})
        r, _c, st = L.one_piece_check(e, ["#ffffff", "#000000"], "#101010", 0)
        self.assertIn(st, ("ok", "warn", "bad"))

        class FakeCanvas:
            def after(self, *a):
                return 1

            def after_cancel(self, *a):
                pass
        pv = V.Preview(FakeCanvas())
        pv._show = lambda: None
        bright = L.from_bytes(L.background_from_palette([("#ff0000", 1.0), ("#00ff00", .5)], False))
        pv.draw(e, bg_image=bright, one_piece=True, tint=0)
        inside = pv.compose().getpixel((V.OX + 150, V.OY + 470))      # panel de teclas, sin tinte
        pv.draw(e, bg_image=bright, one_piece=False)
        solid = pv.compose().getpixel((V.OX + 150, V.OY + 470))       # panel de color sólido
        self.assertNotEqual(inside[:3], solid[:3])
        self.assertEqual(L.npt.IMAGE_SLOTS["fondo"], (1920, 1200))

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
