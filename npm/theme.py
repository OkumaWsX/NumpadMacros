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
    "key": "#262a33", "key_set": "#1f3a4f", "key_set_line": "#3d7aa8",
    "key_global": "#33294a", "key_global_line": "#7e5fc4",
    "ok": "#4cc38a", "bad": "#e5534b", "warn": "#e2b340",
}
