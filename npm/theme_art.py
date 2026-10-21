# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Lo que un tema del Estudio agrega a la ventana además de los colores.

- **Imágenes** en 9 espacios (npt.IMAGE_SLOTS), con GIF animados en los libres.
- **Fondo degradado** de toda la ventana (2–5 colores, desde una esquina, un lado o el centro).
- **Secciones** con transparencia propia (fondo de la sección y su contenido) y borde de realce.

Tk no tiene transparencia por widget, así que las zonas «detrás del contenido» (encabezado, pie,
tabla de teclas, parte de abajo de la pestaña) se dibujan en lienzos: se compone con Pillow el
degradado + la plancha de la sección + la imagen, y encima van textos y botones. Los paneles
(izquierdo, pestañas y contenido) son de color sólido: su «fondo» se mezcla con el color de debajo.
"""
from __future__ import annotations

import io
import os
import tkinter as tk

from . import aa
from .theme import C, mix

try:
    from PIL import Image, ImageSequence
    HAVE_PIL = True
except Exception:                       # pragma: no cover
    HAVE_PIL = False

MAX_FRAMES = 150


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return "#" + "".join(f"{max(0, min(255, int(round(v)))):02x}" for v in rgb[:3])


# ---------------------------------------------------------------- degradado
_START = {"tl": (0, 0), "t": (.5, 0), "tr": (1, 0), "l": (0, .5), "c": (.5, .5), "r": (1, .5),
          "bl": (0, 1), "b": (.5, 1), "br": (1, 1)}


def gradient_image(w, h, stops, start="tl"):
    """Imagen RGB w×h del degradado. stops = [["#rrggbb", 0..100], …]."""
    import numpy as np
    sw, sh = max(2, w // 4), max(2, h // 4)              # se calcula chico y se agranda (es suave)
    ys, xs = np.mgrid[0:sh, 0:sw]
    u = (xs + .5) / sw
    v = (ys + .5) / sh
    if start == "c":
        # circular desde el centro: 0 en el centro, 1 en la esquina (ventana con su proporción)
        dx, dy = (u - .5) * w, (v - .5) * h
        t = np.sqrt(dx * dx + dy * dy) / (0.5 * (w * w + h * h) ** .5)
    else:
        sx, sy = _START.get(start, (0, 0))
        ex, ey = 1 - sx, 1 - sy
        vx, vy = (ex - sx) * w, (ey - sy) * h
        L2 = vx * vx + vy * vy or 1
        t = ((u - sx) * w * vx + (v - sy) * h * vy) / L2
    t = np.clip(t, 0, 1) * 100
    pts = sorted((max(0, min(100, int(p))), _rgb(c)) for c, p in stops)
    pos = [p for p, _ in pts]
    out = np.zeros((sh, sw, 3), dtype=np.float32)
    for ch in range(3):
        out[..., ch] = np.interp(t, pos, [c[ch] for _, c in pts])
    img = Image.fromarray(out.astype("uint8"), "RGB")
    return img.resize((w, h), Image.BILINEAR)


def gradient_average(stops):
    if not stops:
        return C["bg"]
    s = [0, 0, 0]
    for c, _p in stops:
        r = _rgb(c)
        for i in range(3):
            s[i] += r[i]
    return _hex([x / len(stops) for x in s])


# ---------------------------------------------------------------- imágenes del tema
def cover(img, w, h):
    """Recorta al centro para llenar w×h sin deformar."""
    iw, ih = img.size
    if iw <= 0 or ih <= 0 or w <= 0 or h <= 0:
        return img
    k = max(w / iw, h / ih)
    nw, nh = max(1, int(iw * k + .5)), max(1, int(ih * k + .5))
    im = img.resize((nw, nh), Image.LANCZOS)
    x, y = (nw - w) // 2, (nh - h) // 2
    return im.crop((x, y, x + w, y + h))


def contain(img, w, h):
    iw, ih = img.size
    k = min(w / iw, h / ih, 1.0 if max(iw, ih) > 0 else 1.0) if iw and ih else 1.0
    k = min(w / iw, h / ih) if iw and ih else 1.0
    return img.resize((max(1, int(iw * k)), max(1, int(ih * k))), Image.LANCZOS)


class _Slot:
    """Una imagen del tema: uno o varios cuadros (GIF) con su duración."""

    def __init__(self, data: bytes):
        im = Image.open(io.BytesIO(data))
        self.frames, self.durs = [], []
        if getattr(im, "is_animated", False):
            for i, fr in enumerate(ImageSequence.Iterator(im)):
                if i >= MAX_FRAMES:
                    break
                self.frames.append(fr.convert("RGBA"))
                self.durs.append(max(20, int(fr.info.get("duration", im.info.get("duration", 100)) or 100)))
        else:
            self.frames.append(im.convert("RGBA"))
            self.durs.append(0)

    @property
    def animated(self):
        return len(self.frames) > 1

    @property
    def size(self):
        return self.frames[0].size


class ThemeArt:
    def __init__(self, app, theme: dict):
        self.app = app
        self.root = app.root
        self.slots: dict[str, _Slot] = {}
        bg = theme.get("background") or {}
        self.gradient = bg if (bg.get("tipo", "degradado") == "degradado" and bg.get("colores")) else None
        self.sections = theme.get("sections") or {}
        self.layer_alpha = theme.get("layer_alpha") or {}
        self._anims: list[dict] = []
        self._idle = False
        self._pause = theme.get("gif_pause", True) is not False    # el tema puede pedir no pausarlos
        self._photos: dict = {}                     # referencias vivas de PhotoImage
        self._grad_full = None                      # (tamaño, imagen) del degradado de la ventana
        if HAVE_PIL and theme.get("image_slots") and theme.get("file"):
            self._load(theme)

    # ------------------------------------------------------------------ carga
    def _load(self, theme):
        from . import npt, themes
        try:
            t, _ = npt.read_file(os.path.join(themes.themes_dir(), theme["file"]), images=True)
        except Exception:
            return
        for slot, data in (t.get("images") or {}).items():
            try:
                self.slots[slot] = _Slot(data)
            except Exception:
                continue

    @property
    def active(self) -> bool:
        return bool(self.slots or self.gradient or self.sections)

    def has(self, slot) -> bool:
        return slot in self.slots

    # ------------------------------------------------------------------ colores
    def under(self) -> str:
        """Color que queda debajo de los paneles (promedio del degradado o el fondo)."""
        return gradient_average(self.gradient["colores"]) if self.gradient else C["bg"]

    def layer(self, token) -> float:
        """Opacidad propia de una capa del tema (0–1); 1 si no tiene."""
        try:
            return max(0.0, min(1.0, float(self.layer_alpha.get(token, 100)) / 100))
        except (TypeError, ValueError):
            return 1.0

    def section(self, name) -> dict:
        return self.sections.get(name) or {}

    def tweak_colors(self):
        """Antes de crear la ventana: panel, pestañas y bordes según las secciones."""
        if not self.active:
            return
        base = self.under()
        body = self.section("body") or self.section("left")
        if body and body.get("fondo", 100) < 100:
            C["panel"] = mix(base, C["panel"], body["fondo"] / 100)
        if self.gradient:
            C["bg"] = base                         # lo que no se dibuja con el degradado
        tabs = self.section("tabs")
        C["tab_bg"] = mix(base, mix(C["bg"], C["panel"], .5), (tabs.get("fondo", 100) / 100) if tabs else 1)
        if tabs and tabs.get("fondo", 100) < 100:
            C["tab_on"] = mix(base, C["panel"], tabs["fondo"] / 100)

    def content(self, section, color, plate=None):
        """Color de un texto según la transparencia del «contenido» de su sección."""
        sec = self.section(section)
        a = sec.get("contenido", 100) if sec else 100
        if a >= 100:
            return color
        return mix(plate or self.under(), color, a / 100)

    def realce(self, section) -> bool:
        return bool(self.section(section).get("realce"))

    # ------------------------------------------------------------------ fondos compuestos
    def window_gradient(self, W, H):
        if not (self.gradient and HAVE_PIL) or W < 2 or H < 2:
            return None
        if self._grad_full and self._grad_full[0] == (W, H):
            return self._grad_full[1]
        img = gradient_image(W, H, self.gradient["colores"], self.gradient.get("desde", "tl"))
        self._grad_full = ((W, H), img)
        return img

    def compose(self, w, h, box=None, slot=None, section=None, plate_color=None, base_color=None):
        """Fondo de una zona (PIL RGB): degradado (recorte `box` de la ventana) o color,
        plancha de la sección y, encima, la imagen del espacio (cubriendo)."""
        if not HAVE_PIL or w < 2 or h < 2:
            return None
        base = None
        if self.gradient and box is not None:
            g = self.window_gradient(self.root.winfo_width(), self.root.winfo_height())
            if g is not None:
                x, y = box
                base = g.crop((x, y, x + w, y + h)).convert("RGBA")
        if base is None:
            base = Image.new("RGBA", (w, h), _rgb(base_color or C["bg"]) + (255,))
        sec = self.section(section) if section else {}
        if sec and sec.get("fondo", 100) > 0:
            plate = Image.new("RGBA", (w, h), _rgb(plate_color or C["panel"]) + (int(255 * sec.get("fondo", 100) / 100),))
            base.alpha_composite(plate)
        if slot and slot in self.slots:
            base.alpha_composite(cover(self.slots[slot].frames[0], w, h))
        return base.convert("RGB")

    @staticmethod
    def average(img, box=None) -> str:
        if img is None:
            return C["bg"]
        if box:
            W, H = img.size
            x0, y0, x1, y1 = (int(v) for v in box)
            x0, y0 = max(0, min(W - 1, x0)), max(0, min(H - 1, y0))
            x1, y1 = max(x0 + 1, min(W, x1)), max(y0 + 1, min(H, y1))
            box = (x0, y0, x1, y1)
        im = img.crop(box) if box else img
        px = im.resize((1, 1), Image.BOX).getpixel((0, 0))
        return _hex(px)

    def photo(self, key, pil):
        if pil is None:
            return None
        ph = aa._photo(self.root, pil)
        self._photos[key] = ph
        return ph

    # ------------------------------------------------------------------ espacios libres (con GIF)
    def fit_size(self, slot, max_w, max_h):
        s = self.slots.get(slot)
        if s is None:
            return 0, 0
        iw, ih = s.size
        k = min(max_w / iw, max_h / ih)
        return max(1, int(iw * k)), max(1, int(ih * k))

    def frames_for(self, slot, max_w, max_h, mode="contain", backdrop=None):
        """PhotoImages de un espacio ajustados al tamaño, con sus duraciones. `backdrop` (PIL):
        lo que hay detrás, para que los bordes transparentes del GIF se vean bien sobre el degradado."""
        s = self.slots.get(slot)
        if s is None or max_w < 2 or max_h < 2:
            return [], []
        out = []
        for i, fr in enumerate(s.frames):
            im = contain(fr, max_w, max_h) if mode == "contain" else cover(fr, max_w, max_h)
            if backdrop is not None:
                base = backdrop.convert("RGBA").resize(im.size) if backdrop.size != im.size else backdrop.convert("RGBA")
                base.alpha_composite(im)
                im = base
            out.append(aa._photo(self.root, im))
        return out, list(s.durs)

    def show(self, slot, setter, max_w, max_h, mode="contain", key=None, backdrop=None):
        """Pone el espacio con `setter(photo)`; si es GIF lo anima. Devuelve (ancho, alto) o None."""
        frames, durs = self.frames_for(slot, max_w, max_h, mode, backdrop)
        if not frames:
            return None
        self.stop(key or slot)
        setter(frames[0])
        self._photos[("frames", key or slot)] = frames
        if len(frames) > 1:
            a = {"key": key or slot, "frames": frames, "durs": durs, "i": 0, "set": setter, "job": None}
            self._anims.append(a)
            self._schedule(a)
        return frames[0].width(), frames[0].height()

    def _schedule(self, a):
        try:
            a["job"] = self.root.after(a["durs"][a["i"]] or 100, lambda: self._tick(a))
        except tk.TclError:
            pass

    def _tick(self, a):
        a["job"] = None
        if a not in self._anims:
            return
        try:
            visible = self.root.winfo_viewable()
        except tk.TclError:
            return
        if visible and not self._idle:
            a["i"] = (a["i"] + 1) % len(a["frames"])
            try:
                a["set"](a["frames"][a["i"]])
            except tk.TclError:                    # el widget ya no existe
                self._anims.remove(a)
                return
        self._schedule(a)

    def stop(self, key=None):
        for a in list(self._anims):
            if key is None or a["key"] == key:
                if a["job"]:
                    try:
                        self.root.after_cancel(a["job"])
                    except tk.TclError:
                        pass
                self._anims.remove(a)

    def set_idle(self, idle: bool):
        """Con la ventana sin usar (el mouse fuera) los GIF se pausan, como en el Estudio."""
        self._idle = bool(idle) and self._pause


# ================================================================ textos dibujados en un lienzo
class CanvasText:
    """Texto sobre un lienzo que se usa como una tk.Label (configure/cget), para que el fondo
    (degradado o imagen) se vea detrás de las letras."""

    def __init__(self, cv, font, fg, section=None, art=None, relayout=None, anchor="nw", text=""):
        self.cv = cv
        self.section = section
        self.art = art
        self.relayout = relayout
        self._fg = fg
        self.item = cv.create_text(0, 0, anchor=anchor, text=text, font=font, fill=self._color(fg))

    def _color(self, fg):
        return self.art.content(self.section, fg) if (self.art and self.section) else fg

    def configure(self, **kw):
        changed = False
        opts = {}
        if "text" in kw and kw["text"] != self.cv.itemcget(self.item, "text"):
            opts["text"] = kw["text"]
            changed = True
        if "fg" in kw and kw["fg"] is not None:
            self._fg = kw["fg"]
            opts["fill"] = self._color(kw["fg"])
        if "font" in kw:
            opts["font"] = kw["font"]
            changed = True
        if opts:
            try:
                self.cv.itemconfigure(self.item, **opts)
            except tk.TclError:
                return
        if changed and self.relayout:
            self.relayout()

    config = configure

    def cget(self, key):
        if key == "text":
            return self.cv.itemcget(self.item, "text")
        if key in ("fg", "foreground"):
            return self._fg
        return self.cv.itemcget(self.item, key)

    def width(self):
        b = self.cv.bbox(self.item)
        return (b[2] - b[0]) if b and self.cv.itemcget(self.item, "text") else 0

    def height(self):
        b = self.cv.bbox(self.item)
        return (b[3] - b[1]) if b else 0

    def move_to(self, x, y):
        self.cv.coords(self.item, x, y)

    def bind(self, seq, fn):
        self.cv.tag_bind(self.item, seq, fn)


class CanvasPill(CanvasText):
    """Indicador con fondo de píldora y clic (el «Modo macros» del encabezado)."""

    def __init__(self, cv, font, command, art=None, relayout=None, section=None):
        self._bg = C["panel2"]
        self.pill = cv.create_image(0, 0, anchor="nw")
        super().__init__(cv, font, C["muted"], section=section, art=art, relayout=relayout)
        self.command = command
        for it in (self.pill, self.item):
            cv.tag_bind(it, "<Button-1>", lambda e: self.command and self.command())
            cv.tag_bind(it, "<Enter>", lambda e: cv.configure(cursor="hand2"))
            cv.tag_bind(it, "<Leave>", lambda e: cv.configure(cursor=""))
        self._img = None

    def configure(self, **kw):
        if "bg" in kw:
            self._bg = kw.pop("bg")
        super().configure(**kw)
        self._paint()

    config = configure

    def _paint(self):
        x, y = self.cv.coords(self.item) or (0, 0)
        w = self.width()
        if not w:
            self.cv.itemconfigure(self.pill, image="")
            return
        h = self.height() + 2
        self._img = aa.key_shape(self.cv, w + 16, h, max(3, h // 3), self._bg, self._bg, 0)
        self.cv.itemconfigure(self.pill, image=self._img or "")
        self.cv.coords(self.pill, x - 8, y - 1)

    def move_to(self, x, y):
        super().move_to(x, y)
        self._paint()

    def width(self):
        w = super().width()
        return w + 16 if w else 0
