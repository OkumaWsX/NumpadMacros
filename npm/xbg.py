# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Fondo «nativo» de los widgets ttk en Linux (X11 / XWayland).

Los widgets ttk (marcos, botones, etiquetas…) crean su ventana X sin color de fondo. Cuando la
ventana cambia de tamaño, hasta que Tk los vuelve a dibujar (en XWayland ~1 ms cada uno, toda la
ventana ~60 ms) el servidor gráfico deja ahí lo que había antes: restos de las tarjetas o recuadros
oscuros encima del panel. Con un color de fondo puesto, el servidor rellena ese hueco al instante
con el color del panel del tema, así lo que se ve antes de que Tk termine ya es del color correcto.

Tk no tiene una opción para esto en ttk, así que se pone directamente en la ventana X (con una
conexión propia a la pantalla; el fondo es un atributo del servidor, vale para todas). En Windows
y macOS no hace nada; si algo falla, tampoco (todo sigue como antes)."""
import ctypes
import os
import sys
import tkinter as tk
from tkinter import ttk

_x = None                  # (libX11, Display*) o False si no se puede
_done = {}                 # (widget, id de ventana X) -> píxel ya puesto


def _lib():
    global _x
    if _x is not None:
        return _x
    _x = False
    if not sys.platform.startswith("linux") or not os.environ.get("DISPLAY"):
        return _x
    try:
        lib = ctypes.CDLL("libX11.so.6")
        lib.XOpenDisplay.restype = ctypes.c_void_p
        lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        lib.XSetWindowBackground.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong]
        lib.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        # un error (p. ej. una ventana que ya no existe) no debe cerrar el programa: mientras se
        # ponen los colores se usa un manejador que lo ignora y luego se devuelve el de Tk
        handler = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)(lambda d, e: 0)
        lib.XSetErrorHandler.argtypes = [ctypes.c_void_p]
        lib.XSetErrorHandler.restype = ctypes.c_void_p
        dpy = lib.XOpenDisplay(None)
        if dpy:
            _x = (lib, dpy, handler)
    except Exception:
        _x = False
    return _x


def _usable(root) -> bool:
    try:
        return (root.tk.call("tk", "windowingsystem") == "x11" and root.winfo_visual() == "truecolor"
                and root.winfo_depth() >= 24)
    except tk.TclError:
        return False


def paint(root, only_mapped=False):
    """Pone el color de fondo del estilo a cada ventana ttk (una sola vez por ventana y color).
    Barato si ya está hecho: se puede llamar después de cada cambio de tamaño."""
    if not _usable(root):
        return
    x = _lib()
    if not x:
        return
    lib, dpy, handler = x
    style = ttk.Style(root)
    colors = {}
    changed = False

    def pixel(name):
        if name not in colors:
            try:
                r, g, b = root.winfo_rgb(name)
                colors[name] = ((r >> 8) << 16) | ((g >> 8) << 8) | (b >> 8)
            except tk.TclError:
                colors[name] = None
        return colors[name]

    def walk(w):
        nonlocal changed
        try:
            if only_mapped and not w.winfo_ismapped():
                return
            if isinstance(w, ttk.Widget):
                st = w.cget("style") or w.winfo_class()
                col = style.lookup(st, "background") or style.lookup(w.winfo_class(), "background")
                px = pixel(col) if col else None
                if px is not None:
                    wid = w.winfo_id()
                    key = (str(w), wid)
                    if _done.get(key) != px:
                        _done[key] = px
                        lib.XSetWindowBackground(dpy, wid, px)
                        changed = True
        except tk.TclError:
            return
        for c in w.winfo_children():
            walk(c)
    prev = lib.XSetErrorHandler(ctypes.cast(handler, ctypes.c_void_p))
    try:
        walk(root)
        if changed:
            lib.XSync(dpy, 0)                   # los errores llegan aquí, con nuestro manejador
    finally:
        lib.XSetErrorHandler(prev)


def forget():
    """Al volver a armar la ventana (otro tema): los ids nuevos se vuelven a revisar."""
    _done.clear()
