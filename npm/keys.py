# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Identificadores de teclas del numpad y tabla de teclas para los atajos.

Una tecla física se identifica por su *scancode* y la marca E0, con el formato
"47" (Num 7) o "e0:1c" (Enter del numpad). El scancode no cambia con NumLock,
así que Num 7 es siempre "47", esté NumLock encendido o apagado.
"""
import sys

def key_id(code: int, e0: bool) -> str:
    return ("e0:" if e0 else "") + f"{code & 0xFF:02x}"


# id -> (etiqueta, columna, fila, ancho, alto) en la cuadrícula del dibujo
NUMPAD_LAYOUT = {
    "45":    ("NumLk", 0, 0, 1, 1),
    "e0:35": ("/", 1, 0, 1, 1),
    "37":    ("*", 2, 0, 1, 1),
    "4a":    ("−", 3, 0, 1, 1),
    "47":    ("7", 0, 1, 1, 1),
    "48":    ("8", 1, 1, 1, 1),
    "49":    ("9", 2, 1, 1, 1),
    "4e":    ("+", 3, 1, 1, 2),
    "4b":    ("4", 0, 2, 1, 1),
    "4c":    ("5", 1, 2, 1, 1),
    "4d":    ("6", 2, 2, 1, 1),
    "4f":    ("1", 0, 3, 1, 1),
    "50":    ("2", 1, 3, 1, 1),
    "51":    ("3", 2, 3, 1, 1),
    "e0:1c": ("Enter", 3, 3, 1, 2),
    "52":    ("0", 0, 4, 2, 1),
    "53":    (".", 2, 4, 1, 1),
}

NUMPAD_IDS = frozenset(NUMPAD_LAYOUT)

# Fila de números del teclado principal (se usa en "modo macros")
# id -> (etiqueta, columna, fila) en una cuadrícula de 6 x 2
ROW_LAYOUT = {
    "02": ("1", 0, 0), "03": ("2", 1, 0), "04": ("3", 2, 0),
    "05": ("4", 3, 0), "06": ("5", 4, 0), "07": ("6", 5, 0),
    "08": ("7", 0, 1), "09": ("8", 1, 1), "0a": ("9", 2, 1),
    "0b": ("0", 3, 1), "0c": ("-", 4, 1), "0d": ("=", 5, 1),
}
ROW_IDS = frozenset(ROW_LAYOUT)

# Teclas virtuales: no corresponden a ninguna tecla física, solo se tocan en la app del
# celular, así nunca interfieren con los teclados del equipo. Siempre 30 (5 × 6).
VIRTUAL_COLS, VIRTUAL_ROWS = 5, 6
VIRTUAL_COUNT = VIRTUAL_COLS * VIRTUAL_ROWS
PHONE_COUNTS = (VIRTUAL_COUNT,)
PHONE_IDS = frozenset(f"m{i}" for i in range(1, VIRTUAL_COUNT + 1))


def phone_layout(count: int = VIRTUAL_COUNT, cols: int = VIRTUAL_COLS) -> dict:
    """id -> (etiqueta, columna, fila) de las teclas virtuales."""
    return {f"m{i}": (str(i), (i - 1) % cols, (i - 1) // cols) for i in range(1, count + 1)}


def phone_count(cfg: dict | None = None) -> int:
    return VIRTUAL_COUNT

# Modificadores (scancode) -> nombre
MOD_KIDS = {"1d": "ctrl", "e0:1d": "ctrl", "38": "alt", "e0:38": "alt",
            "2a": "shift", "36": "shift", "e0:5b": "win", "e0:5c": "win"}

# Teclas que pueden formar la combinación que activa el modo macros (nombre -> id)
TOGGLE_KEYS = {c: f"{v:02x}" for c, v in zip(
    "qwertyuiop", range(0x10, 0x1A))}
TOGGLE_KEYS.update({c: f"{v:02x}" for c, v in zip("asdfghjkl", range(0x1E, 0x27))})
TOGGLE_KEYS.update({c: f"{v:02x}" for c, v in zip("zxcvbnm", range(0x2C, 0x33))})
TOGGLE_KEYS.update({f"f{i}": f"{0x3A + i:02x}" for i in range(1, 11)})
TOGGLE_KEYS.update({"f11": "57", "f12": "58", "bloqdespl": "46", "espacio": "39",
                    "insert": "e0:52", "supr": "e0:53", "inicio": "e0:47", "fin": "e0:4f",
                    "repag": "e0:49", "avpag": "e0:51"})
TOGGLE_CHOICES = list("abcdefghijklmnopqrstuvwxyz") + [f"f{i}" for i in range(1, 13)] + \
    ["bloqdespl", "insert", "supr", "inicio", "fin", "repag", "avpag", "espacio"]


def parse_toggle(combo: str):
    """'ctrl+alt+m' -> (frozenset({'ctrl','alt'}), '32', 'm'). ValueError si no sirve."""
    mods, key = parse_combo(combo)
    if key not in TOGGLE_KEYS:
        raise ValueError(f"la tecla {key.upper()} no sirve para activar el modo macros")
    return frozenset(mods), TOGGLE_KEYS[key], key

# Nombres para teclas "extra" que traen algunos numpads (calculadora, 00, etc.)
_EXTRA_NAMES = {
    "0e": "Retroceso", "0f": "Tab", "01": "Esc", "0d": "=", "1c": "Enter (principal)",
    "e0:21": "Calculadora", "59": "= (numpad)", "7e": ", (numpad)",
}


def key_label(kid: str) -> str:
    """Nombre legible de una tecla."""
    if kid in ROW_LAYOUT:
        return f"Fila {ROW_LAYOUT[kid][0]}"
    if kid in PHONE_IDS:
        return f"Virtual {kid[1:]}"
    if kid in NUMPAD_LAYOUT:
        name = NUMPAD_LAYOUT[kid][0]
        if name == "NumLk":
            return "NumLock"
        return name if name == "Enter" else f"Num {name}"
    return _EXTRA_NAMES.get(kid, f"Tecla {kid.upper()}")


# ---------------------------------------------------------------- Linux (evdev)
# Los códigos evdev coinciden con el scancode de PC para casi todas las teclas
# "normales" (< 96). Las del numpad que usan E0 en PC tienen código propio.
_EVDEV_SPECIAL = {96: "e0:1c", 98: "e0:35",           # KEY_KPENTER, KEY_KPSLASH
                  97: "e0:1d", 100: "e0:38",           # Ctrl y Alt derechos
                  125: "e0:5b", 126: "e0:5c",          # Super/Win
                  110: "e0:52", 111: "e0:53", 102: "e0:47", 107: "e0:4f",
                  104: "e0:49", 109: "e0:51"}          # Insert, Supr, Inicio, Fin, RePág, AvPág
_EXTRA_NAMES.update({"ev:117": "= (numpad)", "ev:121": ", (numpad)",
                     "ev:140": "Calculadora", "ev:118": "± (numpad)",
                     "ev:179": "( (numpad)", "ev:180": ") (numpad)"})


def evdev_kid(code: int) -> str:
    if code in _EVDEV_SPECIAL:
        return _EVDEV_SPECIAL[code]
    if code < 96:
        return f"{code:02x}"
    return f"ev:{code}"


# ---------------------------------------------------------------- macOS (HID)
# Uso HID (página 0x07 "Keyboard/Keypad") -> id de tecla
HID_KEYPAD = {
    0x53: "45", 0x54: "e0:35", 0x55: "37", 0x56: "4a", 0x57: "4e", 0x58: "e0:1c",
    0x59: "4f", 0x5A: "50", 0x5B: "51", 0x5C: "4b", 0x5D: "4c", 0x5E: "4d",
    0x5F: "47", 0x60: "48", 0x61: "49", 0x62: "52", 0x63: "53",
    0x2A: "0e", 0x2B: "0f", 0x29: "01", 0x28: "1c",
}
_EXTRA_NAMES.update({"hid:67": "= (numpad)", "hid:85": ", (numpad)",
                     "hid:b6": "( (numpad)", "hid:b7": ") (numpad)", "hid:b0": "00 (numpad)"})


def hid_kid(usage: int) -> str:
    return HID_KEYPAD.get(usage, f"hid:{usage:02x}")


# ---------------------------------------------------------------- atajos
# nombre -> (virtual-key, extendida)
MODIFIERS = {
    "ctrl": (0xA2, False),
    "shift": (0xA0, False),
    "alt": (0xA4, False),
    "win": (0x5B, True),
}

KEYS = {}
for _i in range(1, 25):
    KEYS[f"f{_i}"] = (0x6F + _i, False)
for _c in "abcdefghijklmnopqrstuvwxyz":
    KEYS[_c] = (ord(_c.upper()), False)
for _d in "0123456789":
    KEYS[_d] = (ord(_d), False)
    KEYS[f"num{_d}"] = (0x60 + int(_d), False)
KEYS.update({
    "espacio": (0x20, False), "enter": (0x0D, False), "tab": (0x09, False),
    "esc": (0x1B, False), "retroceso": (0x08, False),
    "insert": (0x2D, True), "supr": (0x2E, True), "inicio": (0x24, True),
    "fin": (0x23, True), "repag": (0x21, True), "avpag": (0x22, True),
    "arriba": (0x26, True), "abajo": (0x28, True),
    "izquierda": (0x25, True), "derecha": (0x27, True),
    "impr": (0x2C, True), "pausa": (0x13, False), "bloqdespl": (0x91, False),
    "silenciar": (0xAD, True), "vol-": (0xAE, True), "vol+": (0xAF, True),
    "pista_sig": (0xB0, True), "pista_ant": (0xB1, True),
    "detener": (0xB2, True), "play_pausa": (0xB3, True),
})

# Orden pensado para el desplegable: F13–F24 primero (no chocan con nada)
KEY_CHOICES = ([f"f{i}" for i in range(13, 25)] + [f"f{i}" for i in range(1, 13)]
               + list("abcdefghijklmnopqrstuvwxyz") + list("0123456789")
               + [f"num{d}" for d in "0123456789"]
               + ["espacio", "enter", "tab", "esc", "retroceso", "insert", "supr",
                  "inicio", "fin", "repag", "avpag", "arriba", "abajo", "izquierda",
                  "derecha", "impr", "pausa", "bloqdespl", "silenciar", "vol-", "vol+",
                  "pista_sig", "pista_ant", "detener", "play_pausa"])

# Scancodes de F13–F24 (MapVirtualKey a veces devuelve 0 para estas)
F_SCANCODES = {0x7C: 0x64, 0x7D: 0x65, 0x7E: 0x66, 0x7F: 0x67, 0x80: 0x68, 0x81: 0x69,
               0x82: 0x6A, 0x83: 0x6B, 0x84: 0x6C, 0x85: 0x6D, 0x86: 0x6E, 0x87: 0x76}


def parse_combo(combo: str):
    """'ctrl+shift+f13' -> (['ctrl','shift'], 'f13'). Lanza ValueError si no es válido."""
    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    if not parts:
        raise ValueError("combinación vacía")
    *mods, key = parts
    for m in mods:
        if m not in MODIFIERS:
            raise ValueError(f"modificador desconocido: {m}")
    if key not in KEYS:
        raise ValueError(f"tecla desconocida: {key}")
    return mods, key


def combo_text(combo: str) -> str:
    try:
        mods, key = parse_combo(combo)
    except ValueError:
        return combo
    return "+".join([m.capitalize() for m in mods] + [key.upper()])


# ---------------------------------------------------------------- grabar combinaciones
# Nombre de tecla de tkinter (keysym) -> nombre interno
_KEYSYM = {"space": "espacio", "return": "enter", "kp_enter": "enter", "tab": "tab",
           "escape": "esc", "backspace": "retroceso", "insert": "insert", "delete": "supr",
           "home": "inicio", "end": "fin", "prior": "repag", "next": "avpag", "up": "arriba",
           "down": "abajo", "left": "izquierda", "right": "derecha", "print": "impr",
           "pause": "pausa", "scroll_lock": "bloqdespl", "xf86audiomute": "silenciar",
           "xf86audiolowervolume": "vol-", "xf86audioraisevolume": "vol+",
           "xf86audionext": "pista_sig", "xf86audioprev": "pista_ant",
           "xf86audiostop": "detener", "xf86audioplay": "play_pausa"}
_KP = {"kp_insert": "0", "kp_end": "1", "kp_down": "2", "kp_next": "3", "kp_left": "4",
       "kp_begin": "5", "kp_right": "6", "kp_home": "7", "kp_up": "8", "kp_prior": "9"}
MODIFIER_KEYSYMS = {"control_l": "ctrl", "control_r": "ctrl", "shift_l": "shift", "shift_r": "shift",
                    "alt_l": "alt", "alt_r": "alt", "iso_level3_shift": "alt",
                    "super_l": "win", "super_r": "win", "win_l": "win", "win_r": "win",
                    # macOS: Cmd llega como Meta y Option como Option/Alt
                    "meta_l": "win" if sys.platform == "darwin" else "alt",
                    "meta_r": "win" if sys.platform == "darwin" else "alt",
                    "command": "win", "option_l": "alt", "option_r": "alt"}


def keysym_to_key(keysym: str) -> str | None:
    """'F13' -> 'f13', 'a' -> 'a', 'KP_1' -> 'num1'... None si no se puede usar."""
    k = (keysym or "").lower()
    if k in MODIFIER_KEYSYMS:
        return None
    if k.startswith("f") and k[1:].isdigit() and 1 <= int(k[1:]) <= 24:
        return k
    if len(k) == 1 and (k.isalpha() or k.isdigit()) and k.isascii():
        return k
    if k.startswith("kp_") and k[3:].isdigit():
        return "num" + k[3:]
    if k in _KP:
        return "num" + _KP[k]
    return _KEYSYM.get(k)


def join_combo(mods, key: str) -> str:
    """Combinación en orden fijo: ctrl, shift, alt, win + tecla."""
    order = [m for m in MODIFIERS if m in set(mods)]
    return "+".join(order + [key])


# Combinaciones que ya usan casi todos los programas
BUSY_COMBOS = {"ctrl+c": "copiar", "ctrl+v": "pegar", "ctrl+x": "cortar", "ctrl+z": "deshacer",
               "ctrl+y": "rehacer", "ctrl+s": "guardar", "ctrl+a": "seleccionar todo",
               "ctrl+f": "buscar", "ctrl+p": "imprimir", "ctrl+w": "cerrar pestañas",
               "ctrl+t": "abrir pestañas", "ctrl+n": "abrir ventanas", "ctrl+q": "salir de programas",
               "alt+f4": "cerrar ventanas", "alt+tab": "cambiar de ventana",
               "ctrl+shift+esc": "abrir el administrador de tareas", "win+l": "bloquear el equipo",
               "win+d": "mostrar el escritorio", "win+e": "abrir el explorador", "win+r": "Ejecutar"}


def busy_reason(combo: str) -> str | None:
    try:
        mods, key = parse_combo(combo)
    except ValueError:
        return None
    return BUSY_COMBOS.get(join_combo(mods, key))
