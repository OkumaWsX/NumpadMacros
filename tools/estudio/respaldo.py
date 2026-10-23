# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Pantallas que el servidor X guarda ya dibujadas (Linux: X11 / XWayland).

Tk dibuja widget por widget. Si cada pestaña se esconde y se vuelve a mostrar, al volver hay que pintar
cientos de widgets y el escritorio muestra la pestaña llenándose (100–300 ms; en monitores de alta
frecuencia, como un parpadeo). Por eso todas las pestañas quedan puestas una encima de otra y se trae al
frente la elegida (``tkraise``), y a cada una se le pide al servidor X que guarde su contenido aunque
esté tapada («backing store»). Al traerla al frente aparece de una vez, sin repintarse.

Tk no tiene una opción para eso, así que se pide con libX11 (ctypes) por una conexión propia. En Windows y
macOS, o si algo falla, no hace nada: las pestañas igual funcionan, solo que se repintan.
"""
from __future__ import annotations

import ctypes
import ctypes.util

_ERR = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
_CW_BACKING_STORE = 1 << 6
_ALWAYS = 2


class _Attrs(ctypes.Structure):           # XSetWindowAttributes
    _fields_ = [("background_pixmap", ctypes.c_ulong), ("background_pixel", ctypes.c_ulong),
                ("border_pixmap", ctypes.c_ulong), ("border_pixel", ctypes.c_ulong),
                ("bit_gravity", ctypes.c_int), ("win_gravity", ctypes.c_int), ("backing_store", ctypes.c_int),
                ("backing_planes", ctypes.c_ulong), ("backing_pixel", ctypes.c_ulong),
                ("save_under", ctypes.c_int), ("event_mask", ctypes.c_long),
                ("do_not_propagate_mask", ctypes.c_long), ("override_redirect", ctypes.c_int),
                ("colormap", ctypes.c_ulong), ("cursor", ctypes.c_ulong)]


_X = None


def _x11():
    global _X
    if _X is None:
        try:
            x = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
            x.XOpenDisplay.restype = ctypes.c_void_p
            x.XOpenDisplay.argtypes = [ctypes.c_char_p]
            x.XChangeWindowAttributes.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong,
                                                  ctypes.POINTER(_Attrs)]
            x.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
            x.XSetErrorHandler.restype = ctypes.c_void_p
            x.XSetErrorHandler.argtypes = [ctypes.c_void_p]
            d = x.XOpenDisplay(None)
            if not d:
                raise OSError("sin conexión a X")
            _X = (x, d)
        except Exception:
            _X = False
    return _X or None


def guardar_contenido(widgets) -> bool:
    """Pide «backing store» para las ventanas X de esos widgets. True si se pudo."""
    widgets = list(widgets)
    if not widgets or widgets[0].tk.call("tk", "windowingsystem") != "x11":
        return False
    xd = _x11()
    if xd is None:
        return False
    x, d = xd
    failed = []
    handler = _ERR(lambda _d, _e: failed.append(1) or 0)
    # mientras tanto, un manejador de errores propio; después vuelve el de Tk (el de Xlib por defecto
    # cierra el programa ante cualquier error)
    prev = x.XSetErrorHandler(ctypes.cast(handler, ctypes.c_void_p))
    try:
        a = _Attrs()
        a.backing_store = _ALWAYS
        for w in widgets:
            x.XChangeWindowAttributes(d, w.winfo_id(), _CW_BACKING_STORE, ctypes.byref(a))
        x.XSync(d, 0)
    finally:
        x.XSetErrorHandler(prev)
    return not failed
