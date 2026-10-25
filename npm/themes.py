# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Temas de colores: los incluidos y los importados (.npt)."""
import hashlib
import os

from . import npt
from .config import config_dir

AUTHOR = "OkumaWsX"
# (nombre, colores) — los mismos de docs/temas/temas.json
BUILTIN = [
    ('Original', {"bg":"#14161b","panel":"#1c1f26","panel2":"#232730","line":"#2e333d","text":"#e9e9ec","muted":"#8b909b","on_acc":"#1a1306","acc":"#f2a33a","acc_hover":"#ffb855","acc_dim":"#7a5520","acc_bg":"#3a2c14","key":"#262a33","key_set":"#1f3a4f","key_set_line":"#3d7aa8","key_set_text":"#bfe0ff","key_global":"#33294a","key_global_line":"#7e5fc4","key_global_text":"#d9c9ff","ok":"#4cc38a","on_ok":"#06210f","bad":"#e5534b","warn":"#e2b340"}),
    ('Medianoche', {"bg":"#0b1220","panel":"#111a2e","panel2":"#18233b","line":"#26334f","text":"#e6edf8","muted":"#93a1bb","on_acc":"#04121c","acc":"#4cc2ff","acc_hover":"#7ad3ff","acc_dim":"#1e5f80","acc_bg":"#0f2b3d","key":"#1b2640","key_set":"#163a52","key_set_line":"#3b8fc4","key_set_text":"#cdeaff","key_global":"#2b2350","key_global_line":"#8a74e0","key_global_text":"#ded6ff","ok":"#3fd29a","bad":"#ff6b6b","warn":"#f5c451","on_ok":"#06210f"}),
    ('Bosque', {"bg":"#0f1712","panel":"#15201a","panel2":"#1c2a22","line":"#2a3b30","text":"#e7f0e9","muted":"#93a89a","on_acc":"#102000","acc":"#a6d94a","acc_hover":"#bde56f","acc_dim":"#56742a","acc_bg":"#25331a","key":"#1f2d25","key_set":"#1d3b33","key_set_line":"#3f9a7f","key_set_text":"#c9f2e4","key_global":"#2f2a42","key_global_line":"#8f7bd0","key_global_text":"#e0d8fb","ok":"#57d38c","bad":"#ff6f61","warn":"#f0c75e","on_ok":"#06210f"}),
    ('Vino', {"bg":"#1a0f13","panel":"#24141a","panel2":"#2e1a22","line":"#43262f","text":"#f6e9ec","muted":"#b39aa2","on_acc":"#241600","acc":"#e8b54a","acc_hover":"#f2c96e","acc_dim":"#7d5c1e","acc_bg":"#3a2915","key":"#33202a","key_set":"#3b2236","key_set_line":"#b0577c","key_set_text":"#ffd3e4","key_global":"#2c2448","key_global_line":"#8e7ad6","key_global_text":"#e2dafe","ok":"#5bd08f","bad":"#ff6b70","warn":"#f2c14e","on_ok":"#06210f"}),
    ('Grafito', {"bg":"#121212","panel":"#1b1b1b","panel2":"#242424","line":"#333333","text":"#ececec","muted":"#9a9a9a","on_acc":"#ffffff","acc":"#2860f0","acc_hover":"#1d4fd4","acc_dim":"#1d3f8f","acc_bg":"#16213d","key":"#2a2a2a","key_set":"#1d3346","key_set_line":"#4a8fd0","key_set_text":"#cfe6ff","key_global":"#312a45","key_global_line":"#8d78d8","key_global_text":"#dfd6ff","ok":"#3ccf8e","bad":"#ff5c5c","warn":"#f3c13a","on_ok":"#06210f"}),
    ('Synthwave', {"bg":"#140d22","panel":"#1d1331","panel2":"#261a3f","line":"#3a2a5a","text":"#f3eaff","muted":"#a796c4","on_acc":"#2a0016","acc":"#ff4fa3","acc_hover":"#ff79ba","acc_dim":"#8a2a5a","acc_bg":"#3a1430","key":"#2a1f45","key_set":"#18304f","key_set_line":"#3fb6e8","key_set_text":"#c9f0ff","key_global":"#3a1f52","key_global_line":"#b07cff","key_global_text":"#ead9ff","ok":"#43e5a8","bad":"#ff5c7a","warn":"#ffd166","on_ok":"#06210f"}),
    ('Océano', {"bg":"#0c1719","panel":"#112124","panel2":"#172b2f","line":"#244045","text":"#e4f2f2","muted":"#8fb0b2","on_acc":"#2a0d06","acc":"#ff7a59","acc_hover":"#ff9a80","acc_dim":"#8a3d2a","acc_bg":"#3a1f18","key":"#1a3034","key_set":"#123c46","key_set_line":"#36a3b8","key_set_text":"#c8f3fb","key_global":"#2a2748","key_global_line":"#8b7fd9","key_global_text":"#ddd8ff","ok":"#4fd1a1","bad":"#ff6363","warn":"#f4c24f","on_ok":"#06210f"}),
    ('Claro', {"bg":"#eef0f4","panel":"#ffffff","panel2":"#f3f4f7","line":"#d5d9e0","text":"#1b1e24","muted":"#5d6470","on_acc":"#ffffff","acc":"#a85600","acc_hover":"#924a00","acc_dim":"#e8b77a","acc_bg":"#fff1dd","key":"#e8eaef","key_set":"#dcebfa","key_set_line":"#3b7fc0","key_set_text":"#123a63","key_global":"#ece5fb","key_global_line":"#7a5cc9","key_global_text":"#3b2a72","ok":"#16834f","bad":"#c62f28","warn":"#8a6300","on_ok":"#ffffff"}),
    ('Papel', {"bg":"#efe6d6","panel":"#f8f2e6","panel2":"#efe5d3","line":"#d6c7ab","text":"#2b2116","muted":"#6b5b45","on_acc":"#ffffff","acc":"#8f4a1c","acc_hover":"#a5582a","acc_dim":"#cfa27e","acc_bg":"#f2dfc9","key":"#e7dcc6","key_set":"#d9e6dc","key_set_line":"#4f8a68","key_set_text":"#1d3b2a","key_global":"#e6dcf0","key_global_line":"#7a5c9e","key_global_text":"#3a2752","ok":"#2f7a46","bad":"#b23a2a","warn":"#7d5a00","on_ok":"#ffffff"}),
    ('Nórdico', {"bg":"#242933","panel":"#2e3440","panel2":"#3b4252","line":"#4c566a","text":"#eceff4","muted":"#aab3c5","on_acc":"#1b2430","acc":"#88c0d0","acc_hover":"#a3d3e0","acc_dim":"#3f6470","acc_bg":"#33414d","key":"#3b4252","key_set":"#35506a","key_set_line":"#81a1c1","key_set_text":"#e5efff","key_global":"#4a3f5c","key_global_line":"#b48ead","key_global_text":"#f3e6ff","ok":"#a3be8c","bad":"#e0707a","warn":"#ebcb8b","on_ok":"#06210f"}),
    ('Atardecer', {"bg":"#1c1316","panel":"#26191d","panel2":"#311f25","line":"#4a2e35","text":"#fbece6","muted":"#c2a39d","on_acc":"#2b1000","acc":"#ff8a3d","acc_hover":"#ffa366","acc_dim":"#8c4a1e","acc_bg":"#3d2216","key":"#36232a","key_set":"#2f2440","key_set_line":"#d06a9a","key_set_text":"#ffd6ea","key_global":"#2c2547","key_global_line":"#9d86e6","key_global_text":"#e4dcff","ok":"#5fd39a","on_ok":"#06210f","bad":"#ff6b6b","warn":"#ffcb57"}),
]


def themes_dir() -> str:
    return os.path.join(config_dir(), "Temas")


def builtin() -> list[dict]:
    return [{"name": n, "author": AUTHOR, "version": "1.0", "colors": dict(c), "official": True,
             "file": "", "builtin": True} for n, c in BUILTIN]


def imported() -> list[dict]:
    """Temas .npt de la carpeta de temas (los dañados se saltan)."""
    out = []
    folder = themes_dir()
    try:
        names = sorted(os.listdir(folder), key=str.lower)
    except OSError:
        return out
    for f in names:
        if not f.lower().endswith(npt.EXT):
            continue
        try:
            t, official = npt.read_file(os.path.join(folder, f))
        except npt.NptError:
            continue
        t.update(official=official, file=f, builtin=False)
        out.append(t)
    return out


def extras(th: dict) -> str:
    """Lo que trae un tema del Estudio además de los colores (para mostrarlo en la pestaña Temas)."""
    parts = []
    bg = th.get("background") or {}
    if bg.get("tipo", "degradado") == "degradado" and bg.get("colores"):
        parts.append(f"fondo degradado de {len(bg['colores'])} colores")
    slots = th.get("image_slots") or []
    if slots:
        parts.append(f"{len(slots)} imagen" + ("" if len(slots) == 1 else "es"))
    secs = th.get("sections") or {}
    if secs:
        parts.append(f"transparencia en {len(secs)} secci" + ("ón" if len(secs) == 1 else "ones"))
    return ("Trae " + ", ".join(parts) + ".") if parts else ""


def all_themes() -> list[dict]:
    return builtin() + imported()


def current(cfg: dict) -> dict:
    sel = cfg.get("theme") or {}
    for t in all_themes():
        if t["name"] == sel.get("name") and t.get("file", "") == sel.get("file", ""):
            return t
    return builtin()[0]


def _ver(v) -> tuple:
    from .updater import parse_version
    return parse_version(str(v or "0"))


def same_theme(a: dict, b: dict) -> bool:
    """¿Son el mismo tema? Mismo nombre interno y misma firma: los dos oficiales, o los dos de la
    comunidad con la misma clave de autor (la huella). Un tema sin firma de autor no se reconoce por
    el nombre: dos «Neón» sin firma pueden ser de gente distinta."""
    if a.get("builtin") or b.get("builtin") or a.get("name", "").casefold() != b.get("name", "").casefold():
        return False
    if a.get("official") or b.get("official"):
        return bool(a.get("official")) and bool(b.get("official"))
    ka, kb = a.get("author_key") or "", b.get("author_key") or ""
    return bool(ka) and ka.lower() == kb.lower()


def plan_install(new: dict, installed: list[dict]) -> tuple[str, dict | None]:
    """Decide qué hacer con un tema que llega (importado o descargado). Función pura: no toca el disco.

    ``new`` y cada tema de ``installed`` son dicts de tema; ``sha256`` (si está) es la huella del archivo.
    Devuelve ``(acción, tema_instalado)``:
      - ``"igual"``: ya lo tienes (mismo contenido, o misma versión y misma firma): no se copia;
      - ``"actualizar"``: es el mismo tema con versión más nueva: reemplaza al instalado;
      - ``"anterior"``: es el mismo tema con una versión más vieja: hay que preguntar;
      - ``"nuevo"``: no hay uno igual (``None``): se copia con un nombre de archivo libre.
    """
    sha = new.get("sha256")
    if sha:
        twin = next((t for t in installed if t.get("sha256") == sha and not t.get("builtin")), None)
        if twin is not None:
            return "igual", twin
    same = [t for t in installed if same_theme(new, t)]
    if not same:
        return "nuevo", None
    v = _ver(new.get("version"))
    # si hay varias copias (de antes de esta regla), se toma la de versión más alta: es la que cuenta
    cur = max(same, key=lambda t: _ver(t.get("version")))
    if v == _ver(cur.get("version")):
        return "igual", cur
    return ("actualizar" if v > _ver(cur.get("version")) else "anterior"), cur


def _safe_base(name: str) -> str:
    return "".join(c if c.isalnum() or c in " -_" else "_" for c in name).strip() or "tema"


def free_path(name: str) -> str:
    """Ruta libre en la carpeta de temas para un tema llamado ``name`` («Nombre.npt», «Nombre (2).npt»…)."""
    base = _safe_base(name)
    dest = os.path.join(themes_dir(), base + npt.EXT)
    n = 2
    while os.path.exists(dest):
        dest = os.path.join(themes_dir(), f"{base} ({n}){npt.EXT}")
        n += 1
    return dest


def write_atomic(dest: str, data: bytes) -> None:
    """Guarda ``data`` en ``dest`` de una vez: nunca queda un tema a medias."""
    tmp = dest + ".nuevo"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, dest)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def installed_with_sha() -> list[dict]:
    """Los temas de la carpeta, cada uno con la huella SHA256 de su archivo."""
    out = imported()
    for t in out:
        try:
            with open(os.path.join(themes_dir(), t["file"]), "rb") as f:
                t["sha256"] = hashlib.sha256(f.read()).hexdigest()
        except OSError:
            pass
    return out


def install(path: str, downgrade: bool = False) -> dict:
    """Instala un .npt en la carpeta de temas. Devuelve el tema (NptError si no sirve), con ``result``:
    ``"nuevo"``, ``"igual"`` (ya lo tenías: no se copió), ``"actualizado"`` (se reemplazó la versión
    anterior; ``old_version`` dice cuál era) o ``"anterior"`` (es una versión más vieja que la instalada:
    no se copió; vuelve a llamar con ``downgrade=True`` si el usuario quiere reemplazarla)."""
    try:
        with open(path, "rb") as f:
            data = f.read(npt.MAX_SIZE + 1)
    except OSError as e:
        raise npt.NptError(f"No pude leer el archivo: {e}")
    t, official = npt.unpack(data)
    t.update(official=official, builtin=False, sha256=hashlib.sha256(data).hexdigest())
    os.makedirs(themes_dir(), exist_ok=True)
    action, twin = plan_install(t, installed_with_sha())
    if action == "nuevo":
        dest = free_path(t["name"])
        if os.path.abspath(dest) != os.path.abspath(path):
            write_atomic(dest, data)
        t.update(file=os.path.basename(dest), result="nuevo")
        return t
    t.update(file=twin["file"], old_version=twin.get("version"))
    if action == "igual" or (action == "anterior" and not downgrade):
        t.update(version=twin.get("version") if action == "igual" else t.get("version"),
                 result="igual" if action == "igual" else "anterior")
        return t
    dest = os.path.join(themes_dir(), twin["file"])
    if os.path.abspath(dest) != os.path.abspath(path):
        write_atomic(dest, data)                    # reemplaza al instalado (mismo archivo)
    t["result"] = "actualizado"
    return t


def remove(theme: dict) -> None:
    if theme.get("file"):
        try:
            os.remove(os.path.join(themes_dir(), theme["file"]))
        except OSError:
            pass


def export(theme: dict, path: str) -> None:
    """Guarda un tema como .npt (cifrado, sin firma)."""
    data = npt.pack({k: theme[k] for k in ("name", "author", "version", "colors", "alpha") if k in theme})
    with open(path, "wb") as f:
        f.write(data)


def supports_alpha(theme: dict) -> bool:
    return isinstance(theme.get("alpha"), dict)
