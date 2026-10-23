#!/usr/bin/env bash
# Instala Numpad Macros en tu usuario: lo copia a ~/.local/bin y lo agrega al menú de aplicaciones.
#
# Funciona desde cualquier carpeta y con cualquiera de estas formas:
#   - el .tar.gz descargado (NumpadMacros, icon.png e instalar_linux.sh juntos)
#   - la carpeta del código después de ./compilar.sh (dist/NumpadMacros y assets/icon.png)
#   - indicando el ejecutable a mano:  ./instalar_linux.sh /ruta/a/NumpadMacros
set -euo pipefail
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"

first_file() {           # primer archivo que exista de la lista
  for f in "$@"; do
    if [ -n "$f" ] && [ -f "$f" ]; then
      printf '%s\n' "$f"
      return 0
    fi
  done
  return 1
}

# ---- el programa
ARG="${1:-}"
if [ -n "$ARG" ] && [ -d "$ARG" ]; then ARG="$ARG/NumpadMacros"; fi
APP_BIN="$(first_file "$ARG" "$HERE/NumpadMacros" "$HERE/dist/NumpadMacros" "$PWD/NumpadMacros" \
                     "$PWD/dist/NumpadMacros" "$HERE/../NumpadMacros" "$HERE/../dist/NumpadMacros")" || APP_BIN=""
if [ -z "$APP_BIN" ]; then
  if [ -f "$HERE/compilar.sh" ] && [ -t 0 ]; then
    echo "No encontré el programa compilado (NumpadMacros)."
    read -r -p "¿Compilarlo ahora con ./compilar.sh? Tarda unos minutos [s/N] " ans
    case "$ans" in
      s|S|si|sí|Si|Sí) bash "$HERE/compilar.sh"; APP_BIN="$HERE/dist/NumpadMacros" ;;
    esac
  fi
fi
if [ -z "$APP_BIN" ] || [ ! -f "$APP_BIN" ]; then
  echo "No encontré el programa «NumpadMacros»."
  echo "  - Si descargaste NumpadMacros-Linux.tar.gz: descomprímelo y ejecuta ./instalar_linux.sh desde esa carpeta."
  echo "  - Si compilaste: ejecuta primero ./compilar.sh (deja el programa en dist/)."
  echo "  - O indica dónde está:  ./instalar_linux.sh /ruta/a/NumpadMacros"
  exit 1
fi
BIN_DIR="$(dirname "$APP_BIN")"

# ---- el icono (si no aparece, se instala igual: la app pone su icono al abrirse)
ICON="$(first_file "$HERE/icon.png" "$BIN_DIR/icon.png" "$HERE/assets/icon.png" "$BIN_DIR/../assets/icon.png" \
                   "$PWD/icon.png" "$PWD/assets/icon.png")" || ICON=""

BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
mkdir -p "$BIN" "$APPS"
install -m 755 "$APP_BIN" "$BIN/numpad-macros"
echo "Programa: $APP_BIN -> $BIN/numpad-macros"
if [ -n "$ICON" ]; then
  for size in 48 64 128 256 512; do
    dir="$HOME/.local/share/icons/hicolor/${size}x${size}/apps"
    mkdir -p "$dir"
    if command -v magick >/dev/null 2>&1; then magick "$ICON" -resize ${size}x${size} "$dir/numpad-macros.png"
    else install -m 644 "$ICON" "$dir/numpad-macros.png"; fi
  done
  echo "Icono:    $ICON"
else
  echo "Aviso: no encontré icon.png; el menú usará un icono genérico hasta que abras la app por primera vez."
fi
cat > "$APPS/numpad-macros.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Numpad Macros
Comment=Numpad como botonera de sonidos y atajos
Exec="$BIN/numpad-macros"
Icon=numpad-macros
Terminal=false
Categories=AudioVideo;Audio;Utility;
StartupWMClass=NumpadMacros
StartupNotify=true
DESK
chmod 755 "$APPS/numpad-macros.desktop"
update-desktop-database "$APPS" 2>/dev/null || true
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
command -v kbuildsycoca6 >/dev/null 2>&1 && kbuildsycoca6 >/dev/null 2>&1 || true
echo "Listo: busca «Numpad Macros» en el menú de aplicaciones."
echo "La primera vez, en la pestaña «Numpad y opciones», pulsa «Dar permisos…»."
