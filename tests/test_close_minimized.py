import os
import tempfile
import unittest


class CloseMinimizedTest(unittest.TestCase):
    """Cerrar desde la barra de tareas con la ventana minimizada debe mostrarla con el aviso."""

    def test_close_while_minimized(self):
        try:
            import tkinter as tk
            root = tk.Tk()
        except Exception:
            self.skipTest("sin pantalla")
        old = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()
        try:
            from npm import gui
            app = gui.App(root)
            app.tray = app.tray or type("Tray", (), {"stop": lambda self: None})()
            app.cfg.setdefault("ui", {})["close"] = "ask"
            root.update()
            root.iconify()
            root.update()
            app._on_close()
            root.update()
            self.assertNotEqual(root.state(), "iconic")
            self.assertTrue(app.close_win.winfo_exists())
            self.assertTrue(app.close_win.winfo_viewable())
            app._on_close()                     # otra vez: no duplica el aviso
            root.update()
            self.assertEqual(len([w for w in root.winfo_children() if isinstance(w, tk.Toplevel)
                                  and w.title() == "Cerrar Numpad Macros"]), 1)
            app.close_win.grab_release()
            app.close_win.destroy()
            app._quit()
        finally:
            from npm import aa
            aa._cache.clear()                   # sus imágenes son de esta ventana, ya cerrada
            if old is None:
                os.environ.pop("XDG_CONFIG_HOME", None)
            else:
                os.environ["XDG_CONFIG_HOME"] = old
