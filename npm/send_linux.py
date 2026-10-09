# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Envío de atajos en Linux con un teclado virtual (uinput).

Funciona igual en Wayland y X11, porque el sistema lo ve como un teclado real.
El mismo dispositivo virtual se usa para "devolver" las teclas del numpad que
no tienen acción (o cuando el programa está en pausa).
"""
import threading

from .keys import parse_combo

_ui = None
_ui_lock = threading.Lock()


def _ecodes():
    from evdev import ecodes
    return ecodes


def uinput():
    """Teclado virtual compartido (se crea la primera vez)."""
    global _ui
    with _ui_lock:
        if _ui is None:
            from evdev import UInput
            e = _ecodes()
            try:
                _ui = UInput({e.EV_KEY: list(range(1, 249))}, name="Numpad Macros (virtual)")
            except Exception as ex:   # OSError, PermissionError o UInputError de evdev
                raise RuntimeError(
                    "falta dar permisos (pestaña «Numpad y opciones» → «Dar permisos…»)") from ex
        return _ui


def emit(code: int, value: int):
    ui = uinput()
    e = _ecodes()
    with _ui_lock:
        ui.write(e.EV_KEY, code, value)
        ui.syn()


def _tables():
    e = _ecodes()
    keys = {f"f{i}": getattr(e, f"KEY_F{i}") for i in range(1, 25)}
    for c in "abcdefghijklmnopqrstuvwxyz":
        keys[c] = getattr(e, f"KEY_{c.upper()}")
    for d in "0123456789":
        keys[d] = getattr(e, f"KEY_{d}")
        keys[f"num{d}"] = getattr(e, f"KEY_KP{d}")
    keys.update({
        "espacio": e.KEY_SPACE, "enter": e.KEY_ENTER, "tab": e.KEY_TAB, "esc": e.KEY_ESC,
        "retroceso": e.KEY_BACKSPACE, "insert": e.KEY_INSERT, "supr": e.KEY_DELETE,
        "inicio": e.KEY_HOME, "fin": e.KEY_END, "repag": e.KEY_PAGEUP, "avpag": e.KEY_PAGEDOWN,
        "arriba": e.KEY_UP, "abajo": e.KEY_DOWN, "izquierda": e.KEY_LEFT, "derecha": e.KEY_RIGHT,
        "impr": e.KEY_SYSRQ, "pausa": e.KEY_PAUSE, "bloqdespl": e.KEY_SCROLLLOCK,
        "silenciar": e.KEY_MUTE, "vol-": e.KEY_VOLUMEDOWN, "vol+": e.KEY_VOLUMEUP,
        "pista_sig": e.KEY_NEXTSONG, "pista_ant": e.KEY_PREVIOUSSONG,
        "detener": e.KEY_STOPCD, "play_pausa": e.KEY_PLAYPAUSE,
    })
    mods = {"ctrl": e.KEY_LEFTCTRL, "shift": e.KEY_LEFTSHIFT,
            "alt": e.KEY_LEFTALT, "win": e.KEY_LEFTMETA}
    return keys, mods


class UinputSender:
    unsupported: frozenset = frozenset()

    def __init__(self):
        self.keys, self.mods = _tables()
        uinput()   # falla aquí (con mensaje claro) si no hay permisos

    def _codes(self, combo):
        mods, key = parse_combo(combo)
        return [self.mods[m] for m in mods], self.keys[key]

    def press(self, combo: str):
        mods, key = self._codes(combo)
        ui, e = uinput(), _ecodes()
        with _ui_lock:
            for m in mods:
                ui.write(e.EV_KEY, m, 1)
            ui.write(e.EV_KEY, key, 1)
            ui.syn()

    def release(self, combo: str):
        mods, key = self._codes(combo)
        ui, e = uinput(), _ecodes()
        with _ui_lock:
            ui.write(e.EV_KEY, key, 0)
            for m in reversed(mods):
                ui.write(e.EV_KEY, m, 0)
            ui.syn()
