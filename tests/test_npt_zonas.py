# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Temas del nuevo Estudio: 9 espacios de imagen, GIF, degradado de fondo y secciones."""
import io
import json
import os
import sys
import unittest
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from npm import npt  # noqa: E402
from tests.test_npt import png, theme  # noqa: E402


def gif(w, h):
    try:
        from PIL import Image
    except ImportError:
        raise unittest.SkipTest("Pillow no está instalado")
    frames = [Image.new("P", (w, h), i) for i in (1, 2)]
    buf = io.BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], duration=100, loop=0)
    return buf.getvalue()


GRAD = {"tipo": "degradado", "colores": [["#14161b", 0], ["#3a2c14", 55], ["#33294a", 100]], "desde": "c"}
SECS = {"head": {"fondo": 70, "contenido": 100, "realce": True}, "foot": {"fondo": 60, "contenido": 90}}


class ZonasTest(unittest.TestCase):
    def setUp(self):
        self.key = npt.SigningKey.generate("autor", "@kaori")

    def test_nueve_espacios_degradado_y_secciones(self):
        imgs = {s: png(min(w, 40), min(h, 20)) for s, (w, h) in npt.IMAGE_SLOTS.items()}
        imgs["headmid"] = gif(40, 20)
        imgs["foot"] = gif(30, 20)
        t = theme(images=imgs, background=GRAD, sections=SECS)
        d, official = npt.unpack(npt.write(t, self.key), images=True)
        self.assertFalse(official)
        self.assertEqual(sorted(d["images"]), sorted(npt.IMAGE_SLOTS))
        self.assertEqual(npt.image_format(d["images"]["headmid"]), "gif")
        self.assertEqual(d["background"], GRAD)
        self.assertEqual(d["sections"]["head"], SECS["head"])
        self.assertIn("alpha", d)                      # secciones transparentes → «Admite»

    def test_gif_solo_en_espacios_libres(self):
        with self.assertRaises(npt.NptError):
            npt.write(theme(images={"banner": gif(40, 20)}), self.key)

    def test_degradado_invalido(self):
        for bad in ({"tipo": "degradado", "colores": [["#000000", 0]], "desde": "c"},
                    {"tipo": "degradado", "colores": [["#000000", 0], ["#ffffff", 140]], "desde": "c"},
                    {"tipo": "degradado", "colores": [["#000000", 0], ["#ffffff", 100]], "desde": "x"}):
            with self.assertRaises(npt.NptError):
                npt.write(theme(background=bad), self.key)

    def test_tema_de_un_estudio_mas_nuevo_se_abre(self):
        """Espacios, secciones o tipos de fondo que esta versión no conoce se ignoran al leer."""
        t = theme(images={"logo": png(20, 20)})
        raw = npt._pack_content(t)
        n = int.from_bytes(raw[4:8], "big")
        meta = json.loads(raw[8:8 + n])
        blob = raw[8 + n:]
        extra = png(10, 10)
        meta["imagenes"]["espacio_futuro"] = {"inicio": len(blob), "largo": len(extra), "formato": "png"}
        meta["secciones"] = {"futura": {"fondo": 50}, "head": {"fondo": 80}}
        meta["fondo"] = {"tipo": "imagen_animada"}
        meta["algo_nuevo"] = {"x": 1}
        js = json.dumps(meta).encode()
        content = b"NPTC" + len(js).to_bytes(4, "big") + js + blob + extra
        data = _sign_raw(content, self.key)
        d, _ = npt.unpack(data, images=True)
        self.assertEqual(sorted(d["images"]), ["logo"])
        self.assertEqual(d["sections"], {"head": {"fondo": 80}})
        self.assertEqual(d["background"], {})


def _sign_raw(content: bytes, key) -> bytes:
    """Como npt.write pero con un contenido ya armado (simula un Estudio más nuevo)."""
    real = npt._pack_content
    npt._pack_content = lambda _t: content
    try:
        orig_validate = npt.validate
        npt.validate = lambda *a, **k: None
        try:
            return npt.write(theme(), key)
        finally:
            npt.validate = orig_validate
    finally:
        npt._pack_content = real


if __name__ == "__main__":
    unittest.main()
