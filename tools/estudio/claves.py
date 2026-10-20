# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Dónde guarda el Estudio de Temas tus claves y ajustes, y en qué modo abre.

- ``autor.npkey``: tu firma de autor. Se crea sola la primera vez.
- ``oficial.npkey``: la clave del creador oficial (la misma «firma-temas-OkumaWsX.key»
  del Publicador). Solo existe en su PC; con ella el Estudio abre en modo creador.
- ``ajustes.json``: tu nombre de autor y otras preferencias.
"""
from __future__ import annotations

import json
import os
import sys

from logica import npt  # noqa: F401  (agrega la raíz del repo al path)
from npm.config import config_dir


def folder() -> str:
    d = os.environ.get("NPT_ESTUDIO_DIR") or os.path.join(config_dir(), "estudio")
    os.makedirs(d, exist_ok=True)
    return d


def _path(name: str) -> str:
    return os.path.join(folder(), name)


AUTHOR_FILE, OFFICIAL_FILE, SETTINGS_FILE = "autor.npkey", "oficial.npkey", "ajustes.json"


def _write_private(path: str, data: bytes) -> None:
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


# ---------------------------------------------------------------- ajustes
def load_settings() -> dict:
    try:
        with open(_path(SETTINGS_FILE), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(s: dict) -> None:
    tmp = _path(SETTINGS_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _path(SETTINGS_FILE))


# ---------------------------------------------------------------- firma de autor
def has_author_key() -> bool:
    return os.path.exists(_path(AUTHOR_FILE))


def author_info() -> dict | None:
    try:
        with open(_path(AUTHOR_FILE), "rb") as f:
            return npt.SigningKey.info(f.read())
    except (OSError, npt.KeyFileError):
        return None


def create_author_key(name: str) -> npt.SigningKey:
    k = npt.SigningKey.generate("autor", name)
    _write_private(_path(AUTHOR_FILE), k.to_file())
    return k


def load_author_key(password: str | None = None) -> npt.SigningKey:
    with open(_path(AUTHOR_FILE), "rb") as f:
        return npt.SigningKey.from_file(f.read(), password)


def save_author_key(k: npt.SigningKey, password: str | None = None) -> None:
    _write_private(_path(AUTHOR_FILE), k.to_file(password))


# ---------------------------------------------------------------- clave oficial
def official_info() -> dict | None:
    try:
        with open(_path(OFFICIAL_FILE), "rb") as f:
            return npt.SigningKey.info(f.read())
    except (OSError, npt.KeyFileError):
        return None


def load_official_key(password: str | None = None) -> npt.SigningKey:
    with open(_path(OFFICIAL_FILE), "rb") as f:
        return npt.SigningKey.from_file(f.read(), password)


def mode() -> str:
    """«creador» si la clave oficial está en esta PC; si no, «comunidad»."""
    return "creador" if official_info() else "comunidad"


def official_known(info: dict | None) -> bool:
    """¿Es la clave que Numpad Macros reconoce como oficial (OFFICIAL_KEY)?"""
    return bool(info) and npt.is_official_key(info.get("publica", ""))


def _official_from_pem(raw: bytes) -> bytes:
    """Convierte la clave PEM del Publicador en un .npkey oficial (solo si es la oficial)."""
    try:
        k = npt.SigningKey.from_pem(raw)
    except npt.KeyFileError as e:
        if e.code == "password":
            raise
        raise npt.KeyFileError("formato", "No es una clave de firma de temas.")
    if not k.is_official:
        raise npt.KeyFileError("formato", "Esa clave no es la del creador oficial de Numpad Macros.")
    return k.to_file()


def publicador_key_path() -> str | None:
    """La clave de firma de temas que usa el Publicador en esta PC, si existe."""
    base = os.path.dirname(config_dir())
    try:
        with open(os.path.join(base, "NumpadMacros-Publicador", "config.json"), encoding="utf-8") as f:
            path = json.load(f).get("theme_key", "")
    except (OSError, ValueError, AttributeError):
        return None
    return path if path and os.path.isfile(path) else None


def import_key_file(raw: bytes) -> str:
    """Importa una copia de seguridad (.npkey) o la clave PEM del Publicador (.key).
    Devuelve «autor» u «oficial»."""
    if raw.lstrip().startswith(b"-----BEGIN"):
        raw = _official_from_pem(raw)
    info = npt.SigningKey.info(raw)
    if info.get("tipo") == "oficial" and not npt.is_official_key(info.get("publica", "")):
        raise npt.KeyFileError("formato", "Esa clave no es la del creador oficial de Numpad Macros.")
    kind = "oficial" if info.get("tipo") == "oficial" else "autor"
    _write_private(_path(OFFICIAL_FILE if kind == "oficial" else AUTHOR_FILE), raw)
    if kind == "autor" and info.get("nombre") is not None:
        s = load_settings()
        s["nombre"] = info.get("nombre", "")
        save_settings(s)
    return kind


def read_file(name: str) -> bytes:
    with open(_path(name), "rb") as f:
        return f.read()


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))
