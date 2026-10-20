# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Crea temas .npt (herramienta del creador).

    python tools/crear_tema.py plantilla mi-tema.json        # JSON de ejemplo para editar
    python tools/crear_tema.py crear mi-tema.json --clave firma.key   # -> mi-tema.npt (firmado)
    python tools/crear_tema.py crear mi-tema.json --sin-firma         # tema sin firma
    python tools/crear_tema.py ver tema.npt                  # revisa un .npt

La clave de firma (firma-temas-OkumaWsX.key) es solo del creador: nunca va en GitHub.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from npm import npt, themes  # noqa: E402


def plantilla(path):
    t = themes.builtin()[0]
    data = {"name": "Mi tema", "author": "OkumaWsX", "version": "1.0", "colors": t["colors"],
            "alpha": None}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Plantilla creada: {path}  (cambia los colores y el nombre; 'alpha' = transparencia, "
          'por ejemplo {"window": 0.9, "idle": 0.6}, o null)')


def crear(src, out=None, key=None):
    with open(src, encoding="utf-8") as f:
        theme = json.load(f)
    pk = npt.load_private_key(key) if key else None
    data = npt.pack(theme, pk)
    out = out or os.path.splitext(src)[0] + npt.EXT
    with open(out, "wb") as f:
        f.write(data)
    t, official = npt.unpack(data)
    print(f"Listo: {out}  ·  «{t['name']}»  ·  {'firmado (oficial)' if official else 'sin firma'}")
    return out


def ver(path):
    t, official = npt.read_file(path)
    print(f"«{t['name']}» por {t['author']} · versión {t['version']} · "
          f"{'oficial (firmado por OkumaWsX)' if official else 'de la comunidad (sin firma)'}")
    print("Transparencia:", t.get("alpha") or "no")
    for k, v in t["colors"].items():
        print(f"  {k:16s} {v}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Temas .npt de Numpad Macros")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plantilla")
    p.add_argument("json")
    p = sub.add_parser("crear")
    p.add_argument("json")
    p.add_argument("--salida")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--clave", help="clave privada para firmar (tema oficial)")
    g.add_argument("--sin-firma", action="store_true")
    p = sub.add_parser("ver")
    p.add_argument("npt")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "plantilla":
            plantilla(a.json)
        elif a.cmd == "crear":
            crear(a.json, a.salida, None if a.sin_firma else a.clave)
        else:
            ver(a.npt)
    except (npt.NptError, OSError, ValueError) as e:
        print("Error:", e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
