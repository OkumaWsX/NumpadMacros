# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Imágenes pequeñas para los controles (casillas, opciones, deslizador, barra).

Se dibujan en el momento, con suavizado y transparencia, en Python puro
(sin Pillow: en macOS no se incluye) y salen como PNG para tk.PhotoImage.
"""
import base64
import math
import struct
import zlib

SS = 4          # muestras por lado (suavizado 4 × 4)


def _png(w, h, rows):
    """rows: lista de bytearrays RGBA de largo w*4 → PNG en base64."""
    raw = b"".join(b"\x00" + bytes(r) for r in rows)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    return base64.b64encode(png)


def _rgb(hexcol):
    return tuple(int(hexcol[i:i + 2], 16) for i in (1, 3, 5))


# ---------------------------------------------------------------- formas (distancia con signo)
def rrect(x0, y0, x1, y1, r):
    cx, cy, hw, hh = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2

    def d(x, y):
        qx, qy = abs(x - cx) - hw + r, abs(y - cy) - hh + r
        return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r
    return d


def circle(cx, cy, r):
    return lambda x, y: math.hypot(x - cx, y - cy) - r


def ring(shape, width):
    return lambda x, y: abs(shape(x, y) + width / 2) - width / 2


def polyline(pts, width):
    segs = list(zip(pts, pts[1:]))

    def d(x, y):
        best = 1e9
        for (ax, ay), (bx, by) in segs:
            vx, vy = bx - ax, by - ay
            t = max(0.0, min(1.0, ((x - ax) * vx + (y - ay) * vy) / (vx * vx + vy * vy)))
            best = min(best, math.hypot(x - ax - t * vx, y - ay - t * vy))
        return best - width / 2
    return d


def draw(w, h, layers):
    """layers: [(forma, '#rrggbb', opacidad)] de abajo hacia arriba → PNG base64."""
    cols = [(_rgb(c), a) for _, c, a in layers]
    rows = []
    step = 1 / SS
    offs = [(i + .5) * step for i in range(SS)]
    for py in range(h):
        row = bytearray(w * 4)
        for px in range(w):
            r = g = b = a = 0.0
            for (shape, _c, _a), (rgb, alpha) in zip(layers, cols):
                cov = 0
                for oy in offs:
                    for ox in offs:
                        if shape(px + ox, py + oy) <= 0:
                            cov += 1
                if not cov:
                    continue
                sa = alpha * cov / (SS * SS)
                na = sa + a * (1 - sa)                     # «over» con alfa
                if na > 0:
                    r = (rgb[0] * sa + r * a * (1 - sa)) / na
                    g = (rgb[1] * sa + g * a * (1 - sa)) / na
                    b = (rgb[2] * sa + b * a * (1 - sa)) / na
                a = na
            i = px * 4
            row[i:i + 4] = bytes((round(r), round(g), round(b), round(a * 255)))
        rows.append(row)
    return _png(w, h, rows)


# ---------------------------------------------------------------- controles
def checkbox(size, on, C, hover=False, disabled=False):
    s = size
    box = rrect(1, 1, s - 1, s - 1, s * .24)
    if on:
        col = C["muted"] if disabled else (C["accent_hover"] if hover else C["accent"])
        mark = polyline([(s * .27, s * .52), (s * .43, s * .68), (s * .74, s * .34)], max(1.6, s * .13))
        return draw(s, s, [(box, col, 1.0), (mark, C["on_accent"], 1.0)])
    edge = C["line"] if disabled else (C["text"] if hover else C["muted"])
    return draw(s, s, [(box, C["bg"], .35), (ring(box, max(1.3, s * .09)), edge, 1.0)])


def radio(size, on, C, hover=False, disabled=False):
    s = size
    c = circle(s / 2, s / 2, s / 2 - 1)
    if on:
        col = C["muted"] if disabled else (C["accent_hover"] if hover else C["accent"])
        return draw(s, s, [(ring(c, max(1.6, s * .12)), col, 1.0), (circle(s / 2, s / 2, s * .23), col, 1.0)])
    edge = C["line"] if disabled else (C["text"] if hover else C["muted"])
    return draw(s, s, [(c, C["bg"], .35), (ring(c, max(1.3, s * .09)), edge, 1.0)])


def knob(size, C, hover=False):
    s = size
    c = circle(s / 2, s / 2, s / 2 - 1)
    return draw(s, s, [(c, C["accent_hover"] if hover else C["accent"], 1.0),
                       (circle(s / 2, s / 2, s * .17), C["on_accent"], .9)])


def track(width, height, thick, C):
    """Riel del deslizador (se estira a lo ancho)."""
    y0 = (height - thick) / 2
    return draw(width, height, [(rrect(0.5, y0, width - .5, y0 + thick, thick / 2), C["line"], 1.0)])


def pill(width, height, color):
    """Barra de desplazamiento redondeada (se estira a lo alto)."""
    return draw(width, height, [(rrect(1.5, 1, width - 1.5, height - 1, (width - 3) / 2), color, 1.0)])
