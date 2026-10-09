# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Genera assets/icon.png e icon.ico (se ejecuta una vez; los archivos ya vienen incluidos)."""
import os
from PIL import Image, ImageDraw

S = 512
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((16, 16, S - 16, S - 16), 96, fill=(28, 31, 38, 255))
pad, gap = 76, 22
cell = (S - 2 * pad - 3 * gap) // 4
for r in range(4):
    for c in range(4):
        if (r, c) == (2, 3):                 # ocupada por la tecla + alta
            continue
        x, y = pad + c * (cell + gap), pad + r * (cell + gap)
        y2 = y + cell
        if (r, c) == (1, 3):                 # tecla + alta
            y2 = y + 2 * cell + gap
        col = (242, 163, 58, 255) if (r, c) in ((0, 0), (1, 3)) else (220, 222, 228, 255)
        d.rounded_rectangle((x, y, x + cell, y2), 18, fill=col)
out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
img.save(os.path.join(out, "icon.png"))
img.save(os.path.join(out, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("ok")

# Imágenes del instalador de Windows (Inno Setup usa BMP)
icon = Image.open(os.path.join(out, "icon.png")).convert("RGBA")
big = Image.new("RGB", (164, 314), (20, 22, 27))
ic = icon.resize((120, 120), Image.LANCZOS)
big.paste(ic, (22, 70), ic)
d = ImageDraw.Draw(big)
d.text((22, 210), "Numpad", fill=(233, 233, 236))
d.text((22, 226), "Macros", fill=(242, 163, 58))
big.save(os.path.join(out, "wizard.bmp"))
small = Image.new("RGB", (58, 58), (255, 255, 255))
ic = icon.resize((54, 54), Image.LANCZOS)
small.paste(ic, (2, 2), ic)
small.save(os.path.join(out, "wizard_small.bmp"))
