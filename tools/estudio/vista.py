# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Vista previa de la ventana principal de Numpad Macros 3.4.1.

Se dibuja como imagen (al doble de tamaño y luego reducida, para bordes suaves) con
transparencia real: el degradado del fondo, la transparencia de cada capa y de cada
sección, las 9 zonas con imagen (también animadas) y la opacidad de la ventana sobre
un fondo de escritorio de ejemplo.

Cada parte deja una zona «tocable»: «t:<capa>» (el color que la pinta), «z:<espacio>»
(zona de imagen) y «s:<sección>». Los textos que van sobre el fondo, además, llevan un nombre
(text_zones): con ellos se mide la legibilidad sobre la imagen de fondo, zona por zona.
"""
from __future__ import annotations

import copy
import hashlib
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import logica as L
from logica import npt

W, H = 700, 560                    # lienzo
OX, OY = 10, 10                    # la ventana dentro del lienzo
WW, WH = 680, 540                  # la ventana
S = 2                              # se dibuja al doble y se reduce
FONT = "Segoe UI" if sys.platform == "win32" else ("Helvetica Neue" if sys.platform == "darwin" else "DejaVu Sans")
FS = 2 if sys.platform == "darwin" else 0          # (para la interfaz del Estudio)

# Colores por botón (los mismos 12 del PC y del celular)
KEY_COLORS = {
    "Naranja": "#f2a33a", "Amarillo": "#e2c340", "Lima": "#9bd14a", "Verde": "#4cc38a",
    "Turquesa": "#3cc7c0", "Celeste": "#6aa8ff", "Azul": "#4a6cf0", "Morado": "#9b7fe0",
    "Rosa": "#e06fb8", "Rojo": "#e5534b", "Café": "#b07a4a", "Gris": "#8b909b",
}
# Teclas virtuales de ejemplo: número -> (texto, color o None, global, sin icono de sonido)
SAMPLE_KEYS = {
    1: ("Aplausos", "Verde", False, False), 2: ("Vine boom", "Azul", False, False),
    3: ("Air horn", "Rojo", False, False), 4: ("Risas", "Amarillo", False, False),
    5: ("■ Detener", "Rojo", True, True), 6: ("Suspenso", "Morado", False, False),
    7: ("Tambores", "Turquesa", False, False), 8: ("Ctrl+F16", "Celeste", False, True),
    9: ("Wow", None, False, False), 11: ("Bruh", "Naranja", False, False),
    12: ("Sad trombone", None, False, False), 13: ("Cri cri", "Gris", False, False),
    16: ("Error de Windows", "Rojo", False, False), 21: ("Banco ▶", None, True, True),
    26: ("Victoria", "Lima", False, False),
}
TABS = ("Tecla", "Sonidos", "Numpad y opciones", "Audio", "Celular", "Temas")

# ---------------------------------------------------------------- fuentes
_FONTS: dict = {}


def _font_file(bold):
    name = "Inter-Bold.ttf" if bold else "Inter-Regular.ttf"
    for p in (os.path.join(getattr(sys, "_MEIPASS", ""), "fonts", name),
              os.path.join(L.ROOT, "assets", "fonts", name)):
        if os.path.isfile(p):
            return p
    return None


def font(size, bold=False):
    key = (size, bold)
    if key not in _FONTS:
        path = _font_file(bold)
        try:
            _FONTS[key] = ImageFont.truetype(path, round(size * S)) if path else ImageFont.load_default(size * S)
        except Exception:
            _FONTS[key] = ImageFont.load_default()
    return _FONTS[key]


def text_w(s, size, bold=False):
    return font(size, bold).getlength(s) / S


# ---------------------------------------------------------------- zonas (coordenadas de la ventana)
def _layout():
    """Las 9 zonas de imagen y las 6 secciones, en coordenadas de la ventana."""
    x = 300
    for name in TABS:
        x += text_w(name, 9, True) + 14 - 1
    tabs_end = round(x)
    zones = {
        "banner": (0, 0, WW, 60), "logo": (12, 8, 38, 34), "headmid": (352, 6, 444, 36),
        "keys": (22, 166, 268, 443), "leftbot": (16, 468, 282, 506),
        "tabsend": (min(tabs_end + 8, 620), 66, 672, 85), "corner": (301, 362, 671, 511),
        "footband": (8, 516, 672, 537), "foot": (60, 518, 340, 535),
    }
    secs = {"head": (0, 0, WW, 60), "left": (8, 64, 290, 512), "keys": (28, 172, 262, 437),
            "tabs": (300, 64, tabs_end, 86), "body": (300, 86, 672, 512), "foot": (8, 516, 672, 537)}
    return zones, secs, tabs_end


ZONES, SECTION_BOXES, TABS_END = None, None, None


def zones():
    global ZONES, SECTION_BOXES, TABS_END
    if ZONES is None:
        ZONES, SECTION_BOXES, TABS_END = _layout()
    return ZONES


def zone_size(slot):
    x1, y1, x2, y2 = zones()[slot]
    return x2 - x1, y2 - y1


def export_size(slot):
    """Tamaño con que se guarda la imagen de un espacio: la misma forma que su zona en la vista previa
    (así el tema muestra exactamente el recorte que se ve aquí), lo más grande posible sin pasar del
    máximo del formato .npt."""
    mw, mh = npt.IMAGE_SLOTS[slot]
    if slot not in zones():
        return mw, mh
    zw, zh = zone_size(slot)
    k = min(mw / zw, mh / zh)
    return max(1, min(mw, round(zw * k))), max(1, min(mh, round(zh * k)))


# ---------------------------------------------------------------- dibujo
def rgba(h, a=1.0):
    r, g, b = L.hex2rgb(h)
    return (r, g, b, max(0, min(255, round(a * 255))))


class _Pen:
    """Dibuja en una capa al doble de tamaño, con coordenadas de la ventana."""

    def __init__(self, size=(WW, WH), fill=(0, 0, 0, 0)):
        self.im = Image.new("RGBA", (size[0] * S, size[1] * S), fill)
        self.d = ImageDraw.Draw(self.im)

    @staticmethod
    def _b(x1, y1, x2, y2):
        return [round(x1 * S), round(y1 * S), round(x2 * S) - 1, round(y2 * S) - 1]

    def rect(self, x1, y1, x2, y2, fill=None, outline=None, width=1, r=0):
        box = self._b(x1, y1, x2, y2)
        if box[2] <= box[0] or box[3] <= box[1]:
            return
        kw = dict(fill=fill, outline=outline, width=round(width * S) if outline else 0)
        if r:
            self.d.rounded_rectangle(box, round(r * S), **kw)
        else:
            self.d.rectangle(box, **kw)

    def oval(self, cx, cy, r, fill=None, outline=None, width=1):
        self.d.ellipse(self._b(cx - r, cy - r, cx + r, cy + r), fill=fill, outline=outline,
                       width=round(width * S) if outline else 0)

    def line(self, pts, fill, width=1):
        self.d.line([(round(x * S), round(y * S)) for x, y in pts], fill=fill, width=round(width * S))

    def text(self, x, y, s, fill, size, bold=False, anchor="lm", maxw=None):
        f = font(size, bold)
        if maxw and f.getlength(s) / S > maxw:
            while s and f.getlength(s + "…") / S > maxw:
                s = s[:-1]
            s = s.rstrip() + "…"
        mask, (bx, by) = _text_mask(s, size, bold, anchor)
        if mask is None:
            return
        if fill[3] < 255:
            a = fill[3] / 255
            mask = mask.point(lambda v: round(v * a))
        self.im.paste(fill[:3] + (255,), (round(x * S) + bx, round(y * S) + by), mask)

    def down(self):
        return self.im.reduce(S)


_MASKS: dict = {}


def _text_mask(s, size, bold, anchor):
    """Texto ya dibujado (máscara en gris) y su desplazamiento, guardado para no volver a dibujarlo."""
    key = (s, size, bold, anchor)
    if key not in _MASKS:
        if len(_MASKS) > 600:
            _MASKS.clear()
        f = font(size, bold)
        x0, y0, x1, y1 = f.getbbox(s, anchor=anchor)
        if x1 <= x0 or y1 <= y0:
            _MASKS[key] = (None, (0, 0))
        else:
            m = Image.new("L", (x1 - x0, y1 - y0), 0)
            ImageDraw.Draw(m).text((-x0, -y0), s, font=f, fill=255, anchor=anchor)
            _MASKS[key] = (m, (x0, y0))
    return _MASKS[key]


def _alpha_mul(im, a):
    if a >= 1:
        return im
    ch = im.getchannel("A").point(lambda v: round(v * a))
    im = im.copy()
    im.putalpha(ch)
    return im


_POOL = None
_WORKER = None


def _worker():
    """Un hilo aparte para armar la vista previa (aparte de _pool, que usa ese mismo armado)."""
    global _WORKER
    if _WORKER is None:
        _WORKER = ThreadPoolExecutor(1, thread_name_prefix="vista-armado")
    return _WORKER


def _pool():
    """Hilos para reducir las capas de la vista previa al mismo tiempo."""
    global _POOL
    if _POOL is None:
        _POOL = ThreadPoolExecutor(3, thread_name_prefix="vista")
    return _POOL


_WALL = None


def wallpaper(size=None):
    """Fondo de escritorio de ejemplo (cielo, sol y cerros) para ver la opacidad de la ventana."""
    global _WALL
    if _WALL is None:
        im = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(im)
        for y in range(H):
            t = y / H
            if t < .45:
                c = L.mix("#6aa9d8", "#a7d0c4", t / .45)
            else:
                c = L.mix("#3c6e5a", "#25463a", (t - .46) / .54)
            d.line([(0, y), (W, y)], fill=c)
        d.ellipse([W * .18 - 46, H * .3 - 46, W * .18 + 46, H * .3 + 46], fill="#f4c56a")
        d.polygon([(0, H * .62), (W * .2, H * .5), (W * .45, H * .6), (W * .7, H * .48), (W, H * .58), (W, H), (0, H)],
                  fill="#2f5a49")
        _WALL = {(W, H): im}
    size = size or (W, H)
    if size not in _WALL:
        if len(_WALL) > 4:
            _WALL = {(W, H): _WALL[(W, H)]}
        _WALL[size] = _WALL[(W, H)].resize(size, Image.BILINEAR)
    return _WALL[size]


class Preview:
    """Vista previa en un Canvas de Tk.

    ``slot_frames(slot, size)`` devuelve los cuadros ya preparados de un espacio,
    [(imagen RGBA del tamaño pedido, milisegundos)], o None si el espacio está vacío.
    """

    def __init__(self, cv):
        self.cv = cv
        self.hits: list = []
        self.texts: list = []              # textos con nombre: (x1, y1, x2, y2, etiqueta, nombre), sin OX/OY
        self._flash = None                 # contorno temporal de «Ir» (ver flash)
        self._photo = None
        self._item = None
        self._job = None
        self._t = 0
        self._layers = None
        self.k = 1.0                       # escala de la vista previa (se ajusta al tamaño de la ventana)
        self.quiet = False                 # True: se dibuja (en una pestaña tapada) pero sin animar los GIF

    def set_scale(self, k):
        """Cambia el tamaño de la vista previa. Devuelve True si cambió (hay que volver a dibujar)."""
        k = round(max(.4, min(2.0, k)), 3)     # pasos de ~1 px: al estirar en vivo el movimiento es continuo
        if abs(k - self.k) < .001:
            return False
        self.k = k
        return True

    @property
    def size(self):
        return round(W * self.k), round(H * self.k)

    # ------------------------------------------------------------ armado
    def draw(self, e: dict, slot_frames=None, gradient=None, sections=None, opacity=100, wall=False,
             hover=False, mode="edit", sel=None, paused=False, bg_image=None, one_piece=False,
             tint=L.TINT_DEFAULT):
        """``gradient`` o ``bg_image`` (PIL): fondo de toda la ventana. ``one_piece``: «fondo de una pieza»,
        el fondo pasa también por detrás del panel de teclas y de las pestañas, suavizado y teñido con
        ``tint`` (0–90), como lo dibuja Numpad Macros (npm/theme_art.py)."""
        self._build(e, slot_frames, gradient, sections, opacity, wall, hover, mode, sel, paused, bg_image,
                    one_piece, tint)
        self._present()

    def draw_async(self, *a, **kw):
        """Como draw(), pero la imagen se arma en otro hilo y se muestra cuando está lista: la ventana no se
        traba mientras tanto. Si llegan más pedidos durante un dibujo, después se hace solo el último."""
        self._async(lambda sh: sh._build(*a, **kw))

    def rescale_async(self):
        """Como rescale(), en otro hilo. False si todavía no hay nada dibujado."""
        if getattr(self, "_full", None) is None:
            return False
        self._async(lambda sh: sh._prepare())
        return True

    def _async(self, job):
        self._pending = job
        if not getattr(self, "_busy", False):
            self._start()

    def _start(self):
        job, self._pending = self._pending, None
        self._busy = True
        sh = copy.copy(self)                       # el hilo trabaja sobre una copia: lo visible no cambia
        sh.hits = list(self.hits)
        fut = _worker().submit(lambda: (job(sh), sh)[1])
        self.cv.after(8, lambda: self._collect(fut))

    def _collect(self, fut):
        if not fut.done():
            self.cv.after(8, lambda: self._collect(fut))
            return
        self._busy = False
        try:
            sh = fut.result()
        except Exception:
            self._pending = None
            raise
        for name in ("hits", "texts", "e", "_full", "_layers", "_anim", "_shown", "_cover_key", "_cover_img"):
            if hasattr(sh, name):
                setattr(self, name, getattr(sh, name))
        if abs(sh.k - self.k) > 1e-9 and self._pending is None:
            self._pending = lambda s: s._prepare()     # cambió el tamaño mientras se dibujaba
        if self._pending is not None:
            self.live() if abs(sh.k - self.k) > 1e-9 else self._present()
            self._start()
        else:
            self._present()

    def _build(self, e, slot_frames=None, gradient=None, sections=None, opacity=100, wall=False,
               hover=False, mode="edit", sel=None, paused=False, bg_image=None, one_piece=False,
               tint=L.TINT_DEFAULT):
        """Arma las capas y la imagen (solo Pillow, sin Tk: puede correr en otro hilo)."""
        zones()
        slot_frames = slot_frames or (lambda *a: None)
        sections = sections or {}
        sec = {k: L.section(sections, k) for k in npt.SECTIONS}
        self.hits, self.texts = [], []
        window_bg = None
        if gradient:
            window_bg = L.gradient_image(gradient, (WW * S, WH * S))
            under = L.gradient_avg(gradient, e["bg"])
        elif bg_image is not None:
            window_bg = self._cover(bg_image)
            under = L.image_avg(bg_image)
        else:
            under = e["bg"]
        one_piece = bool(one_piece and window_bg is not None)
        if window_bg is not None:              # como Numpad: lo que no se dibuja con el fondo toma su promedio
            e = dict(e, bg=under)
        if one_piece:
            e = dict(e, panel=L.tint_panel(e, under, tint))
        self.e = e

        # capa 1: fondo de la ventana (sólido, degradado o imagen) y las planchas de cada sección
        base = _Pen(fill=rgba(e["bg"]))
        if window_bg is not None:
            base.im.paste(window_bg, (0, 0))
        self._hit(0, 0, WW, WH, "t:bg")
        if one_piece:
            self._one_piece(base.im, e, tint)
        self._plates(base.im, e, sec, skip=("left", "body") if one_piece else ())

        images = self._slot_images(slot_frames)    # (detrás del contenido, en los espacios libres)
        free = images[1]

        # capa 2: contenido de cada sección (con su propia transparencia)
        mid = _Pen()
        glow = _Pen()
        for k in npt.SECTIONS:
            if sec[k]["realce"]:
                self._glow(glow, k, e)
        if any(sec[k]["realce"] for k in sec):
            g2 = glow.im.reduce(4).filter(ImageFilter.GaussianBlur(7 * S / 4)).resize(glow.im.size)
            mid.im.alpha_composite(g2)
            mid.im.alpha_composite(glow.im)
        tint = _Pen()
        tint.rect(0, 0, WW, 60, fill=rgba(e["panel"], sec["head"]["fondo"] / 100))
        mid.im.alpha_composite(tint.im)
        for k, fn in (("head", self._head), ("left", self._left), ("keys", self._keys), ("tabs", self._tabs),
                      ("body", self._body), ("foot", self._foot)):
            c = sec[k]["contenido"] / 100
            p = mid if c >= 1 else _Pen()
            fn(p, e, sec, hover=hover, under=under, logo="logo" in free or mode == "img")
            if p is not mid:
                mid.im.alpha_composite(_alpha_mul(p.im, c))

        # capa 3: marcas de las zonas o de las secciones
        top = None
        if mode == "img":
            top = self._zone_marks(slot_frames, sel)
        elif mode == "sec":
            top = self._section_marks(sel)

        # las capas grandes se guardan: si después solo cambia el tamaño, basta con volver a reducirlas
        self._full = (base, mid, top, slot_frames, opacity, wall, paused)
        self._prepare(images)

    def rescale(self):
        """Vuelve a mostrar el último dibujo al tamaño actual sin rehacerlo entero (al cambiar el tamaño
        de la ventana). Devuelve False si todavía no hay nada dibujado."""
        if getattr(self, "_full", None) is None:
            return False
        self._fit_layers()
        return True

    def _slot_images(self, slot_frames):
        """Imágenes al tamaño actual: (detrás del contenido, en los espacios libres)."""
        behind, free = {}, {}
        for slot in npt.IMAGE_SLOTS:
            if slot not in zones():                # p. ej. «fondo» (toda la ventana): se dibuja aparte
                continue
            zw, zh = zone_size(slot)
            fr = slot_frames(slot, (max(1, round(zw * self.k)), max(1, round(zh * self.k))))
            if fr:
                (behind if slot in npt.SLOTS_BEHIND else free)[slot] = fr
        return behind, free

    def _fit_layers(self, images=None):
        self._prepare(images)
        self._present()

    def _prepare(self, images=None):
        """Reduce las capas grandes al tamaño actual y arma la imagen (sin Tk)."""
        base, mid, top, slot_frames, opacity, wall, paused = self._full
        behind, free = images or self._slot_images(slot_frames)
        size = (round(WW * self.k), round(WH * self.k))

        def down(p):
            return p.down() if abs(self.k - 1) < .01 else p.im.resize(size, Image.LANCZOS)
        # las capas se reducen a la vez (Pillow suelta el GIL al reducir): unas 3 veces más rápido
        small = list(_pool().map(down, [p for p in (base, mid, top) if p]))
        self._layers = (small[0], small[1], small[2] if top else None, behind, free, opacity / 100, wall)
        self._anim = any(len(f) > 1 for f in list(behind.values()) + list(free.values())) and not paused
        self._shown = self.compose(0)

    def _present(self):
        """Muestra en el lienzo la imagen ya armada y vuelve a empezar los GIF (solo en el hilo de Tk)."""
        if self._job:
            self.cv.after_cancel(self._job)
            self._job = None
        self._t = 0
        self._put(self._shown)
        if self._anim and not self.quiet:
            self._job = self.cv.after(60, self._tick)

    def _hit(self, x1, y1, x2, y2, tag, name=None):
        self.hits.append((x1 + OX, y1 + OY, x2 + OX, y2 + OY, tag))
        if name:
            self.texts.append((x1, y1, x2, y2, tag, name))

    # ------------------------------------------------------------ composición
    @staticmethod
    def _frame(frames, t):
        total = sum(d for _f, d in frames)
        t %= max(total, 1)
        for f, d in frames:
            if t < d:
                return f
            t -= d
        return frames[-1][0]

    def compose(self, t=0):
        base, mid, top, behind, free, op, wall = self._layers
        k = self.k
        win = base.copy()
        for slot, fr in behind.items():
            x1, y1, _x2, _y2 = ZONES[slot]
            win.alpha_composite(self._frame(fr, t), (round(x1 * k), round(y1 * k)))
        win.alpha_composite(mid)
        for slot, fr in free.items():
            x1, y1, _x2, _y2 = ZONES[slot]
            win.alpha_composite(self._frame(fr, t), (round(x1 * k), round(y1 * k)))
        if top is not None:
            win.alpha_composite(top)
        out = wallpaper(self.size).copy() if wall else Image.new("RGBA", self.size, (13, 14, 17, 255))
        out.alpha_composite(_alpha_mul(win, op), (round(OX * k), round(OY * k)))
        return out

    def _show(self):
        self._shown = self.compose(self._t)
        self._put(self._shown)

    def live(self):
        """Mientras se cambia el tamaño: estira al vuelo la última imagen bien dibujada (unos 5 ms), para
        que la vista previa acompañe el movimiento. Después hay que llamar a rescale() para la calidad
        completa. Devuelve False si todavía no hay nada dibujado."""
        shown = getattr(self, "_shown", None)
        if shown is None:
            return False
        self.stop()                         # los GIF siguen después, con rescale()
        if shown.size != self.size:
            if getattr(self, "_shown_rgb", (None,))[0] is not shown:     # la conversión, una sola vez
                self._shown_rgb = (shown, shown.convert("RGB"))
            shown = self._shown_rgb[1].resize(self.size, Image.BILINEAR)
        self._put(shown)
        return True

    def _put(self, im):
        from PIL import ImageTk
        self._photo = ImageTk.PhotoImage(im)
        if self._item is None or not self.cv.find_withtag(self._item):
            self.cv.delete("all")
            self._item = self.cv.create_image(0, 0, anchor="nw", image=self._photo)
        else:
            self.cv.itemconfigure(self._item, image=self._photo)
        if self._flash:                     # el contorno de «Ir» sigue encima (y a la escala nueva)
            self._flash_draw()

    def _tick(self):
        self._job = None
        if not self._anim:
            return
        try:
            visible = self.cv.winfo_ismapped()
        except Exception:
            return
        if visible:
            self._t += 80
            self._show()
        self._job = self.cv.after(80 if visible else 400, self._tick)

    def stop(self):
        if self._job:
            self.cv.after_cancel(self._job)
            self._job = None

    # ------------------------------------------------------------ planchas
    def _cover(self, img):
        key = (id(img), img.size)
        if getattr(self, "_cover_key", None) != key:
            self._cover_key, self._cover_img = key, L.cover(img.convert("RGBA"), WW * S, WH * S)
        return self._cover_img

    # paneles por donde pasa el «fondo de una pieza»: el panel de teclas y el bloque de pestañas
    ONE_PIECE = ((8, 64, 290, 512), (300, 64, 672, 512))

    def _one_piece(self, base, e, tint):
        """Dentro de los paneles el fondo se suaviza (desenfoque) y se tiñe con el color del panel."""
        radius = max(12, min(WW, WH) // 25)
        small = base.reduce(4)
        soft = small.filter(ImageFilter.GaussianBlur(radius * S / 4)).resize(base.size, Image.BILINEAR)
        veil = _Pen()
        for x1, y1, x2, y2 in self.ONE_PIECE:
            box = (x1 * S, y1 * S, x2 * S, y2 * S)
            base.paste(soft.crop(box), box[:2])
            veil.rect(x1, y1, x2, y2, fill=rgba(e["panel"]))
        if tint > 0:
            base.alpha_composite(_alpha_mul(veil.im, tint / 100))

    def _plates(self, base, e, sec, skip=()):
        """Planchas de las secciones: cada una con la transparencia de su fondo, sobre el fondo de la ventana."""
        f = {k: (0 if k in skip else sec[k]["fondo"] / 100) for k in sec}

        def layer(k, draw):
            if f[k] <= 0:
                return
            if f[k] >= 1:
                p = _Pen.__new__(_Pen)
                p.im, p.d = base, ImageDraw.Draw(base)
                draw(p)
                return
            p = _Pen()
            draw(p)
            base.alpha_composite(_alpha_mul(p.im, f[k]))

        layer("left", lambda p: p.rect(8, 64, 290, 512, fill=rgba(e["panel"])))
        self._hit(8, 64, 290, 512, "t:panel")
        layer("body", lambda p: p.rect(300, 86, 672, 512, fill=rgba(e["panel"])))
        self._hit(300, 86, 672, 512, "t:panel")

        def tabs(p):
            x = 300
            for i, name in enumerate(TABS):
                w = text_w(name, 9, True) + 14
                col = e["panel"] if i == 0 else L.mix(e["bg"], e["panel"], .5)
                p.rect(x, 64 if i == 0 else 67, x + w, 87 if i == 0 else 86, fill=rgba(col))
                x += w - 1
        layer("tabs", tabs)
        x = 300
        for i, name in enumerate(TABS):
            w = text_w(name, 9, True) + 14
            self._hit(x, 64, x + w, 86, "t:panel" if i == 0 else "t:bg")
            x += w - 1
        layer("foot", lambda p: p.rect(8, 516, 672, 537, fill=rgba(e["panel"]), r=4))

    def _glow(self, p, k, e):
        x1, y1, x2, y2 = SECTION_BOXES[k]
        w = 3 if k == "keys" else 2
        p.rect(x1 - w, y1 - w, x2 + w, y2 + w, outline=rgba(e["acc"]), width=w, r=6 if k == "keys" else 3)

    # ------------------------------------------------------------ encabezado
    def _head(self, p, e, sec, logo=False, **_kw):
        x = 44 if logo else 12
        p.text(x, 21, "Numpad Macros", rgba(e["text"]), 18, True)
        self._hit(x, 8, x + 150, 34, "t:text", "el título «Numpad Macros»")
        for i, (lab, parts) in enumerate((("Audífonos", ((.46, "ok"), (.10, "warn"))),
                                          ("Micrófono virtual", ((.56, "ok"), (.12, "warn"), (.07, "bad"))))):
            y = 14 + i * 14
            p.text(264, y, lab, rgba(e["muted"]), 8, anchor="rm")
            self._hit(196, y - 6, 264, y + 6, "t:muted", "las etiquetas de los medidores")
            p.rect(268, y - 3, 346, y + 3, fill=rgba(e["line"]))
            x0 = 268
            for frac, tok in parts:
                p.rect(x0, y - 3, x0 + 78 * frac, y + 3, fill=rgba(e[tok]))
                x0 += 78 * frac
            for xx in range(271, 346, 4):
                p.rect(xx, y - 3, xx + 1, y + 3, fill=rgba(e["bg"], .55))
            self._hit(268, y - 4, 346, y + 4, "t:line")
        for x1, ch in ((452, "◀"), (556, "▶")):
            p.rect(x1, 9, x1 + 30, 31, fill=rgba(e["panel2"]), outline=rgba(e["line"]))
            p.text(x1 + 15, 20, ch, rgba(e["text"]), 8, anchor="mm")
            self._hit(x1, 9, x1 + 30, 31, "t:panel2")
        p.text(519, 20, "1. Stream", rgba(e["text"]), 11, True, anchor="mm")
        self._hit(484, 9, 554, 31, "t:text", "«1. Stream» del encabezado")
        p.rect(592, 9, 672, 31, fill=rgba(e["ok"]))
        p.text(632, 20, "● ACTIVO", rgba(e["on_ok"]), 10, True, anchor="mm")
        self._hit(592, 9, 672, 31, "t:ok")
        p.text(12, 49, "● Numpad conectado: USB Keypad", rgba(e["ok"]), 8.5)
        p.text(178, 49, "● Audio listo", rgba(e["ok"]), 8.5)
        self._hit(12, 43, 250, 55, "t:ok")
        p.rect(254, 42, 448, 56, fill=rgba(e["panel2"]))
        p.text(260, 49, "Modo macros apagado (Ctrl+Alt+M)", rgba(e["muted"]), 8.5, True)
        self._hit(254, 42, 448, 56, "t:panel2")

    # ------------------------------------------------------------ panel izquierdo
    def _left(self, p, e, sec, **_kw):
        p.rect(18, 94, 148, 96, fill=rgba(e["line"]))
        p.text(83, 83, "Numpad y fila 1–0", rgba(e["muted"]), 9, True, anchor="mm")
        self._hit(18, 72, 148, 96, "t:line")
        p.rect(152, 72, 280, 96, fill=rgba(e["panel2"]))
        p.rect(152, 94, 280, 96, fill=rgba(e["acc"]))
        p.text(216, 83, "Teclas virtuales", rgba(e["text"]), 9, True, anchor="mm")
        self._hit(152, 72, 280, 96, "t:acc")
        p.text(18, 108, "Capa que estás editando", rgba(e["muted"]), 9)
        self._hit(18, 102, 160, 114, "t:muted", "«Capa que estás editando»")
        p.rect(18, 118, 170, 140, fill=rgba(e["panel2"]), outline=rgba(e["line"]))
        p.text(26, 129, "1. Stream", rgba(e["text"]), 9.5)
        p.text(162, 129, "▼", rgba(e["muted"]), 6, anchor="rm")
        self._hit(18, 118, 170, 140, "t:panel2")
        for i, ch in enumerate(("+", "edit", "×")):
            x1 = 176 + i * 36
            p.rect(x1, 118, x1 + 32, 140, fill=rgba(e["panel2"]), outline=rgba(e["line"]))
            if ch == "edit":
                p.line([(x1 + 13, 133), (x1 + 19, 125)], rgba(e["text"]), 1.8)
                p.line([(x1 + 12, 134.5), (x1 + 13, 133)], rgba(e["muted"]), 1.4)
            else:
                p.text(x1 + 16, 129, ch, rgba(e["text"]), 11, anchor="mm")
            self._hit(x1, 118, x1 + 32, 140, "t:panel2")
        p.text(18, 155, "Teclas virtuales · 30", rgba(e["text"]), 11, True)
        self._hit(18, 148, 170, 162, "t:text", "«Teclas virtuales · 30»")
        p.text(280, 155, "5 × 6 · G = Global", rgba(e["muted"]), 8.5, anchor="rm")
        p.text(18, 456, "Solo se tocan en la app del celular.", rgba(e["muted"]), 8.5)
        self._hit(18, 449, 280, 463, "t:muted", "la nota al pie del panel de teclas")

    def _keys(self, p, e, sec, **_kw):
        fa = sec["keys"]["fondo"] / 100
        kw, gap, x0, y0 = 40, 5, 34, 172
        keys = []
        for n in range(1, 31):
            r, c = divmod(n - 1, 5)
            x1, y1 = x0 + c * (kw + gap), y0 + r * (kw + gap)
            v = SAMPLE_KEYS.get(n)
            g = None
            if v and v[1]:
                col = KEY_COLORS[v[1]]
                fill, line, txt, tag = L.mix(e["panel"], col, .2), col, e["text"], "text"
                if v[2]:
                    g = (col, e["bg"])
            elif v and v[2]:
                fill, line, txt, tag = e["key_global"], e["key_global_line"], e["key_global_text"], "key_global"
                g = (e["key_global_line"], e["bg"])
            elif v:
                fill, line, txt, tag = e["key_set"], e["key_set_line"], e["key_set_text"], "key_set"
            else:
                fill, line, txt, tag = e["key"], e["line"], e["text"], "key"
            keys.append((n, x1, y1, v, g, fill, line, txt, tag))
        # planchas de las teclas (con la transparencia del fondo de la sección «Teclas»)
        plates = _Pen()
        for n, x1, y1, v, g, fill, line, txt, tag in keys:
            plates.rect(x1, y1, x1 + kw, y1 + kw, fill=rgba(fill), r=5)
        p.im.alpha_composite(_alpha_mul(plates.im, fa))
        for n, x1, y1, v, g, fill, line, txt, tag in keys:
            p.rect(x1, y1, x1 + kw, y1 + kw, outline=rgba(e["text"] if n == 7 else line), width=2, r=5)
            p.text(x1 + 5, y1 + 4, str(n), rgba(txt), 12, True, anchor="lt")
            if g:
                p.rect(x1 + kw - 13, y1 + 4, x1 + kw - 4, y1 + 13, fill=rgba(g[0]), r=2)
                p.text(x1 + kw - 8.5, y1 + 8.5, "G", rgba(g[1]), 6, True, anchor="mm")
            elif v and not v[3]:
                p.text(x1 + kw - 5, y1 + 9, "♪", rgba(txt, .85), 8, anchor="rm")
            if v:
                p.text(x1 + kw / 2, y1 + kw - 7, v[0], rgba(txt), 6.5, anchor="mm", maxw=kw - 4)
            self._hit(x1, y1, x1 + kw, y1 + kw, "t:" + tag)

    # ------------------------------------------------------------ pestañas
    def _tabs(self, p, e, sec, **_kw):
        x = 300
        for i, name in enumerate(TABS):
            w = text_w(name, 9, True) + 14
            on = i == 0
            p.rect(x, 64 if on else 67, x + w, 87 if on else 86, outline=rgba(e["line"]))
            p.text(x + w / 2, 76 if on else 77, name, rgba(e["text"] if on else e["muted"]), 9, True, anchor="mm")
            self.texts.append((x, 66, x + w, 86, "t:text" if on else "t:muted", "los nombres de las pestañas"))
            x += w - 1
        tw = text_w(TABS[0], 9, True) + 14
        p.rect(301, 85, 300 + tw - 1, 88, fill=rgba(e["panel"]))

    # ------------------------------------------------------------ panel de la pestaña
    def _body(self, p, e, sec, hover=False, **_kw):
        tw = text_w(TABS[0], 9, True) + 14
        p.line([(300 + tw - 1, 86), (672, 86), (672, 512), (300, 512), (300, 86)], rgba(e["line"]), 1)
        p.text(314, 102, "Virtual 7  ·  Stream", rgba(e["text"]), 14, True)
        self._hit(314, 92, 520, 112, "t:text", "el título de la pestaña")
        p.text(314, 121, "Tecla virtual 7: no es una tecla física, solo se toca en la app del celular.",
               rgba(e["muted"]), 8.5, maxw=344)
        self._hit(314, 114, 658, 128, "t:muted", "la ayuda de la pestaña")

        def field(y, label, val, x1=376, x2=658, arrow=True):
            p.text(314, y + 10, label, rgba(e["muted"]), 9)
            self._hit(314, y, 372, y + 20, "t:muted", "las etiquetas de los campos")
            p.rect(x1, y, x2, y + 20, fill=rgba(e["panel2"]), outline=rgba(e["line"]))
            p.text(x1 + 8, y + 10, val, rgba(e["text"]), 9, maxw=x2 - x1 - 24)
            if arrow:
                p.text(x2 - 8, y + 10, "▼", rgba(e["muted"]), 6, anchor="rm")
            self._hit(x1, y, x2, y + 20, "t:panel2")

        field(136, "Acción", "♪ Reproducir sonido")
        p.text(314, 172, "♪ Tambores", rgba(e["text"]), 11.5, True)
        self._hit(314, 164, 450, 180, "t:text", "«Tambores»")
        field(186, "Buscar", "", x2=530, arrow=False)
        p.rect(536, 186, 658, 206, fill=rgba(e["panel2"]), outline=rgba(e["line"]))
        p.text(597, 196, "+ Agregar archivos…", rgba(e["text"]), 8.5, anchor="mm")
        self._hit(536, 186, 658, 206, "t:panel2")
        p.rect(376, 212, 658, 292, fill=rgba(e["panel2"]), outline=rgba(e["line"]))
        self._hit(376, 212, 658, 292, "t:panel2")
        for i, name in enumerate(("Air horn", "Risas", "Suspenso", "Tambores", "Wow", "Bruh")):
            y = 219 + i * 12.6
            if name == "Tambores":
                p.rect(377, y - 6, 657, y + 6.5, fill=rgba(e["acc_bg"]))
                p.text(384, y, name, rgba(e["acc"]), 9)
                self._hit(377, y - 6, 657, y + 6.5, "t:acc_bg")
            else:
                p.text(384, y, name, rgba(e["text"]), 9)
        field(298, "Al pulsar", "Superponer (cada pulsación suena encima)")
        p.text(314, 334, "Volumen", rgba(e["muted"]), 9)
        p.rect(376, 332, 548, 337, fill=rgba(e["panel2"]), r=2.5)
        p.rect(376, 332, 482, 337, fill=rgba(e["acc_dim"]), r=2.5)
        p.oval(482, 334.5, 6.5, fill=rgba(e["text"]))
        self._hit(376, 326, 548, 342, "t:acc_dim")
        p.text(658, 334, "100 % · 0.0 dB", rgba(e["acc"]), 10, True, anchor="rm")
        self._hit(560, 326, 658, 342, "t:acc")
        p.text(376, 352, "Igualar volumen: mide −21.5 LUFS → se ajusta +5.5 dB.", rgba(e["muted"]), 8.5)
        # parte de abajo (la zona «corner» va detrás)
        for i, lab in enumerate(("Por mis audífonos", "Por el micrófono")):
            x1 = 314 + i * 118
            p.rect(x1, 384, x1 + 13, 397, fill=rgba(e["acc"]), r=3)
            p.text(x1 + 6.5, 390.5, "✓", rgba(e["on_acc"]), 8, True, anchor="mm")
            p.text(x1 + 18, 390.5, lab, rgba(e["text"]), 9)
            self._hit(x1, 384, x1 + 110, 397, "t:acc")
        btn = "acc_hover" if hover else "acc"
        p.rect(580, 379, 658, 402, fill=rgba(e[btn]))
        p.text(619, 390.5, "▶ Probar", rgba(e["on_acc"]), 10, True, anchor="mm")
        self._hit(580, 379, 658, 402, "t:" + btn)
        p.rect(314, 412, 658, 470, fill=rgba(e["panel2"]))
        self._hit(314, 412, 658, 470, "t:panel2")
        p.text(324, 426, "Color del botón", rgba(e["text"]), 9.5, True)
        p.text(414, 426, "Turquesa", rgba(e["muted"]), 9)
        p.text(648, 426, "Se ve igual en el PC y en el celular", rgba(e["muted"]), 8, anchor="rm")
        cx = 333
        p.oval(cx, 451, 8, outline=rgba(e["muted"]), width=1)
        for name, col in KEY_COLORS.items():
            cx += 24
            if name == "Turquesa":
                p.oval(cx, 451, 11, outline=rgba(e["text"]), width=2)
            p.oval(cx, 451, 8, fill=rgba(col))

    # ------------------------------------------------------------ pie
    def _foot(self, p, e, sec, **_kw):
        p.text(16, 526.5, "Listo.", rgba(e["muted"]), 8.5)
        self._hit(16, 520, 54, 533, "t:muted", "«Listo.» del pie")
        p.rect(348, 519, 446, 534, outline=rgba(e["line"]))
        p.text(397, 526.5, "v3.4.1 · Novedades", rgba(e["muted"]), 8, anchor="mm")
        self.texts.append((350, 520, 444, 533, "t:muted", "«Novedades» del pie"))
        self._hit(348, 519, 446, 534, "t:line")
        p.rect(452, 519, 606, 534, fill=rgba(e["panel2"]))
        p.text(529, 526.5, "Creado por OkumaWsX · Soporte", rgba(e["text"]), 8, anchor="mm")
        self._hit(452, 519, 606, 534, "t:panel2")
        p.rect(612, 519, 668, 534, fill=rgba(e["acc"]))
        p.text(640, 526.5, "♥ Donar", rgba(e["on_acc"]), 8.5, True, anchor="mm")
        self._hit(612, 519, 668, 534, "t:on_acc")

    # ------------------------------------------------------------ marcas
    def _zone_marks(self, slot_frames, sel):
        p = _Pen()
        for slot, (x1, y1, x2, y2) in ZONES.items():
            on = slot == sel
            has = slot_frames(slot, zone_size(slot)) is not None
            if not has:
                p.rect(x1 + 1, y1 + 1, x2 - 1, y2 - 1, fill=(255, 255, 255, 18))
                p.text((x1 + x2) / 2, (y1 + y2) / 2, "+", (255, 255, 255, 170), 12, True, anchor="mm")
            if on:
                p.rect(x1, y1, x2, y2, outline=(242, 163, 58, 255), width=2)
            else:
                self._dashed(p, x1 + 1, y1 + 1, x2 - 1, y2 - 1, (255, 255, 255, 140))
        # las zonas chicas quedan encima de las grandes al tocar
        order = sorted(ZONES, key=lambda s: -(zone_size(s)[0] * zone_size(s)[1]))
        for slot in order:
            x1, y1, x2, y2 = ZONES[slot]
            self._hit(x1, y1, x2, y2, "z:" + slot)
        return p

    def _section_marks(self, sel):
        p = _Pen()
        for k, (x1, y1, x2, y2) in SECTION_BOXES.items():
            if k == sel:
                self._dashed(p, x1 - 2, y1 - 2, x2 + 2, y2 + 2, (242, 163, 58, 255), 2)
        order = ("head", "foot", "left", "body", "tabs", "keys")
        for k in order:
            x1, y1, x2, y2 = SECTION_BOXES[k]
            self._hit(x1, y1, x2, y2, "s:" + k)
        return p

    @staticmethod
    def _dashed(p, x1, y1, x2, y2, col, w=1):
        dash, gap = 4, 3
        for (ax, ay, bx, by) in ((x1, y1, x2, y1), (x2, y1, x2, y2), (x2, y2, x1, y2), (x1, y2, x1, y1)):
            ln = abs(bx - ax) + abs(by - ay)
            dx, dy = (bx - ax) / ln if ln else 0, (by - ay) / ln if ln else 0
            t = 0
            while t < ln:
                u = min(t + dash, ln)
                p.line([(ax + dx * t, ay + dy * t), (ax + dx * u, ay + dy * u)], col, w)
                t += dash + gap

    # ------------------------------------------------------------ toque
    def tag_at(self, x, y, prefix):
        """Etiqueta (sin el prefijo) de la zona más arriba bajo el mouse (x, y en píxeles del lienzo)."""
        x, y = x / self.k, y / self.k
        for x1, y1, x2, y2, tag in reversed(self.hits):
            if tag.startswith(prefix) and x1 <= x < x2 and y1 <= y < y2:
                return tag[len(prefix):]
        return None

    # ------------------------------------------------------------ marcas de «Ir»
    def rects(self, marks):
        """Rectángulos (coordenadas de la ventana) de las marcas de un aviso: [(etiqueta, dónde)], con dónde =
        None, «fondo» (fuera de los paneles) o «paneles» (dentro, sin las teclas). Ver logica.PAIR_MARKS."""
        zones()
        out = []
        for tag, where in marks:
            if tag == "ventana":
                out.append((0, 0, WW, WH))
                continue
            for x1, y1, x2, y2, t in self.hits:
                if t != tag:
                    continue
                r = (x1 - OX, y1 - OY, x2 - OX, y2 - OY)
                if where and (_region(r) in ("left", "tabs", "body")) != (where == "paneles"):
                    continue
                if where == "paneles" and _inside(r, SECTION_BOXES["keys"]):
                    continue
                if r not in out:
                    out.append(r)
        return out

    def flash(self, rects, color, dim=None, worst=None, label=None, font=None, ms=4000):
        """Contorno temporal sobre la vista previa (rects en coordenadas de la ventana). Con ``worst``, ese
        se marca más fuerte (y con ``label`` debajo) y los demás con trazos. Se borra solo a los ``ms``; si
        mientras tanto se vuelve a dibujar la vista previa (o cambia su tamaño), se vuelve a poner encima."""
        if self._flash and self._flash.get("job"):
            self.cv.after_cancel(self._flash["job"])
        self._flash = {"rects": list(rects), "color": color, "dim": dim or color, "worst": worst,
                       "label": label, "font": font}
        self._flash_draw()
        self._flash["job"] = self.cv.after(ms, self.unflash)

    def unflash(self):
        if self._flash and self._flash.get("job"):
            try:
                self.cv.after_cancel(self._flash["job"])
            except Exception:
                pass
        self._flash = None
        self.cv.delete("flash")

    def _flash_draw(self):
        f, k, cv = self._flash, self.k, self.cv
        cv.delete("flash")
        for x1, y1, x2, y2 in f["rects"]:
            strong = f["worst"] is None or tuple(f["worst"]) == (x1, y1, x2, y2)
            pad = 3 if strong else 2
            cv.create_rectangle((x1 + OX) * k - pad, (y1 + OY) * k - pad, (x2 + OX) * k + pad, (y2 + OY) * k + pad,
                                outline=f["color"] if strong else f["dim"], width=3 if strong else 1,
                                dash=() if strong else (3, 2), tags="flash")
        if f["worst"] is not None and f["label"]:
            x1, _y1, _x2, y2 = f["worst"]
            t = cv.create_text((x1 + OX) * k + 4, (y2 + OY) * k + 9, anchor="nw", text=f["label"], tags="flash",
                               fill="#1a1306", font=f["font"])
            bb = cv.bbox(t)
            if bb:
                cv.create_rectangle(bb[0] - 4, bb[1] - 2, bb[2] + 4, bb[3] + 2, fill=f["color"], width=0, tags="flash")
                cv.tag_raise(t)
        cv.tag_raise("flash")


def _inside(r, box) -> bool:
    cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
    return box[0] <= cx <= box[2] and box[1] <= cy <= box[3]


def _region(r) -> str:
    """Sección de la ventana donde cae (el centro de) un rectángulo: head, left, tabs, body o foot."""
    zones()
    if _inside(r, SECTION_BOXES["tabs"]) and r[3] <= 86:
        return "tabs"
    for k in ("left", "body", "head", "foot"):
        if _inside(r, SECTION_BOXES[k] if k != "body" else (300, 64, 672, 512)):
            return k
    return "head" if r[1] < 60 else "foot"


# ---------------------------------------------------------------- texto sobre la imagen de fondo
_TEXTS: dict = {}


class _AnyColor(dict):
    def __missing__(self, k):
        return "#808080"


class _NoPen:
    """Lápiz que no dibuja: para recorrer el armado solo por sus zonas (sin tocar las cachés de letras, que
    usa a la vez el hilo de la vista previa)."""

    def __getattr__(self, name):
        return lambda *a, **kw: None


def text_zones(logo=False) -> list:
    """Los textos de la ventana principal que pueden ir sobre el fondo (sin las teclas, que llevan su
    plancha): [{rect, tag, nombre, seccion}], en coordenadas de la ventana. Se arman una vez (sin Tk)."""
    if logo not in _TEXTS:
        zones()
        pv = Preview(None)
        p = _NoPen()
        sec = {k: L.section({}, k) for k in npt.SECTIONS}
        e = _AnyColor()
        for fn in (pv._head, pv._left, pv._tabs, pv._body, pv._foot):
            fn(p, e, sec, logo=logo)
        _TEXTS[logo] = [{"rect": (x1, y1, x2, y2), "tag": tag, "nombre": name, "seccion": _region((x1, y1, x2, y2))}
                        for x1, y1, x2, y2, tag, name in pv.texts]
    return [dict(z) for z in _TEXTS[logo]]


def tab_boxes() -> list:
    """Planchas de las pestañas [(x1, y1, x2, y2)], como en _plates. Usa las letras (anchos): llamar desde el
    hilo de Tk y pasarlas a measure_image."""
    out, x = [], 300
    for i, name in enumerate(TABS):
        w = text_w(name, 9, True) + 14
        out.append((round(x), 64 if i == 0 else 67, round(x + w), 87 if i == 0 else 86))
        x += w - 1
    return out


def text_backdrop(cov, e, under, one_piece, tint, sections, tabs=None):
    """Lo que queda debajo del texto con imagen de fondo, a escala 1 (WW × WH, RGB): ``cov`` es la imagen ya
    oscurecida cubriendo la ventana; encima, el «fondo de una pieza» (suavizado y teñido) y las planchas de
    las secciones, igual que en Preview._build. ``tabs``: tab_boxes() (si falta, se calcula aquí)."""
    from PIL import Image as _I
    sec = {k: L.section(sections or {}, k) for k in npt.SECTIONS}
    im = cov.convert("RGB")
    panel = L.tint_panel(e, under, tint) if one_piece else e["panel"]
    prgb = L.hex2rgb(panel)

    def veil(box, a):
        if a <= 0:
            return
        reg = im.crop(box)
        im.paste(_I.blend(reg, _I.new("RGB", reg.size, prgb), min(1.0, a)), box[:2])
    if one_piece:
        radius = max(12, min(WW, WH) // 25)
        soft = im.reduce(2).filter(ImageFilter.GaussianBlur(radius / 2)).resize(im.size, _I.BILINEAR)
        for box in Preview.ONE_PIECE:
            im.paste(soft.crop(box), box[:2])
            veil(box, tint / 100)
    for k, box in (("left", (8, 64, 290, 512)), ("body", (300, 86, 672, 512)), ("foot", (8, 516, 672, 537))):
        veil(box, 0 if one_piece and k in ("left", "body") else sec[k]["fondo"] / 100)
    if sec["tabs"]["fondo"] > 0:                               # las pestañas (como en _plates)
        layer = _I.new("RGBA", im.size, (0, 0, 0, 0))
        from PIL import ImageDraw as _D
        d = _D.Draw(layer)
        for i, box in enumerate(tabs or tab_boxes()):
            col = panel if i == 0 else L.mix(under, panel, .5)
            d.rectangle(list(box), fill=L.hex2rgb(col) + (round(255 * sec["tabs"]["fondo"] / 100),))
        im = _I.alpha_composite(im.convert("RGBA"), layer).convert("RGB")
    veil((0, 0, WW, 60), sec["head"]["fondo"] / 100)          # el tinte del encabezado (va con el contenido)
    return im


_SRC: dict = {}
_SRC_LOCK = threading.Lock()


def _source(src: bytes):
    """La imagen de fondo sin oscurecer cubriendo la ventana (WW × WH) y su color promedio. Se guarda la
    última: los dos hilos (la medición y la exportación) la pueden pedir."""
    key = hashlib.md5(src).digest()
    with _SRC_LOCK:
        if _SRC.get("key") == key:
            return _SRC["val"]
    im = L.load_frames(src, max_side=1920)[0][0].convert("RGB")
    val = (L.cover(im, WW, WH).convert("RGB"), L.image_avg(im))
    with _SRC_LOCK:
        _SRC.update(key=key, val=val)
    return val


def on_image(z, one_piece, sections) -> bool:
    """¿Se ve la imagen debajo de este texto? En los paneles sin «fondo de una pieza» y en las secciones
    con plancha opaca, no: ahí el texto va sobre su color (eso lo revisan las parejas de colores)."""
    k = z["seccion"]
    if one_piece and k in ("left", "body"):
        return True
    return L.section(sections or {}, k)["fondo"] < 100


def measure_image(src: bytes, bg: str, e: dict, dark: int, tint: int, one_piece: bool, sections: dict,
                  logo=False, zones=None, tabs=None):
    """Legibilidad del texto sobre la imagen de fondo, zona por zona (logica.image_check), o None si ningún
    texto queda sobre la imagen. Desde otro hilo, pasar ``zones`` (text_zones) y ``tabs`` (tab_boxes) ya
    calculados en el hilo de Tk: así este solo trabaja con la imagen y no toca las letras (FreeType)."""
    from PIL import Image as _I
    cov0, avg0 = _source(src)
    bgc = L.hex2rgb(bg)
    zs = []
    for z in (dict(z) for z in zones) if zones is not None else text_zones(logo):
        if on_image(z, one_piece, sections):
            z["panel"] = one_piece and z["seccion"] in ("left", "tabs", "body")
            z["contenido"] = L.section(sections or {}, z["seccion"])["contenido"]   # se mezcla con lo de abajo
            zs.append(z)

    def backdrop(d, t):
        img = _I.blend(cov0, _I.new("RGB", cov0.size, bgc), d / 100) if d else cov0
        return text_backdrop(img, e, L.mix(avg0, bg, d / 100), one_piece, t, sections, tabs)
    return L.image_check(backdrop, zs, e, dark, tint, one_piece)
