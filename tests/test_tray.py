import unittest

try:
    from PIL import Image
except Exception:            # pragma: no cover
    Image = None

from npm import tray_sni


@unittest.skipIf(Image is None, "Pillow no está")
class SniMenuTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.label = "Pausar"
        self.tray = tray_sni.SniTray(
            "NumpadMacros", "Numpad Macros", Image.new("RGBA", (64, 64), (242, 163, 58, 255)),
            lambda: [("Mostrar ventana", lambda: self.calls.append("show")),
                     (self.label, lambda: self.calls.append("toggle")), None,
                     ("Salir", lambda: self.calls.append("quit"))])

    def test_pixmaps_argb(self):
        w, h, data = self.tray.pix[0]
        self.assertEqual(len(data), w * h * 4)
        self.assertEqual(data[:4], bytes((255, 242, 163, 58)))      # A R G B

    def test_layout_and_click(self):
        rev, items = 0, self.tray._layout()[2]
        self.assertEqual([v[1][0] for v in items], [1, 2, 3, 4])
        self.assertEqual(items[2][1][1]["type"], ("s", "separator"))
        self.assertEqual(items[1][1][1]["label"], ("s", "Pausar"))
        self.tray._clicked(4, "clicked")
        self.tray._clicked(2, "hovered")
        self.assertEqual(self.calls, ["quit"])
        self.label = "Reanudar"
        self.assertEqual(self.tray._layout()[2][1][1][1]["label"], ("s", "Reanudar"))
        del rev

    def test_no_session_bus(self):
        import os
        old = {k: os.environ.pop(k, None) for k in ("DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR")}
        try:
            self.assertFalse(self.tray.start())
        finally:
            for k, v in old.items():
                if v is not None:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
