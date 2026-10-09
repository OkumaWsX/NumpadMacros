# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Capa común de captura: elige el método según el sistema operativo.

Cada backend expone la misma interfaz:
    start(), stop(), learn_device(segundos), set_device(id), connected()
    learns_device  -> True si identifica un numpad concreto
y llama a engine.decide(id_tecla, presionada) por cada tecla del numpad.
"""
import re
import sys

PLATFORM = "win" if sys.platform == "win32" else "mac" if sys.platform == "darwin" else "linux"


class BackendError(RuntimeError):
    pass


# id, título, descripción
MODES = {
    "win": [
        ("interception", "Interception — solo el numpad elegido (recomendado)",
         "Requiere el driver Interception instalado. Los demás teclados no se tocan."),
        ("hook", "Sin driver — teclas numéricas de cualquier teclado",
         "No instala nada, pero también captura el numpad de otros teclados conectados."),
    ],
    "linux": [
        ("evdev", "evdev — solo el numpad elegido",
         "Toma el numpad en exclusiva. La primera vez hay que dar permisos (botón de abajo)."),
    ],
    "mac": [
        ("iokit", "IOKit — solo el numpad elegido",
         "Requiere permisos de Monitoreo de entrada y Accesibilidad para Terminal/Python."),
    ],
}


def modes():
    return MODES[PLATFORM]


def default_mode():
    return MODES[PLATFORM][0][0]


def describe_device(dev_id: str) -> str:
    """Texto corto para mostrar el numpad elegido."""
    if not dev_id:
        return "ninguno"
    m = re.search(r"VID_([0-9A-F]{4}).*PID_([0-9A-F]{4})", dev_id, re.I)   # Windows
    if m:
        return f"VID {m.group(1).upper()} · PID {m.group(2).upper()}"
    parts = dev_id.split(":", 2)                                            # Linux / macOS
    if len(parts) == 3:
        name = parts[2] or "teclado"
        return f"{name} ({parts[0].upper()}:{parts[1].upper()})"
    return dev_id


def create(mode: str, engine, device_id: str):
    if PLATFORM == "win":
        from . import capture_win
        if mode == "hook":
            return capture_win.HookBackend(engine)
        return capture_win.InterceptionBackend(engine, device_id)
    if PLATFORM == "linux":
        from . import capture_linux
        return capture_linux.EvdevBackend(engine, device_id)
    from . import capture_mac
    return capture_mac.IOKitBackend(engine, device_id)
