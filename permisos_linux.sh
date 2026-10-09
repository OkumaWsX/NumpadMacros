#!/usr/bin/env bash
# Da permiso a tu usuario para leer el numpad (/dev/input) y crear el teclado
# virtual (/dev/uinput). Se ejecuta UNA vez.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  exec sudo -- bash "$0" "$(id -un)"
fi
TARGET_USER="${1:-${SUDO_USER:-}}"
if [ -z "$TARGET_USER" ] || [ "$TARGET_USER" = "root" ]; then
  echo "Ejecuta este script con tu usuario normal (él mismo pedirá la contraseña)."
  exit 1
fi

echo "-> Reglas udev (acceso para la sesión abierta)"
cat > /etc/udev/rules.d/60-numpad-macros.rules <<'EOF'
KERNEL=="uinput", SUBSYSTEM=="misc", MODE="0660", GROUP="input", TAG+="uaccess", OPTIONS+="static_node=uinput"
SUBSYSTEM=="input", KERNEL=="event*", TAG+="uaccess"
EOF

echo "-> Cargar el módulo uinput al iniciar"
echo uinput > /etc/modules-load.d/numpad-macros.conf
modprobe uinput || true

echo "-> Agregar a '$TARGET_USER' al grupo input (respaldo)"
groupadd -f input
usermod -aG input "$TARGET_USER"

udevadm control --reload-rules
udevadm trigger --action=change --subsystem-match=misc --subsystem-match=input || true
udevadm settle || true

echo
echo "Listo."
