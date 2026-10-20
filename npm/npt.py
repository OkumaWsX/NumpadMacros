# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Archivos de tema .npt (NumPad Theme).

Estructura (binaria):
    "NPT" | versión (1 byte) | opciones (1 byte, bit 0 = firmado) | nonce (12 bytes)
    | largo del contenido (4 bytes) | contenido cifrado (AES-256-GCM) | firma (64 bytes, si va firmado)

El contenido es el tema en JSON comprimido. El cifrado hace que no se pueda leer
ni editar con un editor de texto y su sello (GCM) detecta cualquier cambio: si
el archivo se daña o se modifica, no se abre. La firma Ed25519 (opcional) solo
la puede hacer el creador: así se reconocen los temas oficiales.
"""
import hashlib
import json
import os
import struct
import zlib

MAGIC = b"NPT"
VERSION = 1
FLAG_SIGNED = 1
EXT = ".npt"
MAX_SIZE = 256 * 1024
# Clave pública del creador (OkumaWsX) para reconocer los temas oficiales
OFFICIAL_KEY = "d22a3b4117eb17f96229d2ee90240c0f5e324ac34f97783de09124765d6711ff"
_K = hashlib.sha256(b"NumpadMacros/npt/1/" + bytes.fromhex(OFFICIAL_KEY)[::-1]).digest()

REQUIRED = ("bg", "panel", "panel2", "line", "text", "muted", "acc", "on_acc", "key", "key_set",
            "key_global", "ok", "bad", "warn")


class NptError(ValueError):
    """El archivo no es un tema válido (el mensaje explica por qué, para el usuario)."""


def _aes():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as e:                     # pragma: no cover
        raise NptError(f"Falta un componente para leer temas ({e})")
    return AESGCM(_K)


def _valid_hex(v):
    return isinstance(v, str) and len(v) == 7 and v[0] == "#" and all(c in "0123456789abcdefABCDEF" for c in v[1:])


def check_theme(t: dict) -> dict:
    """Revisa y limpia un tema. Devuelve el tema; NptError si le falta algo."""
    if not isinstance(t, dict):
        raise NptError("El tema no tiene el formato correcto")
    name = str(t.get("name", "")).strip()[:40]
    if not name:
        raise NptError("El tema no tiene nombre")
    colors = t.get("colors")
    if not isinstance(colors, dict):
        raise NptError("El tema no tiene colores")
    clean = {k: v.lower() for k, v in colors.items() if _valid_hex(v)}
    missing = [k for k in REQUIRED if k not in clean]
    if missing:
        raise NptError("Al tema le faltan colores: " + ", ".join(missing))
    out = {"name": name, "author": str(t.get("author", "")).strip()[:40] or "Desconocido",
           "version": str(t.get("version", "1.0"))[:12], "colors": clean}
    alpha = t.get("alpha")
    if isinstance(alpha, dict):              # transparencia (solo temas que la permiten)
        try:
            out["alpha"] = {"window": min(1.0, max(0.5, float(alpha.get("window", 1.0)))),
                            "idle": min(1.0, max(0.3, float(alpha.get("idle", 1.0))))}
        except (TypeError, ValueError):
            pass
    return out


def pack(theme: dict, private_key=None) -> bytes:
    """Tema -> bytes .npt (cifrado; firmado si se entrega la clave privada Ed25519)."""
    theme = check_theme(theme)
    payload = zlib.compress(json.dumps(theme, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9)
    flags = FLAG_SIGNED if private_key is not None else 0
    nonce = os.urandom(12)
    head = MAGIC + bytes([VERSION, flags]) + nonce
    ct = _aes().encrypt(nonce, payload, head)
    body = head + struct.pack(">I", len(ct)) + ct
    if private_key is not None:
        body += private_key.sign(body)
    return body


def unpack(data: bytes) -> tuple[dict, bool]:
    """bytes .npt -> (tema, es_oficial). NptError con un mensaje claro si falla."""
    if len(data) > MAX_SIZE:
        raise NptError("El archivo es demasiado grande para ser un tema")
    if len(data) < 21 or data[:3] != MAGIC:
        raise NptError("No es un archivo de tema de Numpad Macros (.npt)")
    if data[3] != VERSION:
        raise NptError("Este tema es de una versión más nueva de Numpad Macros: actualiza el programa")
    flags = data[4]
    nonce = data[5:17]
    (n,) = struct.unpack(">I", data[17:21])
    end = 21 + n
    if len(data) < end:
        raise NptError("El archivo está incompleto o dañado")
    ct = data[21:end]
    official = False
    if flags & FLAG_SIGNED:
        sig = data[end:end + 64]
        if len(sig) != 64 or len(data) != end + 64:
            raise NptError("El archivo está incompleto o dañado")
        official = verify(data[:end], sig)
        if not official:
            raise NptError("La firma del tema no es válida: el archivo fue modificado")
    elif len(data) != end:
        raise NptError("El archivo está dañado o fue modificado")
    try:
        payload = _aes().decrypt(nonce, ct, data[:17])
    except Exception:
        raise NptError("El archivo está dañado o fue modificado (no pasó la revisión de integridad)")
    try:
        theme = json.loads(zlib.decompress(payload).decode("utf-8"))
    except Exception:
        raise NptError("El archivo está dañado")
    return check_theme(theme), official


def verify(body: bytes, sig: bytes) -> bool:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(OFFICIAL_KEY)).verify(sig, body)
        return True
    except Exception:
        return False


def load_private_key(path: str):
    """Clave privada del creador (archivo PEM)."""
    from cryptography.hazmat.primitives import serialization
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def read_file(path: str) -> tuple[dict, bool]:
    try:
        with open(path, "rb") as f:
            data = f.read(MAX_SIZE + 1)
    except OSError as e:
        raise NptError(f"No pude leer el archivo: {e}")
    return unpack(data)
