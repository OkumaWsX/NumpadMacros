#!/usr/bin/env bash
# Instala Numpad Macros en tu usuario: lo copia a ~/.local/bin y lo agrega al menú de aplicaciones.
# Funciona desde cualquier carpeta: con el .tar.gz descargado (programa e icon.png junto al script),
# con la carpeta del código después de ./compilar.sh (dist/NumpadMacros y assets/icon.png) o
# indicando las rutas. También pregunta si quieres el Estudio de Temas (editor de temas): si lo
# activas, se instala y Numpad Macros buscará también sus actualizaciones.
#   ./instalar_linux.sh [--estudio | --sin-estudio] [ruta/al/programa] [ruta/al/icono.png]
set -euo pipefail
REPO="OkumaWsX/NumpadMacros"

ESTUDIO=""                      # "1" sí, "0" no, "" preguntar
ARGS=()
for a in "$@"; do
  case "$a" in
    --estudio) ESTUDIO=1 ;;
    --sin-estudio) ESTUDIO=0 ;;
    -h|--help) sed -n '2,7p' "$(readlink -f "$0")" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) ARGS+=("$a") ;;
  esac
done
# Las rutas dadas como argumento se resuelven antes de cambiar de carpeta (una carpeta vale:
# se busca NumpadMacros dentro)
APP="${ARGS[0]:+$(realpath -- "${ARGS[0]}")}"
ICON="${ARGS[1]:+$(realpath -- "${ARGS[1]}")}"
if [ -n "$APP" ] && [ -d "$APP" ]; then APP="$APP/NumpadMacros"; fi
CALLER="$PWD"
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$HERE"

# Devuelve la primera ruta que exista como archivo
primero() {
  for p in "$@"; do
    if [ -n "$p" ] && [ -f "$p" ]; then echo "$p"; return 0; fi
  done
  return 1
}

if [ -z "$APP" ]; then
  # dist/ primero: si se recompiló, ese es el binario más nuevo. También donde se ejecutó el script
  # y la carpeta de arriba (el script suelto dentro de otra carpeta del paquete).
  APP="$(primero dist/NumpadMacros NumpadMacros "$CALLER/dist/NumpadMacros" "$CALLER/NumpadMacros" \
                 ../dist/NumpadMacros ../NumpadMacros)" || APP=""
  if [ -z "$APP" ] && [ -f compilar.sh ] && [ -t 0 ]; then
    echo "No encontré el programa compilado (NumpadMacros)."
    read -r -p "¿Compilarlo ahora con ./compilar.sh? Tarda unos minutos [s/N] " ans
    case "$ans" in
      s|S|si|sí|Si|Sí) bash ./compilar.sh && APP="$HERE/dist/NumpadMacros" ;;
    esac
  fi
  if [ -z "$APP" ] || [ ! -f "$APP" ]; then
    echo "No encontré el programa «NumpadMacros»."
    echo "  - Si descargaste NumpadMacros-Linux.tar.gz: descomprímelo y ejecuta ./instalar_linux.sh desde esa carpeta."
    echo "  - Si compilaste: ejecuta primero ./compilar.sh (deja el programa en dist/)."
    echo "  - O indica dónde está:  ./instalar_linux.sh /ruta/a/NumpadMacros"
    exit 1
  fi
fi
[ -f "$APP" ] || { echo "No existe el programa: $APP"; exit 1; }
APP_DIR="$(dirname "$APP")"
# el icono es opcional: si no aparece, se instala igual (la app pone su icono al abrirse)
if [ -z "$ICON" ]; then
  ICON="$(primero icon.png assets/icon.png "$APP_DIR/icon.png" "$APP_DIR/../assets/icon.png" \
                  "$CALLER/icon.png" "$CALLER/assets/icon.png")" || ICON=""
elif [ ! -f "$ICON" ]; then
  echo "Aviso: no existe el icono $ICON; se instala sin él."
  ICON=""
fi
echo "Programa: $APP"
if [ -n "$ICON" ]; then echo "Icono:    $ICON"
else echo "Aviso: no encontré icon.png; el menú usará un icono genérico hasta que abras la app por primera vez."; fi

BIN="$HOME/.local/bin"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
CONF="${XDG_CONFIG_HOME:-$HOME/.config}/NumpadMacros"
APPS="$DATA/applications"
ESTUDIO_BIN="$BIN/estudio-temas"
PRIMERA=1
[ -e "$BIN/numpad-macros" ] && PRIMERA=0
mkdir -p "$BIN" "$APPS"

if command -v magick >/dev/null 2>&1; then RESIZE=(magick)
elif command -v convert >/dev/null 2>&1; then RESIZE=(convert)
else RESIZE=(); fi

# Copia el icono en todos los tamaños del tema hicolor:  iconos origen.png nombre
iconos() {
  for size in 48 64 128 256 512; do
    local dir="$DATA/icons/hicolor/${size}x${size}/apps"
    mkdir -p "$dir"
    if [ ${#RESIZE[@]} -gt 0 ] && "${RESIZE[@]}" "$1" -resize "${size}x${size}" "$dir/$2.png" 2>/dev/null; then :
    else install -m 644 "$1" "$dir/$2.png"; fi
  done
}

# Copia a un temporal y renombra: así se puede reinstalar aunque el programa esté abierto
instalar_bin() {
  install -m 755 "$1" "$2.tmp.$$"
  mv -f "$2.tmp.$$" "$2"
}

# ---------------------------------------------------------------- Estudio de Temas
# ¿Quiere el Estudio? Se pregunta al instalar por primera vez (o si ya está instalado, si quiere
# que Numpad Macros busque también sus actualizaciones). Sin terminal interactiva no se pregunta:
# la app lo activa sola si el Estudio está instalado.
if [ -z "$ESTUDIO" ] && { [ "$PRIMERA" = 1 ] || [ -e "$ESTUDIO_BIN" ]; }; then
  if [ -t 0 ]; then
    if [ -e "$ESTUDIO_BIN" ]; then
      read -r -p "El Estudio de Temas ya está instalado. ¿Buscar también sus actualizaciones desde Numpad Macros? [S/n] " r
      case "$r" in [nN]*) ESTUDIO=0 ;; *) ESTUDIO=1 ;; esac
    else
      echo "El Estudio de Temas es el editor para crear tus propios temas (programa aparte)."
      read -r -p "¿Instalarlo también? Numpad Macros buscará además sus actualizaciones. [s/N] " r
      case "$r" in [sS]*) ESTUDIO=1 ;; *) ESTUDIO=0 ;; esac
    fi
  fi
fi

# Etiqueta de la última versión publicada del Estudio («estudio-vX.Y.Z»; sin las de prueba).
# El Estudio tiene sus propias Releases en el mismo repositorio, que nunca son «la última» de
# GitHub (esa es la de Numpad Macros): hay que buscarla en la lista de Releases.
ultima_estudio() {
  local json
  json="$(curl -fsSL -H 'Accept: application/vnd.github+json' \
          "https://api.github.com/repos/$REPO/releases?per_page=30")" || return 1
  if command -v python3 >/dev/null 2>&1; then
    printf '%s' "$json" | python3 -c '
import json, re, sys
best = None
for r in json.load(sys.stdin):
    t = str(r.get("tag_name", ""))
    if r.get("draft") or r.get("prerelease") or not re.fullmatch(r"estudio-v\d+(\.\d+)*", t):
        continue
    v = tuple(int(n) for n in t[9:].split("."))
    if best is None or v > best[0]:
        best = (v, t)
if best:
    print(best[1])
' 2>/dev/null
  else                  # sin python3: la más reciente de la lista (GitHub la da de más nueva a más vieja)
    printf '%s' "$json" | grep -o '"tag_name": *"estudio-v[0-9.]*"' | head -n 1 | grep -o 'estudio-v[0-9.]*'
  fi
}

# Busca el Estudio junto al script o lo descarga de su última versión publicada (verificado con
# SHA256SUMS.txt). Deja en EST_EXE, EST_ICON y EST_VER lo encontrado.
obtener_estudio() {
  EST_EXE="$(primero tools/estudio/dist/EstudioTemas-NumpadMacros EstudioTemas-NumpadMacros EstudioTemas/EstudioTemas-NumpadMacros)" || EST_EXE=""
  EST_ICON="$(primero assets/icon-estudio.png icon-estudio.png EstudioTemas/icon-estudio.png)" || EST_ICON=""
  EST_VER=""
  if [ -n "$EST_EXE" ]; then
    [ -f tools/estudio/estudio.py ] && EST_VER="$(sed -n 's/^VERSION = "\(.*\)"$/\1/p' tools/estudio/estudio.py)"
    return 0
  fi
  command -v curl >/dev/null 2>&1 || { echo "Para descargar el Estudio hace falta curl."; return 1; }
  TMPD="$(mktemp -d)"
  local tag
  tag="$(ultima_estudio)" || tag=""
  [ -n "$tag" ] || { echo "No encontré ninguna versión publicada del Estudio de Temas."; return 1; }
  local url="https://github.com/$REPO/releases/download/$tag"
  echo "Descargando el Estudio de Temas ${tag#estudio-v}…"
  curl -fsSL -o "$TMPD/EstudioTemas-Linux.tar.gz" "$url/EstudioTemas-Linux.tar.gz" &&
    curl -fsSL -o "$TMPD/SHA256SUMS.txt" "$url/SHA256SUMS.txt" || { echo "No se pudo descargar."; return 1; }
  EST_VER="${tag#estudio-v}"
  (cd "$TMPD" && grep ' \*\{0,1\}EstudioTemas-Linux.tar.gz$' SHA256SUMS.txt | sha256sum -c --status) || {
    echo "El archivo descargado no coincide con su huella de seguridad: no se instala."; return 1; }
  tar -C "$TMPD" -xzf "$TMPD/EstudioTemas-Linux.tar.gz"
  EST_EXE="$TMPD/EstudioTemas/EstudioTemas-NumpadMacros"
  EST_ICON="$TMPD/EstudioTemas/icon-estudio.png"
  [ -f "$EST_EXE" ] || { echo "El paquete del Estudio no trae el programa."; return 1; }
}

instalar_estudio() {
  TMPD=""
  if obtener_estudio; then
    instalar_bin "$EST_EXE" "$ESTUDIO_BIN"
    if [ -n "$EST_VER" ]; then echo "$EST_VER" > "$ESTUDIO_BIN.version"; else rm -f "$ESTUDIO_BIN.version"; fi
    [ -n "$EST_ICON" ] && [ -f "$EST_ICON" ] && iconos "$EST_ICON" estudio-temas-numpad-macros
    cat > "$APPS/estudio-temas-numpad-macros.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Estudio de Temas · Numpad Macros
Comment=Crear temas para Numpad Macros
Exec="$ESTUDIO_BIN"
Icon=estudio-temas-numpad-macros
Terminal=false
Categories=Graphics;Utility;
StartupWMClass=EstudioTemasNumpadMacros
StartupNotify=true
DESK
    chmod 755 "$APPS/estudio-temas-numpad-macros.desktop"
    echo "Estudio de Temas instalado${EST_VER:+ (versión $EST_VER)}."
  else
    echo "No se instaló el Estudio de Temas. Numpad Macros se instala igual;"
    echo "puedes instalarlo después desde la pestaña «Temas» → «Crear o editar temas…»."
  fi
  [ -n "$TMPD" ] && rm -rf "$TMPD"
  return 0
}

# ---------------------------------------------------------------- Numpad Macros
instalar_bin "$APP" "$BIN/numpad-macros"
[ -n "$ICON" ] && iconos "$ICON" numpad-macros
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

if [ "$ESTUDIO" = 1 ] && [ ! -e "$ESTUDIO_BIN" ]; then instalar_estudio; fi
if [ -n "$ESTUDIO" ]; then      # la app lo lee una vez al abrirse y activa (o no) la opción
  mkdir -p "$CONF"
  echo "$ESTUDIO" > "$CONF/estudio-eleccion"
fi

update-desktop-database "$APPS" 2>/dev/null || true
gtk-update-icon-cache -f -t "$DATA/icons/hicolor" 2>/dev/null || true
for k in kbuildsycoca6 kbuildsycoca5; do
  command -v "$k" >/dev/null 2>&1 && { "$k" >/dev/null 2>&1 || true; break; }
done
echo "Listo: busca «Numpad Macros» en el menú de aplicaciones."
echo "La primera vez, en la pestaña «Numpad y opciones», pulsa «Dar permisos…»."
