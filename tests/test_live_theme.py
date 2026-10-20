import os
import tempfile
import unittest


class LiveThemeTest(unittest.TestCase):
    def test_switch_without_restart(self):
        try:
            import tkinter as tk
            root = tk.Tk()
        except Exception:
            self.skipTest("sin pantalla")
        old = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()
        try:
            from npm import gui, themes
            from npm.theme import C
            app = gui.App(root)
            claro = [t for t in themes.all_themes() if t["name"] == "Claro"][0]
            app.nb.select(2)
            app.apply_theme_live(claro)
            root.update()
            self.assertEqual(C["bg"], claro["colors"]["bg"])
            self.assertEqual(app.nb.index("current"), 2)
            self.assertIsNone(app.relaunch)
            app._quit()
        finally:
            if old is None:
                os.environ.pop("XDG_CONFIG_HOME", None)
            else:
                os.environ["XDG_CONFIG_HOME"] = old
            from npm.theme import apply_theme
            apply_theme(None)
