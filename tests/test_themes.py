# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Temas: archivos .npt (cifrado, integridad, firma) y temas incluidos."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from npm import npt, theme, themes  # noqa: E402


def lum(h):
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    x, y = sorted([lum(a), lum(b)], reverse=True)
    return (x + 0.05) / (y + 0.05)


class NptTest(unittest.TestCase):
    def setUp(self):
        self.t = themes.builtin()[3]

    def test_roundtrip_unsigned(self):
        data = npt.pack(self.t)
        self.assertEqual(data[:3], b"NPT")
        self.assertNotIn(b"panel", data)                       # no se lee con un editor de texto
        self.assertNotIn(self.t["name"].encode(), data)
        t, official = npt.unpack(data)
        self.assertEqual((t["name"], t["colors"]), (self.t["name"], self.t["colors"]))
        self.assertFalse(official)

    def test_damaged_file_is_rejected(self):
        data = bytearray(npt.pack(self.t))
        for pos in (25, len(data) - 3):
            bad = bytearray(data)
            bad[pos] ^= 0x01
            with self.assertRaises(npt.NptError):
                npt.unpack(bytes(bad))
        with self.assertRaises(npt.NptError):
            npt.unpack(bytes(data[:-5]))                       # incompleto
        with self.assertRaises(npt.NptError):
            npt.unpack(b"hola, no soy un tema")

    def test_signed_official(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization as ser
        k = Ed25519PrivateKey.generate()
        pub = k.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw).hex()
        with mock.patch.object(npt, "OFFICIAL_KEY", pub):
            t, official = npt.unpack(npt.pack(self.t, k))
            self.assertTrue(official)
            # firmado con otra clave: se rechaza (nadie puede hacerse pasar por el creador)
            other = Ed25519PrivateKey.generate()
            with self.assertRaises(npt.NptError):
                npt.unpack(npt.pack(self.t, other))

    def test_missing_colors(self):
        with self.assertRaises(npt.NptError):
            npt.pack({"name": "x", "colors": {"bg": "#000000"}})
        with self.assertRaises(npt.NptError):
            npt.pack({"name": "", "colors": self.t["colors"]})

    def test_alpha_clamped(self):
        t = dict(self.t, alpha={"window": 0.1, "idle": 2})
        back, _ = npt.unpack(npt.pack(t))
        self.assertEqual(back["alpha"], {"window": 0.5, "idle": 1.0})
        self.assertTrue(themes.supports_alpha(back))
        self.assertFalse(any(themes.supports_alpha(x) for x in themes.builtin()))

    def test_install_export_and_current(self):
        d = tempfile.mkdtemp()
        with mock.patch.object(themes, "themes_dir", lambda: os.path.join(d, "Temas")):
            src = os.path.join(d, "x.npt")
            themes.export(dict(self.t, name="Neón Tokio"), src)
            t = themes.install(src)
            self.assertEqual(t["file"], "Neón Tokio.npt")
            self.assertFalse(t["official"])
            cfg = {"theme": {"name": "Neón Tokio", "file": "Neón Tokio.npt"}}
            self.assertEqual(themes.current(cfg)["name"], "Neón Tokio")
            with open(os.path.join(d, "Temas", "roto.npt"), "wb") as f:
                f.write(b"NPT\x01\x00" + b"0" * 30)
            self.assertEqual([x["name"] for x in themes.imported()], ["Neón Tokio"])   # el dañado se salta
            themes.remove(t)
            self.assertEqual(themes.current(cfg)["name"], "Original")


class BuiltinThemesTest(unittest.TestCase):
    def test_same_as_docs(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, "docs", "temas", "temas.json"), encoding="utf-8") as f:
            doc = json.load(f)["escritorio_y_celular"]
        self.assertEqual([t["nombre"] for t in doc], [n for n, _ in themes.BUILTIN])
        self.assertEqual(len(themes.BUILTIN), 11)

    def test_text_is_readable(self):
        for t in themes.builtin():
            c = t["colors"]
            for fg, bg, need in (("text", "bg", 7), ("text", "panel", 7), ("text", "panel2", 7),
                                 ("muted", "panel", 4.5), ("on_acc", "acc", 4.5), ("on_ok", "ok", 4.5),
                                 ("key_set_text", "key_set", 4.5), ("key_global_text", "key_global", 4.5),
                                 ("text", "acc_dim", 4.5)):
                self.assertGreaterEqual(contrast(c[fg], c[bg]), need, f"{t['name']}: {fg} sobre {bg}")

    def test_apply_theme(self):
        try:
            theme.apply_theme(themes.builtin()[7]["colors"])           # Claro
            self.assertEqual(theme.C["bg"], "#eef0f4")
            self.assertEqual(theme.C["on_accent"], "#ffffff")
            theme.apply_theme(None)
            self.assertEqual(theme.C, theme.ORIGINAL)
        finally:
            theme.apply_theme(None)


if __name__ == "__main__":
    unittest.main()
