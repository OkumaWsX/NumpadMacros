# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Pruebas de la lógica del Estudio de Temas (sin abrir ventanas)."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)                       # el código del Estudio está en esta carpeta
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
        pv._put = lambda im: None
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
        quick._put = full._put = lambda im: None
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
        pv._put = lambda im: None
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


import hashlib  # noqa: E402
import json  # noqa: E402
import pathlib  # noqa: E402
import time  # noqa: E402

try:
    import actualizar as U  # noqa: E402
except ImportError:
    U = None

FALSAS = [
    {"tag_name": "v3.4.4", "name": "Numpad Macros 3.4.4", "body": "- otro programa"},
    {"tag_name": "estudio-v9.9.9", "name": "Estudio de Temas 9.9.9", "draft": True},
    {"tag_name": "estudio-v2.0.0-beta.1", "name": "Estudio de Temas 2.0.0", "prerelease": True,
     "html_url": "https://x/beta", "body": "### Añadido\n- Beta"},
    {"tag_name": "estudio-v1.2.0", "name": "Estudio de Temas 1.2.0", "published_at": "2026-11-02T10:00:00Z",
     "html_url": "https://x/1.2.0",
     "body": "### Añadido\n- **Algo** nuevo\n- Otra cosa\n\n### Corregido\n- Un arreglo con `código`\n\n---\n"
             "Pie que no se muestra\n- viñeta del pie"},
    {"tag_name": "estudio-v1.0.0", "name": "Estudio de Temas 1.0.0"},
]


@unittest.skipIf(U is None, "actualizar.py no se pudo importar")
class ActualizarTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._old = os.environ.get("ESTUDIO_API")
        self.addCleanup(self._restore)

    def _restore(self):
        if self._old is None:
            os.environ.pop("ESTUDIO_API", None)
        else:
            os.environ["ESTUDIO_API"] = self._old

    def api(self, data=None):
        path = pathlib.Path(self.tmp) / "releases.json"
        path.write_text(json.dumps(FALSAS if data is None else data), encoding="utf-8")
        os.environ["ESTUDIO_API"] = path.as_uri()

    def test_versiones(self):
        self.assertEqual(U.parse_version("estudio-v1.2.3"), (1, 2, 3))
        self.assertEqual(U.parse_version("v1.0"), (1, 0, 0))
        self.assertEqual(U.parse_version("2.0.0-beta.1"), (2, 0, 0))
        self.assertTrue(U.newer("1.10.0", "1.9.9"))
        self.assertFalse(U.newer("1.0.0", "1.0.0"))
        self.assertFalse(U.newer("0.9.9", "1.0.0"))

    def test_fetch_latest_filtra(self):
        self.api()
        rel = U.fetch_latest(beta=False)
        self.assertEqual((rel.tag, rel.version), ("estudio-v1.2.0", "1.2.0"))
        self.assertEqual(rel.published, "2026-11-02")
        rel = U.fetch_latest(beta=True)
        self.assertEqual(rel.version, "2.0.0-beta.1")
        self.assertTrue(rel.prerelease)

    def test_fetch_latest_sin_estudio_o_con_error(self):
        self.api([FALSAS[0], FALSAS[1]])
        self.assertIsNone(U.fetch_latest())
        os.environ["ESTUDIO_API"] = (pathlib.Path(self.tmp) / "no-existe.json").as_uri()
        with self.assertRaises(U.UpdateError):
            U.fetch_latest()

    def test_check_y_skip(self):
        self.api()
        upd = {"auto": True, "beta": False, "last_check": 0, "skip": ""}
        self.assertEqual(U.check(upd, "1.0.0").version, "1.2.0")
        self.assertGreater(upd["last_check"], 0)
        self.assertIsNone(U.check(upd, "1.2.0"))
        upd["skip"] = "1.2.0"
        self.assertIsNone(U.check(upd, "1.0.0"))
        self.assertEqual(U.check(upd, "1.0.0", manual=True).version, "1.2.0")

    def test_due(self):
        self.assertTrue(U.due({"auto": True, "last_check": 0}))
        self.assertFalse(U.due({"auto": True, "last_check": time.time()}))
        self.assertFalse(U.due({"auto": False, "last_check": 0}))
        self.assertTrue(U.due({"auto": True, "last_check": time.time() - 25 * 3600}))

    def test_notes_lines_corta_el_pie(self):
        rel = U.Release(FALSAS[3])
        self.assertEqual(rel.notes_lines(), [("Añadido", "Algo nuevo"), ("Añadido", "Otra cosa"),
                                              ("Corregido", "Un arreglo con código")])

    def _release_con_archivo(self, contenido, huella):
        nombre = U.ASSET[U.platform_key()]
        archivo = pathlib.Path(self.tmp) / "origen" / nombre
        archivo.parent.mkdir(exist_ok=True)
        archivo.write_bytes(contenido)
        assets = [{"name": nombre, "browser_download_url": archivo.as_uri(), "size": len(contenido)}]
        if huella is not None:
            sums = pathlib.Path(self.tmp) / "origen" / "SHA256SUMS.txt"
            sums.write_text(f"{huella}  {nombre}\n{'0' * 64}  otro.zip\n", encoding="utf-8")
            assets.append({"name": "SHA256SUMS.txt", "browser_download_url": sums.as_uri(), "size": 1})
        return U.Release({"tag_name": "estudio-v1.2.0", "assets": assets})

    def test_download_huella_correcta(self):
        datos = os.urandom(200_000)
        rel = self._release_con_archivo(datos, hashlib.sha256(datos).hexdigest())
        avances = []
        path = U.download(rel, lambda a, t: avances.append((a, t)))
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        self.assertEqual(open(path, "rb").read(), datos)
        self.assertEqual(avances[-1][0], len(datos))

    def test_download_huella_incorrecta_borra(self):
        rel = self._release_con_archivo(b"hola", "f" * 64)
        carpetas = set(os.listdir(tempfile.gettempdir()))
        with self.assertRaises(U.UpdateError):
            U.download(rel)
        for nuevo in set(os.listdir(tempfile.gettempdir())) - carpetas:
            if nuevo.startswith("estudiotemas-upd-"):
                self.assertEqual(os.listdir(os.path.join(tempfile.gettempdir(), nuevo)), [])

    def test_download_sin_huella(self):
        rel = self._release_con_archivo(b"hola", None)
        with self.assertRaises(U.UpdateError):
            U.download(rel)

    def test_download_cancelada(self):
        datos = b"x" * 1000
        rel = self._release_con_archivo(datos, hashlib.sha256(datos).hexdigest())
        with self.assertRaises(U.UpdateError):
            U.download(rel, cancelled=lambda: True)

    def test_changelog(self):
        txt = ("# Historial\n\n## [Sin publicar]\n### Añadido\n- No va\n\n## [1.1.0] - 2026-11-01\n### Corregido\n"
               "- Arreglo **uno**\n\n## [1.0.0] - pendiente\n### Añadido\n- Primera\n- Segunda\n")
        ruta = pathlib.Path(self.tmp) / "CHANGELOG.md"
        ruta.write_text(txt, encoding="utf-8")
        e = U.read_changelog(str(ruta))
        self.assertEqual([x["version"] for x in e], ["1.1.0", "1.0.0"])
        self.assertEqual(U.changelog_for(e, "1.0.0")["groups"], [("Añadido", ["Primera", "Segunda"])])
        self.assertEqual(U.changelog_for(e, "9.9.9")["version"], "1.1.0")      # no existe: la primera
        self.assertEqual(e[0]["groups"], [("Corregido", ["Arreglo uno"])])
        self.assertEqual(U.read_changelog(str(ruta) + ".no"), [])

    def test_changelog_real_tiene_la_version_actual(self):
        ruta = os.path.join(HERE, "CHANGELOG.md")
        e = U.read_changelog(ruta)
        self.assertTrue(e)
        self.assertTrue(U.changelog_for(e, "1.0.0")["groups"])

    def test_entorno_limpio(self):
        os.environ["_PYI_PRUEBA"] = "1"
        os.environ["_MEIPASS2"] = "x"
        self.addCleanup(lambda: [os.environ.pop(k, None) for k in ("_PYI_PRUEBA", "_MEIPASS2")])
        env = U.relaunch_env()
        self.assertFalse([k for k in env if k.startswith(("_PYI", "_MEI"))])

    def test_install_linux_reemplaza_con_copia(self):
        import io
        import tarfile
        from unittest import mock
        carpeta = pathlib.Path(self.tmp) / "app"
        carpeta.mkdir()
        exe = carpeta / "EstudioTemas-NumpadMacros"
        exe.write_bytes(b"viejo")
        tar = pathlib.Path(self.tmp) / "x.tar.gz"
        with tarfile.open(tar, "w:gz") as tf:
            info = tarfile.TarInfo("EstudioTemas/EstudioTemas-NumpadMacros")
            info.size = 5
            tf.addfile(info, io.BytesIO(b"nuevo"))
        with mock.patch.object(U.sys, "executable", str(exe)):
            U.install_linux(str(tar))
        self.assertEqual(exe.read_bytes(), b"nuevo")
        self.assertEqual((carpeta / "EstudioTemas-NumpadMacros.anterior").read_bytes(), b"viejo")
        self.assertEqual(sorted(os.listdir(carpeta)), ["EstudioTemas-NumpadMacros",
                                                       "EstudioTemas-NumpadMacros.anterior"])


class DiscordAnuncioTest(unittest.TestCase):
    def test_mensaje(self):
        import anunciar_discord as A
        notes = ("### Añadido\n- **Pinceles nuevos**: para el fondo.\n- Más plantillas.\n"
                 "### Corregido\n- El degradado ya no se corta.\n\n---\n- pie que no va")
        self.assertEqual(A.items(notes), ["Pinceles nuevos", "Más plantillas", "El degradado ya no se corta"])
        m = A.message("1.2.3", notes, beta=True)
        self.assertIn("**Estudio de Temas 1.2.3** (versión de prueba)", m)
        self.assertIn("releases/tag/estudio-v1.2.3", m)
        self.assertNotIn("pie", m)
        many = "\n".join(f"- cosa {i}" for i in range(9))
        self.assertIn("…y 4 más.", A.message("1.0.0", many))
        self.assertLessEqual(len(A.message("1.0.0", "- " + "x" * 5000)), 1900)


@unittest.skipIf(L is None, "Pillow no está instalado")
class EnvioComunidadTest(unittest.TestCase):
    def _tema(self, **kw):
        npt = L.npt
        t = npt.Theme(name=kw.pop("name", "Mi Tema"), author=kw.pop("author", "Ana"),
                      colors=L.builtin_themes()[0]["colores"], version=kw.pop("version", "1.0"), **kw)
        return npt.write(t, kw.get("key") or npt.SigningKey.generate("autor", "Ana"))

    def test_foro_url(self):
        ok = ("https://discord.com/channels/123/456", "https://discord.gg/AbC-12", "https://discord.gg/abc/")
        for u in ok:
            self.assertTrue(L.foro_url_valida(u), u)
        for u in ("", "   ", "http://discord.com/channels/1/2", "https://discord.com/channels/1",
                  "https://discord.com.evil.com/channels/1/2", "https://evil.com/https://discord.gg/x",
                  "https://discord.gg/", "javascript:alert(1)", "https://discord.com/channels/a/b"):
            self.assertFalse(L.foro_url_valida(u), u)

    def test_recortar(self):
        self.assertEqual(L.recortar("hola", 10), "hola")
        r = L.recortar("x" * 50, 10)
        self.assertEqual((len(r), r[-1]), (10, "…"))

    def test_nombre_y_carpeta(self):
        self.assertEqual(L.nombre_envio("Mi Tema Ñandú!", "1.2"), "mi-tema-nandu-1.2.npt")
        self.assertEqual(L.nombre_envio("###", "2"), "tema-2.npt")
        old = os.environ.get("NPT_ENVIOS_DIR")
        try:
            os.environ["NPT_ENVIOS_DIR"] = "/tmp/x-envios"
            self.assertEqual(L.carpeta_envios(), "/tmp/x-envios")
            del os.environ["NPT_ENVIOS_DIR"]
            self.assertEqual(os.path.basename(L.carpeta_envios()), L.CARPETA_ENVIOS)
            self.assertTrue(os.path.isabs(L.carpeta_envios()))
        finally:
            os.environ.pop("NPT_ENVIOS_DIR", None)
            if old is not None:
                os.environ["NPT_ENVIOS_DIR"] = old

    def test_armar_envio_limites(self):
        t, m = L.armar_envio("Mi Tema", "1.0", "Ana", "Un tema azul.", "AAAA BBBB", "1.1.0")
        self.assertEqual(t, "Mi Tema 1.0 · por Ana")
        for s in ("Un tema azul.", "Autor: Ana", "Huella de la firma de autor: AAAA BBBB",
                  "Requiere Numpad Macros 3.5.0 o superior", "Enviado desde Estudio de Temas 1.1.0"):
            self.assertIn(s, m)
        t, m = L.armar_envio("N" * 80, "1.0", "A" * 50, "d" * 5000, "H", "1.1.0")
        self.assertLessEqual(len(t), 100)
        self.assertTrue(t.endswith("…"))
        self.assertLessEqual(len(m), 2000)
        self.assertIn("Huella de la firma de autor: H", m)         # lo recortado es la descripción
        self.assertTrue(m.endswith("Estudio de Temas 1.1.0"))
        _t, m = L.armar_envio("T", "1", "", "", "H", "1.1.0")      # sin descripción ni autor
        self.assertIn("Autor: Anónimo", m)
        self.assertFalse(m.startswith("\n"))

    def test_problemas_previos(self):
        self.assertEqual(L.problemas_previos("Mi Tema", "1.0", "comunidad", "Ana"), [])
        self.assertTrue(L.problemas_previos("Mi Tema", "1.0", "creador", "Ana"))
        self.assertTrue(L.problemas_previos("", "1.0", "comunidad", "Ana"))
        self.assertTrue(L.problemas_previos("a", "1.0", "comunidad", "Ana"))   # el identificador necesita 2+
        for v in ("", "v1", "1.2.3.4", "1..2", "1.0-beta"):
            self.assertTrue(L.problemas_previos("Mi Tema", v, "comunidad", "Ana"), v)
        self.assertTrue(L.problemas_previos("Mi Tema", "1.0", "comunidad", "OkumaWsX"))
        self.assertTrue(L.problemas_previos("Mi Tema", "1.0", "comunidad", "0kuma W5X"))

    def test_problemas_archivo(self):
        self.assertEqual(L.problemas_archivo(self._tema(), "1.0"), [])
        self.assertTrue(L.problemas_archivo(self._tema(), "2.0"))                # versión distinta
        self.assertTrue(L.problemas_archivo(b"no es un tema", "1.0"))
        self.assertTrue(L.problemas_archivo(b"x" * (L.npt.MAX_SIZE + 1), "1.0"))  # demasiado grande
        self.assertTrue(L.problemas_archivo(self._tema(author="OkumaWsX"), "1.0"))  # nombre reservado

    def test_mostrar_archivo_sin_gestor(self):
        from unittest import mock
        with mock.patch("shutil.which", return_value=None), mock.patch.object(L.sys, "platform", "linux"):
            self.assertFalse(L.mostrar_archivo("/tmp/no-existe/tema.npt"))


if __name__ == "__main__":
    unittest.main()
