# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Pruebas del formato de temas .npt (cifrado, firma, validación)."""
import io
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from npm import npt  # noqa: E402

TEMAS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "temas", "temas.json")


def base_colors():
    with open(TEMAS, encoding="utf-8") as f:
        c = dict(json.load(f)["escritorio_y_celular"][0]["colores"])
    c.setdefault("on_ok", "#06210f")
    return c


def png(w, h, color=(200, 80, 40)):
    try:
        from PIL import Image
    except ImportError:
        raise unittest.SkipTest("Pillow no está instalado")
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


def theme(**kw):
    d = dict(name="Neón Tokio", author="@kaori", colors=base_colors(), description="Prueba")
    d.update(kw)
    return npt.Theme(**d)


class FormatTest(unittest.TestCase):
    def setUp(self):
        self.key = npt.SigningKey.generate("autor", "@kaori")

    def test_roundtrip(self):
        t = theme(alpha={"panel": 85, "key": 80}, window={"opacidad": 90, "sin_usar": 70})
        res = npt.read(npt.write(t, self.key))
        self.assertEqual(res.theme.name, "Neón Tokio")
        self.assertEqual(res.theme.colors["acc"], t.colors["acc"].lower())
        self.assertEqual(res.theme.alpha, {"key": 80, "panel": 85})
        self.assertEqual(res.theme.window, {"opacidad": 90, "sin_usar": 70})
        self.assertTrue(res.theme.transparency)
        self.assertEqual(res.author_key, self.key.public_hex)
        self.assertFalse(res.official)
        self.assertEqual(res.label, "Comunidad · @kaori")

    def test_opaque_theme_has_no_transparency(self):
        res = npt.read(npt.write(theme(alpha={"panel": 100}), self.key))
        self.assertFalse(res.theme.transparency)
        self.assertEqual(res.theme.alpha, {})

    def test_unreadable_in_text_editor(self):
        data = npt.write(theme(name="Tema Secreto Visible"), self.key)
        self.assertNotIn(b"Tema Secreto", data)
        self.assertNotIn(b"colores", data)
        self.assertNotIn(b"#14161b", data)
        self.assertTrue(data.startswith(b"NPT\x02"))

    def test_any_changed_byte_is_rejected(self):
        data = bytearray(npt.write(theme(), self.key))
        for pos in (6, 40, len(data) // 2, len(data) - 70, len(data) - 1):
            bad = bytearray(data)
            bad[pos] ^= 0x01
            with self.assertRaises(npt.NptError) as cm:
                npt.read(bytes(bad))
            self.assertEqual(cm.exception.code, "danado", pos)

    def test_cut_file_is_rejected(self):
        data = npt.write(theme(), self.key)
        with self.assertRaises(npt.NptError) as cm:
            npt.read(data[:-10])
        self.assertEqual(cm.exception.code, "danado")

    def test_not_a_theme(self):
        with self.assertRaises(npt.NptError) as cm:
            npt.read(b"hola, esto es texto")
        self.assertEqual(cm.exception.code, "formato")

    def test_newer_version(self):
        data = bytearray(npt.write(theme(), self.key))
        data[3] = 9
        with self.assertRaises(npt.NptError) as cm:
            npt.read(bytes(data))
        self.assertEqual(cm.exception.code, "version")

    def test_official_key(self):
        official = npt.SigningKey.generate("oficial", "OkumaWsX")
        with mock.patch.object(npt, "OFFICIAL_KEY", official.public_hex):
            res = npt.read(npt.write(theme(author="OkumaWsX"), official))
            self.assertTrue(res.official)
            self.assertFalse(res.reserved_name)
            self.assertEqual(res.label, "Oficial · OkumaWsX")
            self.assertTrue(official.is_official)
            # la misma clave de antes sigue siendo de la comunidad
            self.assertFalse(npt.read(npt.write(theme(), self.key)).official)

    def test_reserved_name_without_official_key(self):
        for name in ("OkumaWsX", "okuma wsx", "0KUMA_WSX", "x.OkumaWsX.x", "Okumа WsX", "Okuma_Ws×", "ＯｋｕｍａＷｓＸ"):
            res = npt.read(npt.write(theme(author=name), self.key))
            self.assertFalse(res.official)
            self.assertTrue(res.reserved_name, name)
        self.assertFalse(npt.is_reserved_name("@kaori"))
        self.assertFalse(npt.is_reserved_name(""))

    def test_unpack_gives_numpad_macros_dict(self):
        imgs = {"logo": png(64, 64)}
        t, official = npt.unpack(npt.write(theme(alpha={"key": 70}, window={"opacidad": 80, "sin_usar": 60},
                                                 images=imgs), self.key), images=True)
        self.assertFalse(official)
        self.assertEqual(t["author"], "@kaori")
        self.assertEqual(t["alpha"], {"window": 0.8, "idle": 0.6})
        self.assertEqual(t["layer_alpha"], {"key": 70})
        self.assertEqual(t["images"], imgs)
        self.assertEqual(t["author_key"], self.key.public_hex)
        self.assertEqual(len(t["colors"]), 22)
        self.assertEqual(t["image_slots"], ["logo"])
        self.assertNotIn("images", npt.unpack(npt.write(theme(images=imgs), self.key))[0])
        t2, _ = npt.unpack(npt.write(theme(), self.key))
        self.assertNotIn("alpha", t2)                         # opaco: no «admite transparencia»

    def test_reads_version_1(self):
        v1 = npt.pack({"name": "Viejo", "author": "Ana", "colors": base_colors(),
                       "alpha": {"window": 0.9, "idle": 0.7}})
        res = npt.read(v1)
        self.assertEqual((res.format, res.theme.name, res.theme.author), (1, "Viejo", "Ana"))
        self.assertEqual(res.theme.window, {"opacidad": 90, "sin_usar": 70})
        self.assertEqual(res.author_key, "")
        self.assertFalse(res.official)

    def test_weak_key_forgery_is_rejected(self):
        import zlib
        plain = zlib.compress(npt._pack_content(theme(name="Falso")))
        for weak in ("01" + "00" * 31, "00" * 32, "ec" + "ff" * 30 + "7f",
                     "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a"):
            pub = bytes.fromhex(weak)
            head = b"NPT\x02\x00"
            nonce = b"\1" * 12
            body = head + pub + nonce + npt._aes().encrypt(nonce, plain, head + pub)
            forged = body + pub + b"\0" * 32                 # firma «universal» con clave débil
            with self.assertRaises(npt.NptError) as cm:
                npt.read(forged)
            self.assertEqual(cm.exception.code, "danado")
        self.assertFalse(npt._weak_key(self.key.public_bytes))
        for _ in range(20):
            self.assertFalse(npt._weak_key(npt.SigningKey.generate().public_bytes))

    def test_reserved_name_hidden_in_numpad_macros(self):
        t, _ = npt.unpack(npt.write(theme(author="OkumaWsX"), self.key))
        self.assertEqual(t["author"], "Anónimo")
        self.assertTrue(t["reserved_name"])
        v1, _ = npt.unpack(npt.pack({"name": "x", "author": "okuma wsx", "colors": base_colors()}))
        self.assertEqual(v1["author"], "Desconocido")

    def test_anonymous_label(self):
        res = npt.read(npt.write(theme(author=""), self.key))
        self.assertEqual(res.label, "Comunidad · Anónimo")

    def test_invalid_themes(self):
        cases = [
            dict(name=""),
            dict(name="x" * 33),
            dict(kind="gris"),
            dict(colors={**base_colors(), "acc": "naranja"}),
            dict(colors={k: v for k, v in base_colors().items() if k != "warn"}),
            dict(alpha={"bg": 50}),
            dict(alpha={"panel": 120}),
            dict(window={"opacidad": 30, "sin_usar": 100}),
        ]
        for kw in cases:
            with self.assertRaises(npt.NptError, msg=kw) as cm:
                npt.write(theme(**kw), self.key)
            self.assertEqual(cm.exception.code, "contenido")

    def test_images_roundtrip(self):
        imgs = {"banner": png(1200, 120), "logo": png(64, 64, (10, 200, 120))}
        res = npt.read(npt.write(theme(images=imgs), self.key))
        self.assertEqual(res.theme.images, imgs)
        self.assertEqual(npt.image_size(imgs["banner"]), (1200, 120))

    def test_image_too_big_or_wrong(self):
        with self.assertRaises(npt.NptError):
            npt.write(theme(images={"logo": png(128, 128)}), self.key)
        with self.assertRaises(npt.NptError):
            npt.write(theme(images={"fondo": png(10, 10)}), self.key)
        with self.assertRaises(npt.NptError):
            npt.write(theme(images={"logo": b"GIF89a" + b"\0" * 30}), self.key)

    def test_size_limit(self):
        noise = os.urandom(npt.MAX_FILE)
        with self.assertRaises(npt.NptError) as cm:
            npt.read(noise)
        self.assertIn(cm.exception.code, ("grande", "formato"))
        with mock.patch.object(npt, "MAX_FILE", 300):
            with self.assertRaises(npt.NptError) as cm:
                npt.write(theme(), self.key)
            self.assertEqual(cm.exception.code, "grande")


class KeyTest(unittest.TestCase):
    def test_save_and_load(self):
        k = npt.SigningKey.generate("autor", "@kaori")
        k2 = npt.SigningKey.from_file(k.to_file())
        self.assertEqual(k.public_hex, k2.public_hex)
        self.assertEqual(k2.name, "@kaori")
        self.assertEqual(k2.kind, "autor")

    def test_password(self):
        k = npt.SigningKey.generate("oficial", "OkumaWsX")
        raw = k.to_file("clave segura")
        self.assertTrue(npt.SigningKey.info(raw)["protegida"])
        self.assertNotIn(b"clave segura", raw)
        with self.assertRaises(npt.KeyFileError) as cm:
            npt.SigningKey.from_file(raw)
        self.assertEqual(cm.exception.code, "password")
        with self.assertRaises(npt.KeyFileError) as cm:
            npt.SigningKey.from_file(raw, "otra")
        self.assertEqual(cm.exception.code, "wrong")
        self.assertEqual(npt.SigningKey.from_file(raw, "clave segura").public_hex, k.public_hex)

    def test_bad_file(self):
        with self.assertRaises(npt.KeyFileError):
            npt.SigningKey.from_file(b"no es una clave")

    def test_fingerprint(self):
        fp = npt.fingerprint("00" * 32)
        self.assertRegex(fp, r"^([0-9A-F]{4} ){3}[0-9A-F]{4} · ([0-9A-F]{4} ){3}[0-9A-F]{4}$")


if __name__ == "__main__":
    unittest.main()
