# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Utilidades del sistema: una sola instancia e inicio automático (Windows, Linux, macOS)."""
import os
import sys

from .config import config_dir

APP = "NumpadMacros"
_lock = None


def resource(*parts) -> str:
    """Ruta a un archivo incluido con la app (funciona también empaquetada)."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def open_url(url: str) -> bool:
    """Abre un enlace en el navegador. En Linux, con la app empaquetada, se limpia
    el entorno para que el navegador no herede las librerías de la app."""
    if sys.platform.startswith("linux") and getattr(sys, "frozen", False):
        import shutil
        import subprocess
        from .soundboard import clean_env
        opener = shutil.which("xdg-open")
        if opener:
            try:
                subprocess.Popen([opener, url], env=clean_env(), stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
                return True
            except OSError:
                pass
    import webbrowser
    return webbrowser.open(url, new=2)


def single_instance() -> bool:
    """False si ya hay otra copia abierta."""
    global _lock
    if sys.platform == "win32":
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.restype = ctypes.c_void_p
        _lock = k32.CreateMutexW(None, False, "Local\\NumpadMacros_instancia")
        return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS
    import fcntl
    os.makedirs(config_dir(), exist_ok=True)
    _lock = open(os.path.join(config_dir(), "instancia.lock"), "w")
    try:
        fcntl.flock(_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def release_instance():
    """Suelta el candado de instancia única (antes de abrir la versión nueva)."""
    global _lock
    try:
        if _lock is not None and hasattr(_lock, "close"):
            _lock.close()
    except Exception:
        pass
    _lock = None


def _command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--minimizado"]
    exe = sys.executable
    if sys.platform == "win32":
        pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.isfile(pyw):
            exe = pyw
    return [exe, os.path.abspath(sys.argv[0]), "--minimizado"]


# ------------------------------------------------------------------ rutas por sistema
def _linux_file():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "autostart", "numpad-macros.desktop")


def _mac_file():
    return os.path.expanduser("~/Library/LaunchAgents/com.numpadmacros.app.plist")


def autostart_enabled() -> bool:
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
                winreg.QueryValueEx(k, APP)
                return True
        except OSError:
            return False
    return os.path.isfile(_mac_file() if sys.platform == "darwin" else _linux_file())


def set_autostart(on: bool):
    cmd = _command()
    if sys.platform == "win32":
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run",
                            0, winreg.KEY_SET_VALUE) as k:
            if on:
                winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, " ".join(f'"{c}"' for c in cmd))
            else:
                try:
                    winreg.DeleteValue(k, APP)
                except OSError:
                    pass
        return
    path = _mac_file() if sys.platform == "darwin" else _linux_file()
    if not on:
        if os.path.isfile(path):
            os.remove(path)
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if sys.platform == "darwin":
        from xml.sax.saxutils import escape
        args = "".join(f"<string>{escape(c)}</string>" for c in cmd)
        text = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                '<plist version="1.0"><dict>'
                '<key>Label</key><string>com.numpadmacros.app</string>'
                f'<key>ProgramArguments</key><array>{args}</array>'
                '<key>RunAtLoad</key><true/></dict></plist>\n')
    else:
        import shlex
        text = ("[Desktop Entry]\nType=Application\nName=Numpad Macros\n"
                f"Exec={' '.join(shlex.quote(c) for c in cmd)}\n"
                "X-GNOME-Autostart-enabled=true\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
