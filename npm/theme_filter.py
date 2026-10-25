# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Buscador, filtros y orden de la pestaña Temas (sin ventana: se prueba aparte).

Cada elemento de la lista es {"th": tema instalado o None, "entry": entrada del catálogo o None}.
facts() saca de él lo que sirve para filtrar; si el catálogo no lo dice (temas incluidos o
importados que no están en el catálogo), se deduce del propio tema: el estilo por lo oscuro del
fondo, el color por el acento y los extras por lo que trae el archivo.
"""
import colorsys
import re
import unicodedata

# los mismos tonos que usa el armador del catálogo (NumpadMacros-Temas/tools/armar_catalogo.py)
COLORES = (("rojo", 0), ("naranja", 25), ("amarillo", 50), ("verde", 120), ("celeste", 185),
           ("azul", 225), ("morado", 270), ("rosa", 320), ("rojo", 360))
# orden y muestra de cada color en el filtro
SWATCH = {"rojo": "#e5534b", "naranja": "#ff8a3d", "amarillo": "#f2c14e", "verde": "#57d38c",
          "celeste": "#4cc2ff", "azul": "#3f6fe8", "morado": "#9a7ce0", "rosa": "#ff5fae", "gris": "#9a9a9a"}
EXTRAS = ("imagenes", "gif", "transparencia", "degradado")
ORDERS = ("nombre", "recientes", "oficiales")

DEFAULT = {"q": "", "origen": "todos", "mostrar": "todos", "estilo": "todos", "color": "",
           "extras": [], "orden": "nombre"}


def new_filters() -> dict:
    return {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULT.items()}


def active(filt: dict) -> bool:
    """¿Hay algún filtro puesto? (el orden no cuenta)."""
    return bool(filt.get("q", "").strip() or filt.get("origen", "todos") != "todos"
                or filt.get("mostrar", "todos") != "todos" or filt.get("estilo", "todos") != "todos"
                or filt.get("color") or filt.get("extras"))


def clear(filt: dict) -> None:
    """Quita los filtros (deja el orden)."""
    orden = filt.get("orden", "nombre")
    filt.clear()
    filt.update(new_filters(), orden=orden)


# ------------------------------------------------------------------------------- colores
def _rgb(hexcol):
    try:
        return tuple(int(hexcol[i:i + 2], 16) / 255 for i in (1, 3, 5))
    except (TypeError, ValueError, IndexError):
        return (.5, .5, .5)


def luminance(hexcol: str) -> float:
    """Luminancia relativa (0 negro … 1 blanco)."""
    def lin(c):
        return c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in _rgb(hexcol))
    return .2126 * r + .7152 * g + .0722 * b


def color_name(hexcol: str) -> str:
    """El color como nombre simple (igual que el catálogo)."""
    r, g, b = _rgb(hexcol)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if s < .18 or l < .08 or l > .95:
        return "gris"
    deg = h * 360
    return min(COLORES, key=lambda c: abs(c[1] - deg))[0]


def _plain(text) -> str:
    """Minúsculas y sin tildes (para buscar «oceano» y encontrar «Océano»)."""
    s = unicodedata.normalize("NFKD", str(text or "")).casefold()
    return "".join(c for c in s if not unicodedata.combining(c))


# ------------------------------------------------------------------------------- datos de un tema
def facts(it: dict, has_update=None) -> dict:
    """Lo que se sabe de un elemento para filtrarlo y ordenarlo.
    ``has_update(entry, th)``: la función del catálogo (se pasa para no depender de él aquí)."""
    th, e = it.get("th"), it.get("entry")
    colors = (th or {}).get("colors") or (e or {}).get("colores") or {}
    if th is not None:
        name = th.get("name", "")
        official = bool(th.get("builtin") or th.get("official"))
        author = "OkumaWsX" if official else str(th.get("author") or "")
    else:
        name = e.get("nombre", "")
        official = e.get("origen") == "oficial"
        author = str(e.get("autor") or "")
    # creador digital: lo dice la entrada del catálogo (su archivo va firmado con la clave oficial,
    # por eso un tema instalado que corresponde a esa entrada también cuenta como creador)
    creator = bool(e is not None and e.get("origen") == "creador" and not (th or {}).get("builtin"))
    creator_name = str(e.get("creador") or e.get("autor") or "") if creator else ""
    if creator:
        official = False
    # estilo: lo que diga el tema o el catálogo; si no, por lo claro del fondo
    style = (th or {}).get("kind") or (e or {}).get("estilo")
    if not isinstance(style, str) or style not in ("oscuro", "claro"):
        style = "claro" if luminance(colors.get("bg", "#000000")) > .4 else "oscuro"
    color = (e or {}).get("color")
    color = color if isinstance(color, str) and color else color_name(colors.get("acc", "#888888"))
    # extras: los del archivo instalado mandan; si no está instalado, los del catálogo
    ex = set()
    if th is not None:
        if th.get("image_slots"):
            ex.add("imagenes")
        if th.get("animated_slots"):
            ex.add("gif")
        if isinstance(th.get("alpha"), dict) or any(
                min(s.get("fondo", 100), s.get("contenido", 100)) < 100
                for s in (th.get("sections") or {}).values() if isinstance(s, dict)):
            ex.add("transparencia")
        bg = th.get("background") or {}
        if bg.get("tipo", "degradado") == "degradado" and bg.get("colores"):
            ex.add("degradado")
    elif e is not None:
        x = e.get("extras")
        x = x if isinstance(x, dict) else {}       # un catálogo raro puede traer una lista u otra cosa
        for key, k in (("imagenes", "imagenes"), ("animado", "gif"), ("transparencia", "transparencia"),
                       ("degradado", "degradado")):
            if x.get(key):
                ex.add(k)
    tags = (e or {}).get("etiquetas")
    tags = [t for t in tags if isinstance(t, str)] if isinstance(tags, (list, tuple)) else []
    date = (e or {}).get("fecha") or (th or {}).get("created")
    date = date if isinstance(date, str) else ""
    name = name if isinstance(name, str) else str(name or "")
    upd = bool(th is not None and e is not None and has_update is not None and has_update(e, th))
    return {"name": name, "author": author, "official": official, "creator": creator,
            "creator_name": creator_name, "installed": th is not None,
            "update": upd, "style": style, "color": color, "extras": ex, "date": date,
            "builtin": bool((th or {}).get("builtin")),
            "text": _plain(" ".join([name, author, creator_name] + tags))}


# ------------------------------------------------------------------------------- filtrar y ordenar
def matches(f: dict, filt: dict) -> bool:
    """¿El tema (sus facts) pasa los filtros?"""
    words = _plain(filt.get("q", "")).split()
    if any(w not in f["text"] for w in words):
        return False
    origen = filt.get("origen", "todos")
    if (origen == "oficial" and not f["official"] or origen == "creador" and not f["creator"]
            or origen == "comunidad" and (f["official"] or f["creator"])):
        return False
    show = filt.get("mostrar", "todos")
    if (show == "instalados" and not f["installed"] or show == "disponibles" and f["installed"]
            or show == "actualizar" and not f["update"]):
        return False
    style = filt.get("estilo", "todos")
    if style in ("oscuro", "claro") and f["style"] != style:
        return False
    if filt.get("color") and f["color"] != filt["color"]:
        return False
    return all(x in f["extras"] for x in filt.get("extras") or [])


def _ymd(date: str):
    """(año, mes, día) de una fecha AAAA-MM-DD (admite una hora detrás); None si no es una fecha válida."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})(?!\d)", date.strip()) if isinstance(date, str) else None
    return tuple(int(g) for g in m.groups()) if m else None


def sort_key(f: dict, orden: str):
    name = _plain(f["name"])
    if orden == "recientes":
        # las fechas van como AAAA-MM-DD: invertir los dígitos ordena de la más nueva a la más vieja
        d = _ymd(f["date"])
        return (d is None, tuple(-n for n in d) if d else (), name)
    if orden == "oficiales":
        # oficiales, luego creadores, luego comunidad
        return (0 if f["official"] else 1 if f["creator"] else 2, not f["builtin"], name)
    return (name,)


def apply(items: list, filt: dict, get_facts=lambda it: it["facts"]) -> list:
    """Los elementos que pasan los filtros, en el orden elegido."""
    orden = filt.get("orden", "nombre")
    out = [it for it in items if matches(get_facts(it), filt)]
    out.sort(key=lambda it: sort_key(get_facts(it), orden))
    return out


def colors_in(items: list, get_facts=lambda it: it["facts"]) -> list:
    """Los colores que tienen los temas de la lista (en el orden del arcoíris)."""
    have = {get_facts(it)["color"] for it in items}
    return [c for c in SWATCH if c in have]
