# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Envío de atajos en macOS con eventos Quartz (CGEvent).

Requiere dar permiso de Accesibilidad a la app que ejecuta el programa
(Terminal, iTerm o Python) en Ajustes del Sistema → Privacidad y seguridad.
"""
import ctypes
import ctypes.util

from .keys import parse_combo

# Códigos de tecla virtuales de macOS (kVK_*)
MAC_KEYS = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
    "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19,
    "3": 20, "4": 21, "6": 22, "5": 23, "9": 25, "7": 26, "8": 28, "0": 29, "o": 31,
    "u": 32, "i": 34, "p": 35, "l": 37, "j": 38, "k": 40, "n": 45, "m": 46,
    "enter": 36, "tab": 48, "espacio": 49, "retroceso": 51, "esc": 53,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98, "f8": 100,
    "f9": 101, "f10": 109, "f11": 103, "f12": 111, "f13": 105, "f14": 107, "f15": 113,
    "f16": 106, "f17": 64, "f18": 79, "f19": 80, "f20": 90,
    "insert": 114, "inicio": 115, "repag": 116, "supr": 117, "fin": 119, "avpag": 121,
    "izquierda": 123, "derecha": 124, "abajo": 125, "arriba": 126,
    "num0": 82, "num1": 83, "num2": 84, "num3": 85, "num4": 86, "num5": 87,
    "num6": 88, "num7": 89, "num8": 91, "num9": 92,
    "silenciar": 74, "vol-": 73, "vol+": 72,
}
MAC_MODS = {"ctrl": (59, 0x40000), "shift": (56, 0x20000),
            "alt": (58, 0x80000), "win": (55, 0x100000)}   # win = Command

# Uso HID del keypad -> tecla virtual (para devolver teclas sin acción)
HID_TO_MAC = {
    0x53: 71, 0x54: 75, 0x55: 67, 0x56: 78, 0x57: 69, 0x58: 76, 0x59: 83, 0x5A: 84,
    0x5B: 85, 0x5C: 86, 0x5D: 87, 0x5E: 88, 0x5F: 89, 0x60: 91, 0x61: 92, 0x62: 82,
    0x63: 65, 0x67: 81, 0x2A: 51, 0x2B: 48, 0x29: 53, 0x28: 36,
}

_cg = None
MARKER = 0x4E4D50          # se marca en los eventos propios para que la app no los reprocese
USERDATA_FIELD = 42        # kCGEventSourceUserData


def _lib():
    global _cg
    if _cg is None:
        lib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("ApplicationServices"))
        lib.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
        lib.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
        lib.CGEventSetFlags.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        lib.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
        lib.CFRelease.argtypes = [ctypes.c_void_p]
        lib.CGEventSetIntegerValueField.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int64]
        _cg = lib
    return _cg


def post_key(keycode: int, down: bool, flags: int = 0):
    lib = _lib()
    ev = lib.CGEventCreateKeyboardEvent(None, keycode, down)
    if not ev:
        raise RuntimeError("macOS no permitió crear el evento de teclado")
    if flags:
        lib.CGEventSetFlags(ev, flags)
    lib.CGEventSetIntegerValueField(ev, USERDATA_FIELD, MARKER)
    lib.CGEventPost(0, ev)   # kCGHIDEventTap
    lib.CFRelease(ev)


class QuartzSender:
    unsupported = frozenset({"f21", "f22", "f23", "f24", "impr", "pausa", "bloqdespl",
                             "pista_sig", "pista_ant", "detener", "play_pausa"})

    def __init__(self):
        _lib()

    def _parse(self, combo):
        mods, key = parse_combo(combo)
        if key not in MAC_KEYS:
            raise RuntimeError(f"La tecla {key.upper()} no existe en macOS")
        flags = 0
        for m in mods:
            flags |= MAC_MODS[m][1]
        return mods, MAC_KEYS[key], flags

    def press(self, combo: str):
        mods, key, flags = self._parse(combo)
        acc = 0
        for m in mods:
            acc |= MAC_MODS[m][1]
            post_key(MAC_MODS[m][0], True, acc)
        post_key(key, True, flags)

    def release(self, combo: str):
        mods, key, flags = self._parse(combo)
        post_key(key, False, flags)
        acc = flags
        for m in reversed(mods):
            acc &= ~MAC_MODS[m][1]
            post_key(MAC_MODS[m][0], False, acc)


# Tecla virtual de macOS -> id de tecla (fila de números y teclas de la combinación)
MAC_TO_KID = {18: "02", 19: "03", 20: "04", 21: "05", 23: "06", 22: "07",
              26: "08", 28: "09", 25: "0a", 29: "0b", 27: "0c", 24: "0d"}


# F13–F20 del teclado Apple (macOS no tiene F21–F24)
MAC_TO_KID.update({105: "f13", 107: "f14", 113: "f15", 106: "f16", 64: "f17",
                   79: "f18", 80: "f19", 90: "f20"})


def _build_mac_table():
    from .keys import TOGGLE_KEYS
    for name, kid in TOGGLE_KEYS.items():
        if name in MAC_KEYS:
            MAC_TO_KID.setdefault(MAC_KEYS[name], kid)
    MAC_TO_KID.setdefault(107, "46")      # F14 hace de Bloq Despl en teclados de PC


_build_mac_table()


def flags_to_mods(flags: int) -> set:
    return {name for name, (_code, bit) in MAC_MODS.items() if flags & bit}
