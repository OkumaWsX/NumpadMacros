# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Envío de atajos con SendInput (Windows)."""
import ctypes
import sys
import threading

from .keys import F_SCANCODES, KEYS, MODIFIERS, parse_combo

MARKER = 0x4E4D50  # dwExtraInfo para reconocer nuestras propias pulsaciones

if sys.platform == "win32":
    from ctypes import wintypes as wt

    ULONG_PTR = ctypes.c_size_t

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                    ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                    ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wt.DWORD), ("wParamL", wt.WORD), ("wParamH", wt.WORD)]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wt.DWORD), ("u", _INPUTUNION)]

    _u32 = ctypes.WinDLL("user32", use_last_error=True)
    _u32.SendInput.argtypes = [wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    _u32.SendInput.restype = wt.UINT
    _u32.MapVirtualKeyW.argtypes = [wt.UINT, wt.UINT]
    _u32.MapVirtualKeyW.restype = wt.UINT

    INPUT_KEYBOARD = 1
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002


class KeySender:
    unsupported: frozenset = frozenset()

    def __init__(self):
        self._lock = threading.Lock()
        self._held: dict[str, int] = {}   # combo -> veces presionado

    @staticmethod
    def _event(vk: int, ext: bool, up: bool):
        scan = F_SCANCODES.get(vk) or _u32.MapVirtualKeyW(vk, 0)  # MAPVK_VK_TO_VSC
        flags = (KEYEVENTF_EXTENDEDKEY if ext else 0) | (KEYEVENTF_KEYUP if up else 0)
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.u.ki = KEYBDINPUT(vk, scan, flags, 0, MARKER)
        return inp

    def _send(self, events):
        arr = (INPUT * len(events))(*events)
        sent = _u32.SendInput(len(events), arr, ctypes.sizeof(INPUT))
        if sent != len(events):
            raise RuntimeError("Windows bloqueó el envío de teclas (¿la ventana activa "
                               "corre como administrador? Ejecuta este programa también "
                               "como administrador)")

    def press(self, combo: str):
        mods, key = parse_combo(combo)
        ev = [self._event(*MODIFIERS[m], False) for m in mods]
        ev.append(self._event(*KEYS[key], False))
        with self._lock:
            self._held[combo] = self._held.get(combo, 0) + 1
            self._send(ev)

    def release(self, combo: str):
        mods, key = parse_combo(combo)
        ev = [self._event(*KEYS[key], True)]
        ev += [self._event(*MODIFIERS[m], True) for m in reversed(mods)]
        with self._lock:
            n = self._held.get(combo, 0)
            if n <= 1:
                self._held.pop(combo, None)
            else:
                self._held[combo] = n - 1
            self._send(ev)
