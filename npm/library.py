# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Biblioteca de sonidos propia (reemplaza la lista de Soundpad).

La biblioteca es una lista de archivos guardada en la configuración:
    cfg["library"] = [{"path": "...", "title": "..."}, ...]
Los archivos no se copian: se usan desde donde estén.
"""
import os
import xml.etree.ElementTree as ET

from .soundboard import AUDIO_EXT, title_of


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def is_audio(path: str) -> bool:
    return path.lower().endswith(AUDIO_EXT)


def add(cfg: dict, paths, title: str | None = None) -> int:
    """Agrega archivos (sin repetir). Devuelve cuántos se agregaron."""
    lib = cfg.setdefault("library", [])
    have = {_norm(x["path"]) for x in lib}
    n = 0
    for p in paths:
        if not p or not is_audio(p):
            continue
        key = _norm(p)
        if key in have:
            continue
        lib.append({"path": os.path.abspath(p), "title": title or title_of(p)})
        have.add(key)
        n += 1
    return n


def scan_folder(folder: str, limit: int = 5000) -> list[str]:
    """Todos los audios de una carpeta (y sus subcarpetas), ordenados."""
    found = []
    for root, dirs, files in os.walk(folder):
        dirs.sort(key=str.lower)
        for f in sorted(files, key=str.lower):
            if is_audio(f):
                found.append(os.path.join(root, f))
                if len(found) >= limit:
                    return found
    return found


def read_spl(path: str) -> list[tuple[str, str]]:
    """Lee una lista exportada de Soundpad (.spl). Devuelve [(ruta, título)]."""
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as e:
        raise ValueError(f"No pude leer la lista de Soundpad: {e}")
    base = os.path.dirname(os.path.abspath(path))
    out = []
    for el in root.iter("Sound"):
        url = el.get("url", "")
        if not url:
            continue
        if not os.path.isabs(url):
            url = os.path.join(base, url)
        title = el.get("title") or title_of(url)
        artist = el.get("artist")
        out.append((url, f"{artist} – {title}" if artist else title))
    return out


def import_spl(cfg: dict, path: str) -> tuple[int, int]:
    """Importa una lista .spl. Devuelve (agregados, total en la lista)."""
    items = read_spl(path)
    n = 0
    for url, title in items:
        n += add(cfg, [url], title)
    return n, len(items)


def remove(cfg: dict, paths) -> None:
    drop = {_norm(p) for p in paths}
    cfg["library"] = [x for x in cfg.get("library", []) if _norm(x["path"]) not in drop]


def search(cfg: dict, text: str) -> list[dict]:
    q = text.strip().lower()
    items = cfg.get("library", [])
    if not q:
        return list(items)
    return [x for x in items if q in x["title"].lower() or q in os.path.basename(x["path"]).lower()]


def usage(cfg: dict) -> dict[str, int]:
    """Cuántas teclas usan cada archivo."""
    count: dict[str, int] = {}
    for layer in [cfg["global"]] + [b["keys"] for b in cfg["banks"]]:
        for act in layer.values():
            if act.get("type") == "file" and act.get("path"):
                k = _norm(act["path"])
                count[k] = count.get(k, 0) + 1
    return count


def norm(path: str) -> str:
    return _norm(path)


def migrate_soundpad(cfg: dict) -> int:
    """Convierte las teclas que usaban Soundpad en teclas con archivo propio."""
    changed = 0
    for layer in [cfg["global"]] + [b["keys"] for b in cfg["banks"]]:
        for kid, act in list(layer.items()):
            if act.get("type") != "sound":
                continue
            url = act.get("url", "")
            if url:
                layer[kid] = {"type": "file", "path": url,
                              "title": act.get("title") or title_of(url), "volume": 1.0,
                              "speakers": act.get("speakers", True), "mic": act.get("mic", True),
                              "mode": "overlap"}
                add(cfg, [url], act.get("title"))
            else:
                del layer[kid]
            changed += 1
    return changed
