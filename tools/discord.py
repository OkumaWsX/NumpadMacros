#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Anuncia una versión en Discord con el webhook del secreto DISCORD_WEBHOOK.

    WEBHOOK=... python tools/discord.py 3.3.0 [--extra " · beta"] [--resumen "…"]

Si Discord responde con un error, explica en palabras simples qué revisar
(sin mostrar la dirección del webhook, que es secreta).
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

REPO = os.environ.get("GITHUB_REPOSITORY", "OkumaWsX/NumpadMacros")
# Acepta discord.com / discordapp.com / ptb. / canary. y /api/v10/webhooks/, aunque venga con texto alrededor
WEBHOOK_RE = re.compile(r"https://(?:[a-z]+\.)?discord(?:app)?\.com/api/(?:v\d+/)?webhooks/\d+/[\w-]+")


def describe(text: str) -> str:
    """Qué hay guardado en el secreto, sin mostrar la parte secreta."""
    t = text.strip()
    if "discord.gg/" in t or "discord.com/invite/" in t:
        return ("Guardaste un enlace de invitación al servidor, no la URL del webhook. En Discord: Editar canal → "
                "Integraciones → Webhooks → elige el webhook → «Copiar URL del webhook».")
    if "discord.com/channels/" in t:
        return ("Guardaste el enlace de un canal, no la URL del webhook. En Discord: Editar canal → Integraciones → "
                "Webhooks → elige el webhook → «Copiar URL del webhook».")
    if "webhooks" in t:
        cut = t[:t.index("webhooks") + len("webhooks")]
        return (f"Empieza con «{cut}…» pero está incompleta o tiene otro formato: copia de nuevo la URL completa "
                "con «Copiar URL del webhook».")
    start = t[:8] + "…" if len(t) > 8 else t
    return (f"Tiene {len(t)} caracteres y empieza con «{start}». La URL correcta empieza con "
            "https://discord.com/api/webhooks/ y se obtiene con «Copiar URL del webhook».")


HINTS = {
    401: "el webhook no es válido: vuelve a copiar su URL en Discord y guárdala de nuevo en el secreto DISCORD_WEBHOOK.",
    403: "Discord rechazó el mensaje: revisa que el webhook siga existiendo y tenga permiso en el canal.",
    404: "el webhook ya no existe (¿lo borraste en Discord?): crea uno nuevo y actualiza el secreto DISCORD_WEBHOOK.",
    429: "Discord pidió esperar (demasiados mensajes seguidos): vuelve a intentarlo en unos minutos.",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    ap.add_argument("--extra", default="")
    ap.add_argument("--resumen", default="")
    a = ap.parse_args()
    hook = (os.environ.get("WEBHOOK") or "").strip().strip('"').strip("'")
    if not hook:
        print("::notice::No hay webhook de Discord configurado (secreto DISCORD_WEBHOOK): no se anuncia.")
        return 0
    found = WEBHOOK_RE.search(hook)
    if not found:
        print("::error::El secreto DISCORD_WEBHOOK no contiene una URL de webhook de Discord. " + describe(hook))
        return 1
    hook = found.group(0)
    url = f"https://github.com/{REPO}/releases/tag/v{a.version}"
    msg = (f"🎉 **Numpad Macros {a.version}**{a.extra} ya está disponible.\n"
           + (f"Novedades: {a.resumen}.\n" if a.resumen else "")
           + f"Abre la app y pulsa «Actualizar», o descárgala aquí: {url}")
    body = json.dumps({"content": msg[:1900], "username": "Numpad Macros",
                       "allowed_mentions": {"parse": []}}).encode()
    req = urllib.request.Request(hook.split("?")[0] + "?wait=true", data=body, method="POST", headers={
        "Content-Type": "application/json",
        "User-Agent": f"DiscordBot (https://github.com/{REPO}, 1.0)"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print(f"Anunciado en Discord (respuesta {r.status}).")
            return 0
    except urllib.error.HTTPError as e:
        detail = e.read()[:300].decode("utf-8", "replace")
        hint = HINTS.get(e.code, "revisa el webhook en Discord.")
        print(f"::error::Discord respondió {e.code}: {hint}")
        print(f"Detalle de Discord: {detail}")
        return 1
    except Exception as e:
        print(f"::error::No pude conectar con Discord: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
