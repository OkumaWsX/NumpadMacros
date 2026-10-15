# SPDX-License-Identifier: LGPL-3.0-or-later
"""Pruebas de tools/release.py (capturas por versión en las notas de la Release)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
import release  # noqa: E402


class CapturasTest(unittest.TestCase):
    def test_section_pinned_to_ref(self):
        sec = release.captures_section("3.3.0", "v3.3.0")
        self.assertIn("/raw/v3.3.0/docs/capturas/3.3.0/principal.png", sec)
        self.assertTrue(sec.startswith(release.CAPS_START) and sec.endswith(release.CAPS_END))
        self.assertEqual(release.captures_section("0.0.1", "v0.0.1"), "")     # sin carpeta: sin capturas

    def test_replace_keeps_one_section(self):
        body = "### Añadido\n- algo\n\n### Descargas\n| x |\n"
        once = release.put_captures(body, release.captures_section("3.3.0", "aaa"))
        twice = release.put_captures(once, release.captures_section("3.3.0", "bbb"))
        self.assertEqual(twice.count(release.CAPS_START), 1)
        self.assertIn("/raw/bbb/", twice)
        self.assertNotIn("/raw/aaa/", twice)
        self.assertLess(twice.index(release.CAPS_START), twice.index("### Descargas"))


if __name__ == "__main__":
    unittest.main()
