# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Formas suavizadas (sin «dientes de sierra») para los dibujos de la ventana.

El lienzo de Tk dibuja círculos, esquinas redondeadas y líneas en diagonal sin
suavizado. Aquí se dibujan con Pillow a 4× de tamaño y se reducen con un
filtro de calidad, como hacen los navegadores; el resultado es una imagen con
transparencia que se pone en el lienzo. Las imágenes se guardan en caché.

Si Pillow no está (no debería pasar en la app empaquetada) se usan las formas
de ui_images en Python puro para lo pequeño, y las funciones devuelven None
para lo grande (el que llama dibuja como antes).
"""
import base64
import io
import math
import tkinter as tk

try:
    from PIL import Image, ImageDraw
    HAVE_PIL = True
except Exception:                       # pragma: no cover
    HAVE_PIL = False

SS = 4                                  # sobre-muestreo
_cache: dict = {}
_MAX = 600


def _photo(master, img):
    buf = io.BytesIO()
    img.save(buf, "PNG", compress_level=1)
    return tk.PhotoImage(master=master, data=base64.b64encode(buf.getvalue()))


def _render(master, key, w, h, paint):
    """Dibuja con `paint(draw, s)` en un lienzo de (w·SS × h·SS) y lo reduce."""
    if not HAVE_PIL or w < 1 or h < 1:
        return None
    full = key
    img = _cache.get(full)
    if img is not None:
        return img
    big = Image.new("RGBA", (int(w * SS), int(h * SS)), (0, 0, 0, 0))
    paint(ImageDraw.Draw(big), SS)
    small = big.resize((int(w), int(h)), Image.LANCZOS)
    img = _photo(master, small)
    if len(_cache) > _MAX:
        _cache.clear()
    _cache[full] = img
    return img


def _rgba(col, alpha=1.0):
    col = col.lstrip("#")
    return (int(col[0:2], 16), int(col[2:4], 16), int(col[4:6], 16), int(round(alpha * 255)))


# ---------------------------------------------------------------- formas
def key_shape(master, w, h, r, fill, line, lw, alpha=1.0):
    """Tecla: rectángulo redondeado con borde (borde = 0 → sin borde). `alpha` = opacidad del relleno
    (deja ver la imagen del tema que está detrás de las teclas)."""
    def paint(d, s):
        W, H = w * s, h * s
        if alpha >= 1:
            d.rounded_rectangle((0, 0, W - 1, H - 1), radius=r * s, fill=_rgba(line if lw else fill))
            if lw:
                k = lw * s
                d.rounded_rectangle((k, k, W - 1 - k, H - 1 - k), radius=max(1, (r - lw) * s), fill=_rgba(fill))
            return
        if lw:
            d.rounded_rectangle((0, 0, W - 1, H - 1), radius=r * s, outline=_rgba(line), width=int(lw * s))
            k = lw * s
            d.rounded_rectangle((k, k, W - 1 - k, H - 1 - k), radius=max(1, (r - lw) * s), fill=_rgba(fill, alpha))
        else:
            d.rounded_rectangle((0, 0, W - 1, H - 1), radius=r * s, fill=_rgba(fill, alpha))
    return _render(master, ("key", w, h, r, fill, line, lw, round(alpha, 2)), w, h, paint)


def badge(master, size, fill, radius=None):
    """Cuadrito redondeado (marca «G»)."""
    rad = size * .28 if radius is None else radius

    def paint(d, s):
        d.rounded_rectangle((0, 0, size * s - 1, size * s - 1), radius=rad * s, fill=_rgba(fill))
    return _render(master, ("badge", size, fill, rad), size, size, paint)


def dot(master, size, fill, outline=None, width=1.0):
    """Círculo lleno, con borde opcional."""
    def paint(d, s):
        S = size * s
        if outline:
            d.ellipse((0, 0, S - 1, S - 1), fill=_rgba(outline))
            k = width * s
            d.ellipse((k, k, S - 1 - k, S - 1 - k), fill=_rgba(fill))
        else:
            d.ellipse((0, 0, S - 1, S - 1), fill=_rgba(fill))
    return _render(master, ("dot", size, fill, outline, width), size, size, paint)


def swatch(master, size, color, selected, ring, mark, empty_col=None):
    """Muestra de color del editor de teclas.
    color None = «sin color» (círculo punteado con ✕). `ring` = color del anillo de selección,
    `mark` = color del ✓."""
    def paint(d, s):
        S = size * s
        if selected:
            w = 2 * s
            d.ellipse((0, 0, S - 1, S - 1), outline=_rgba(ring), width=int(w))
        inset = size * .17 * s
        box = (inset, inset, S - 1 - inset, S - 1 - inset)
        if color is None:
            col = _rgba(empty_col)
            n, w = 12, 2 * s
            for i in range(n):              # anillo punteado
                a0 = i * 360 / n
                d.arc(box, a0, a0 + 360 / n * .55, fill=col, width=int(w))
            c, k = S / 2, S * .12
            d.line((c - k, c - k, c + k, c + k), fill=col, width=int(1.6 * s))
            d.line((c - k, c + k, c + k, c - k), fill=col, width=int(1.6 * s))
        else:
            d.ellipse(box, fill=_rgba(color))
            if selected:
                c = S / 2
                pts = [(c - S * .15, c + S * .01), (c - S * .04, c + S * .12), (c + S * .16, c - S * .10)]
                d.line(pts, fill=_rgba(mark), width=int(2.2 * s), joint="curve")
                for x, y in (pts[0], pts[-1]):
                    rr = 1.1 * s
                    d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=_rgba(mark))
    return _render(master, ("swatch", size, color, selected, ring, mark, empty_col), size, size, paint)


def curve(master, w, h, segments, dots=()):
    """Líneas suavizadas: segments = [(puntos, color, ancho, guiones o None)], dots = [(x, y, r, color)]."""
    def paint(d, s):
        for pts, col, width, dash in segments:
            P = [(x * s, y * s) for x, y in pts]
            if not dash:
                d.line(P, fill=_rgba(col), width=max(1, int(width * s)), joint="curve")
                continue
            on, off = dash[0] * s, dash[1] * s
            for (x0, y0), (x1, y1) in zip(P, P[1:]):
                L = math.hypot(x1 - x0, y1 - y0)
                t = 0.0
                while t < L:
                    t1 = min(L, t + on)
                    d.line((x0 + (x1 - x0) * t / L, y0 + (y1 - y0) * t / L,
                            x0 + (x1 - x0) * t1 / L, y0 + (y1 - y0) * t1 / L),
                           fill=_rgba(col), width=max(1, int(width * s)))
                    t = t1 + off
        for x, y, r, col in dots:
            d.ellipse((x * s - r * s, y * s - r * s, x * s + r * s, y * s + r * s), fill=_rgba(col))
    key = ("curve", w, h, tuple((tuple(p), c, wd, dash) for p, c, wd, dash in segments), tuple(dots))
    return _render(master, key, w, h, paint)


# ---------------------------------------------------------------- selector de sonidos
def rounded_image(master, key, pil_img, size, radius):
    """Imagen PIL (cuadrada) reducida a `size` con esquinas redondeadas suavizadas."""
    if not HAVE_PIL or pil_img is None or size < 4:
        return None
    full = ("rimg", key, size, radius)
    img = _cache.get(full)
    if img is not None:
        return img
    im = pil_img.convert("RGB").resize((size, size), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size * SS, size * SS), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size * SS - 1, size * SS - 1), radius=radius * SS, fill=255)
    im.putalpha(mask.resize((size, size), Image.LANCZOS))
    img = _photo(master, im)
    if len(_cache) > _MAX:
        _cache.clear()
    _cache[full] = img
    return img


def check_badge(master, size, fill, mark):
    """Círculo con ✓ (elemento elegido)."""
    def paint(d, s):
        S = size * s
        d.ellipse((0, 0, S - 1, S - 1), fill=_rgba(fill))
        pts = [(S * .28, S * .53), (S * .44, S * .68), (S * .73, S * .36)]
        d.line(pts, fill=_rgba(mark), width=int(S * .13), joint="curve")
        for x, y in (pts[0], pts[-1]):
            r = S * .065
            d.ellipse((x - r, y - r, x + r, y + r), fill=_rgba(mark))
    return _render(master, ("check", size, fill, mark), size, size, paint)


def play_badge(master, size, bg, fg, playing, alpha=.82):
    """Botón redondo de escuchar (▶) o detener (❚❚)."""
    def paint(d, s):
        S = size * s
        d.ellipse((0, 0, S - 1, S - 1), fill=_rgba(bg, 1.0 if playing else alpha))
        if playing:
            w, h = S * .12, S * .38
            for x in (S * .36, S * .52):
                d.rounded_rectangle((x, S / 2 - h / 2, x + w, S / 2 + h / 2), radius=w / 3, fill=_rgba(fg))
        else:
            c = S / 2
            d.polygon([(c - S * .13, c - S * .2), (c - S * .13, c + S * .2), (c + S * .22, c)], fill=_rgba(fg))
    return _render(master, ("play", size, bg, fg, playing, alpha), size, size, paint)


def grid_icon(master, size, n, color):
    """Icono de cuadrícula n × n (botones de vista y de tamaño)."""
    def paint(d, s):
        S = size * s
        gap = S * (.14 if n <= 2 else .1)
        cell = (S - gap * (n - 1)) / n
        for i in range(n):
            for j in range(n):
                x, y = i * (cell + gap), j * (cell + gap)
                d.rounded_rectangle((x, y, x + cell, y + cell), radius=cell * .22, fill=_rgba(color))
    return _render(master, ("grid", size, n, color), size, size, paint)


def list_icon(master, size, color):
    """Icono de lista (tres renglones con viñeta)."""
    def paint(d, s):
        S = size * s
        t = S * .14
        for k in range(3):
            y = S * (.18 + .32 * k)
            d.ellipse((0, y - t / 2, t, y + t / 2), fill=_rgba(color))
            d.rounded_rectangle((t * 2, y - t / 2, S, y + t / 2), radius=t / 2, fill=_rgba(color))
    return _render(master, ("list", size, color), size, size, paint)


def wave_icon(master, w, h, color):
    """Forma de onda (sonidos sin portada)."""
    bars = (.25, .55, 1.0, .4, .75, .35, .65, .25)

    def paint(d, s):
        W, H = w * s, h * s
        n = len(bars)
        bw = W / (n * 2 - 1)
        for i, k in enumerate(bars):
            x = i * 2 * bw
            bh = max(bw, H * k)
            d.rounded_rectangle((x, (H - bh) / 2, x + bw, (H + bh) / 2), radius=bw / 2, fill=_rgba(color))
    return _render(master, ("wave", w, h, color), w, h, paint)
