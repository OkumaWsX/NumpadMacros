#!/usr/bin/env bash
# Instala Numpad Macros en tu usuario: lo copia a ~/.local/bin y lo agrega al menú de aplicaciones.
set -euo pipefail
cd "$(dirname "$0")"
BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
mkdir -p "$BIN" "$APPS"
install -m 755 NumpadMacros "$BIN/numpad-macros"
for size in 48 64 128 256 512; do
  dir="$HOME/.local/share/icons/hicolor/${size}x${size}/apps"
  mkdir -p "$dir"
  if command -v magick >/dev/null 2>&1; then magick icon.png -resize ${size}x${size} "$dir/numpad-macros.png"
  else install -m 644 icon.png "$dir/numpad-macros.png"; fi
done
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
