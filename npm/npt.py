# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Archivos de tema .npt (NumPad Theme).

Hay dos versiones del formato y Numpad Macros lee las dos:

**Versión 1** (temas de Numpad Macros y del Publicador)::

    "NPT" | 1 | opciones (1 byte, bit 0 = firmado) | nonce (12 bytes)
    | largo del contenido (4 bytes) | contenido cifrado (AES-256-GCM) | firma (64 bytes, si va firmado)

Solo el creador firma (con ``OFFICIAL_KEY``); los temas sin firma son de la comunidad.

**Versión 2** (temas del Estudio de Temas: transparencia por capa e imágenes)::

    "NPT" | 2 | opciones (0) | clave pública del autor (32 bytes) | nonce (12 bytes)
    | contenido cifrado (AES-256-GCM) | firma Ed25519 del autor (64 bytes)

Todos los temas v2 van firmados: por el creador (oficial) o por la firma de autor
de cada persona (comunidad). Así nadie puede hacerse pasar por otro autor.

En las dos, el cifrado hace que no se pueda leer ni editar con un editor de texto
y su sello (GCM) detecta cualquier cambio. Como el código es abierto, la clave de
contenido no es secreta: lo que nadie puede falsificar es la firma.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import zlib
from dataclasses import dataclass, field
from datetime import date

MAGIC = b"NPT"
VERSION = 1                       # versión que escribe pack()
VERSION_STUDIO = 2                # versión que escribe write() (Estudio de Temas)
FLAG_SIGNED = 1
EXT = EXTENSION = ".npt"
MAX_SIZE = MAX_FILE = 5 * 1024 * 1024        # 5 MB por tema, imágenes incluidas
MAX_PLAIN = 24 * 1024 * 1024                 # tope al descomprimir (evita archivos trampa)
# Clave pública del creador (OkumaWsX) para reconocer los temas oficiales
OFFICIAL_KEY = "d22a3b4117eb17f96229d2ee90240c0f5e324ac34f97783de09124765d6711ff"
OFFICIAL_NAME = "OkumaWsX"
_K = hashlib.sha256(b"NumpadMacros/npt/1/" + bytes.fromhex(OFFICIAL_KEY)[::-1]).digest()

REQUIRED = ("bg", "panel", "panel2", "line", "text", "muted", "acc", "on_acc", "key", "key_set",
            "key_global", "ok", "bad", "warn")
# Las 22 capas de color, en el orden en que se muestran (los temas v2 traen todas).
TOKENS = (
    "bg", "panel", "panel2", "line", "text", "muted",
    "acc", "on_acc", "acc_hover", "acc_dim", "acc_bg",
    "key", "key_set", "key_set_line", "key_set_text", "key_global", "key_global_line", "key_global_text",
    "ok", "on_ok", "bad", "warn",
)
# Todas menos el fondo pueden tener transparencia propia (el fondo usa la de la ventana).
ALPHA_TOKENS = tuple(t for t in TOKENS if t != "bg")
# Capa sobre la que se mezcla cada una cuando no es opaca.
PARENT = {
    "panel": "bg", "panel2": "panel", "line": "panel", "text": "panel", "muted": "panel",
    "acc": "panel", "on_acc": "acc", "acc_hover": "panel", "acc_dim": "panel2", "acc_bg": "panel",
    "key": "panel", "key_set": "panel", "key_set_line": "panel", "key_set_text": "key_set",
    "key_global": "panel", "key_global_line": "panel", "key_global_text": "key_global",
    "ok": "bg", "on_ok": "ok", "bad": "panel", "warn": "panel",
}
# Espacios para imágenes (v2) y su tamaño máximo (ancho, alto). Los 9 del Estudio de Temas:
# detrás del contenido (banner, keys, corner, footband) y espacios libres (logo, headmid, tabsend,
# leftbot, foot). Un espacio que esta versión no conoce se ignora al leer (temas más nuevos).
IMAGE_SLOTS = {
    "banner": (1200, 120),     # encabezado completo, detrás del título
    "keys": (600, 520),        # detrás de la tabla de teclas
    "logo": (64, 64),          # junto al título
    "headmid": (360, 48),      # encabezado · espacio central
    "tabsend": (240, 28),      # pestañas · espacio al final
    "leftbot": (360, 160),     # panel de teclas · espacio de abajo
    "corner": (600, 200),      # pestaña · parte de abajo, detrás de los botones
    "footband": (1200, 40),    # pie · banda completa, detrás de los botones
    "foot": (420, 28),         # pie · espacio libre
    "fondo": (1920, 1200),     # fondo de toda la ventana (con fondo.tipo = "imagen")
}
# Espacios que aceptan GIF animado (stickers); los demás, solo PNG.
ANIMATED_SLOTS = frozenset({"headmid", "tabsend", "leftbot", "foot"})
SLOTS_BEHIND = ("banner", "keys", "corner", "footband")          # detrás del contenido
SLOTS_FREE = ("logo", "headmid", "tabsend", "leftbot", "foot")    # en huecos sin botones
MAX_FRAMES = 120                  # cuadros por imagen animada
# Fondo de la ventana con degradado: desde dónde empieza (4 esquinas, 4 lados o el centro).
GRADIENT_FROM = ("tl", "t", "tr", "l", "c", "r", "bl", "b", "br")
GRADIENT_STOPS = (2, 5)
# Secciones con transparencia propia (fondo de la sección y su contenido) y borde de realce.
SECTIONS = ("head", "left", "keys", "tabs", "body", "foot")
# Cómo se ve una sección sin ajustes (encabezado y pie sin plancha; el resto, normal)
SECTION_DEFAULTS = {"head": {"fondo": 0, "contenido": 100, "realce": False},
                    "left": {"fondo": 100, "contenido": 100, "realce": False},
                    "keys": {"fondo": 100, "contenido": 100, "realce": False},
                    "tabs": {"fondo": 100, "contenido": 100, "realce": False},
                    "body": {"fondo": 100, "contenido": 100, "realce": False},
                    "foot": {"fondo": 0, "contenido": 100, "realce": False}}
SECTION_MIN_CONTENT = 30          # el Estudio no deja bajar el contenido de aquí (para que se lea algo)
WINDOW_MIN = 50                   # opacidad mínima de la ventana, igual que el Laboratorio

_PUB_LEN, _NONCE_LEN, _SIG_LEN = 32, 12, 64
_HEX = re.compile(r"^#[0-9a-fA-F]{6}\Z")


class NptError(ValueError):
    """El archivo no es un tema válido (el mensaje explica por qué, para el usuario).

    ``code``: formato, version, danado, grande o contenido.
    """

    def __init__(self, message: str = "", code: str = "contenido"):
        super().__init__(message)
        self.code = code


def _aes():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as e:                     # pragma: no cover
        raise NptError(f"Falta un componente para leer temas ({e})")
    return AESGCM(_K)


def _valid_hex(v):
    return isinstance(v, str) and len(v) == 7 and v[0] == "#" and all(c in "0123456789abcdefABCDEF" for c in v[1:])


# ================================================================ versión 1
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
    """Tema -> bytes .npt v1 (cifrado; firmado si se entrega la clave privada Ed25519)."""
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


def _unpack_v1(data: bytes) -> tuple[dict, bool]:
    flags = data[4]
    nonce = data[5:17]
    (n,) = struct.unpack(">I", data[17:21])
    end = 21 + n
    if len(data) < end:
        raise NptError("El archivo está incompleto o dañado", "danado")
    ct = data[21:end]
    official = False
    if flags & FLAG_SIGNED:
        sig = data[end:end + 64]
        if len(sig) != 64 or len(data) != end + 64:
            raise NptError("El archivo está incompleto o dañado", "danado")
        official = verify(data[:end], sig)
        if not official:
            raise NptError("La firma del tema no es válida: el archivo fue modificado", "danado")
    elif len(data) != end:
        raise NptError("El archivo está dañado o fue modificado", "danado")
    try:
        payload = _aes().decrypt(nonce, ct, data[:17])
    except Exception:
        raise NptError("El archivo está dañado o fue modificado (no pasó la revisión de integridad)", "danado")
    try:
        d = zlib.decompressobj()
        raw = d.decompress(payload, MAX_PLAIN)
        if d.unconsumed_tail:
            raise ValueError
        theme = json.loads(raw.decode("utf-8"))
    except Exception:
        raise NptError("El archivo está dañado", "danado")
    t = check_theme(theme)
    if not official and is_reserved_name(t["author"]):
        t["author"] = "Desconocido"              # nadie más puede usar el nombre del creador
    return t, official


def unpack(data: bytes, images: bool = False) -> tuple[dict, bool]:
    """bytes .npt (v1 o v2) -> (tema, es_oficial). NptError con un mensaje claro si falla.

    El tema es un dict con name, author, version, colors y, si usa transparencia de
    ventana, alpha = {"window", "idle"}. Los temas v2 traen además ``layer_alpha``
    (transparencia por capa, 0–100), ``images`` (espacio -> PNG), ``description``,
    ``kind``, ``author_key`` y ``reserved_name``. Las imágenes solo se incluyen con
    ``images=True`` (si no, ``image_slots`` dice qué espacios tienen imagen).
    """
    _check_head(data)
    if data[3] == VERSION:
        return _unpack_v1(data)
    res = _read_v2(data)
    return res.to_dict(images), res.official


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


def read_file(path: str, images: bool = False) -> tuple[dict, bool]:
    try:
        with open(path, "rb") as f:
            data = f.read(MAX_SIZE + 1)
    except OSError as e:
        raise NptError(f"No pude leer el archivo: {e}")
    return unpack(data, images)


def _check_head(data: bytes) -> None:
    if len(data) > MAX_SIZE:
        raise NptError("El archivo es demasiado grande para ser un tema", "grande")
    if len(data) < 21 or data[:3] != MAGIC:
        raise NptError("No es un archivo de tema de Numpad Macros (.npt)", "formato")
    if data[3] not in (VERSION, VERSION_STUDIO):
        raise NptError("Este tema es de una versión más nueva de Numpad Macros: actualiza el programa", "version")


# ================================================================ versión 2 (Estudio de Temas)
@dataclass
class Theme:
    name: str
    author: str
    colors: dict
    version: str = "1.0"
    description: str = ""
    kind: str = "oscuro"                                  # "oscuro" o "claro"
    alpha: dict = field(default_factory=dict)             # capa -> 0..100 (falta = 100)
    window: dict = field(default_factory=lambda: {"opacidad": 100, "sin_usar": 100})
    images: dict = field(default_factory=dict)            # espacio -> bytes PNG (o GIF en los libres)
    created: str = field(default_factory=lambda: date.today().isoformat())
    # {"tipo": "degradado", "colores": [["#rrggbb", 0..100], …], "desde": "tl"…"br"/"c"}; {} = color sólido
    background: dict = field(default_factory=dict)
    # sección -> {"fondo": 0..100, "contenido": 0..100, "realce": bool}
    sections: dict = field(default_factory=dict)
    gif_pause: bool = True        # pausar las animaciones cuando no se usa la ventana

    @property
    def transparency(self) -> bool:
        """El tema usa transparencia (ventana o capas): el Laboratorio lo muestra como «Admite»."""
        return (any(v < 100 for v in self.alpha.values())
                or self.window.get("opacidad", 100) < 100 or self.window.get("sin_usar", 100) < 100
                or any(min(s.get("fondo", 100), s.get("contenido", 100)) < 100 for s in self.sections.values()))

    @property
    def gradient(self) -> dict:
        """El degradado ({"colores", "desde"}) o {} si el fondo es de color sólido."""
        bg = self.background
        if bg and bg.get("tipo", "degradado") == "degradado" and bg.get("colores"):
            return {"colores": [list(s) for s in bg["colores"]], "desde": bg.get("desde", "tl")}
        return {}

    def section(self, name: str) -> dict:
        """Ajustes de una sección, con los valores normales donde falten."""
        return {**SECTION_DEFAULTS[name], **self.sections.get(name, {})}

    @property
    def animated(self) -> list:
        """Espacios cuya imagen es animada (GIF o PNG animado)."""
        return sorted(k for k, v in self.images.items() if image_frames(v) > 1)


@dataclass
class ReadResult:
    theme: Theme
    author_key: str            # clave pública de quien firmó (hex); "" si no va firmado
    official: bool             # firmado por el creador oficial
    reserved_name: bool        # usa el nombre del creador oficial sin ser oficial
    format: int = 2

    @property
    def label(self) -> str:
        if self.official:
            return f"Oficial · {OFFICIAL_NAME}"
        return f"Comunidad · {self.theme.author or 'Anónimo'}"

    def to_dict(self, images: bool = True) -> dict:
        """El tema como lo usa Numpad Macros (las mismas claves que la versión 1, más las nuevas)."""
        t = self.theme
        author = OFFICIAL_NAME if self.official else ("Anónimo" if self.reserved_name or not t.author else t.author)
        out = {"name": t.name, "author": author,
               "version": t.version, "colors": dict(t.colors)}
        if t.transparency:
            out["alpha"] = {"window": t.window.get("opacidad", 100) / 100, "idle": t.window.get("sin_usar", 100) / 100}
        out.update(description=t.description, kind=t.kind, created=t.created, layer_alpha=dict(t.alpha),
                   image_slots=sorted(t.images),
                   background=dict(t.background), sections={k: dict(v) for k, v in t.sections.items()},
                   animated_slots=t.animated, gif_pause=t.gif_pause,
                   author_key=self.author_key, reserved_name=self.reserved_name, format=self.format)
        if images:
            out["images"] = dict(t.images)
        return out


# letras de otros alfabetos que se ven iguales a las latinas (para que no se cuele el nombre del creador)
_LOOKALIKE = str.maketrans("аеорсухкмтвнѕіјԁԝωυսµ×０１２３４５６７８９",
                           "aeopcyxkmtbhsijdwwuuux0123456789")


def normalize_name(name: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", name or "").lower().translate(_LOOKALIKE)
    s = s.translate(str.maketrans("0135@", "oiesa"))
    return re.sub(r"[^a-z0-9]", "", s)


def is_reserved_name(name: str) -> bool:
    """¿Se parece al nombre del creador oficial? (mayúsculas, espacios y símbolos no cuentan)."""
    return normalize_name(OFFICIAL_NAME) in normalize_name(name)


def is_official_key(pub_hex: str) -> bool:
    return isinstance(pub_hex, str) and pub_hex.lower() == OFFICIAL_KEY.lower()


def fingerprint(pub_hex: str) -> str:
    """Huella corta y legible de una clave pública: «7F3A 9C21 E4B0 55D8 · 0A6E 13F9 C2B7 4D80»."""
    h = hashlib.sha256(bytes.fromhex(pub_hex)).hexdigest()[:32].upper()
    g = [h[i:i + 4] for i in range(0, 32, 4)]
    return " ".join(g[:4]) + " · " + " ".join(g[4:])


class KeyFileError(Exception):
    """Problema con un archivo de clave. ``code``: password (falta), wrong (incorrecta), formato."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class SigningKey:
    """Clave para firmar temas v2. ``kind`` es "autor" (comunidad) u "oficial"."""

    def __init__(self, private, kind: str = "autor", name: str = "", created: str = ""):
        self._k = private
        self.kind = kind
        self.name = name
        self.created = created or date.today().isoformat()

    @classmethod
    def generate(cls, kind: str = "autor", name: str = "") -> "SigningKey":
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        return cls(Ed25519PrivateKey.generate(), kind, name)

    @property
    def public_bytes(self) -> bytes:
        from cryptography.hazmat.primitives import serialization as ser
        return self._k.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)

    @property
    def public_hex(self) -> str:
        return self.public_bytes.hex()

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.public_hex)

    @property
    def is_official(self) -> bool:
        return is_official_key(self.public_hex)

    def sign(self, data: bytes) -> bytes:
        return self._k.sign(data)

    # archivo .npkey: JSON con la clave privada (PEM, cifrada si hay contraseña)
    def to_file(self, password: str | None = None) -> bytes:
        from cryptography.hazmat.primitives import serialization as ser
        enc = ser.BestAvailableEncryption(password.encode()) if password else ser.NoEncryption()
        pem = self._k.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.PKCS8, enc)
        data = {"npkey": 1, "tipo": self.kind, "nombre": self.name, "creada": self.created,
                "protegida": bool(password), "publica": self.public_hex, "pem": pem.decode()}
        return json.dumps(data, ensure_ascii=False, indent=1).encode()

    @classmethod
    def info(cls, raw: bytes) -> dict:
        """Datos visibles de un .npkey sin pedir la contraseña."""
        try:
            d = json.loads(raw.decode())
            assert isinstance(d, dict) and d.get("npkey") == 1 and isinstance(d.get("pem"), str)
        except Exception:
            raise KeyFileError("formato", "No es un archivo de clave del Estudio de Temas.")
        return d

    @classmethod
    def from_file(cls, raw: bytes, password: str | None = None) -> "SigningKey":
        d = cls.info(raw)
        return cls(_load_pem(d["pem"].encode(), password), d.get("tipo", "autor"), d.get("nombre", ""),
                   d.get("creada", ""))

    @classmethod
    def from_pem(cls, raw: bytes, password: str | None = None, kind: str = "oficial", name: str = OFFICIAL_NAME):
        """Clave PEM suelta (la «firma-temas-OkumaWsX.key» del Publicador)."""
        return cls(_load_pem(raw, password), kind, name)


def _load_pem(pem: bytes, password: str | None):
    from cryptography.hazmat.primitives import serialization as ser
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    try:
        k = ser.load_pem_private_key(pem, password.encode() if password else None)
    except TypeError:
        raise KeyFileError("password" if not password else "wrong",
                           "La clave está protegida con contraseña." if not password
                           else "La clave no está protegida con contraseña.")
    except ValueError:
        raise KeyFileError("wrong" if password else "formato",
                           "La contraseña no es correcta." if password else "El archivo no tiene una clave válida.")
    if not isinstance(k, Ed25519PrivateKey):
        raise KeyFileError("formato", "El archivo no tiene una clave válida.")
    return k


def validate(theme: Theme, strict: bool = True) -> None:
    """Revisa que un tema v2 esté completo y sea válido. Lanza NptError('contenido').

    ``strict=False`` (al leer): lo que esta versión no conoce —espacios de imagen, secciones o
    tipos de fondo nuevos— se quita sin rechazar el tema, para abrir temas de un Estudio más nuevo.
    Lo que sí conoce tiene que estar bien.
    """
    def bad(msg):
        raise NptError(msg, "contenido")

    if not strict:
        theme.images = {k: v for k, v in theme.images.items() if k in IMAGE_SLOTS} \
            if isinstance(theme.images, dict) else theme.images
        if isinstance(theme.sections, dict):
            theme.sections = {k: v for k, v in theme.sections.items() if k in SECTIONS}
        if isinstance(theme.background, dict) and theme.background.get("tipo") not in (None, "solido", "degradado",
                                                                                       "imagen"):
            theme.background = {}

    if not isinstance(theme.name, str) or not theme.name.strip() or len(theme.name) > 32:
        bad("El nombre del tema debe tener entre 1 y 32 caracteres.")
    if not isinstance(theme.author, str) or len(theme.author) > 24:
        bad("El nombre de autor puede tener hasta 24 caracteres.")
    if not isinstance(theme.version, str) or not isinstance(theme.description, str) \
            or len(theme.version) > 8 or len(theme.description) > 80:
        bad("La versión o la descripción no son válidas.")
    if theme.kind not in ("oscuro", "claro"):
        bad("El tipo de tema debe ser «oscuro» o «claro».")
    if not isinstance(theme.colors, dict) or not isinstance(theme.alpha, dict) \
            or not isinstance(theme.window, dict) or not isinstance(theme.images, dict):
        bad("El contenido del tema no tiene el formato correcto.")
    missing = [t for t in TOKENS if not _HEX.match(str(theme.colors.get(t, "")))]
    if missing:
        bad("Faltan colores o no son válidos: " + ", ".join(missing))
    for k, v in theme.alpha.items():
        if k not in ALPHA_TOKENS or type(v) is not int or not 0 <= v <= 100:
            bad(f"Transparencia no válida en «{k}».")
    for k in ("opacidad", "sin_usar"):
        v = theme.window.get(k, 100)
        if type(v) is not int or not WINDOW_MIN <= v <= 100:
            bad(f"La opacidad de la ventana debe estar entre {WINDOW_MIN} y 100.")
    for slot, data in theme.images.items():
        if slot not in IMAGE_SLOTS:
            bad(f"Espacio de imagen desconocido: «{slot}».")
        fmt = image_format(data) if isinstance(data, (bytes, bytearray)) else None
        if fmt != "png" and not (fmt == "gif" and slot in ANIMATED_SLOTS):
            bad(f"La imagen de «{slot}» debe ser PNG" + (" o GIF." if slot in ANIMATED_SLOTS else "."))
        w, h = image_size(data)
        mw, mh = IMAGE_SLOTS[slot]
        if not (0 < w <= mw and 0 < h <= mh):
            bad(f"La imagen de «{slot}» mide {w}×{h}; el máximo es {mw}×{mh}.")
        n = image_frames(data)
        if n > MAX_FRAMES:                       # también al leer: nadie decodifica cientos de cuadros
            bad(f"La animación de «{slot}» tiene más de {MAX_FRAMES} cuadros.")
        if strict and n > 1 and slot not in ANIMATED_SLOTS:
            bad(f"La imagen de «{slot}» no puede ser animada.")
    if not isinstance(theme.gif_pause, bool):
        bad("El contenido del tema no tiene el formato correcto.")
    bg = theme.background
    if not isinstance(bg, dict):
        bad("El fondo de la ventana no tiene el formato correcto.")
    if bg and bg.get("tipo", "degradado") == "degradado":
        stops = bg.get("colores")
        lo, hi = GRADIENT_STOPS
        if not isinstance(stops, list) or not lo <= len(stops) <= hi:
            bad(f"El degradado debe tener entre {lo} y {hi} colores.")
        for st in stops:
            if not (isinstance(st, (list, tuple)) and len(st) == 2 and _HEX.match(str(st[0]))
                    and type(st[1]) is int and 0 <= st[1] <= 100):
                bad("Un color del degradado no es válido.")
        if bg.get("desde", "tl") not in GRADIENT_FROM:
            bad("No se sabe desde dónde empieza el degradado.")
    if bg and bg.get("tipo") == "imagen" and "fondo" not in theme.images:
        bad("El fondo de imagen necesita la imagen «fondo».")
    if bg:
        if not isinstance(bg.get("una_pieza", False), bool):
            bad("«Fondo de una pieza» no es válido.")
        t = bg.get("tinte", 35)
        if type(t) is not int or not 0 <= t <= 90:
            bad("El tinte de los paneles debe estar entre 0 y 90.")
    if not isinstance(theme.sections, dict):
        bad("Las secciones no tienen el formato correcto.")
    for k, sec in theme.sections.items():
        if k not in SECTIONS or not isinstance(sec, dict):
            bad(f"Sección desconocida: «{k}».")
        for part in ("fondo", "contenido"):
            v = sec.get(part, 100)
            if type(v) is not int or not 0 <= v <= 100:
                bad(f"Transparencia no válida en la sección «{k}».")
        if not isinstance(sec.get("realce", False), bool):
            bad(f"Borde de realce no válido en la sección «{k}».")


def image_format(data: bytes) -> str | None:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def image_frames(data: bytes) -> int:
    """Cuadros de una imagen sin abrirla: 1, los del PNG animado (bloque acTL) o los del GIF."""
    fmt = image_format(data)
    if fmt == "gif":
        return max(1, data.count(b"\x21\xf9\x04"))
    if fmt != "png":
        return 0
    i = 8
    while i + 8 <= len(data):
        ln = struct.unpack(">I", data[i:i + 4])[0]
        kind = data[i + 4:i + 8]
        if kind == b"acTL" and ln >= 8 and i + 16 <= len(data):
            return max(1, struct.unpack(">I", data[i + 8:i + 12])[0])
        if kind in (b"IDAT", b"IEND") or ln > len(data):
            break
        i += 12 + ln
    return 1


def image_size(data: bytes) -> tuple[int, int]:
    """Ancho y alto leídos del encabezado PNG (sin abrir la imagen)."""
    fmt = image_format(data)
    if fmt == "png" and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if fmt == "gif" and len(data) >= 10:
        return struct.unpack("<HH", data[6:10])
    return 0, 0


def _pack_content(theme: Theme) -> bytes:
    blobs, index, off = [], {}, 0
    for slot in sorted(theme.images):
        data = bytes(theme.images[slot])
        index[slot] = {"inicio": off, "largo": len(data), "formato": image_format(data)}
        if image_frames(data) > 1:
            index[slot]["cuadros"] = image_frames(data)
        blobs.append(data)
        off += len(data)
    meta = {
        "formato": VERSION_STUDIO, "nombre": theme.name, "autor": theme.author, "version": theme.version,
        "descripcion": theme.description, "tipo": theme.kind, "creado": theme.created,
        "colores": {t: theme.colors[t].lower() for t in TOKENS},
        "alfa": {k: v for k, v in sorted(theme.alpha.items()) if v < 100},
        "ventana": {"opacidad": theme.window.get("opacidad", 100), "sin_usar": theme.window.get("sin_usar", 100)},
        "admite_transparencia": theme.transparency,
        "imagenes": index,
    }
    if theme.background:
        meta["fondo"] = dict(theme.background)
        if isinstance(meta["fondo"].get("colores"), list):
            meta["fondo"]["colores"] = [[str(c).lower(), p] for c, p in meta["fondo"]["colores"]]
    if theme.sections:
        meta["secciones"] = {k: v for k, v in sorted(theme.sections.items())}
    if not theme.gif_pause:
        meta["pausar_animaciones"] = False
    js = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).encode()
    return b"NPTC" + struct.pack(">I", len(js)) + js + b"".join(blobs)


def _unpack_content(raw: bytes) -> Theme:
    try:
        if raw[:4] != b"NPTC":
            raise ValueError
        n = struct.unpack(">I", raw[4:8])[0]
        meta = json.loads(raw[8:8 + n].decode())
        if not isinstance(meta, dict):
            raise ValueError
        blob = raw[8 + n:]
        images = {}
        idx = meta.get("imagenes") or {}
        if not isinstance(idx, dict):
            raise ValueError
        for slot, e in idx.items():
            a, ln = int(e["inicio"]), int(e["largo"])
            if a < 0 or ln <= 0 or a + ln > len(blob):
                raise ValueError
            images[slot] = blob[a:a + ln]
        th = Theme(name=meta["nombre"], author=meta.get("autor", ""), colors=meta["colores"],
                   version=meta.get("version", "1.0"), description=meta.get("descripcion", ""),
                   kind=meta.get("tipo", "oscuro"), alpha=meta.get("alfa") or {},
                   window=meta.get("ventana") or {}, images=images, created=str(meta.get("creado", "")),
                   background=meta.get("fondo") or {}, sections=meta.get("secciones") or {},
                   gif_pause=meta.get("pausar_animaciones", True) is not False)
    except Exception:
        raise NptError("El contenido del tema no se puede leer.", "contenido")
    validate(th, strict=False)
    th.colors = {k: th.colors[k].lower() for k in TOKENS}
    return th


def write(theme: Theme, key: SigningKey) -> bytes:
    """Crea un .npt v2: valida, comprime, cifra y firma con la clave de autor (o la oficial)."""
    validate(theme)
    plain = zlib.compress(_pack_content(theme), 9)
    header = MAGIC + bytes([VERSION_STUDIO, 0])
    pub = key.public_bytes
    nonce = os.urandom(_NONCE_LEN)
    ct = _aes().encrypt(nonce, plain, header + pub)
    body = header + pub + nonce + ct
    out = body + key.sign(body)
    if len(out) > MAX_FILE:
        raise NptError(f"El tema pesa {len(out) // 1024} KB; el máximo es {MAX_FILE // 1024 // 1024} MB. "
                       "Usa imágenes más livianas o menos imágenes.", "grande")
    return out


_P = 2 ** 255 - 19
_D = -121665 * pow(121666, _P - 2, _P) % _P


def _weak_key(pub: bytes) -> bool:
    """True si la clave no es un punto válido de orden grande (claves «débiles» con las que
    cualquiera podría falsificar una firma). Se multiplica el punto por 8: si da el neutro, es débil."""
    y = int.from_bytes(pub, "little") & ((1 << 255) - 1)
    sign = pub[31] >> 7
    if y >= _P:
        return True
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P:
        x = x * pow(2, (_P - 1) // 4, _P) % _P
    if (x * x - x2) % _P or (x == 0 and sign):
        return True
    if x & 1 != sign:
        x = _P - x
    for _ in range(3):                           # 3 duplicaciones = multiplicar por 8
        xy = x * y % _P
        t = _D * xy * xy % _P
        x, y = 2 * xy * pow(1 + t, _P - 2, _P) % _P, (y * y + x * x) * pow(1 - t, _P - 2, _P) % _P
    return x == 0 and y == 1


def _read_v2(data: bytes) -> ReadResult:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    if len(data) < 5 + _PUB_LEN + _NONCE_LEN + 16 + _SIG_LEN:
        raise NptError("El archivo está incompleto o dañado", "danado")
    header, pub = data[:5], data[5:5 + _PUB_LEN]
    body, sig = data[:-_SIG_LEN], data[-_SIG_LEN:]
    if _weak_key(pub):
        raise NptError("El archivo está dañado o fue modificado después de crearlo.", "danado")
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(sig, body)
    except (InvalidSignature, ValueError):
        raise NptError("El archivo está dañado o fue modificado después de crearlo.", "danado")
    nonce = data[5 + _PUB_LEN:5 + _PUB_LEN + _NONCE_LEN]
    try:
        plain = _aes().decrypt(nonce, body[5 + _PUB_LEN + _NONCE_LEN:], header + pub)
    except Exception:
        raise NptError("El archivo está dañado o fue modificado después de crearlo.", "danado")
    try:
        d = zlib.decompressobj()
        raw = d.decompress(plain, MAX_PLAIN)
    except zlib.error:
        raise NptError("El contenido del tema no se puede leer.", "contenido")
    if d.unconsumed_tail:
        raise NptError("El contenido del tema es demasiado grande.", "contenido")
    theme = _unpack_content(raw)
    pub_hex = pub.hex()
    official = is_official_key(pub_hex)
    return ReadResult(theme, pub_hex, official, (not official) and is_reserved_name(theme.author), 2)


def read(data: bytes) -> ReadResult:
    """Lee un .npt de cualquier versión (para el Estudio): firma, sello, descifrado y validación."""
    _check_head(data)
    if data[3] == VERSION_STUDIO:
        return _read_v2(data)
    t, official = _unpack_v1(data)
    a = t.get("alpha")
    window = ({"opacidad": max(WINDOW_MIN, round(a["window"] * 100)),
               "sin_usar": max(WINDOW_MIN, round(a["idle"] * 100))} if a else {"opacidad": 100, "sin_usar": 100})
    th = Theme(name=t["name"][:32], author="" if t["author"] == "Desconocido" else t["author"][:24],
               colors=dict(t["colors"]), version=t["version"][:8], window=window)
    return ReadResult(th, OFFICIAL_KEY if official else "", official,
                      (not official) and is_reserved_name(th.author), 1)
