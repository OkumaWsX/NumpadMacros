# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Integración con el escritorio de Linux (KDE, GNOME…): agrega la app al menú
con su propio icono, para que la barra de tareas muestre el icono de Numpad Macros
en vez de uno genérico.

El escritorio reconoce la ventana por su clase (WM_CLASS = «NumpadMacros») y la
relaciona con el archivo .desktop que tiene StartupWMClass=NumpadMacros e Icon=.
Todo se guarda en la carpeta del usuario (~/.local/share): no pide contraseña.
"""
import hashlib
import os
import shutil
import subprocess

SIZES = (48, 64, 128, 256, 512)


def data_dir() -> str:
    return os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")


def desktop_text(name, comment, exec_path, icon_name, wm_class, categories) -> str:
    return ("[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={name}\n"
            f"Comment={comment}\n"
            f'Exec="{exec_path}"\n'
            f"Icon={icon_name}\n"
            "Terminal=false\n"
            f"Categories={categories}\n"
            f"StartupWMClass={wm_class}\n"
            "StartupNotify=true\n")


def install(app_id, name, comment, exec_path, icon_png, wm_class,
            categories="AudioVideo;Audio;Utility;", env=None) -> bool:
    """Crea o actualiza el acceso del menú y los iconos. Devuelve True si cambió algo."""
    apps = os.path.join(data_dir(), "applications")
    desktop = os.path.join(apps, f"{app_id}.desktop")
    text = desktop_text(name, comment, exec_path, app_id, wm_class, categories)
    try:                       # si el icono cambia entre versiones, se vuelve a copiar
        with open(icon_png, "rb") as f:
            text += f"X-NumpadMacros-Icon={hashlib.sha1(f.read()).hexdigest()[:12]}\n"
    except OSError:
        pass
    try:
        from PIL import Image
    except Exception:          # sin Pillow: un solo icono grande (el escritorio lo escala)
        Image = None
    sizes = SIZES if Image is not None else (512,)
    icons = [os.path.join(data_dir(), "icons", "hicolor", f"{s}x{s}", "apps", f"{app_id}.png") for s in sizes]
    try:
        with open(desktop, encoding="utf-8") as f:
            current = f.read()
    except OSError:
        current = ""
    if current == text and all(os.path.isfile(p) for p in icons):
        return False
    os.makedirs(apps, exist_ok=True)
    try:
        img = Image.open(icon_png).convert("RGBA") if Image is not None else None
    except Exception:
        img = None
    for size, path in zip(sizes, icons):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if img is not None:
            img.resize((size, size), Image.LANCZOS).save(path)
        else:
            shutil.copyfile(icon_png, path)
    tmp = desktop + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(tmp, 0o755)
    os.replace(tmp, desktop)
    refresh(apps, env)
    return True


def refresh(apps_dir, env=None):
    """Avisa al escritorio que hay accesos/iconos nuevos (si las herramientas existen)."""
    hicolor = os.path.join(data_dir(), "icons", "hicolor")
    for cmd in (["update-desktop-database", apps_dir],
                ["gtk-update-icon-cache", "-f", "-t", hicolor],
                ["kbuildsycoca6"], ["kbuildsycoca5"]):
        if shutil.which(cmd[0]):
            try:
                subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
            except OSError:
                pass
