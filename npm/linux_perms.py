# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Permisos de Linux para leer el numpad y crear el teclado virtual.

La regla udev usa "uaccess": el usuario con la sesión abierta recibe acceso de
inmediato, sin cerrar sesión. Además se agrega al grupo "input" como respaldo.
"""
import getpass
import os
import shutil
import subprocess
import tempfile

SCRIPT = r"""#!/usr/bin/env bash
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
"""


def has_access() -> bool:
    """True si ya se puede crear el teclado virtual y leer algún teclado."""
    if not os.access("/dev/uinput", os.R_OK | os.W_OK):
        return False
    try:
        events = [f for f in os.listdir("/dev/input") if f.startswith("event")]
    except OSError:
        return False
    return any(os.access(os.path.join("/dev/input", f), os.R_OK) for f in events)


def can_ask() -> bool:
    return shutil.which("pkexec") is not None


def grant(env=None) -> tuple[bool, str]:
    """Ejecuta el script como administrador con pkexec (abre la ventana de contraseña)."""
    pk = shutil.which("pkexec")
    if not pk:
        return False, ("No encuentro pkexec. Ejecuta en una terminal: ./permisos_linux.sh")
    fd, path = tempfile.mkstemp(prefix="numpad-macros-", suffix=".sh")
    with os.fdopen(fd, "w") as f:
        f.write(SCRIPT)
    os.chmod(path, 0o755)
    try:
        r = subprocess.run([pk, "/bin/bash", path, getpass.getuser()], capture_output=True,
                           text=True, timeout=180, env=env)
    except subprocess.TimeoutExpired:
        return False, "Se acabó el tiempo esperando la contraseña"
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    if r.returncode in (126, 127):
        return False, "No se dieron los permisos (se canceló la contraseña)"
    if r.returncode != 0:
        return False, (r.stderr or r.stdout).strip()[-300:] or "El script de permisos falló"
    return True, "Permisos listos"
