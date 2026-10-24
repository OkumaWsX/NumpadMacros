#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Anuncia una versión del Estudio de Temas en Discord (webhook del secreto DISCORD_WEBHOOK_ESTUDIO).

    WEBHOOK=... python tools/estudio/anunciar_discord.py 1.0.1 --notas notas.md [--beta]

Lo usa «Publicar Estudio de Temas». Si Discord responde con un error, explica qué revisar sin mostrar la
dirección del webhook (es secreta). Es aparte de tools/discord.py, que es el de Numpad Macros.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

REPO = os.environ.get("GITHUB_REPOSITORY", "OkumaWsX/NumpadMacros")
SECRET = "DISCORD_WEBHOOK_ESTUDIO"
# acepta discord.com / discordapp.com / ptb. / canary. y /api/v10/webhooks/, aunque venga con texto alrededor
WEBHOOK_RE = re.compile(r"https://(?:[a-z]+\.)?discord(?:app)?\.com/api/(?:v\d+/)?webhooks/\d+/[\w-]+")
MAX_ITEMS = 5

HINTS = {
    401: f"el webhook no es válido: vuelve a copiar su URL en Discord y guárdala de nuevo en el secreto {SECRET}.",
    403: "Discord rechazó el mensaje: revisa que el webhook siga existiendo y tenga permiso en el canal.",
    404: f"el webhook ya no existe (¿lo borraste en Discord?): crea uno nuevo y actualiza el secreto {SECRET}.",
    429: "Discord pidió esperar (demasiados mensajes seguidos): vuelve a intentarlo en unos minutos.",
}


def items(notes: str) -> list[str]:
    """Las novedades (viñetas) de las notas de la Release, sin el pie que va tras «---»."""
    out = []
    for line in notes.splitlines():
        t = line.strip()
        if re.fullmatch(r"-{3,}", t):
            break
        if t.startswith(("- ", "* ")):
            t = t[2:].strip()
            m = re.match(r"\*\*(.+?)\*\*", t)          # «**Título**: detalle» -> solo el título
            out.append((m.group(1) if m else t).replace("*", "").replace("`", "").rstrip(":. "))
    return out


def message(version: str, notes: str, beta: bool = False) -> str:
    url = f"https://github.com/{REPO}/releases/tag/estudio-v{version}"
    lines = [f"🎨 **Estudio de Temas {version}**{' (versión de prueba)' if beta else ''} ya está disponible."]
    news = items(notes)
    if news:
        lines.append("Novedades:")
        for t in news[:MAX_ITEMS]:
            lines.append(f"• {t[:160] + '…' if len(t) > 160 else t}")
        if len(news) > MAX_ITEMS:
            lines.append(f"…y {len(news) - MAX_ITEMS} más.")
    lines.append(f"Abre el Estudio y te avisará para actualizar, o descárgalo aquí: {url}")
    return "\n".join(lines)[:1900]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    ap.add_argument("--notas", default="", help="archivo con las notas de la Release")
    ap.add_argument("--beta", action="store_true")
    a = ap.parse_args()
    hook = (os.environ.get("WEBHOOK") or "").strip().strip('"').strip("'")
    if not hook:
        print(f"::notice::No hay webhook de Discord para el Estudio (secreto {SECRET}): no se anuncia.")
        return 0
    found = WEBHOOK_RE.search(hook)
    if not found:
        print(f"::error::El secreto {SECRET} no contiene una URL de webhook de Discord (debe empezar con "
              "https://discord.com/api/webhooks/; en Discord: «Copiar URL del webhook»).")
        return 1
    notes = ""
    if a.notas:
        try:
            with open(a.notas, encoding="utf-8") as f:
                notes = f.read()
        except OSError:
            pass
    body = json.dumps({"content": message(a.version, notes, a.beta), "username": "Estudio de Temas",
                       "allowed_mentions": {"parse": []}}).encode()
    req = urllib.request.Request(found.group(0) + "?wait=true", data=body, method="POST", headers={
        "Content-Type": "application/json",
        "User-Agent": f"DiscordBot (https://github.com/{REPO}, 1.0)"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print(f"Anunciado en Discord (respuesta {r.status}).")
            return 0
    except urllib.error.HTTPError as e:
        print(f"::error::Discord respondió {e.code}: {HINTS.get(e.code, 'revisa el webhook en Discord.')}")
        print(f"Detalle de Discord: {e.read()[:300].decode('utf-8', 'replace')}")
        return 1
    except Exception as e:
        print(f"::error::No pude conectar con Discord: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
