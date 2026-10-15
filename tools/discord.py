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
    if not re.match(r"^https://(?:\w+\.)?(?:discord|discordapp)\.com/api/webhooks/\d+/[\w-]+", hook):
        print("::error::El secreto DISCORD_WEBHOOK no parece una URL de webhook de Discord "
              "(debe empezar con https://discord.com/api/webhooks/). Vuelve a copiarla en Discord.")
        return 1
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
