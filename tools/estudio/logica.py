# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Lógica del Estudio de Temas, sin interfaz: colores, legibilidad, colores
desde una imagen, imágenes de los espacios y archivo de proyecto."""
from __future__ import annotations

import base64
import colorsys
import io
import json
import os
import re
import subprocess
import sys
import unicodedata
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # en el repositorio: tools/estudio → raíz
if not os.path.isdir(os.path.join(ROOT, "npm")):       # en local: carpeta hermana «Numpad Macros X.Y.Z»
    import glob
    ROOT = next(iter(sorted(glob.glob(os.path.join(os.path.dirname(HERE), "Numpad Macros *", "")),
                            reverse=True)), ROOT).rstrip(os.sep)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from npm import npt  # noqa: E402

PROJECT_EXT = ".nptproj"

# ---------------------------------------------------------------- colores
def hex2rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb2hex(c) -> str:
    return "#" + "".join(f"{max(0, min(255, round(v))):02x}" for v in c)


def mix(a: str, b: str, t: float) -> str:
    """Mezcla: t=0 da a, t=1 da b."""
    ra, rb = hex2rgb(a), hex2rgb(b)
    return rgb2hex([x + (y - x) * t for x, y in zip(ra, rb)])


def lum(h: str) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in hex2rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a: str, b: str) -> float:
    x, y = lum(a), lum(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


def to_hsl(h: str) -> tuple[float, float, float]:
    r, g, b = (v / 255 for v in hex2rgb(h))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    return hh * 360, ss, ll


def hsl(hh: float, s: float, l: float) -> str:
    s, l = max(0.0, min(1.0, s)), max(0.0, min(1.0, l))
    r, g, b = colorsys.hls_to_rgb((hh % 360) / 360, l, s)
    return rgb2hex((r * 255, g * 255, b * 255))


def clamp(v, a, b):
    return max(a, min(b, v))


def is_dark(colors: dict) -> bool:
    return lum(colors["bg"]) < 0.2


def derive(colors: dict) -> None:
    """Calcula los tonos del acento (pasar el mouse, atenuado y fondo de avisos)."""
    dark = is_dark(colors)
    colors["acc_hover"] = mix(colors["acc"], "#ffffff" if dark else "#000000", 0.18)
    colors["acc_dim"] = mix(colors["acc"], colors["bg"], 0.5)
    colors["acc_bg"] = mix(colors["acc"], colors["bg"], 0.8)


def effective(colors: dict, alpha: dict) -> dict:
    """Colores tal como se ven: cada capa mezclada con la de abajo según su transparencia."""
    out: dict = {}

    def f(k):
        if k not in out:
            p = npt.PARENT.get(k)
            out[k] = mix(f(p), colors[k], alpha.get(k, 100) / 100) if p else colors[k]
        return out[k]

    for k in colors:
        f(k)
    return out


# ---------------------------------------------------------------- legibilidad
# (nombre, texto, fondo, mínimo)
PAIRS = (
    ("Texto sobre fondo", "text", "bg", 4.5),
    ("Texto sobre paneles", "text", "panel", 4.5),
    ("Secundario sobre paneles", "muted", "panel", 3.0),
    ("Botón con acento", "on_acc", "acc", 4.5),
    ("Tecla con acción", "key_set_text", "key_set", 4.5),
    ("Tecla global", "key_global_text", "key_global", 4.5),
    ("Botón ACTIVO", "on_ok", "ok", 4.5),
    ("Selección en listas", "text", "acc_dim", 3.0),
)
WINDOW_WARN, WINDOW_BAD = 75, 60


def legibility(colors: dict, alpha: dict, window: dict) -> list[tuple[str, float, float, str]]:
    """Lista de (nombre, contraste, mínimo, estado) con estado ok / warn / bad."""
    e = effective(colors, alpha)
    out = []
    for name, f, b, mn in PAIRS:
        r = ratio(e[f], e[b])
        out.append((name, r, mn, "ok" if r >= mn else ("warn" if r >= mn * 0.75 else "bad")))
    op = window.get("opacidad", 100)
    if op < WINDOW_WARN:
        out.append(("Opacidad de la ventana", float(op), WINDOW_WARN, "bad" if op < WINDOW_BAD else "warn"))
    return out


def fix_legibility(colors: dict, alpha: dict) -> list[str]:
    """Aclara u oscurece solo el texto que no se lee. Devuelve las capas que cambió."""
    changed = []
    for _name, f, b, mn in PAIRS:
        if f == "text" and b == "acc_dim":       # se arregla con el acento, no con el texto
            continue
        for _ in range(40):
            e = effective(colors, alpha)
            if ratio(e[f], e[b]) >= mn:
                break
            hh, s, l = to_hsl(colors[f])
            step = -0.025 if lum(e[b]) > 0.18 else 0.025
            if (step < 0 and l <= 0) or (step > 0 and l >= 1):
                break
            colors[f] = hsl(hh, s, l + step)
            if f not in changed:
                changed.append(f)
    return changed


# ---------------------------------------------------------------- colores desde una imagen
def extract_palette(img, k: int = 6) -> list[tuple[str, float]]:
    """Colores principales de una imagen (PIL), del más usado al menos usado: [(hex, fracción)]."""
    from PIL import Image
    im = img.convert("RGBA")
    im.thumbnail((128, 128))
    bg = Image.new("RGBA", im.size, (0, 0, 0, 0))
    im = Image.alpha_composite(bg, im)
    raw = im.tobytes()
    opaque = [raw[i:i + 3] for i in range(0, len(raw), 4) if raw[i + 3] > 128]
    if not opaque:
        return []
    flat = Image.frombytes("RGB", (len(opaque), 1), b"".join(opaque))
    q = flat.quantize(colors=k, method=Image.Quantize.MEDIANCUT, kmeans=4)
    pal = q.getpalette()
    counts = sorted(q.getcolors(), reverse=True)
    total = sum(c for c, _ in counts)
    out = []
    for c, i in counts:
        out.append((rgb2hex(pal[i * 3:i * 3 + 3]), c / total))
    return out


def pick_accent(palette: list[tuple[str, float]]) -> int:
    best, score = 0, -1.0
    for i, (c, n) in enumerate(palette):
        _h, s, l = to_hsl(c)
        sc = s * (1 - abs(l - 0.58) * 1.4) * (0.55 + min(n * 4, 1) * 0.45)
        if sc > score:
            best, score = i, sc
    return best


def _hue_far(palette, avoid, min_deg):
    for c, _n in palette:
        hh, s, _l = to_hsl(c)
        if s > 0.15 and all(min(abs(hh - a), 360 - abs(hh - a)) > min_deg for a in avoid):
            return hh
    return None


def palette_to_theme(palette, accent: int, dark: bool, current: dict) -> dict:
    """Reparte los colores de la imagen en las 22 capas. Estados (bien, error, aviso) se mantienen."""
    h0, s0, _ = to_hsl(palette[0][0])
    bs = min(s0, 0.32)
    ha, sa, la = to_hsl(palette[accent][0])
    sa = max(sa, 0.55)
    h2 = _hue_far(palette, [ha], 35)
    h2 = ha + 150 if h2 is None else h2
    h3 = _hue_far(palette, [ha, h2], 35)
    h3 = h2 + 70 if h3 is None else h3
    if dark:
        t = dict(bg=hsl(h0, bs, .08), panel=hsl(h0, bs, .11), panel2=hsl(h0, bs, .145), line=hsl(h0, bs * .9, .21),
                 key=hsl(h0, bs, .165), text=hsl(h0, .14, .93), muted=hsl(h0, .1, .62),
                 acc=hsl(ha, sa, clamp(la, .52, .68)),
                 key_set=hsl(h2, .38, .2), key_set_line=hsl(h2, .5, .48), key_set_text=hsl(h2, .6, .88),
                 key_global=hsl(h3, .34, .2), key_global_line=hsl(h3, .48, .52), key_global_text=hsl(h3, .6, .9))
    else:
        t = dict(bg=hsl(h0, bs * .8, .955), panel=hsl(h0, bs * .6, .985), panel2=hsl(h0, bs * .8, .925),
                 line=hsl(h0, bs * .6, .82), key=hsl(h0, bs * .7, .9), text=hsl(h0, .25, .13), muted=hsl(h0, .12, .4),
                 acc=hsl(ha, sa, clamp(la, .36, .46)),
                 key_set=hsl(h2, .45, .88), key_set_line=hsl(h2, .45, .52), key_set_text=hsl(h2, .55, .22),
                 key_global=hsl(h3, .4, .9), key_global_line=hsl(h3, .42, .55), key_global_text=hsl(h3, .5, .24))
    out = dict(current)
    out.update(t)
    out["on_acc"] = hsl(ha, .5, .08) if lum(out["acc"]) > 0.3 else "#ffffff"
    out["on_ok"] = "#06210f" if lum(out["ok"]) > 0.3 else "#ffffff"
    derive(out)
    return out


# ---------------------------------------------------------------- imágenes de los espacios
# espacio -> (nombre, grupo «Detrás»/«Libre», ajustes por defecto)
SLOTS = {
    "banner": ("Banner del encabezado", "Detrás", {"fit": "cover", "op": 100, "dark": 55, "blur": 0}),
    "keys": ("Fondo de las teclas", "Detrás", {"fit": "cover", "op": 100, "dark": 65, "blur": 4}),
    "corner": ("Pestaña · parte de abajo, detrás de los botones", "Detrás",
               {"fit": "cover", "op": 100, "dark": 45, "blur": 0}),
    "footband": ("Pie · banda completa, detrás de los botones", "Detrás",
                 {"fit": "cover", "op": 100, "dark": 45, "blur": 0}),
    "logo": ("Logo junto al título", "Libre", {"fit": "cover", "op": 100, "dark": 0, "blur": 0}),
    "headmid": ("Encabezado · espacio central", "Libre", {"fit": "contain", "op": 100, "dark": 0, "blur": 0}),
    "tabsend": ("Pestañas · espacio al final", "Libre", {"fit": "contain", "op": 100, "dark": 0, "blur": 0}),
    "leftbot": ("Panel de teclas · espacio de abajo", "Libre", {"fit": "cover", "op": 100, "dark": 35, "blur": 0}),
    "foot": ("Pie · espacio libre", "Libre", {"fit": "contain", "op": 100, "dark": 0, "blur": 0}),
}
SLOT_NAMES = {k: v[0] for k, v in SLOTS.items()}
SLOT_DEFAULTS = {k: dict(v[2]) for k, v in SLOTS.items()}
FREE = tuple(k for k, v in SLOTS.items() if v[1] == "Libre" and k != "logo")
FITS = {"cover": "Cubrir (recorta los bordes)", "contain": "Ajustar (se ve completa)",
        "tile": "Mosaico", "center": "Centrar sin escalar"}
TEMPLATES = (
    ("none", "Solo colores", ()),
    ("banner", "Banner", ("banner",)),
    ("keys", "Teclas con fondo", ("keys",)),
    ("full", "Completa", ("banner", "keys", "logo")),
    ("stickers", "Stickers animados", FREE),
    ("todo", "Todo", tuple(k for k in SLOTS if k != "foot")),
)
# imágenes de ejemplo de la plantilla «Stickers animados» (las demás usan la imagen de los colores)
TEMPLATE_SAMPLES = {"headmid": "ecualizador", "foot": "ecualizador", "tabsend": "estrellas"}
MAX_SOURCE = 1600                     # lado máximo de la imagen original que se guarda en el proyecto


MAX_DECODE = 160_000_000              # píxeles en total (todos los cuadros) que se aceptan al abrir


def load_frames(data: bytes, max_side: int = MAX_SOURCE) -> list:
    """Cuadros de una imagen (GIF, PNG animado o imagen fija): [(imagen RGBA, milisegundos)].
    Cada cuadro se achica a ``max_side`` apenas se lee, y se rechazan imágenes gigantes."""
    from PIL import Image, ImageSequence
    im = Image.open(io.BytesIO(data))
    n = min(getattr(im, "n_frames", 1), npt.MAX_FRAMES)
    if im.width * im.height * n > MAX_DECODE:
        raise ValueError("La imagen es demasiado grande (o tiene demasiados cuadros de ese tamaño).")
    frames = []
    for fr in ImageSequence.Iterator(im):
        dur = int(fr.info.get("duration") or im.info.get("duration") or 100)
        f = fr.convert("RGBA")
        if max(f.size) > max_side:
            f.thumbnail((max_side, max_side))
        frames.append((f, max(20, dur)))
        if len(frames) >= npt.MAX_FRAMES:
            break
    return frames or [(im.convert("RGBA"), 100)]


def frame_count(data: bytes) -> int:
    from PIL import Image
    try:
        return min(getattr(Image.open(io.BytesIO(data)), "n_frames", 1), npt.MAX_FRAMES)
    except Exception:
        return 1


def source_count(data: bytes) -> int:
    """Cuadros de la imagen original (sin recortar), para avisar si pasa de 120."""
    from PIL import Image
    try:
        return getattr(Image.open(io.BytesIO(data)), "n_frames", 1)
    except Exception:
        return 1


def encode(frames) -> bytes:
    """Una imagen fija como PNG; varios cuadros como PNG animado (conserva la transparencia)."""
    if len(frames) == 1:
        return to_png(frames[0][0])
    buf = io.BytesIO()
    first = frames[0][0]
    first.save(buf, "PNG", save_all=True, append_images=[f for f, _d in frames[1:]],
               duration=[d for _f, d in frames], loop=0, disposal=1, blend=0, optimize=True)
    return buf.getvalue()


def prepare_source(data: bytes) -> bytes:
    """Imagen importada lista para guardar en el proyecto: tamaño razonable y todos sus cuadros."""
    return encode(load_frames(data))


def render_slot(src, slot: str, fit: str, op: int, dark: int, blur: int, bg: str, size=None):
    """Prepara una imagen (un cuadro) tal como se guardará: recorte, desenfoque,
    oscurecido con el color de fondo y opacidad. Devuelve una imagen PIL RGBA."""
    from PIL import Image, ImageFilter
    w, h = size or npt.IMAGE_SLOTS[slot]
    im = src.convert("RGBA")
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if fit == "cover":
        sc = max(w / im.width, h / im.height)
        r = im.resize((max(1, round(im.width * sc)), max(1, round(im.height * sc))), Image.LANCZOS)
        out.paste(r, ((w - r.width) // 2, (h - r.height) // 2))
    elif fit == "contain":
        sc = min(w / im.width, h / im.height)
        r = im.resize((max(1, round(im.width * sc)), max(1, round(im.height * sc))), Image.LANCZOS)
        out.paste(r, ((w - r.width) // 2, (h - r.height) // 2))
    elif fit == "tile":
        t = im.copy()
        t.thumbnail((max(16, w // 4), max(16, h // 2)))
        for y in range(0, h, t.height):
            for x in range(0, w, t.width):
                out.paste(t, (x, y))
    else:  # center
        out.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
    if blur:
        out = out.filter(ImageFilter.GaussianBlur(blur))
    if dark:
        a = out.getchannel("A")
        veil = Image.new("RGBA", (w, h), hex2rgb(bg) + (round(255 * dark / 100),))
        out = Image.alpha_composite(out, veil)
        out.putalpha(a)
    if op < 100:
        a = out.getchannel("A").point(lambda v: round(v * op / 100))
        out.putalpha(a)
    return out


def render_slot_frames(data: bytes, slot: str, s: dict, bg: str, size=None, blur_scale: float = 1.0) -> list:
    """Todos los cuadros de un espacio preparados: [(imagen RGBA, milisegundos)]."""
    blur = round(s["blur"] * blur_scale)
    frames = load_frames(data)
    if slot not in npt.ANIMATED_SLOTS:          # detrás del contenido y el logo: imagen fija (primer cuadro)
        frames = frames[:1]
    return [(render_slot(im, slot, s["fit"], s["op"], s["dark"], blur, bg, size=size), d) for im, d in frames]


def _sample_anim(kind: str) -> bytes:
    """GIF de ejemplo para la plantilla «Stickers animados» (dibujado aquí, sin archivos)."""
    from PIL import Image, ImageDraw
    import math
    frames = []
    if kind == "ecualizador":
        w, h, n = 120, 40, 16
        cols = [(255, 111, 190), (190, 120, 255), (110, 150, 255), (60, 205, 200)]
        for i in range(n):
            im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            for b in range(12):
                v = 0.5 + 0.5 * math.sin(i / n * 2 * math.pi * 2 + b * 0.9) * math.cos(b * 0.37 + i / n * 2 * math.pi)
                bh = 6 + v * (h - 10)
                x = 4 + b * 9.6
                d.rounded_rectangle([x, h - 2 - bh, x + 6, h - 2], 2, fill=cols[b * len(cols) // 12])
            frames.append((im, 70))
    else:
        w, h, n = 120, 28, 12
        stars = [(10, 8), (34, 18), (58, 6), (80, 16), (104, 9), (22, 21), (92, 22)]
        for i in range(n):
            im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            for j, (x, y) in enumerate(stars):
                v = 0.5 + 0.5 * math.sin((i / n + j * 0.23) * 2 * math.pi)
                r = 1.2 + v * 3.2
                c = (255, 225, 140, round(90 + 165 * v))
                d.polygon([(x, y - r * 1.6), (x + r * .45, y - r * .45), (x + r * 1.6, y), (x + r * .45, y + r * .45),
                           (x, y + r * 1.6), (x - r * .45, y + r * .45), (x - r * 1.6, y), (x - r * .45, y - r * .45)],
                          fill=c)
            frames.append((im, 90))
    return encode(frames)


_SAMPLES: dict = {}


def sample_anim(kind: str) -> bytes:
    if kind not in _SAMPLES:
        _SAMPLES[kind] = _sample_anim(kind)
    return _SAMPLES[kind]


# ---------------------------------------------------------------- fondo de la ventana: degradado
# desde -> (flecha, «empieza en…», «termina en…»)
GRADIENT_DIRS = {
    "tl": ("↖", "arriba a la izquierda", "abajo a la derecha"), "t": ("↑", "arriba", "abajo"),
    "tr": ("↗", "arriba a la derecha", "abajo a la izquierda"), "l": ("←", "la izquierda", "la derecha"),
    "c": ("●", "el centro", "los bordes"), "r": ("→", "la derecha", "la izquierda"),
    "bl": ("↙", "abajo a la izquierda", "arriba a la derecha"), "b": ("↓", "abajo", "arriba"),
    "br": ("↘", "abajo a la derecha", "arriba a la izquierda"),
}


def gradient_stops(g: dict) -> list:
    return sorted(([c, int(p)] for c, p in g.get("colores", [])), key=lambda s: s[1])


def gradient_color(stops: list, t: float) -> str:
    """Color del degradado en la posición t (0–1)."""
    p = t * 100
    if p <= stops[0][1]:
        return stops[0][0]
    for (c1, p1), (c2, p2) in zip(stops, stops[1:]):
        if p <= p2:
            return mix(c1, c2, 0 if p2 == p1 else (p - p1) / (p2 - p1))
    return stops[-1][0]


_START = {"tl": (0, 0), "t": (.5, 0), "tr": (1, 0), "l": (0, .5), "c": (.5, .5), "r": (1, .5),
          "bl": (0, 1), "b": (.5, 1), "br": (1, 1)}


def gradient_image(g: dict, size):
    """Dibuja el degradado (PIL RGBA) del tamaño pedido, con la misma geometría que Numpad Macros
    (npm/theme_art.py): proyección sobre la línea que va del punto de inicio al opuesto, o circular
    desde el centro hasta las esquinas."""
    from PIL import Image
    w, h = size
    stops = gradient_stops(g)
    frm = g.get("desde", "tl")
    lut = [hex2rgb(gradient_color(stops, i / 255)) for i in range(256)]
    sw = 64
    sh = max(2, round(sw * h / max(w, 1)))
    px = []
    if frm == "c":
        half = 0.5 * (w * w + h * h) ** .5
        for y in range(sh):
            dy = ((y + .5) / sh - .5) * h
            for x in range(sw):
                dx = ((x + .5) / sw - .5) * w
                px.append(round(min(1.0, (dx * dx + dy * dy) ** .5 / half) * 255))
    else:
        sx, sy = _START.get(frm, (0, 0))
        vx, vy = (1 - 2 * sx) * w, (1 - 2 * sy) * h
        l2 = vx * vx + vy * vy or 1
        for y in range(sh):
            v = (y + .5) / sh
            for x in range(sw):
                u = (x + .5) / sw
                tt = ((u - sx) * w * vx + (v - sy) * h * vy) / l2
                px.append(round(max(0.0, min(1.0, tt)) * 255))
    pos = Image.new("L", (sw, sh))
    pos.putdata(px)
    pos = pos.resize((w, h), Image.BILINEAR)
    r = pos.point([c[0] for c in lut])
    gch = pos.point([c[1] for c in lut])
    b = pos.point([c[2] for c in lut])
    return Image.merge("RGBA", (r, gch, b, Image.new("L", (w, h), 255)))


def gradient_avg(g: dict, bg: str) -> str:
    """Color promedio del degradado (con él se mezclan los paneles transparentes)."""
    st = g.get("colores") if g else None
    if not st:
        return bg
    s = [0, 0, 0]
    for c, _p in st:
        for i, v in enumerate(hex2rgb(c)):
            s[i] += v
    return rgb2hex([v / len(st) for v in s])


def gradient_from_theme(colors: dict) -> list:
    return [[colors["bg"], 0], [mix(colors["bg"], colors["acc"], .28), 55],
            [mix(colors["bg"], colors["key_global_line"], .3), 100]]


def gradient_from_palette(palette, dark: bool) -> list:
    cs = [mix("#000000", c, .42) if dark else mix("#ffffff", c, .35) for c, _n in palette[:3]]
    if len(cs) < 2:
        return []
    return [[c, round(i * 100 / (len(cs) - 1))] for i, c in enumerate(cs)]


def gradient_add_stop(stops: list) -> list:
    """Agrega un color en el hueco más grande, mezcla de sus vecinos."""
    st = sorted(stops, key=lambda s: s[1])
    gi, gap = 0, -1
    for i in range(len(st) - 1):
        if st[i + 1][1] - st[i][1] > gap:
            gi, gap = i, st[i + 1][1] - st[i][1]
    return stops + [[mix(st[gi][0], st[gi + 1][0], .5), round((st[gi][1] + st[gi + 1][1]) / 2)]]


def gradient_check(colors: dict, alpha: dict, g: dict):
    """El texto sobre el color más difícil del degradado: (contraste, color, estado)."""
    if not g:
        return None
    e = effective(colors, alpha)
    worst = min(((ratio(e["text"], c), c) for c, _p in g["colores"]), key=lambda x: x[0])
    r = worst[0]
    return r, worst[1], "ok" if r >= 4.5 else ("warn" if r >= 3.4 else "bad")


# ---------------------------------------------------------------- fondo de imagen y «fondo de una pieza»
TINT_DEFAULT = 35
BG_LIMIT = 2_400_000                  # peso máximo de la imagen de fondo dentro del tema (deja sitio al resto)


def cover(img, w, h):
    """Recorta al centro para llenar w×h sin deformar (igual que Numpad Macros)."""
    from PIL import Image
    iw, ih = img.size
    k = max(w / iw, h / ih)
    nw, nh = max(1, int(iw * k + .5)), max(1, int(ih * k + .5))
    im = img.resize((nw, nh), Image.LANCZOS)
    x, y = (nw - w) // 2, (nh - h) // 2
    return im.crop((x, y, x + w, y + h))


def background_png(src: bytes, dark: int, bg: str) -> bytes:
    """Imagen de fondo lista para el tema: hasta 1920 × 1200, oscurecida, y que no pese demasiado."""
    from PIL import Image
    im = load_frames(src, max_side=1920)[0][0].convert("RGB")
    mw, mh = npt.IMAGE_SLOTS["fondo"]
    k = min(1.0, mw / im.width, mh / im.height)
    if k < 1:
        im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    if dark:
        im = Image.blend(im, Image.new("RGB", im.size, hex2rgb(bg)), dark / 100)
    data = to_png(im)
    while len(data) > BG_LIMIT and max(im.size) > 480:
        im = im.resize((round(im.width * .8), round(im.height * .8)), Image.LANCZOS)
        data = to_png(im)
    return data


def background_from_palette(palette, dark: bool, size=(1600, 1000)) -> bytes:
    """Fondo generado con los colores de la paleta: manchas suaves de color, como pintura difuminada."""
    from PIL import Image, ImageDraw, ImageFilter
    w, h = size
    cols = [c for c, _n in palette] or ["#202430"]
    base = cols[0]
    base = mix("#000000", base, .45) if dark else mix("#ffffff", base, .35)
    im = Image.new("RGB", (w // 4, h // 4), hex2rgb(base))
    d = ImageDraw.Draw(im)
    spots = ((.15, .2, .55), (.8, .25, .5), (.55, .75, .6), (.1, .85, .45), (.9, .9, .4), (.45, .35, .35))
    for i, (x, y, r) in enumerate(spots):
        c = cols[(i + 1) % len(cols)]
        c = mix("#000000", c, .6) if dark else mix("#ffffff", c, .55)
        rr = r * min(w, h) / 4
        cx, cy = x * w / 4, y * h / 4
        d.ellipse([cx - rr, cy - rr * .8, cx + rr, cy + rr * .8], fill=hex2rgb(c))
    im = im.filter(ImageFilter.GaussianBlur(min(w, h) / 4 / 7))
    im = im.resize((w, h), Image.BICUBIC)
    return to_png(im)


def image_avg(img) -> str:
    small = img.convert("RGB").resize((1, 1), 4)          # 4 = BOX
    return rgb2hex(small.getpixel((0, 0)))


def background_colors(img, k: int = 5) -> list:
    """Colores principales de la imagen de fondo (para revisar que el texto se lea)."""
    return [c for c, _n in extract_palette(img, k)]


def tint_panel(e: dict, under: str, tint: int) -> str:
    """Color con que se tiñen los paneles en el «fondo de una pieza» (como Numpad Macros)."""
    return mix(under, e["panel"], max(.35, tint / 100))


def one_piece_check(e: dict, colors: list, under: str, tint: int):
    """Texto sobre los paneles de una pieza, en el color más difícil del fondo: (contraste, fondo, estado)."""
    panel = tint_panel(e, under, tint)
    worst = min(((ratio(e["text"], mix(c, panel, tint / 100)), mix(c, panel, tint / 100)) for c in colors),
                key=lambda x: x[0])
    r = worst[0]
    return r, worst[1], "ok" if r >= 4.5 else ("warn" if r >= 3.4 else "bad")


def colors_check(e: dict, colors: list):
    """Texto directamente sobre el fondo (encabezado, pie y bordes): (contraste, color, estado)."""
    worst = min(((ratio(e["text"], c), c) for c in colors), key=lambda x: x[0])
    r = worst[0]
    return r, worst[1], "ok" if r >= 4.5 else ("warn" if r >= 3.4 else "bad")


# ---------------------------------------------------------------- transparencia por sección
SECTIONS = {
    "head": ("Encabezado", "Banda detrás del título y los bancos. Si hay banner, lo tiñe."),
    "left": ("Panel de teclas", "El panel con el selector de capas y las teclas."),
    "keys": ("Teclas", "Solo las teclas. Si hay fondo de teclas, la imagen se ve a través."),
    "tabs": ("Pestañas", "Los botones de las pestañas."),
    "body": ("Panel de la pestaña", "El contenido de la pestaña abierta."),
    "foot": ("Pie", "Banda con Novedades, Soporte y Donar."),
}
PRESETS = {
    "normal": ("Normal", {k: (v["fondo"], v["contenido"], v["realce"]) for k, v in npt.SECTION_DEFAULTS.items()}),
    "teclas": ("Destacar teclas", {"head": (0, 70, 0), "left": (45, 60, 0), "keys": (100, 100, 1),
                                   "tabs": (40, 55, 0), "body": (40, 55, 0), "foot": (0, 55, 0)}),
    "pestana": ("Destacar la pestaña", {"head": (0, 70, 0), "left": (40, 55, 0), "keys": (40, 55, 0),
                                        "tabs": (100, 100, 0), "body": (100, 100, 1), "foot": (0, 55, 0)}),
    "cristal": ("Cristal", {"head": (25, 100, 0), "left": (45, 100, 0), "keys": (55, 100, 0),
                            "tabs": (50, 100, 0), "body": (45, 100, 0), "foot": (25, 100, 0)}),
}


def section(sections: dict, k: str) -> dict:
    return {**npt.SECTION_DEFAULTS[k], **sections.get(k, {})}


def sections_clean(sections: dict) -> dict:
    """Solo las secciones que cambian (lo que se guarda en el tema)."""
    out = {}
    for k in npt.SECTIONS:
        s = section(sections, k)
        if s != npt.SECTION_DEFAULTS[k]:
            out[k] = s
    return out


def preset(pid: str) -> dict:
    return sections_clean({k: {"fondo": f, "contenido": c, "realce": bool(b)}
                           for k, (f, c, b) in PRESETS[pid][1].items()})


def focus(sections: dict, sel: str) -> dict:
    """«Destacar»: la sección elegida a todo color y con realce; las demás atenuadas."""
    out = {}
    for k in npt.SECTIONS:
        s = section(sections, k)
        if k == sel:
            out[k] = {"fondo": 60 if k in ("head", "foot") else 100, "contenido": 100, "realce": True}
        else:
            out[k] = {"fondo": min(s["fondo"], 40), "contenido": 55, "realce": False}
    return sections_clean(out)


def section_rows(colors: dict, alpha: dict, sections: dict, g: dict, images: dict) -> list:
    """Legibilidad de cada sección: [(sección, nombre, contraste, plancha, texto, estado, cambiada, con imagen)]."""
    e = effective(colors, alpha)
    under = gradient_avg(g, e["bg"])
    left = section(sections, "left")
    out = []
    for k, (name, _note) in SECTIONS.items():
        s = section(sections, k)
        base, plate, txt = under, e["panel"], e["text"]
        if k == "keys":
            base, plate, txt = mix(e["bg"], e["panel"], left["fondo"] / 100), e["key_set"], e["key_set_text"]
        elif k == "tabs":
            txt = e["muted"]
        pe = mix(base, plate, s["fondo"] / 100)
        te = mix(pe, txt, s["contenido"] / 100)
        r = ratio(te, pe)
        img = (k == "keys" and "keys" in images) or (k == "head" and "banner" in images)
        out.append((k, name, r, pe, te, "ok" if r >= 4.5 else "warn", s != npt.SECTION_DEFAULTS[k], bool(img)))
    return out


def to_png(im) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def from_bytes(data: bytes):
    from PIL import Image
    im = Image.open(io.BytesIO(data))
    im.load()
    return im


def sample_image():
    """Imagen de ejemplo (un atardecer), para que el Estudio no parta vacío."""
    from PIL import Image, ImageDraw
    w, h = 480, 300
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    top, mid, low = (43, 27, 79), (184, 70, 122), (245, 154, 74)
    for y in range(190):
        t = y / 189
        a, b, u = (top, mid, t / .55) if t < .55 else (mid, low, (t - .55) / .45)
        d.line([(0, y), (w, y)], fill=tuple(round(x + (z - x) * u) for x, z in zip(a, b)))
    d.rectangle([0, 190, w, h], fill=low)
    d.ellipse([286, 121, 374, 209], fill=(255, 211, 110))
    d.polygon([(0, 200), (60, 140), (130, 185), (210, 120), (300, 190), (380, 150), (480, 195), (480, 300), (0, 300)],
              fill=(58, 31, 77))
    d.polygon([(0, 230), (90, 190), (170, 225), (260, 180), (350, 228), (480, 205), (480, 300), (0, 300)],
              fill=(26, 18, 48))
    d.rectangle([0, 255, w, h], fill=(19, 54, 63))
    return im


# ---------------------------------------------------------------- temas incluidos
def themes_path() -> str:
    base = getattr(sys, "_MEIPASS", None)
    for p in ([os.path.join(base, "temas.json")] if base else []) + [os.path.join(ROOT, "docs", "temas", "temas.json")]:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("temas.json")


def builtin_themes() -> list[dict]:
    with open(themes_path(), encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for t in data["escritorio_y_celular"]:
        c = dict(t["colores"])
        c.setdefault("on_ok", "#06210f")
        out.append({"nombre": t["nombre"], "descripcion": t.get("descripcion", ""), "colores": c})
    return out


def slug(s: str) -> str:
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "tema"


# ---------------------------------------------------------------- proyecto (.nptproj)
def save_project(path: str, state: dict) -> None:
    """Guarda el proyecto sin cifrar (solo para quien lo edita). Las imágenes van en base64."""
    data = dict(state)
    data["imagenes"] = {k: {**{kk: vv for kk, vv in v.items() if kk != "src"},
                            "src": base64.b64encode(v["src"]).decode()} for k, v in state.get("imagenes", {}).items()}
    if state.get("imagen_colores"):
        data["imagen_colores"] = base64.b64encode(state["imagen_colores"]).decode()
    data["nptproj"] = 1
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def load_project(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("nptproj") != 1:
        raise ValueError("No es un proyecto del Estudio de Temas.")
    for k, v in (data.get("imagenes") or {}).items():
        v["src"] = base64.b64decode(v["src"])
    if data.get("imagen_colores"):
        data["imagen_colores"] = base64.b64decode(data["imagen_colores"])
    return data


# ---------------------------------------------------------------- enviar a la comunidad
# Lo que Discord admite en una publicación de foro, y lo que exige el catálogo de la Librería de Temas
# (tools/armar_catalogo.py) a un tema de la comunidad.
DISCORD_TITULO_MAX = 100
DISCORD_MENSAJE_MAX = 2000
VERSION_OK = re.compile(r"^\d+(\.\d+){0,2}$")                       # 1, 1.2 o 1.2.3
ID_TEMA_OK = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")                # el «slug» es la carpeta del catálogo
REQUIERE_APP = "3.5.0"                                              # versión mínima de Numpad Macros (la del catálogo)
CARPETA_ENVIOS = "Temas para enviar"
_FORO_OK = re.compile(r"^https://(discord\.com/channels/\d+/\d+|discord\.gg/[A-Za-z0-9-]+)/?$")


def foro_url_valida(url: str) -> bool:
    """¿Es un enlace de Discord que se puede abrir? (canal/foro o invitación; nada más)."""
    return bool(_FORO_OK.match((url or "").strip()))


def recortar(texto: str, maximo: int) -> str:
    """Recorta a ``maximo`` caracteres; si se cortó, termina en «…» (sin pasarse del máximo)."""
    texto = texto or ""
    if len(texto) <= maximo:
        return texto
    return texto[:max(0, maximo - 1)].rstrip() + "…"


def nombre_envio(nombre: str, version: str) -> str:
    """Nombre del archivo que se envía: ``<slug>-<versión>.npt``."""
    ver = re.sub(r"[^0-9.]", "", str(version)) or "1.0"
    return f"{slug(nombre)}-{ver}{npt.EXTENSION}"


def _carpeta_documentos() -> str:
    """La carpeta de documentos del sistema si existe; si no, la carpeta personal."""
    casa = os.path.expanduser("~")
    if sys.platform == "win32":
        try:                                    # respeta la carpeta movida (OneDrive…)
            import ctypes
            from ctypes import wintypes
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and os.path.isdir(buf.value):
                return buf.value
        except Exception:
            pass
    elif sys.platform != "darwin":              # Linux: ~/.config/user-dirs.dirs (XDG_DOCUMENTS_DIR)
        conf = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.join(casa, ".config"), "user-dirs.dirs")
        try:
            with open(conf, encoding="utf-8") as f:
                for linea in f:
                    m = re.match(r'\s*XDG_DOCUMENTS_DIR="?([^"\n]+)"?', linea)
                    if m:
                        d = m.group(1).replace("$HOME", casa)
                        if os.path.isdir(d):
                            return d
        except OSError:
            pass
    for nombre in ("Documents", "Documentos"):
        d = os.path.join(casa, nombre)
        if os.path.isdir(d):
            return d
    return casa


def carpeta_envios() -> str:
    """Carpeta fija donde queda el tema listo para enviar. ``NPT_ENVIOS_DIR`` la redirige (pruebas)."""
    return os.environ.get("NPT_ENVIOS_DIR") or os.path.join(_carpeta_documentos(), CARPETA_ENVIOS)


def problemas_previos(nombre: str, version: str, modo: str, autor: str) -> list[str]:
    """Qué impide enviar el tema a la comunidad, antes de exportar (lista vacía = todo bien)."""
    out = []
    if modo == "creador":
        out.append("Los temas oficiales se publican con el Publicador, no se envían a la comunidad.")
    if not (nombre or "").strip() or not ID_TEMA_OK.match(slug(nombre)):
        out.append("El nombre del tema debe tener al menos 2 letras o números (el catálogo lo usa como identificador).")
    if not VERSION_OK.match((version or "").strip()):
        out.append(f"La versión «{version}» no es válida: usa números separados por puntos (1.0, 1.2.3).")
    if modo != "creador" and npt.is_reserved_name(autor or ""):
        out.append("Ese nombre de autor está reservado para el creador oficial: cámbialo en «Mi firma de autor».")
    return out


def problemas_archivo(data: bytes, version: str) -> list[str]:
    """Lo mismo que revisa el catálogo sobre el ``.npt`` ya firmado (tamaño, firma, oficial, versión)."""
    if len(data) > npt.MAX_SIZE:
        return [f"El tema pesa {len(data) // 1024} KB y el máximo es {npt.MAX_SIZE // 1024} KB."]
    try:
        r = npt.read(data)
    except npt.NptError as e:
        return [f"El archivo no es un tema válido ({e})."]
    out = []
    if r.official:
        out.append("El tema salió con la firma oficial: los temas oficiales se publican con el Publicador.")
    elif r.format < 2 or not r.author_key:
        out.append("El tema no lleva la firma de autor: el catálogo exige que venga firmado por su autor.")
    if r.reserved_name:
        out.append("El tema usa el nombre del creador oficial sin serlo.")
    if r.theme.version != (version or "").strip():
        out.append(f"La versión del archivo ({r.theme.version}) no coincide con la del tema ({version}).")
    return out


def armar_envio(nombre: str, version: str, autor: str, descripcion: str, huella: str,
                version_estudio: str, requiere_app: str = REQUIERE_APP) -> tuple[str, str]:
    """Título y mensaje de la publicación del foro, ya dentro de los límites de Discord."""
    autor = (autor or "").strip() or "Anónimo"
    titulo = recortar(f"{nombre.strip() or 'Sin nombre'} {version} · por {autor}", DISCORD_TITULO_MAX)
    datos = [f"Autor: {autor}", f"Huella de la firma de autor: {huella}"]
    if requiere_app:
        datos.append(f"Requiere Numpad Macros {requiere_app} o superior")
    datos += ["", f"Enviado desde Estudio de Temas {version_estudio}"]
    pie = "\n".join(datos)
    desc = (descripcion or "").strip()
    if not desc:
        return titulo, pie
    # lo que se recorta es la descripción; los datos de la firma siempre van completos
    return titulo, recortar(desc, DISCORD_MENSAJE_MAX - len(pie) - 2) + "\n\n" + pie


def _entorno_limpio() -> dict:
    """Entorno para lanzar programas del sistema desde la app empaquetada (PyInstaller cambia
    LD_LIBRARY_PATH y eso rompe el navegador y el gestor de archivos)."""
    env = os.environ.copy()
    if getattr(sys, "frozen", False):
        orig = env.pop("LD_LIBRARY_PATH_ORIG", None)
        if orig is not None:
            env["LD_LIBRARY_PATH"] = orig
        else:
            env.pop("LD_LIBRARY_PATH", None)
    return env


def abrir_enlace(url: str) -> bool:
    """Abre un enlace con el navegador del sistema (en Linux empaquetado, con el entorno limpio)."""
    if sys.platform.startswith("linux") and getattr(sys, "frozen", False):
        import shutil
        opener = shutil.which("xdg-open")
        if opener:
            try:
                subprocess.Popen([opener, url], env=_entorno_limpio(), stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
                return True
            except OSError:
                pass
    import webbrowser
    return bool(webbrowser.open(url, new=2))


def mostrar_archivo(path: str) -> bool:
    """Abre la carpeta del archivo, dejándolo seleccionado si el gestor de archivos lo permite."""
    import shutil
    path = os.path.abspath(path)
    carpeta = os.path.dirname(path)
    env = _entorno_limpio()
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", path])
            return True
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
            return True
        dbus = shutil.which("dbus-send")
        if dbus and os.path.exists(path):          # Dolphin, Nautilus, Thunar…: la carpeta con el archivo marcado
            r = subprocess.run([dbus, "--session", "--print-reply", "--dest=org.freedesktop.FileManager1",
                                "/org/freedesktop/FileManager1", "org.freedesktop.FileManager1.ShowItems",
                                f"array:string:file://{quote(path)}", "string:"],
                               env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
            if r.returncode == 0:
                return True
        opener = shutil.which("xdg-open")
        if opener:
            subprocess.Popen([opener, carpeta], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            return True
    except (OSError, subprocess.SubprocessError):
        pass
    return False
