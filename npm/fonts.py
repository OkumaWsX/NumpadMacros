# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Fuente de la interfaz: Inter (incluida en assets/fonts, licencia SIL OFL 1.1).

Se registra solo para este programa (no se instala en el sistema), así la
ventana se ve igual en Windows, macOS y cualquier Linux. Si algo falla se usa
la fuente del sistema.
"""
import ctypes
import ctypes.util
import os
import sys

FAMILY = "Inter"
FILES = ("Inter-Regular.ttf", "Inter-Bold.ttf")


def _paths():
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths = [os.path.join(base, "assets", "fonts", f) for f in FILES]
    return [p for p in paths if os.path.isfile(p)]


def _linux(paths):
    try:
        import _tkinter  # noqa: F401  (carga Tk y su fontconfig: hay que usar ese mismo)
    except Exception:
        pass
    lib = None
    for name in ("libfontconfig.so.1", ctypes.util.find_library("fontconfig")):
        if not name:
            continue
        try:
            lib = ctypes.CDLL(name)
            break
        except OSError:
            continue
    if lib is None:
        return False
    lib.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.FcConfigAppFontAddFile.restype = ctypes.c_int
    return all(lib.FcConfigAppFontAddFile(None, os.fsencode(p)) for p in paths)


def _windows(paths):
    gdi = ctypes.windll.gdi32
    gdi.AddFontResourceExW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_void_p]
    FR_PRIVATE = 0x10
    return all(gdi.AddFontResourceExW(p, FR_PRIVATE, None) > 0 for p in paths)


def _mac(paths):
    cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    ct = ctypes.CDLL("/System/Library/Frameworks/CoreText.framework/CoreText")
    cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
    cf.CFURLCreateFromFileSystemRepresentation.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                                           ctypes.c_long, ctypes.c_bool]
    cf.CFRelease.argtypes = [ctypes.c_void_p]
    ct.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool
    ct.CTFontManagerRegisterFontsForURL.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
    ok = True
    for p in paths:
        raw = os.fsencode(p)
        url = cf.CFURLCreateFromFileSystemRepresentation(None, raw, len(raw), False)
        if not url:
            ok = False
            continue
        ok = ct.CTFontManagerRegisterFontsForURL(url, 1, None) and ok    # 1 = solo este proceso
        cf.CFRelease(url)
    return ok


def load(fallback: str) -> str:
    """Registra Inter para este proceso y devuelve el nombre de fuente a usar."""
    if os.environ.get("NUMPAD_MACROS_SYSTEM_FONT"):
        return fallback
    paths = _paths()
    if len(paths) != len(FILES):
        return fallback
    try:
        if sys.platform.startswith("linux"):
            ok = _linux(paths)
        elif sys.platform == "win32":
            ok = _windows(paths)
        elif sys.platform == "darwin":
            ok = _mac(paths)
        else:
            ok = False
    except Exception:
        ok = False
    return FAMILY if ok else fallback
