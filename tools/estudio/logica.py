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
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
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
SLOT_NAMES = {"banner": "Banner del encabezado", "keys": "Fondo de las teclas", "logo": "Logo junto al título"}
SLOT_DEFAULTS = {
    "banner": {"fit": "cover", "op": 100, "dark": 55, "blur": 0},
    "keys": {"fit": "cover", "op": 100, "dark": 65, "blur": 4},
    "logo": {"fit": "cover", "op": 100, "dark": 0, "blur": 0},
}
FITS = {"cover": "Cubrir (recorta los bordes)", "contain": "Ajustar (se ve completa)",
        "tile": "Mosaico", "center": "Centrar sin escalar"}
TEMPLATES = (
    ("none", "Solo colores", ()),
    ("banner", "Banner", ("banner",)),
    ("keys", "Teclas con fondo", ("keys",)),
    ("full", "Completa", ("banner", "keys", "logo")),
)


def render_slot(src, slot: str, fit: str, op: int, dark: int, blur: int, bg: str, size=None):
    """Prepara la imagen de un espacio tal como se guardará: recorte, desenfoque,
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
