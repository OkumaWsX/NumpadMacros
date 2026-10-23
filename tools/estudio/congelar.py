# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Cambios «de una sola vez» en Linux (X11 / XWayland).

Tk dibuja widget por widget y sin búfer para toda la ventana. Al cambiar de pantalla, por ejemplo, se
mapean cientos de ventanitas X que se van pintando de a poco (50–150 ms), y el escritorio muestra todo
ese proceso: la pantalla nueva vacía y llenándose. En monitores de alta frecuencia se ve como un parpadeo.

``Congelar`` toma una foto de lo que se ve, la pone encima como una ventana aparte, hace el cambio por
debajo y quita la foto cuando todo está dibujado. El compositor (KWin) dibuja cada ventana por separado,
así que quitar la foto no obliga a repintar nada: el cambio se ve de una vez.

En Windows y macOS (o si algo falla) no hace nada especial: el cambio se hace directo.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import time
import tkinter as tk


class _XImage(ctypes.Structure):
    _fields_ = [("width", ctypes.c_int), ("height", ctypes.c_int), ("xoffset", ctypes.c_int),
                ("format", ctypes.c_int), ("data", ctypes.c_void_p), ("byte_order", ctypes.c_int),
                ("bitmap_unit", ctypes.c_int), ("bitmap_bit_order", ctypes.c_int),
                ("bitmap_pad", ctypes.c_int), ("depth", ctypes.c_int), ("bytes_per_line", ctypes.c_int),
                ("bits_per_pixel", ctypes.c_int)]


_ERR = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)


class _X11:
    """Lo mínimo de libX11 para leer los píxeles de una ventana (con una conexión propia)."""

    def __init__(self):
        x = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        x.XOpenDisplay.restype = ctypes.c_void_p
        x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x.XGetImage.restype = ctypes.POINTER(_XImage)
        x.XGetImage.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
                                ctypes.c_uint, ctypes.c_ulong, ctypes.c_int]
        x.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x.XFree.argtypes = [ctypes.c_void_p]
        x.XSetErrorHandler.restype = ctypes.c_void_p
        x.XSetErrorHandler.argtypes = [ctypes.c_void_p]
        self.x = x
        self.d = x.XOpenDisplay(None)
        if not self.d:
            raise OSError("sin conexión a X")
        self._failed = False

        def on_error(_d, _e):
            self._failed = True
            return 0
        self._handler = _ERR(on_error)              # se guarda: si no, Python lo libera

    def grab(self, win, w, h):
        """Píxeles de la ventana (PIL RGB), o None. Mientras tanto usa su propio manejador de errores de X
        y después deja el de Tk: el de Xlib por defecto cierra el programa ante cualquier error."""
        from PIL import Image
        x = self.x
        prev = x.XSetErrorHandler(ctypes.cast(self._handler, ctypes.c_void_p))
        self._failed = False
        try:
            p = x.XGetImage(self.d, win, 0, 0, w, h, 0xFFFFFFFF, 2)       # ZPixmap
            x.XSync(self.d, 0)
            if self._failed or not p:
                return None
            im = p.contents
            try:
                if im.bits_per_pixel != 32 or im.depth < 24:
                    return None
                buf = ctypes.string_at(im.data, im.bytes_per_line * im.height)
                return Image.frombuffer("RGBX", (im.width, im.height), buf, "raw", "BGRX", im.bytes_per_line,
                                        1).convert("RGB")
            finally:
                x.XFree(im.data)
                x.XFree(p)
        finally:
            x.XSetErrorHandler(prev)


_X = None


def _x11(root):
    global _X
    if _X is None:
        try:
            if root.tk.call("tk", "windowingsystem") != "x11":
                raise OSError("no es X11")
            _X = _X11()
        except Exception:
            _X = False
    return _X or None


class Congelar:
    """``Congelar(root).hacer(cambio)``: hace ``cambio()`` sin que se vea a medio dibujar."""

    _activo = None

    def __init__(self, root):
        self.root = root

    ESPERA_MAX = .3                              # nunca se espera más que esto para quitar la foto

    def hacer(self, cambio, despues=None, listo=None):
        """``listo()``: True cuando lo nuevo ya está dibujado del todo (por ejemplo, la vista previa, que se
        arma en otro hilo); hasta entonces la foto sigue encima, como mucho ESPERA_MAX segundos."""
        act = Congelar._activo
        if act is not None:                      # ya hay una foto encima: el cambio va por debajo
            act._cambios.append(cambio)
            return
        top = self._foto()
        if top is None:
            cambio()
            if despues:
                despues()
            return
        Congelar._activo = self
        self._top, self._cambios, self._despues, self._listo = top, [cambio], despues, listo
        self._t0 = time.monotonic()
        top.update_idletasks()                   # la foto ya dibujada antes de tocar nada debajo
        self.root.after(16, self._cambiar)       # un cuadro para que el escritorio la muestre

    def _foto(self):
        x = _x11(self.root)
        if x is None:
            return None
        r = self.root
        try:
            r.update_idletasks()
            w, h = r.winfo_width(), r.winfo_height()
            if w < 2 or h < 2 or not r.winfo_viewable():
                return None
            im = x.grab(r.winfo_id(), w, h)
            if im is None:
                return None
            from PIL import ImageTk
            top = tk.Toplevel(r, bd=0, highlightthickness=0)
            top.withdraw()
            top.overrideredirect(True)
            top.geometry(f"{w}x{h}+{r.winfo_rootx()}+{r.winfo_rooty()}")
            top._photo = ImageTk.PhotoImage(im, master=top)
            tk.Label(top, image=top._photo, bd=0, highlightthickness=0).pack()
            top.deiconify()
            return top
        except Exception:
            return None

    def _cambiar(self):
        try:
            while self._cambios:
                self._cambios.pop(0)()
            self.root.update_idletasks()        # geometría y dibujo pendientes de lo nuevo
        finally:
            # las ventanitas recién mostradas se pintan al llegar sus avisos de X: se dan dos vueltas
            self.root.after(25, self._soltar)

    def _soltar(self):
        if self._cambios:                        # llegaron más cambios mientras tanto
            self._cambiar()
            return
        if self._listo is not None and time.monotonic() - self._t0 < self.ESPERA_MAX:
            try:
                ready = self._listo()
            except Exception:
                ready = True
            if not ready:
                self.root.after(10, self._soltar)
                return
        if not getattr(self, "_synced", False):
            # update() (no solo update_idletasks) se sincroniza con el servidor X y procesa los avisos de
            # «esta ventanita quedó a la vista»: recién ahí Tk pinta lo que se acaba de mostrar
            self._synced = True
            try:
                self.root.update()
            except tk.TclError:
                pass
            self.root.after(1, self._soltar)     # puede haber traído más cambios o dibujos pendientes
            return
        try:
            self.root.update_idletasks()
        finally:
            Congelar._activo = None
            try:
                self._top.destroy()
            except tk.TclError:
                pass
            if self._despues:
                self._despues()
