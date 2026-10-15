#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Prepara una versión para publicar (lo usa el robot «Publicar versión»).

    python tools/release.py prepare --tipo mejora [--version 3.4.0] [--importante]

1. Calcula el número de versión:
   - --version X.Y.Z si se indica (el Publicador manda el del código), o
   - «automatico»: el número que ya trae el código si es mayor que el publicado, o
   - corrección / mejora / grande: suma 1 al último número publicado.
2. Revisa que la sección «## [Sin publicar]» del CHANGELOG tenga novedades.
3. Escribe el número en npm/__init__.py, convierte «Sin publicar» en
   «## [X.Y.Z] - fecha» y deja una sección «Sin publicar» vacía.
4. Genera notas.md (las notas de la Release) y escribe version=X.Y.Z en
   $GITHUB_OUTPUT.
Si algo no está bien, termina con un mensaje claro y código 1: no se publica nada.
"""
import argparse
import datetime
import os
import re
import subprocess
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INIT = os.path.join(ROOT, "npm", "__init__.py")
CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")
REPO = "OkumaWsX/NumpadMacros"
UNRELEASED = re.compile(r"^## \[Sin publicar\][^\n]*\n", re.M | re.I)
IMPORTANT = "<!-- importante -->"
CAPS_START, CAPS_END = "<!-- capturas -->", "<!-- /capturas -->"


def fail(msg):
    print(f"::error::{msg}")
    print(f"\n✗ {msg}")
    sys.exit(1)


def parse(v):
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (v or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def code_version():
    m = re.search(r'__version__\s*=\s*"([^"]+)"', open(INIT, encoding="utf-8").read())
    return m.group(1) if m else "0.0.0"


def published_versions():
    try:
        out = subprocess.run(["git", "tag", "--list", "v*"], cwd=ROOT, capture_output=True, text=True).stdout
    except OSError:
        out = ""
    return sorted(p for p in (parse(t) for t in out.split()) if p)


def target_version(tipo, explicit, last):
    if explicit:
        v = parse(explicit)
        if not v:
            fail(f"«{explicit}» no es un número de versión válido (ejemplo: 3.4.0).")
        return v
    code = parse(code_version())
    if tipo == "automatico":
        if code and code > last:
            return code
        fail(f"El código dice {code_version()}, que no es mayor que la última publicada "
             f"({'.'.join(map(str, last))}). Elige el tipo de versión (corrección, mejora o grande).")
    a, b, c = last
    return {"correccion": (a, b, c + 1), "mejora": (a, b + 1, 0), "grande": (a + 1, 0, 0)}[tipo]


def split_unreleased(text):
    m = UNRELEASED.search(text)
    if not m:
        fail("El CHANGELOG no tiene la sección «## [Sin publicar]» con las novedades.")
    nxt = re.search(r"^## \[", text[m.end():], re.M)
    end = m.end() + (nxt.start() if nxt else len(text) - m.end())
    return m, text[m.end():end], end


def prepare(args):
    last = (published_versions() or [(0, 0, 0)])[-1]
    ver_t = target_version(args.tipo, args.version, last)
    if ver_t <= last:
        fail(f"La versión {'.'.join(map(str, ver_t))} no es mayor que la última publicada "
             f"({'.'.join(map(str, last))}).")
    ver = ".".join(map(str, ver_t))
    text = open(CHANGELOG, encoding="utf-8").read()
    m, body, end = split_unreleased(text)
    if not re.search(r"^\s*[-*] \S", body, re.M):
        fail("La sección «Sin publicar» del CHANGELOG está vacía: anota qué cambió antes de publicar.")
    date = datetime.date.today().isoformat()
    body = body.strip("\n")
    new = (text[:m.start()] + "## [Sin publicar]\n\n" + f"## [{ver}] - {date}\n" + body + "\n\n"
           + text[end:].lstrip("\n"))
    link = f"[{ver}]: https://github.com/{REPO}/releases/tag/v{ver}"
    if link not in new:
        refs = re.search(r"^\[\d+\.\d+\.\d+\]: ", new, re.M)
        new = new[:refs.start()] + link + "\n" + new[refs.start():] if refs else new.rstrip("\n") + "\n\n" + link + "\n"
    with open(CHANGELOG, "w", encoding="utf-8") as f:
        f.write(new)
    src = open(INIT, encoding="utf-8").read()
    src = re.sub(r'__version__\s*=\s*"[^"]+"', f'__version__ = "{ver}"', src)
    with open(INIT, "w", encoding="utf-8") as f:
        f.write(src)
    caps = captures_section(ver, f"v{ver}")          # enlaces fijos a la etiqueta de esta versión
    notes = (IMPORTANT + "\n" if args.importante else "") + body + "\n\n" + (caps + "\n\n" if caps else "") + DOWNLOADS
    with open(os.path.join(ROOT, "notas.md"), "w", encoding="utf-8") as f:
        f.write(notes)
    summary = re.findall(r"^\s*[-*] (.+)$", body, re.M)
    with open(os.path.join(ROOT, "resumen.txt"), "w", encoding="utf-8") as f:
        f.write("; ".join(re.sub(r"[*`]", "", s).split(":")[0].strip().rstrip(".") for s in summary[:3]))
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"version={ver}\n")
    print(f"✓ Versión {ver} preparada ({len(summary)} cambios anotados).")


def captures_section(version, ref):
    """Sección «Capturas» con las imágenes de docs/capturas/<versión>/, enlazadas a `ref`
    (una etiqueta o un commit), para que la Release muestre siempre esa versión de la app."""
    folder = os.path.join(ROOT, "docs", "capturas", version)
    manifest = os.path.join(folder, "capturas.txt")
    items = []
    if os.path.isfile(manifest):
        for line in open(manifest, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, _, caption = (p.strip() for p in line.partition("|"))
            if os.path.isfile(os.path.join(folder, name)):
                items.append((name, caption))
    elif os.path.isdir(folder):
        items = [(n, "") for n in sorted(os.listdir(folder)) if n.lower().endswith((".png", ".jpg", ".gif"))]
    if not items:
        return ""
    base = f"https://github.com/{REPO}/raw/{ref}/docs/capturas/{version}"
    out = [CAPS_START, f"### Capturas (versión {version})", ""]
    for name, caption in items:
        alt = caption or name
        out.append(f"![{alt}]({base}/{urllib.parse.quote(name)})")
        if caption:
            out.append(f"<sub>{caption}</sub>")
        out.append("")
    out.append(CAPS_END)
    return "\n".join(out).rstrip()


def put_captures(body, section):
    """Reemplaza (o agrega) la sección de capturas en las notas de una Release."""
    body = body or ""
    if CAPS_START in body and CAPS_END in body:
        a, rest = body.split(CAPS_START, 1)
        _, b = rest.split(CAPS_END, 1)
        return (a.rstrip() + "\n\n" + section + "\n\n" + b.lstrip()).strip() + "\n"
    marker = "### Descargas"
    if marker in body:
        a, b = body.split(marker, 1)
        return a.rstrip() + "\n\n" + section + "\n\n" + marker + b
    return body.rstrip() + "\n\n" + section + "\n"


def captures_cmd(args):
    version = args.version.lstrip("v")
    section = captures_section(version, args.ref)
    if not section:
        fail(f"No hay capturas para la versión {version} (falta la carpeta docs/capturas/{version}/).")
    body = open(args.notas, encoding="utf-8").read() if args.notas else ""
    sys.stdout.write(put_captures(body, section))


DOWNLOADS = """### Descargas
| Sistema | Archivo |
|---|---|
| Windows 10/11 (instalador) | `NumpadMacros-Windows-Setup.exe` |
| Windows (portátil) | `NumpadMacros-Windows-portable.zip` |
| Linux | `NumpadMacros-Linux.tar.gz` |
| macOS | `NumpadMacros-macOS.zip` |

Si ya tienes Numpad Macros 3.3 o posterior, la app te avisa y se actualiza sola con un clic.
Guía de instalación: [README](https://github.com/OkumaWsX/NumpadMacros#instalación)
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--tipo", choices=["automatico", "correccion", "mejora", "grande"], default="automatico")
    p.add_argument("--version", default="")
    p.add_argument("--importante", action="store_true")
    c = sub.add_parser("capturas", help="notas de una Release con su sección de capturas")
    c.add_argument("--version", required=True)
    c.add_argument("--ref", required=True, help="etiqueta o commit donde están las imágenes")
    c.add_argument("--notas", default="", help="archivo con las notas actuales")
    args = ap.parse_args()
    if args.cmd == "prepare":
        prepare(args)
    elif args.cmd == "capturas":
        captures_cmd(args)


if __name__ == "__main__":
    main()
