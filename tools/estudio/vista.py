# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Vista previa de la ventana principal de Numpad Macros 3.4.1.

Se dibuja como imagen (al doble de tamaño y luego reducida, para bordes suaves) con
transparencia real: el degradado del fondo, la transparencia de cada capa y de cada
sección, las 9 zonas con imagen (también animadas) y la opacidad de la ventana sobre
un fondo de escritorio de ejemplo.

Cada parte deja una zona «tocable»: «t:<capa>» (el color que la pinta), «z:<espacio>»
(zona de imagen) y «s:<sección>».
"""
from __future__ import annotations

import os
import sys
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
        self._photo = None
        self._item = None
        self._job = None
        self._t = 0
        self._layers = None
        self.k = 1.0                       # escala de la vista previa (se ajusta al tamaño de la ventana)

    def set_scale(self, k):
        """Cambia el tamaño de la vista previa. Devuelve True si cambió (hay que volver a dibujar)."""
        k = round(max(.4, min(2.0, k)), 2)
        if abs(k - self.k) < .01:
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
        zones()
        slot_frames = slot_frames or (lambda *a: None)
        sections = sections or {}
        sec = {k: L.section(sections, k) for k in npt.SECTIONS}
        self.hits = []
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
        self._fit_layers(images)

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
        base, mid, top, slot_frames, opacity, wall, paused = self._full
        behind, free = images or self._slot_images(slot_frames)
        size = (round(WW * self.k), round(WH * self.k))

        def down(p):
            return p.down() if abs(self.k - 1) < .01 else p.im.resize(size, Image.LANCZOS)
        # las capas se reducen a la vez (Pillow suelta el GIL al reducir): unas 3 veces más rápido
        small = list(_pool().map(down, [p for p in (base, mid, top) if p]))
        self._layers = (small[0], small[1], small[2] if top else None, behind, free, opacity / 100, wall)
        self._anim = any(len(f) > 1 for f in list(behind.values()) + list(free.values())) and not paused
        if self._job:
            self.cv.after_cancel(self._job)
            self._job = None
        self._t = 0
        self._show()
        if self._anim:
            self._job = self.cv.after(60, self._tick)

    def _hit(self, x1, y1, x2, y2, tag):
        self.hits.append((x1 + OX, y1 + OY, x2 + OX, y2 + OY, tag))

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
        from PIL import ImageTk
        self._photo = ImageTk.PhotoImage(self.compose(self._t))
        if self._item is None or not self.cv.find_withtag(self._item):
            self.cv.delete("all")
            self._item = self.cv.create_image(0, 0, anchor="nw", image=self._photo)
        else:
            self.cv.itemconfigure(self._item, image=self._photo)

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
        self._hit(x, 8, x + 150, 34, "t:text")
        for i, (lab, parts) in enumerate((("Audífonos", ((.46, "ok"), (.10, "warn"))),
                                          ("Micrófono virtual", ((.56, "ok"), (.12, "warn"), (.07, "bad"))))):
            y = 14 + i * 14
            p.text(264, y, lab, rgba(e["muted"]), 8, anchor="rm")
            self._hit(196, y - 6, 264, y + 6, "t:muted")
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
        self._hit(484, 9, 554, 31, "t:text")
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
        self._hit(18, 102, 160, 114, "t:muted")
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
        self._hit(18, 148, 170, 162, "t:text")
        p.text(280, 155, "5 × 6 · G = Global", rgba(e["muted"]), 8.5, anchor="rm")
        p.text(18, 456, "Solo se tocan en la app del celular.", rgba(e["muted"]), 8.5)
        self._hit(18, 449, 280, 463, "t:muted")

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
            x += w - 1
        tw = text_w(TABS[0], 9, True) + 14
        p.rect(301, 85, 300 + tw - 1, 88, fill=rgba(e["panel"]))

    # ------------------------------------------------------------ panel de la pestaña
    def _body(self, p, e, sec, hover=False, **_kw):
        tw = text_w(TABS[0], 9, True) + 14
        p.line([(300 + tw - 1, 86), (672, 86), (672, 512), (300, 512), (300, 86)], rgba(e["line"]), 1)
        p.text(314, 102, "Virtual 7  ·  Stream", rgba(e["text"]), 14, True)
        self._hit(314, 92, 520, 112, "t:text")
        p.text(314, 121, "Tecla virtual 7: no es una tecla física, solo se toca en la app del celular.",
               rgba(e["muted"]), 8.5, maxw=344)
        self._hit(314, 114, 658, 128, "t:muted")

        def field(y, label, val, x1=376, x2=658, arrow=True):
            p.text(314, y + 10, label, rgba(e["muted"]), 9)
            self._hit(314, y, 372, y + 20, "t:muted")
            p.rect(x1, y, x2, y + 20, fill=rgba(e["panel2"]), outline=rgba(e["line"]))
            p.text(x1 + 8, y + 10, val, rgba(e["text"]), 9, maxw=x2 - x1 - 24)
            if arrow:
                p.text(x2 - 8, y + 10, "▼", rgba(e["muted"]), 6, anchor="rm")
            self._hit(x1, y, x2, y + 20, "t:panel2")

        field(136, "Acción", "♪ Reproducir sonido")
        p.text(314, 172, "♪ Tambores", rgba(e["text"]), 11.5, True)
        self._hit(314, 164, 450, 180, "t:text")
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
        self._hit(16, 520, 54, 533, "t:muted")
        p.rect(348, 519, 446, 534, outline=rgba(e["line"]))
        p.text(397, 526.5, "v3.4.1 · Novedades", rgba(e["muted"]), 8, anchor="mm")
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
