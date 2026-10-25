# SPDX-License-Identifier: LGPL-3.0-or-later
"""Pruebas del buscador, los filtros y el orden de la pestaña Temas (sin ventana)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from npm import catalogo, theme_filter as tf, themes  # noqa: E402

DARK = {"bg": "#14161b", "acc": "#f2a33a"}
LIGHT = {"bg": "#eef0f4", "acc": "#2860f0"}


def entry(eid, nombre, origen="comunidad", autor="kenji", estilo="oscuro", color="rosa", fecha="2026-10-01",
          etiquetas=(), extras=None, version="1.0", colores=None):
    return {"id": eid, "nombre": nombre, "origen": origen, "autor": autor, "estilo": estilo, "color": color,
            "fecha": fecha, "etiquetas": list(etiquetas), "extras": extras or {}, "version": version,
            "colores": colores or DARK}


def item(th=None, e=None):
    it = {"th": th, "entry": e}
    it["facts"] = tf.facts(it, catalogo.has_update)
    return it


def names(items):
    return [it["facts"]["name"] for it in items]


class Facts(unittest.TestCase):
    def test_builtin_style_and_color_by_colors(self):
        f = {th["name"]: item(th)["facts"] for th in themes.builtin()}
        self.assertEqual(f["Original"]["style"], "oscuro")
        self.assertEqual(f["Claro"]["style"], "claro")         # por la luminancia del fondo
        self.assertEqual(f["Papel"]["style"], "claro")
        self.assertEqual(f["Medianoche"]["color"], "celeste")  # por el acento
        self.assertTrue(f["Original"]["official"] and f["Original"]["installed"])
        self.assertEqual(f["Original"]["extras"], set())

    def test_installed_extras_from_theme(self):
        th = {"name": "Foto", "author": "ana", "colors": LIGHT, "kind": "oscuro", "image_slots": ["banner"],
              "animated_slots": ["free1"], "alpha": {"window": .9, "idle": .9},
              "background": {"tipo": "degradado", "colores": [["#000000", 0], ["#ffffff", 100]]}}
        f = item(th)["facts"]
        self.assertEqual(f["extras"], {"imagenes", "gif", "transparencia", "degradado"})
        self.assertEqual(f["style"], "oscuro")                  # lo que dice el tema manda
        self.assertEqual(f["author"], "ana")
        self.assertFalse(f["official"])

    def test_catalog_entry(self):
        e = entry("c/x", "Sakura", extras={"imagenes": 2, "animado": True, "transparencia": False},
                  etiquetas=["Rosa"])
        f = item(e=e)["facts"]
        self.assertEqual(f["extras"], {"imagenes", "gif"})
        self.assertFalse(f["installed"])
        self.assertEqual(f["color"], "rosa")
        self.assertIn("rosa", f["text"])

    def test_update(self):
        th = {"name": "Sakura", "author": "kenji", "colors": DARK, "version": "1.0"}
        self.assertTrue(item(th, entry("c/s", "Sakura", version="1.1"))["facts"]["update"])
        self.assertFalse(item(th, entry("c/s", "Sakura", version="1.0"))["facts"]["update"])

    def test_color_name(self):
        self.assertEqual(tf.color_name("#808080"), "gris")
        self.assertEqual(tf.color_name("#ff0000"), "rojo")
        self.assertEqual(tf.color_name("#fe0010"), "rojo")      # cerca de 360°
        self.assertEqual(tf.color_name("#00c000"), "verde")


class Creadores(unittest.TestCase):
    """Creadores digitales: firmados con la clave oficial, pero con su propio sello y nombre."""
    def setUp(self):
        self.creador = entry("creador/aqua/dos-mares", "Dos Mares", origen="creador", autor="OkumaWsX",
                             fecha="2026-10-22")
        self.creador["creador"] = "AquamanChileno"
        self.items = [item(th) for th in themes.builtin()] + [
            item(e=entry("c/sakura", "Sakura", autor="kenji")),
            item(e=entry("o/mar", "Mar", origen="oficial", autor="OkumaWsX")),
            item(e=self.creador),
        ]

    def run_f(self, **kw):
        filt = tf.new_filters()
        filt.update(kw)
        return names(tf.apply(self.items, filt))

    def test_facts(self):
        f = item(e=self.creador)["facts"]
        self.assertTrue(f["creator"])
        self.assertFalse(f["official"])
        self.assertEqual(f["creator_name"], "AquamanChileno")

    def test_installed_matching_creator_entry_counts_as_creator(self):
        # el archivo instalado va firmado con la clave oficial, pero la entrada lo hace «creador»
        th = {"name": "Dos Mares", "author": "OkumaWsX", "official": True, "colors": DARK, "version": "1.0"}
        f = item(th, self.creador)["facts"]
        self.assertTrue(f["creator"] and not f["official"] and f["installed"])
        self.assertTrue(item(th)["facts"]["official"])             # sin entrada de creador, es oficial

    def test_origin_filter(self):
        self.assertEqual(self.run_f(origen="creador"), ["Dos Mares"])
        self.assertEqual(self.run_f(origen="comunidad"), ["Sakura"])
        self.assertNotIn("Dos Mares", self.run_f(origen="oficial"))
        self.assertTrue(tf.active({**tf.new_filters(), "origen": "creador"}))

    def test_search_by_creator_name(self):
        self.assertEqual(self.run_f(q="aquaman"), ["Dos Mares"])

    def test_official_first_order(self):
        n = len(themes.builtin())
        self.assertEqual(self.run_f(orden="oficiales")[n:], ["Mar", "Dos Mares", "Sakura"])


class Filtering(unittest.TestCase):
    def setUp(self):
        self.items = [item(th) for th in themes.builtin()] + [
            item(e=entry("c/sakura", "Sakura", autor="kenji", etiquetas=["rosa", "suave"], fecha="2026-10-24",
                         extras={"imagenes": 1})),
            item(e=entry("c/pastel", "Pastel", autor="mimi", estilo="claro", color="naranja", fecha="2026-10-20",
                         colores=LIGHT)),
            item(e=entry("o/dos", "Dos Mares", origen="oficial", autor="OkumaWsX", color="amarillo",
                         fecha="2026-10-22", extras={"transparencia": True, "imagenes": 7})),
        ]

    def run_f(self, **kw):
        filt = tf.new_filters()
        filt.update(kw)
        return names(tf.apply(self.items, filt))

    def test_no_filters_all(self):
        self.assertEqual(len(self.run_f()), len(self.items))
        self.assertFalse(tf.active(tf.new_filters()))

    def test_search_name_author_tags_without_accents(self):
        self.assertEqual(self.run_f(q="oceano"), ["Océano"])
        self.assertEqual(self.run_f(q="MIMI"), ["Pastel"])
        self.assertEqual(self.run_f(q="suave"), ["Sakura"])
        self.assertEqual(self.run_f(q="kenji rosa"), ["Sakura"])  # todas las palabras
        self.assertEqual(self.run_f(q="zzz"), [])

    def test_origin_and_show(self):
        self.assertEqual(sorted(self.run_f(origen="comunidad")), ["Pastel", "Sakura"])
        self.assertIn("Dos Mares", self.run_f(origen="oficial"))
        self.assertEqual(sorted(self.run_f(mostrar="disponibles")), ["Dos Mares", "Pastel", "Sakura"])
        self.assertEqual(len(self.run_f(mostrar="instalados")), len(themes.builtin()))
        self.assertEqual(self.run_f(mostrar="actualizar"), [])

    def test_style_color_extras(self):
        self.assertEqual(sorted(self.run_f(estilo="claro")), ["Claro", "Papel", "Pastel"])
        self.assertEqual(self.run_f(color="naranja", origen="comunidad"), ["Pastel"])
        self.assertEqual(sorted(self.run_f(extras=["imagenes"])), ["Dos Mares", "Sakura"])
        self.assertEqual(self.run_f(extras=["imagenes", "transparencia"]), ["Dos Mares"])
        self.assertTrue(tf.active({**tf.new_filters(), "extras": ["gif"]}))

    def test_orders(self):
        self.assertEqual(self.run_f(origen="comunidad", orden="nombre"), ["Pastel", "Sakura"])
        rec = self.run_f(orden="recientes")
        self.assertEqual(rec[:3], ["Sakura", "Dos Mares", "Pastel"])   # sin fecha (incluidos) al final
        ofi = self.run_f(orden="oficiales")
        n = len(themes.builtin())
        self.assertEqual(ofi[:n], sorted(ofi[:n], key=tf._plain))   # primero los incluidos, por nombre
        self.assertEqual(ofi[n:], ["Dos Mares", "Pastel", "Sakura"])  # luego los oficiales, luego comunidad

    def test_clear_keeps_order(self):
        filt = {**tf.new_filters(), "q": "x", "color": "rosa", "extras": ["gif"], "orden": "recientes"}
        tf.clear(filt)
        self.assertFalse(tf.active(filt))
        self.assertEqual(filt["orden"], "recientes")

    def test_colors_in(self):
        cols = tf.colors_in(self.items)
        self.assertIn("rosa", cols)
        self.assertEqual(cols, [c for c in tf.SWATCH if c in cols])   # en el orden del arcoíris

    def test_hundred_themes_fast(self):
        import time
        many = [item(e=entry(f"c/{i}", f"Tema {i}", color=("rosa", "azul")[i % 2])) for i in range(100)]
        t0 = time.perf_counter()
        for _ in range(20):
            tf.apply(many, {**tf.new_filters(), "q": "tema 5", "color": "azul", "orden": "recientes"})
        self.assertLess((time.perf_counter() - t0) / 20, .02)


class Robustez(unittest.TestCase):
    """Entradas raras del catálogo o de un .npt: ni facts() ni el orden deben lanzar."""

    def test_fecha_no_ascii_no_rompe_el_orden(self):
        its = [item(e=entry("a", "A", fecha="Mañana")), item(e=entry("b", "B", fecha="é")),
               item(e=entry("c", "C", fecha="2026-01-05")), item(e=entry("d", "D", fecha="2026-03-01")),
               item(e=entry("e", "E", fecha=""))]
        out = tf.apply(its, {**tf.new_filters(), "orden": "recientes"})
        # válidas de la más nueva a la más vieja; sin fecha (o inválida) al final, por nombre
        self.assertEqual(names(out), ["D", "C", "A", "B", "E"])

    def test_catalogo_con_tipos_raros(self):
        e = entry("x", "X")
        e.update({"autor": None, "extras": ["gif"], "etiquetas": None, "estilo": 3, "color": 5, "fecha": 20261001})
        f = tf.facts({"th": None, "entry": e}, catalogo.has_update)
        self.assertEqual(f["author"], "")
        self.assertEqual(f["extras"], set())
        self.assertEqual(f["date"], "")
        self.assertIn(f["style"], ("oscuro", "claro"))
        self.assertIsInstance(f["color"], str)
        e["etiquetas"] = ["ok", 7, None]
        self.assertIn("ok", tf.facts({"th": None, "entry": e})["text"])

    def test_tema_instalado_con_autor_o_fecha_raros(self):
        th = {"name": "T", "author": None, "created": "Mañana", "colors": DARK}
        f = tf.facts({"th": th, "entry": None})
        self.assertEqual((f["author"], f["date"]), ("", "Mañana"))
        tf.apply([item(th=th)], {**tf.new_filters(), "orden": "recientes"})


if __name__ == "__main__":
    unittest.main()
