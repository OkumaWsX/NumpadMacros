# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Pruebas de la lógica del Estudio de Temas (sin abrir ventanas)."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# código del Estudio: tools/estudio en el repositorio, o esta misma carpeta en la copia local por programas
EST = os.path.join(HERE, "tools", "estudio") if os.path.isdir(os.path.join(HERE, "tools", "estudio")) else HERE
sys.path.insert(0, EST)
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


def _estudio():
    """El módulo de la ventana (sin abrirla), o None si este Python no tiene Tk."""
    try:
        import estudio
        return estudio
    except Exception:
        return None


class _FakeCanvas:
    def after(self, *a):
        return 1

    def after_cancel(self, *a):
        pass


@unittest.skipIf(L is None, "Pillow no está instalado")
class AvisosTest(unittest.TestCase):
    """Avisos de legibilidad con «Ir» (1.3.0): a qué control lleva cada uno, orden y repetidos."""

    def setUp(self):
        self.base = dict(L.builtin_themes()[0]["colores"])
        E = _estudio()
        self.labels = E.LABELS if E else {k: k for k in L.npt.TOKENS}

    def probs(self, colors, sections=None, window=None, auto=False):
        return L.problems(colors, {}, window or {"opacidad": 100}, sections or {}, {}, {}, auto, self.labels)

    def test_cada_pareja_lleva_a_su_control(self):
        import vista as V
        pv = V.Preview(_FakeCanvas())
        pv._put = lambda im: None
        pv.draw(L.effective(self.base, {}))
        E = _estudio()
        for name, f, b, _mn in L.PAIRS:
            c = dict(self.base)
            c[f] = c[b]                              # el texto igual a su fondo: no se lee
            ps = {p["nombre"]: p for p in self.probs(c)}
            self.assertIn(name, ps, name)
            p = ps[name]
            self.assertEqual(p["pestana"], "edit")
            self.assertTrue(p["capas"] and set(p["capas"]) <= set(L.npt.TOKENS), name)
            self.assertTrue({f, b} & set(p["capas"]), name)
            if E:
                self.assertIn(p["capas"][0], E.LABELS, name)        # hay una fila con ese color
            self.assertTrue(pv.rects(L.PAIR_MARKS[name]), f"{name}: nada que marcar en la vista previa")
            self.assertTrue(p["frase"].endswith(".") and "«" in p["frase"], name)
        # «Selección en listas» con los tonos derivados: se arregla con el acento
        c = dict(self.base, acc_dim=self.base["text"])
        p = next(p for p in self.probs(c, auto=True) if p["nombre"] == "Selección en listas")
        self.assertEqual(p["capas"][0], "acc")
        # opacidad y secciones también llevan a su control
        p = self.probs(self.base, window={"opacidad": 50})[0]
        self.assertEqual((p["nombre"], p["control"], p["st"]), ("Opacidad de la ventana", "ventana", "bad"))
        p = self.probs(self.base, {"tabs": {"fondo": 100, "contenido": 30, "realce": False}})[0]
        self.assertEqual((p["pestana"], p["seccion"]), ("sec", "tabs"))
        self.assertIn("ahora 30 %", p["frase"])

    def test_orden_por_gravedad(self):
        c = dict(self.base, key_set_text="#4a4638", key_set="#3d3a30", muted="#5d626d", panel="#1c1f26")
        secs = {"tabs": {"fondo": 100, "contenido": 30, "realce": False},
                "body": {"fondo": 100, "contenido": 55, "realce": False}}
        ps = self.probs(c, secs)
        sts = [p["st"] for p in ps]
        self.assertEqual(sts, sorted(sts, key=lambda s: s != "bad"))       # primero ✗, luego ⚠
        self.assertEqual(ps[0]["nombre"], "Tecla con acción")
        warns = [p["r"] / p["mn"] for p in ps if p["st"] == "warn"]
        self.assertEqual(warns, sorted(warns))                               # lo más lejos del mínimo, antes
        self.assertTrue(any(p["st"] == "warn" and p["r"] / p["mn"] < .75 for p in ps))   # una sección muy atenuada

    def test_seccion_repetida_no_se_duplica(self):
        c = dict(self.base, key_set_text="#4a4638", key_set="#3d3a30")
        ps = self.probs(c)
        names = [p["nombre"] for p in ps]
        self.assertNotIn("Sección · Teclas", names)
        self.assertEqual(next(p for p in ps if p["nombre"] == "Tecla con acción")["secciones"], ["keys"])
        # si la sección se atenuó a propósito, es otro aviso (y lleva a la pestaña de secciones)
        ps = self.probs(c, {"keys": {"fondo": 100, "contenido": 50, "realce": False}})
        self.assertIn("Sección · Teclas", [p["nombre"] for p in ps])
        # sin problema de colores, una sección atenuada avisa sola
        ps = self.probs(self.base, {"keys": {"fondo": 100, "contenido": 30, "realce": False}})
        self.assertEqual([p["nombre"] for p in ps], ["Sección · Teclas"])


def _imagen_luna():
    """Noche oscura con una luna brillante en un hueco del encabezado donde no hay texto."""
    from PIL import Image, ImageDraw, ImageFilter
    import vista as V
    w, h = 1600, 1000
    im = Image.new("RGB", (w, h), (20, 26, 56))
    k = max(V.WW / w, V.WH / h)
    cx, cy = (400 + (w * k - V.WW) / 2) / k, 24 / k
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).ellipse([cx - 80, cy - 70, cx + 80, cy + 70], fill=255)
    im.paste((255, 250, 235), (0, 0), m.filter(ImageFilter.GaussianBlur(6)))
    return im


def _imagen_brillo():
    """Doce franjas oscuras (llenan la paleta) y un brillo claro y chico justo bajo el título."""
    from PIL import Image, ImageDraw, ImageFilter
    import vista as V
    w, h = 1600, 1000
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for i, c in enumerate([(40, 20, 70), (80, 25, 50), (20, 50, 90), (15, 80, 70), (90, 40, 20), (30, 20, 50),
                           (20, 90, 30), (70, 70, 15), (15, 40, 40), (60, 15, 90), (95, 20, 20), (25, 60, 60)]):
        d.rectangle([0, i * h // 12, w, (i + 1) * h // 12], fill=c)
    k = max(V.WW / w, V.WH / h)
    ox = (w * k - V.WW) / 2
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([(8 + ox) / k, 4 / k, (170 + ox) / k, 40 / k], radius=20, fill=255)
    im.paste((250, 240, 215), (0, 0), m.filter(ImageFilter.GaussianBlur(4)))
    return im


@unittest.skipIf(L is None, "Pillow no está instalado")
class MedicionPorZonaTest(unittest.TestCase):
    """Texto sobre la imagen de fondo, medido zona por zona (1.3.0)."""

    def setUp(self):
        import vista as V
        self.V = V
        self.colors = dict(L.builtin_themes()[0]["colores"])
        self.e = L.effective(self.colors, {})

    def medir(self, im, dark=0, one_piece=False, tint=35):
        return self.V.measure_image(L.to_png(im), self.colors["bg"], self.e, dark, tint, one_piece, {})

    def antes(self, im):
        """Lo que hacía el Estudio hasta la 1.2: los 5 colores principales y el peor."""
        return L.colors_check(self.e, L.background_colors(im))

    def test_luna_en_un_hueco_sin_texto_no_bloquea(self):
        im = _imagen_luna()
        self.assertEqual(self.antes(im)[2], "bad")              # el método viejo bloqueaba sin motivo
        res = self.medir(im)
        self.assertEqual(res["st"], "ok", res["peor"])
        self.assertEqual(res["malas"], [])

    def test_brillo_bajo_el_titulo_si_bloquea(self):
        im = _imagen_brillo()
        self.assertEqual(self.antes(im)[2], "ok")               # el método viejo no lo veía
        res = self.medir(im)
        self.assertEqual(res["st"], "bad")
        self.assertIn("título", res["peor"]["nombre"])
        self.assertEqual(res["peor"]["rect"][:2], (12, 8))      # y marca esa zona
        self.assertIn("«Oscurecer la imagen»", L.image_advice(res))

    def test_sugerencia_del_minimo(self):
        res = self.medir(_imagen_brillo())
        d = res["sug_oscurecer"]
        self.assertIsNotNone(d)
        self.assertEqual(d % 5, 0)
        self.assertLessEqual(d, L.DARK_MAX)
        self.assertEqual(self.medir(_imagen_brillo(), dark=d)["st"], "ok")
        self.assertNotEqual(self.medir(_imagen_brillo(), dark=d - 5)["st"], "ok")      # es el mínimo
        self.assertIn(f"a {d} %", L.image_advice(res))

    def test_sugerencia_con_tope_y_tinte_solo_en_paneles(self):
        from PIL import Image
        # fondo de prueba: gris que se oscurece con «Oscurecer»; los paneles, con el tinte
        zones = [{"rect": (0, 0, 10, 10), "tag": "t:text", "nombre": "el título", "panel": False},
                 {"rect": (20, 0, 30, 10), "tag": "t:text", "nombre": "un texto del panel", "panel": True}]
        e = {"text": "#ffffff", "muted": "#aaaaaa"}

        def backdrop(level_head, level_panel):
            def f(d, t):
                im = Image.new("RGB", (40, 10), (level_head(d),) * 3)
                im.paste((level_panel(d, t),) * 3, (20, 0, 40, 10))
                return im
            return f
        def minimo(level):           # el primer valor (de 5 en 5) con que el blanco se lee sobre ese gris
            return next(v for v in range(5, 95, 5) if L.ratio("#ffffff", L.rgb2hex((level(v),) * 3)) >= 4.5)
        # el encabezado se arregla oscureciendo: el mínimo exacto, de 5 en 5
        bd = backdrop(lambda d: 255 - d * 4, lambda d, t: 40)
        res = L.image_check(bd, zones, e, 0, 35, True)
        self.assertEqual((res["st"], res["peor"]["nombre"], res["sug_oscurecer"], res["sug_tinte"]),
                         ("bad", "el título", minimo(lambda d: 255 - d * 4), None))   # no está en un panel: sin tinte
        # nada lo arregla: sin sugerencia (el control no pasa de DARK_MAX)
        res = L.image_check(backdrop(lambda d: 255, lambda d, t: 40), zones, e, 0, 35, True)
        self.assertIsNone(res["sug_oscurecer"])
        self.assertIn("ni oscureciéndola al máximo", L.image_advice(res))
        # la peor está en un panel de una pieza: también se sugiere el tinte
        res = L.image_check(backdrop(lambda d: 40, lambda d, t: 255 - t * 3), zones, e, 0, 35, True)
        t = minimo(lambda t: 255 - t * 3)
        self.assertEqual((res["peor"]["nombre"], res["sug_tinte"]), ("un texto del panel", t))
        self.assertIn(f"«Tinte de los paneles» (ahora 35 %) a {t} %", L.image_advice(res))
        self.assertIsNone(L.image_check(bd, [], e, 0, 35, True))           # sin texto sobre la imagen

    def test_contenido_atenuado_cuenta(self):
        # el «Contenido» de la sección mezcla el texto con la imagen: a medias se lee peor
        from PIL import Image
        im = Image.new("RGB", (1600, 1000), (40, 40, 40))
        lleno = self.medir(im)
        src, bg = L.to_png(im), self.colors["bg"]
        atenuado = self.V.measure_image(src, bg, self.e, 0, 35, False,
                                        {"head": {"fondo": 0, "contenido": 40, "realce": False}})
        cab = [z for z in atenuado["zonas"] if z["seccion"] == "head"]
        self.assertTrue(cab and all(z["r"] < min(y["r"] for y in lleno["zonas"] if y["seccion"] == "head")
                                    for z in cab))
        # las pestañas y «Novedades» del pie también son texto que puede ir sobre la imagen
        nombres = {z["nombre"] for z in self.V.text_zones()}
        self.assertIn("los nombres de las pestañas", nombres)
        self.assertIn("«Novedades» del pie", nombres)

    def test_paneles_opacos_no_cuentan(self):
        # sin «fondo de una pieza», los paneles tapan la imagen: solo se mide el encabezado y el pie
        res = self.medir(_imagen_luna())
        self.assertEqual({z["seccion"] for z in res["zonas"]}, {"head", "foot"})
        res = self.medir(_imagen_luna(), one_piece=True)
        self.assertTrue({"left", "body"} <= {z["seccion"] for z in res["zonas"]})


@unittest.skipIf(L is None, "Pillow no está instalado")
class AppAvisosTest(unittest.TestCase):
    """La ventana de verdad (sin mostrar diálogos ni usar la red): «Ir», bloqueo al exportar y el hilo de la
    medición por zona."""

    @classmethod
    def setUpClass(cls):
        cls.E = _estudio()
        if cls.E is None:
            raise unittest.SkipTest("este Python no tiene Tk")
        cls.tmp = tempfile.mkdtemp()
        cls.env = {k: os.environ.get(k) for k in ("NPT_ESTUDIO_DIR", "NPT_ENVIOS_DIR", "ESTUDIO_API")}
        api = os.path.join(cls.tmp, "releases.json")
        with open(api, "w", encoding="utf-8") as f:
            f.write("[]")
        os.environ.update(NPT_ESTUDIO_DIR=os.path.join(cls.tmp, "estudio"),
                          NPT_ENVIOS_DIR=os.path.join(cls.tmp, "envios"), ESTUDIO_API="file://" + api)
        try:
            cls.root = cls.E._make_root("EstudioPrueba")
        except Exception:
            cls._restore()
            raise unittest.SkipTest("sin pantalla")
        cls.root.withdraw()
        cls._startup = cls.E.App.startup
        cls.E.App.startup = lambda self: None                 # sin el asistente de la primera vez
        cls.app = cls.E.App(cls.root)
        cls.root.update()

    @classmethod
    def _restore(cls):
        for k, v in cls.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    @classmethod
    def tearDownClass(cls):
        cls.E.App.startup = cls._startup
        try:
            cls.root.destroy()
        except Exception:
            pass
        cls._restore()
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.app.new_theme()
        self.app._zone.update(key=None, res=None, last=None, want=None, inflight=None)
        self.app._show_now("about")
        self.root.update()

    def poner_imagen(self, im, dark=0):
        app = self.app
        app._set_bg_image(L.to_png(im.convert("RGB")), "Fondo de prueba.")
        app.images["fondo"]["dark"] = dark
        app._render_now()

    def test_ir_a_cada_control(self):
        app = self.app
        casos = {"ventana": lambda: None, "grad": lambda: app.bg_mode("degradado"),
                 "tinte": lambda: (app.bg_mode("degradado"), app.grad.update(una_pieza=True)),
                 "imagen": lambda: self.poner_imagen(_imagen_brillo())}
        destino = {"ventana": lambda: app.win_box, "grad": lambda: app.grad_ed, "tinte": lambda: app.tint_scale,
                   "imagen": lambda: app.bgdark_scale}
        for control, preparar in casos.items():
            with self.subTest(control=control):
                app._show_now("about")
                preparar()
                app._render_now()
                p = {"nombre": "Prueba", "r": 1.0, "mn": 4.5, "st": "bad", "pestana": "edit", "capas": ["text"],
                     "control": control, "marcas": (("t:text", "fondo"),), "secciones": [], "frase": "Haz algo."}
                app.go(p)
                self.root.update()
                w = destino[control]()
                self.assertEqual(app.screen, "edit")
                self.assertTrue(w.winfo_exists() and w.winfo_manager(), control)
                # el resaltado: cuatro marcos encima del control, que se van solos
                self.assertTrue([c for c in w.master.place_slaves() if c.cget("bg") == self.E.C["acc"]], control)
                self.assertEqual(app.status.cget("text"), "Haz algo.")

    def test_exportar_bloquea_sin_esperar_al_hilo(self):
        from tkinter import messagebox
        app = self.app
        self.poner_imagen(_imagen_brillo())
        self.assertIsNone(app._zone["key"])                   # el hilo todavía no midió
        self.assertIn("Texto sobre la imagen de fondo", app.blocking_rows())
        avisos = []
        old = messagebox.showwarning
        messagebox.showwarning = lambda *a, **kw: avisos.append(a)
        try:
            self.assertTrue(app._blocked_by_legibility())
        finally:
            messagebox.showwarning = old
        self.assertIn("«1 · Editar tema»", avisos[0][1])
        self.assertNotIn("Transparencia por sección", avisos[0][1])
        self.poner_imagen(_imagen_brillo(), dark=90)           # bien oscurecida: se puede exportar
        self.assertEqual(app.blocking_rows(), [])

    def test_medicion_con_error_no_reintenta(self):
        app, E = self.app, self.E
        llamadas = []

        def falla(params):
            llamadas.append(params)
            try:
                raise RuntimeError("falla de prueba")
            except RuntimeError:
                return {"done": True, "err": sys.exc_info()}
        old_async, old_log = E._measure_async, E._log_error
        E._measure_async, E._log_error = falla, lambda *a: None
        try:
            self.poner_imagen(_imagen_luna())
            res, fresh = app.image_check()
            self.assertFalse(fresh)                              # pedida al hilo
            app._zone_launch()
            for _ in range(100):
                self.root.update()
                if app._zone["key"] is not None:
                    break
                time.sleep(.02)
            res, fresh = app.image_check()
            self.assertTrue(fresh and res["respaldo"])           # la revisión de antes, no «midiendo…»
            self.assertEqual(res["st"], L.colors_check(app.eff(), app.bg_colors())[2])
            app._render_now()
            app._zone_launch()
            self.root.update()
            self.assertEqual(len(llamadas), 1)                   # con la misma clave no se vuelve a intentar
            self.assertNotIn("midiendo", app.leg_img.cget("text"))
            self.assertIn("colores principales", app.leg_img.cget("text"))
        finally:
            E._measure_async, E._log_error = old_async, old_log

    def test_resultado_viejo_se_descarta(self):
        app = self.app
        self.poner_imagen(_imagen_luna())
        viejo = {"r": 99.0, "mn": 4.5, "st": "ok"}
        app._zone_poll(("otra clave",), {"done": True, "res": viejo})
        self.assertIsNone(app._zone["key"])                   # no queda como vigente
        self.assertIs(app._zone["last"], viejo)               # solo como «la última», mientras se mide
        res, fresh = app.image_check(sync=True)
        self.assertTrue(fresh)
        self.assertIsNot(res, viejo)


class NotaBetaTest(unittest.TestCase):
    def test_version_y_nota_beta(self):
        import re
        E = _estudio()
        if E is None:
            self.skipTest("este Python no tiene Tk o Pillow")
        self.assertRegex(E.VERSION, r"^\d+\.\d+\.\d+$")         # el Publicador solo entiende X.Y.Z
        if E.PRUEBA:
            self.assertRegex(E.PRUEBA, r"^beta\.\d+$")
            nota = E.beta_note()
            self.assertIn(f"Versión de prueba ({E.VERSION}-{E.PRUEBA})", nota)
            self.assertIn("avísale a OkumaWsX", nota)
            self.assertEqual(E.app_title(), f"Estudio de Temas {E.VERSION} (beta)")
        old = E.PRUEBA
        try:
            E.PRUEBA = ""                                        # una versión estable: sin nota
            self.assertEqual(E.beta_note(), "")
            self.assertEqual(E.app_title(), "Estudio de Temas")
        finally:
            E.PRUEBA = old
        self.assertTrue(re.match(r"^\d+\.\d+\.\d+$", E.VERSION))


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
        con = U.read_changelog(str(ruta), unreleased=True)          # una beta en local: «Sin publicar» también
        self.assertTrue(con[0]["unreleased"])
        self.assertEqual(con[0]["groups"], [("Añadido", ["No va"])])
        self.assertEqual([x["version"] for x in con[1:]], ["1.1.0", "1.0.0"])

    def test_changelog_real_tiene_la_version_actual(self):
        ruta = os.path.join(EST, "CHANGELOG.md")
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
        for autor in ("", "   ", "A", "!!"):                        # sin nombre de creador válido
            p = L.problemas_previos("Mi Tema", "1.0", "comunidad", autor)
            self.assertTrue(any("nombre de creador" in x for x in p), autor)
        self.assertFalse(any("nombre de creador" in x for x in L.problemas_previos("Mi Tema", "1.0", "comunidad", "Ana")))

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


@unittest.skipIf(L is None, "Pillow no está instalado")
class RevisionComunidadTest(unittest.TestCase):
    """La revisión «comunidad» (la del bot Centinela) copiada en el Estudio."""
    ORIGEN = "/home/okuma/Documentos/Proyectos/revision automatica de bot/revision"

    @classmethod
    def setUpClass(cls):
        import revision_comunidad
        cls.RC = revision_comunidad

    def _tema(self, **kw):
        npt = L.npt
        t = npt.Theme(name=kw.pop("name", "Aurora Neón"), author=kw.pop("author", "nico-gamer"),
                      colors=L.builtin_themes()[0]["colores"], version=kw.pop("version", "1.0"), **kw)
        return npt.write(t, npt.SigningKey.generate("autor", t.author))

    def _copia(self, destino, origen):
        ruta = os.path.join(self.ORIGEN, origen)
        if not os.path.isfile(ruta):
            self.skipTest("no está la carpeta de origen de la revisión")
        with open(ruta, "rb") as a, open(os.path.join(EST, destino), "rb") as b:
            self.assertEqual(a.read(), b.read(), f"{destino} ya no coincide con revision/{origen}: vuelve a copiarlo")

    def test_copias_iguales_al_origen(self):
        self._copia("reglas.json", "reglas.json")
        self._copia("revision_comunidad.py", "npt.py")

    def test_tema_del_estudio_pasa_la_revision(self):
        r = self.RC.revisar(self._tema(description="Un tema azul con acentos: ñandú."))
        self.assertTrue(r["ok"], r["errores"])
        self.assertEqual(r["datos"]["autor_slug"], "nico-gamer")
        self.assertEqual(r["datos"]["tema_id"], "aurora-neon")

    def test_tema_con_imagen_pasa_la_revision(self):
        from PIL import Image
        import io
        buf = io.BytesIO()
        Image.new("RGBA", (1200, 106), (20, 30, 60, 255)).save(buf, "PNG")
        t = L.npt.Theme(name="Con Banner", author="Ana", colors=L.builtin_themes()[0]["colores"], version="1.0",
                        images={"banner": buf.getvalue()})
        r = self.RC.revisar(L.npt.write(t, L.npt.SigningKey.generate("autor", "Ana")))
        self.assertTrue(r["ok"], r["errores"])

    def test_descripcion_con_enlace(self):
        r = self.RC.revisar(self._tema(description="Inspirado en auroras. Más en bit.ly/x"))
        self.assertFalse(r["ok"])
        self.assertIn("texto_enlace", [e["codigo"] for e in r["errores"]])
        for e in r["errores"]:
            self.assertTrue(e["mensaje"])

    def test_no_es_un_tema(self):
        r = self.RC.revisar(b"esto no es un tema")        # nunca lanza
        self.assertFalse(r["ok"])
        self.assertTrue(r["errores"])

    def test_nombre_de_archivo_y_carpeta_del_dialogo(self):
        r = self.RC.revisar(self._tema())
        self.assertEqual(L.nombre_envio("Aurora Neón", "1.0"), "aurora-neon-1.0.npt")
        self.assertEqual(L.carpeta_comunidad(r["datos"]), "comunidad/nico-gamer/aurora-neon/")

    def test_formatear_huella(self):
        ya = "7C1A 09E2 44B0 D1F3 · 2B9C 61AA 0F7E 93D5"
        self.assertEqual(L.formatear_huella(ya), ya)
        self.assertEqual(L.formatear_huella("7c1a09e244b0d1f32b9c61aa0f7e93d5"), ya)
        self.assertEqual(L.formatear_huella(""), "")
        self.assertEqual(L.formatear_huella("raro"), "raro")
        r = self.RC.revisar(self._tema())
        self.assertEqual(L.formatear_huella(r["datos"]["huella"]), r["datos"]["huella"])


class CapturasReleaseTest(unittest.TestCase):
    """Sección «Capturas» de las notas de una Release del Estudio (no necesita Pillow)."""

    def setUp(self):
        import capturas_release
        self.C = capturas_release
        self.dir = tempfile.mkdtemp()
        d = os.path.join(self.dir, "2.0.0")
        os.makedirs(d)
        for n in ("b.png", "a.png", "nota.txt"):
            open(os.path.join(d, n), "wb").close()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_lista_sin_manifiesto_ordena_imagenes(self):
        self.assertEqual(self.C.lista("2.0.0", self.dir), [("a.png", ""), ("b.png", "")])
        self.assertEqual(self.C.lista("9.9.9", self.dir), [])

    def test_lista_con_manifiesto_respeta_orden_y_omite_faltantes(self):
        with open(os.path.join(self.dir, "2.0.0", "capturas.txt"), "w", encoding="utf-8") as f:
            f.write("# comentario\nb.png | La B\nfalta.png | No está\na.png\n")
        self.assertEqual(self.C.lista("2.0.0", self.dir), [("b.png", "La B"), ("a.png", "")])

    def test_seccion_enlaza_a_la_ref(self):
        sec = self.C.seccion("2.0.0", "estudio-v2.0.0", self.dir)
        self.assertTrue(sec.startswith(self.C.INICIO) and sec.endswith(self.C.FIN))
        self.assertIn("### Capturas (versión 2.0.0)", sec)
        self.assertIn("/raw/estudio-v2.0.0/tools/estudio/capturas/2.0.0/a.png", sec)
        self.assertEqual(self.C.seccion("9.9.9", "x", self.dir), "")

    def test_poner_antes_del_pie_y_reemplazar(self):
        notas = "### Añadido\n- **Algo**: nuevo.\n\n---\nPie del Estudio.\n"
        sec = self.C.seccion("2.0.0", "abc", self.dir)
        out = self.C.poner(notas, sec)
        self.assertLess(out.index("### Añadido"), out.index(self.C.INICIO))
        self.assertLess(out.index(self.C.FIN), out.index("---\nPie"))
        otra = self.C.seccion("2.0.0", "def", self.dir)
        out2 = self.C.poner(out, otra)
        self.assertEqual(out2.count(self.C.INICIO), 1)
        self.assertIn("/raw/def/", out2)
        self.assertNotIn("/raw/abc/", out2)

    def test_las_imagenes_no_llegan_al_aviso_ni_a_discord(self):
        import anunciar_discord
        notas = self.C.poner("### Añadido\n- **Algo**: nuevo.\n\n---\nPie.\n",
                             self.C.seccion("2.0.0", "abc", self.dir))
        self.assertEqual(anunciar_discord.items(notas), ["Algo"])
        if L is not None:
            import actualizar
            rel = actualizar.Release({"tag_name": "estudio-v2.0.0", "body": notas, "assets": []})
            self.assertEqual([t for _s, t in rel.notes_lines()], ["Algo: nuevo."])

    def test_version_publicada_tiene_capturas(self):
        # versiones ya publicadas con sus capturas: si se borran, su Release queda con imágenes rotas
        for ver in ("1.0.0", "1.1.0"):
            self.assertTrue(self.C.lista(ver), ver)


if __name__ == "__main__":
    unittest.main()
