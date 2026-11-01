# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Sección «Capturas» de las notas de una Release del Estudio de Temas.

Cada versión publicada lleva capturas de ESA versión, en tools/estudio/capturas/<versión>/ con un
capturas.txt (``archivo | descripción``). Los enlaces apuntan a una etiqueta o un commit fijo, así la
Release sigue mostrando cómo era el Estudio aunque las imágenes cambien después.

La sección va antes del pie «---»: el aviso de versión nueva (actualizar.py) y el anuncio de Discord
solo leen las viñetas, así que las imágenes no les afectan.

Uso (agregar o reemplazar las capturas de una Release ya publicada):
    python tools/estudio/capturas_release.py --version 1.1.0 --ref <commit> --notas actuales.md > nuevas.md
"""
import argparse
import os
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
CARPETA = os.path.join(HERE, "capturas")
REPO = "OkumaWsX/NumpadMacros"
INICIO, FIN = "<!-- capturas -->", "<!-- /capturas -->"
EXT = (".png", ".jpg", ".jpeg", ".gif")


def lista(version: str, carpeta: str = CARPETA) -> list[tuple[str, str]]:
    """[(archivo, descripción)] de capturas/<versión>/, en el orden de capturas.txt (o por nombre)."""
    d = os.path.join(carpeta, version)
    manifiesto = os.path.join(d, "capturas.txt")
    if os.path.isfile(manifiesto):
        out = []
        with open(manifiesto, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea or linea.startswith("#"):
                    continue
                nombre, _, texto = (p.strip() for p in linea.partition("|"))
                if os.path.isfile(os.path.join(d, nombre)):
                    out.append((nombre, texto))
        return out
    if os.path.isdir(d):
        return [(n, "") for n in sorted(os.listdir(d)) if n.lower().endswith(EXT)]
    return []


def seccion(version: str, ref: str, carpeta: str = CARPETA) -> str:
    """La sección en Markdown, con las imágenes enlazadas a ``ref``; vacía si no hay capturas."""
    items = lista(version, carpeta)
    if not items:
        return ""
    base = f"https://github.com/{REPO}/raw/{ref}/tools/estudio/capturas/{version}"
    out = [INICIO, f"### Capturas (versión {version})", ""]
    for nombre, texto in items:
        out.append(f"![{texto or nombre}]({base}/{urllib.parse.quote(nombre)})")
        if texto:
            out.append(f"<sub>{texto}</sub>")
        out.append("")
    out.append(FIN)
    return "\n".join(out).rstrip()


def poner(notas: str, sec: str) -> str:
    """Reemplaza la sección de capturas de las notas, o la agrega antes del pie «---»."""
    notas = notas or ""
    if INICIO in notas and FIN in notas:
        a, resto = notas.split(INICIO, 1)
        b = resto.split(FIN, 1)[1]
        return (a.rstrip() + "\n\n" + sec + "\n\n" + b.lstrip()).strip() + "\n"
    lineas = notas.splitlines()
    for i, linea in enumerate(lineas):
        if linea.strip() and set(linea.strip()) == {"-"} and len(linea.strip()) >= 3:
            antes, despues = "\n".join(lineas[:i]).rstrip(), "\n".join(lineas[i:])
            return antes + "\n\n" + sec + "\n\n" + despues.rstrip() + "\n"
    return notas.rstrip() + "\n\n" + sec + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", required=True)
    ap.add_argument("--ref", required=True, help="etiqueta o commit donde están las imágenes")
    ap.add_argument("--notas", default="", help="archivo con las notas actuales de la Release")
    a = ap.parse_args()
    version = a.version.lstrip("v").removeprefix("estudio-v")
    sec = seccion(version, a.ref)
    if not sec:
        sys.exit(f"No hay capturas de la versión {version} (falta tools/estudio/capturas/{version}/).")
    notas = ""
    if a.notas:
        with open(a.notas, encoding="utf-8") as f:
            notas = f.read()
    sys.stdout.write(poner(notas, sec))


if __name__ == "__main__":
    main()
