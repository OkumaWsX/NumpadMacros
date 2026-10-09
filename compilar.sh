#!/usr/bin/env bash
# Compila la app independiente en Linux o macOS (necesita Python 3.12 solo para compilar).
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv-build
. .venv-build/bin/activate
pip install -q -r requirements.txt pyinstaller==6.22.3 pillow
pyinstaller --noconfirm NumpadMacros.spec
echo
if [ "$(uname)" = "Darwin" ]; then
  echo "Listo: dist/Numpad Macros.app"
else
  echo "Listo: dist/NumpadMacros  (luego ./instalar_linux.sh desde una carpeta con el binario e icon.png)"
fi
