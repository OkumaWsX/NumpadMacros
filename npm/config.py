# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Configuración guardada en %APPDATA%\\NumpadMacros\\config.json."""
import copy
import json
import os
import sys
import tempfile

APP_NAME = "NumpadMacros"


def config_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, APP_NAME)


def config_path() -> str:
    return os.path.join(config_dir(), "config.json")


DEFAULT = {
    "version": 1,
    "mode": "",                      # método de captura (según el sistema)
    "device": "",                    # numpad elegido
    "block_unassigned": True,        # teclas sin acción: bloquear o dejar pasar
    "bank_toast": True,              # aviso en pantalla al cambiar de banco
    "global": {"45": {"type": "bank_next"}},   # capa que aplica en todos los bancos
    "banks": [{"name": "Banco 1", "keys": {}},
              {"name": "Banco 2", "keys": {}}],
    "active_bank": 0,
    "extra_keys": [],                # teclas no estándar detectadas en el numpad
    "audio": {                       # botonera propia
        "monitor_device": "",        # "" = salida predeterminada
        "mic_device": "",            # micrófono virtual (VB-Cable / BlackHole)
        "mix_mic": False,            # mezclar el micrófono real con los sonidos
        "mic_input": "",
        "volume": 1.0,
        "normalize": True,           # igualar el volumen de todos los sonidos
        "target_lufs": -16.0,        # volumen objetivo al igualar (LUFS)
        "compressor": {              # compresor/limitador de la mezcla
            "on": True, "preset": "media", "thr": -18.0, "ratio": 3.0, "ceil": -1.0},
    },
    "updates": {                     # buscar versiones nuevas en GitHub
        "auto": True,                # una vez al día, al abrir la app
        "beta": False,               # recibir también versiones de prueba
        "skip": "",                  # versión que el usuario decidió omitir
        "last_check": 0,
        "show_news": True,           # mostrar novedades al abrir una versión nueva
        "last_seen": "",             # última versión cuyas novedades se mostraron
    },
    "last_dir": "",
    "library": [],                   # biblioteca de sonidos: [{"path", "title"}]
    "phone": {"count": 24,           # teclas virtuales de la app del celular
              "only": False},        # True = sin teclado: solo se usa el celular
    "row_mode": {                    # fila de números del teclado principal
        "enabled": True,
        "toggle": "ctrl+alt+m",      # combinación que activa/desactiva el modo macros
    },
}


def load(path: str | None = None) -> dict:
    path = path or config_path()
    cfg = copy.deepcopy(DEFAULT)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update(data)
    except FileNotFoundError:
        pass
    except (OSError, ValueError):
        # Archivo dañado: se respalda y se parte de cero
        try:
            os.replace(path, path + ".dañado")
        except OSError:
            pass
    # Versiones anteriores guardaban el numpad como "device_hwid"
    if not cfg.get("device") and cfg.get("device_hwid"):
        cfg["device"] = cfg.pop("device_hwid")
    cfg.pop("device_hwid", None)
    row = copy.deepcopy(DEFAULT["row_mode"])
    row.update(cfg.get("row_mode") or {})
    cfg["row_mode"] = row
    audio = copy.deepcopy(DEFAULT["audio"])
    audio.update(cfg.get("audio") or {})
    comp = copy.deepcopy(DEFAULT["audio"]["compressor"])
    comp.update(audio.get("compressor") or {})
    audio["compressor"] = comp
    cfg["audio"] = audio
    ph = copy.deepcopy(DEFAULT["phone"])
    ph.update(cfg.get("phone") or {})
    cfg["phone"] = ph
    cfg.pop("fkeys", None)
    migrate_fkeys(cfg)
    upd = copy.deepcopy(DEFAULT["updates"])
    upd.update(cfg.get("updates") or {})
    cfg["updates"] = upd
    from .capture import MODES, PLATFORM
    if cfg.get("mode") not in [m[0] for m in MODES[PLATFORM]]:
        cfg["mode"] = MODES[PLATFORM][0][0]
    if not cfg.get("banks"):
        cfg["banks"] = copy.deepcopy(DEFAULT["banks"])
    # Teclas de versiones anteriores que usaban Soundpad -> archivos propios
    from .library import add, migrate_soundpad
    migrate_soundpad(cfg)
    # Todo archivo asignado a una tecla aparece también en la biblioteca
    for layer in [cfg["global"]] + [b["keys"] for b in cfg["banks"]]:
        for act in layer.values():
            if act.get("type") == "file" and act.get("path"):
                add(cfg, [act["path"]], act.get("title"))
    cfg["active_bank"] = min(max(0, int(cfg.get("active_bank", 0))), len(cfg["banks"]) - 1)
    return cfg


def migrate_fkeys(cfg: dict) -> int:
    """En 3.3.1 F13–F24 servían como teclas de entrada. Ahora las reemplazan las
    teclas virtuales del celular: lo asignado a "f13"… pasa a la primera tecla
    virtual libre de la misma capa (y se agranda la cantidad si hace falta)."""
    from .keys import PHONE_COUNTS
    moved, top = 0, 0
    for layer in [cfg["global"]] + [b["keys"] for b in cfg["banks"]]:
        old = sorted((k for k in layer if k.startswith("f") and k[1:].isdigit() and 13 <= int(k[1:]) <= 24),
                     key=lambda k: int(k[1:]))
        for kid in old:
            act = layer.pop(kid)
            if not act or act.get("type", "none") == "none":
                continue
            i = 1
            while f"m{i}" in layer and i < PHONE_COUNTS[-1]:
                i += 1
            if f"m{i}" in layer:
                continue                                   # no queda espacio: se descarta
            layer[f"m{i}"] = act
            top = max(top, i)
            moved += 1
    if top:
        ph = cfg["phone"]
        if int(ph.get("count", 24)) < top:
            ph["count"] = next(n for n in PHONE_COUNTS if n >= top)
    return moved


def save(cfg: dict, path: str | None = None) -> None:
    path = path or config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Escritura atómica: nunca queda un archivo a medias
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
