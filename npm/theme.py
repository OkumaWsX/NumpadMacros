# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Colores, fuentes y nombres que comparten todas las ventanas."""
from .capture import PLATFORM

IS_WIN, IS_MAC, IS_LINUX = PLATFORM == "win", PLATFORM == "mac", PLATFORM == "linux"
FONT = {"win": "Segoe UI", "mac": "Helvetica Neue", "linux": "DejaVu Sans"}[PLATFORM]
BASE = 13 if IS_MAC else 10           # macOS dibuja las fuentes más chicas
OS_NAME = {"win": "Windows", "mac": "macOS", "linux": "Linux"}[PLATFORM]
MOD_LABEL = {"ctrl": "Ctrl", "shift": "Shift", "alt": "Option" if IS_MAC else "Alt",
             "win": "Cmd" if IS_MAC else ("Win" if IS_WIN else "Super")}

C = {
    "bg": "#14161b", "panel": "#1c1f26", "panel2": "#232730", "line": "#2e333d",
    "text": "#e9e9ec", "muted": "#8b909b", "accent": "#f2a33a", "accent_dim": "#7a5520",
    "accent_hover": "#ffb855", "accent_bg": "#3a2c14", "on_accent": "#1a1306",
    "key": "#262a33", "key_set": "#1f3a4f", "key_set_line": "#3d7aa8", "key_set_text": "#bfe0ff",
    "key_global": "#33294a", "key_global_line": "#7e5fc4", "key_global_text": "#d9c9ff",
    "ok": "#4cc38a", "on_ok": "#06210f", "bad": "#e5534b", "warn": "#e2b340",
}
ORIGINAL = dict(C)

# Nombre en los temas (.npt y docs/temas/temas.json) -> nombre en C
TOKENS = {"bg": "bg", "panel": "panel", "panel2": "panel2", "line": "line", "text": "text",
          "muted": "muted", "on_acc": "on_accent", "acc": "accent", "acc_hover": "accent_hover",
          "acc_dim": "accent_dim", "acc_bg": "accent_bg", "key": "key", "key_set": "key_set",
          "key_set_line": "key_set_line", "key_set_text": "key_set_text", "key_global": "key_global",
          "key_global_line": "key_global_line", "key_global_text": "key_global_text",
          "ok": "ok", "on_ok": "on_ok", "bad": "bad", "warn": "warn"}

# Los 12 colores que se pueden elegir para cada botón (iguales en todos los temas)
BUTTON_COLORS = [("Naranja", "#f2a33a"), ("Amarillo", "#e2c340"), ("Lima", "#9bd14a"),
                 ("Verde", "#4cc38a"), ("Turquesa", "#3cc7c0"), ("Celeste", "#6aa8ff"),
                 ("Azul", "#4a6cf0"), ("Morado", "#9b7fe0"), ("Rosa", "#e06fb8"),
                 ("Rojo", "#e5534b"), ("Café", "#b07a4a"), ("Gris", "#8b909b")]


def button_color(act):
    """Color elegido para una tecla (hex) o None."""
    try:
        i = int((act or {}).get("color", -1))
    except (TypeError, ValueError):
        return None
    return BUTTON_COLORS[i][1] if 0 <= i < len(BUTTON_COLORS) else None


def mix(c1: str, c2: str, t: float) -> str:
    """Mezcla dos colores (#rrggbb): t=0 -> c1, t=1 -> c2."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def apply_theme(colors: dict | None):
    """Cambia C a los colores de un tema (antes de crear las ventanas)."""
    C.clear()
    C.update(ORIGINAL)
    for k, v in (colors or {}).items():
        if k in TOKENS and isinstance(v, str) and len(v) == 7 and v.startswith("#"):
            C[TOKENS[k]] = v.lower()
