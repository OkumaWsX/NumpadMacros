#!/usr/bin/env bash
# Instala Numpad Macros en tu usuario: lo copia a ~/.local/bin y lo agrega al menú de aplicaciones.
set -euo pipefail
cd "$(dirname "$0")"
BIN="$HOME/.local/bin"
ICONS="$HOME/.local/share/icons/hicolor/512x512/apps"
APPS="$HOME/.local/share/applications"
mkdir -p "$BIN" "$ICONS" "$APPS"
install -m 755 NumpadMacros "$BIN/numpad-macros"
install -m 644 icon.png "$ICONS/numpad-macros.png"
cat > "$APPS/numpad-macros.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Numpad Macros
Comment=Numpad como panel de sonidos y atajos
Exec=$BIN/numpad-macros
Icon=numpad-macros
Categories=AudioVideo;Utility;
StartupWMClass=NumpadMacros
DESK
update-desktop-database "$APPS" 2>/dev/null || true
echo "Listo: busca «Numpad Macros» en el menú de aplicaciones."
echo "La primera vez, en la pestaña «Numpad y opciones», pulsa «Dar permisos…»."
