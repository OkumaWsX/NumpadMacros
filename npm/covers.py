# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Portadas y duración de los sonidos (para el selector en cuadrícula).

La portada sale de, en este orden:
  1. una imagen con el mismo nombre al lado del archivo (Tambores.jpg / .png / .webp);
  2. la imagen que trae dentro el archivo: MP3 y WAV (etiqueta ID3, marco APIC/PIC),
     FLAC (bloque PICTURE) y OGG / Opus (METADATA_BLOCK_PICTURE o COVERART).
Se lee solo lo necesario (no se decodifica el audio). Sin dependencias GPL.
"""
from __future__ import annotations

import base64
import io
import os
import struct

MAX_READ = 24 * 1024 * 1024          # no leer más que esto buscando una portada
SIDECAR = (".jpg", ".jpeg", ".png", ".webp")


# ---------------------------------------------------------------- utilidades
def _synchsafe(b: bytes) -> int:
    return (b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3]


def _deunsync(data: bytes) -> bytes:
    return data.replace(b"\xff\x00", b"\xff")


def _skip_text(data: bytes, pos: int, enc: int) -> int:
    """Salta un texto terminado en 0 (UTF-16 → doble 0 alineado)."""
    if enc in (1, 2):
        while pos + 1 < len(data):
            if data[pos] == 0 and data[pos + 1] == 0:
                return pos + 2
            pos += 2
        return len(data)
    end = data.find(b"\x00", pos)
    return len(data) if end < 0 else end + 1


# ---------------------------------------------------------------- ID3 (MP3, WAV)
def _id3_picture(tag: bytes) -> bytes | None:
    """tag = etiqueta ID3v2 completa (empieza con «ID3»)."""
    if len(tag) < 10 or tag[:3] != b"ID3":
        return None
    ver, flags = tag[3], tag[5]
    size = _synchsafe(tag[6:10])
    body = tag[10:10 + size]
    if flags & 0x80 and ver < 4:
        body = _deunsync(body)
    pos = 0
    if flags & 0x40:                                       # cabecera extendida
        if ver == 3 and len(body) >= 4:
            pos = 4 + struct.unpack(">I", body[:4])[0]
        elif ver == 4 and len(body) >= 4:
            pos = _synchsafe(body[:4])
    best, first = None, None
    while pos + (6 if ver == 2 else 10) <= len(body):
        if ver == 2:
            fid = body[pos:pos + 3]
            fsize = int.from_bytes(body[pos + 3:pos + 6], "big")
            pos += 6
            fflags = 0
        else:
            fid = body[pos:pos + 4]
            fsize = _synchsafe(body[pos + 4:pos + 8]) if ver == 4 else struct.unpack(">I", body[pos + 4:pos + 8])[0]
            fflags = struct.unpack(">H", body[pos + 8:pos + 10])[0]
            pos += 10
        if not fid.strip(b"\x00") or fsize <= 0:
            break
        frame = body[pos:pos + fsize]
        pos += fsize
        if fid not in (b"APIC", b"PIC"):
            continue
        if ver == 4:
            if fflags & 0x0001:                            # indicador de largo
                frame = frame[4:]
            if fflags & 0x0002:
                frame = _deunsync(frame)
        if len(frame) < 6:
            continue
        enc = frame[0]
        if fid == b"PIC":
            p = 4                                          # 3 letras de formato
        else:
            p = _skip_text(frame, 1, 0)                    # tipo MIME (latin-1)
        if p >= len(frame):
            continue
        ptype = frame[p]
        p = _skip_text(frame, p + 1, enc)                  # descripción
        data = frame[p:]
        if not data:
            continue
        if ptype == 3:                                     # portada frontal
            return data
        best = best or (data if ptype in (0, 4) else None)
        first = first or data
    return best or first


def _riff_id3(f) -> bytes | None:
    """WAV/AIFF con una etiqueta ID3 dentro («id3 » / «ID3 »)."""
    head = f.read(12)
    if len(head) < 12 or head[:4] not in (b"RIFF", b"FORM"):
        return None
    big = head[:4] == b"FORM"
    read = 12
    while read < MAX_READ:
        ch = f.read(8)
        if len(ch) < 8:
            return None
        cid = ch[:4]
        size = struct.unpack(">I" if big else "<I", ch[4:])[0]
        if cid in (b"id3 ", b"ID3 ", b"ID32"):
            return _id3_picture(f.read(min(size, MAX_READ)))
        f.seek(size + (size & 1), 1)
        read += 8 + size
    return None


# ---------------------------------------------------------------- FLAC / OGG
def _flac_picture_block(b: bytes) -> tuple[int, bytes] | None:
    try:
        ptype, mlen = struct.unpack(">II", b[:8])
        p = 8 + mlen
        dlen = struct.unpack(">I", b[p:p + 4])[0]
        p += 4 + dlen + 16
        size = struct.unpack(">I", b[p:p + 4])[0]
        return ptype, b[p + 4:p + 4 + size]
    except struct.error:
        return None


def _flac_picture(f) -> bytes | None:
    if f.read(4) != b"fLaC":
        return None
    best = None
    while True:
        h = f.read(4)
        if len(h) < 4:
            return best
        last, btype, size = h[0] & 0x80, h[0] & 0x7F, int.from_bytes(h[1:], "big")
        if btype == 6:
            pic = _flac_picture_block(f.read(size))
            if pic:
                if pic[0] == 3:
                    return pic[1]
                best = best or pic[1]
        else:
            f.seek(size, 1)
        if last:
            return best


def _ogg_packets(f, want=2):
    """Primeros `want` paquetes de un archivo Ogg."""
    packets, cur, total = [], b"", 0
    while len(packets) < want and total < MAX_READ:
        head = f.read(27)
        if len(head) < 27 or head[:4] != b"OggS":
            break
        nseg = head[26]
        table = f.read(nseg)
        for seg in table:
            cur += f.read(seg)
            total += seg
            if seg < 255:
                packets.append(cur)
                cur = b""
                if len(packets) >= want:
                    break
    return packets


def _ogg_picture(f) -> bytes | None:
    pk = _ogg_packets(f, 2)
    if len(pk) < 2:
        return None
    c = pk[1]
    if c[:7] == b"\x03vorbis":
        p = 7
    elif c[:8] == b"OpusTags":
        p = 8
    else:
        return None
    try:
        vlen = struct.unpack("<I", c[p:p + 4])[0]
        p += 4 + vlen
        n = struct.unpack("<I", c[p:p + 4])[0]
        p += 4
        legacy = None
        for _ in range(n):
            ln = struct.unpack("<I", c[p:p + 4])[0]
            p += 4
            entry = c[p:p + ln]
            p += ln
            key, _, val = entry.partition(b"=")
            key = key.upper()
            if key == b"METADATA_BLOCK_PICTURE":
                pic = _flac_picture_block(base64.b64decode(val))
                if pic:
                    return pic[1]
            elif key == b"COVERART":
                legacy = base64.b64decode(val)
        return legacy
    except (struct.error, ValueError):
        return None


# ---------------------------------------------------------------- público
def sidecar(path: str) -> str | None:
    stem, _ = os.path.splitext(path)
    folder = os.path.dirname(path) or "."
    base = os.path.basename(stem).lower()
    try:
        names = os.listdir(folder)
    except OSError:
        return None
    for name in names:
        s, ext = os.path.splitext(name)
        if s.lower() == base and ext.lower() in SIDECAR:
            return os.path.join(folder, name)
    return None


def embedded(path: str) -> bytes | None:
    """Bytes de la imagen que trae dentro el archivo, o None."""
    try:
        with open(path, "rb") as f:
            head = f.read(4)
            f.seek(0)
            if head[:3] == b"ID3":
                f.seek(6)
                size = _synchsafe(f.read(4))
                f.seek(0)
                return _id3_picture(f.read(min(10 + size, MAX_READ)))
            if head == b"fLaC":
                return _flac_picture(f)
            if head == b"OggS":
                return _ogg_picture(f)
            if head in (b"RIFF", b"FORM"):
                return _riff_id3(f)
    except (OSError, ValueError):
        return None
    return None


def cover_image(path: str, size: int = 256):
    """Imagen PIL cuadrada (recortada al centro) de la portada, o None."""
    try:
        from PIL import Image
    except Exception:
        return None
    src = sidecar(path)
    data = None
    if src is None:
        data = embedded(path)
        if not data:
            return None
    try:
        im = Image.open(src) if src else Image.open(io.BytesIO(data))
        im.draft("RGB", (size * 2, size * 2))
        im = im.convert("RGB")
    except Exception:
        return None
    w, h = im.size
    s = min(w, h)
    im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
    return im.resize((size, size), Image.LANCZOS)


def duration(path: str) -> float | None:
    try:
        import soundfile as sf
        return float(sf.info(path).duration)
    except Exception:
        return None


def fmt_duration(sec: float | None) -> str:
    if sec is None:
        return "—"
    sec = int(round(sec))
    return f"{sec // 60}:{sec % 60:02d}"
