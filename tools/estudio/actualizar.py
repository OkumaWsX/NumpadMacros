# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Actualizaciones del Estudio de Temas: busca versiones nuevas en GitHub y las instala.

Sin Tk y sin importar estudio.py (la versión actual llega como parámetro).

Las Releases del Estudio comparten repositorio con Numpad Macros, pero usan etiquetas
«estudio-vX.Y.Z» y nunca son la «última» de GitHub; por eso se usa la lista de Releases y se
filtran las etiquetas «estudio-v». Archivos esperados en cada Release (no cambiar sus nombres):
EstudioTemas-Windows-Setup.exe, EstudioTemas-Windows-portable.zip, EstudioTemas-Linux.tar.gz,
EstudioTemas-macOS.zip y SHA256SUMS.txt.

No se envía ningún dato del usuario: solo una petición GET con el User-Agent «EstudioTemas/versión».
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request

REPO = "OkumaWsX/NumpadMacros"
TAG_PREFIX = "estudio-v"
RELEASES_URL = f"https://github.com/{REPO}/releases"
DEFAULT_API = f"https://api.github.com/repos/{REPO}/releases?per_page=30"
ASSET = {"win32": "EstudioTemas-Windows-Setup.exe",
         "linux": "EstudioTemas-Linux.tar.gz",
         "darwin": "EstudioTemas-macOS.zip"}
LINUX_BINARY = "EstudioTemas-NumpadMacros"
SUMS = "SHA256SUMS.txt"
CHECK_EVERY = 24 * 3600
_USER_VERSION = ["0"]


class UpdateError(RuntimeError):
    pass


def api_url() -> str:
    """Dirección de la lista de Releases (ESTUDIO_API la cambia, para pruebas)."""
    return os.environ.get("ESTUDIO_API") or DEFAULT_API


def platform_key() -> str:
    if sys.platform == "win32":
        return "win32"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def parse_version(text: str) -> tuple:
    text = (text or "").strip()
    if text.startswith(TAG_PREFIX):
        text = text[len(TAG_PREFIX):]
    nums = re.findall(r"\d+", text.lstrip("vV").split("-")[0])[:3]
    return tuple(int(n) for n in nums) + (0,) * (3 - len(nums))


def newer(a: str, b: str) -> bool:
    """¿a es más nueva que b?"""
    return parse_version(a) > parse_version(b)


class Release:
    def __init__(self, data: dict):
        self.tag = data.get("tag_name", "") or ""
        self.version = self.tag[len(TAG_PREFIX):] if self.tag.startswith(TAG_PREFIX) else self.tag.lstrip("vV")
        self.name = data.get("name") or f"Estudio de Temas {self.version}"
        self.notes = (data.get("body") or "").replace("\r\n", "\n").strip()
        self.url = data.get("html_url") or RELEASES_URL
        self.prerelease = bool(data.get("prerelease"))
        self.published = (data.get("published_at") or "")[:10]
        self.assets = {a["name"]: (a["browser_download_url"], int(a.get("size") or 0))
                       for a in data.get("assets") or [] if a.get("name") and a.get("browser_download_url")}

    def asset(self):
        """(url, tamaño) del archivo para este sistema, o None."""
        return self.assets.get(ASSET[platform_key()])

    def notes_lines(self) -> list[tuple[str, str]]:
        """Las notas como [(sección, texto)]. Se corta en la línea «---» (el pie no se muestra)."""
        out, section = [], ""
        for line in self.notes.splitlines():
            t = line.strip()
            if re.fullmatch(r"-{3,}", t):
                break
            if t.startswith("#"):
                section = t.lstrip("#").strip()
            elif t.startswith(("- ", "* ")):
                out.append((section, t[2:].strip().replace("*", "").replace("`", "")))
        return out


# ---------------------------------------------------------------- red
def _context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _open(url, timeout=10, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={
        "User-Agent": f"EstudioTemas/{_USER_VERSION[0]}", "Accept": accept})
    if url.startswith("file:"):
        return urllib.request.urlopen(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout, context=_context())


def set_user_agent_version(version: str) -> None:
    _USER_VERSION[0] = str(version)


def fetch_latest(beta: bool = False) -> Release | None:
    """La versión más nueva del Estudio (las de prueba solo con beta=True; nunca los borradores)."""
    try:
        with _open(api_url()) as r:
            data = json.load(r)
    except Exception as e:
        raise UpdateError(f"No pude consultar GitHub: {e}")
    if not isinstance(data, list):
        raise UpdateError("GitHub respondió algo inesperado.")
    best = None
    for item in data:
        if not isinstance(item, dict) or item.get("draft"):
            continue
        if item.get("prerelease") and not beta:
            continue
        if not str(item.get("tag_name", "")).startswith(TAG_PREFIX):
            continue                           # p. ej. «v3.4.4»: es de Numpad Macros
        rel = Release(item)
        if not re.match(r"^\d", rel.version):
            continue
        if best is None or newer(rel.version, best.version):
            best = rel
    return best


def due(upd: dict) -> bool:
    """¿Toca buscar automáticamente? (una vez al día)"""
    try:
        last = float(upd.get("last_check", 0))
    except (TypeError, ValueError):
        last = 0
    return bool(upd.get("auto", True)) and time.time() - last > CHECK_EVERY


def check(upd: dict, current: str, manual: bool = False) -> Release | None:
    """Devuelve la Release si hay una versión nueva que mostrar. Anota la hora en upd['last_check']."""
    set_user_agent_version(current)
    rel = fetch_latest(bool(upd.get("beta")))
    upd["last_check"] = time.time()
    if not rel or not newer(rel.version, current):
        return None
    if not manual and upd.get("skip") == rel.version:
        return None
    return rel


# ---------------------------------------------------------------- instalación
def install_kind() -> str:
    """'installer' (Windows instalado), 'binary' (Linux empaquetado y con permiso) o 'manual'."""
    if not getattr(sys, "frozen", False):
        return "manual"                       # ejecutando desde el código
    exe_dir = os.path.dirname(sys.executable)
    if sys.platform == "win32":
        return "installer" if os.path.exists(os.path.join(exe_dir, "unins000.exe")) else "manual"
    if sys.platform.startswith("linux"):
        ok = os.access(exe_dir, os.W_OK) and os.access(sys.executable, os.W_OK)
        return "binary" if ok else "manual"
    return "manual"


def _expected_hash(rel: Release, name: str) -> str | None:
    hit = rel.assets.get(SUMS)
    if not hit:
        return None
    try:
        with _open(hit[0], accept="application/octet-stream") as r:
            text = r.read().decode("utf-8", "replace")
    except Exception as e:
        raise UpdateError(f"No pude descargar las huellas de seguridad: {e}")
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1].lstrip("*") == name:
            return parts[0].lower()
    return None


def _rm(path):
    try:
        os.remove(path)
    except OSError:
        pass


def download(rel: Release, progress=None, cancelled=lambda: False) -> str:
    """Descarga el archivo de este sistema y lo verifica con SHA256SUMS.txt. Devuelve la ruta.
    Si la huella no coincide o no existe, borra el archivo y falla."""
    name = ASSET[platform_key()]
    hit = rel.asset()
    if not hit:
        raise UpdateError("Esta versión no trae archivo para tu sistema.")
    url, size = hit
    expected = _expected_hash(rel, name)
    if not expected:
        raise UpdateError("La versión no trae huella de seguridad (SHA256SUMS.txt): no se instala.")
    path = os.path.join(tempfile.mkdtemp(prefix="estudiotemas-upd-"), name)
    h = hashlib.sha256()
    done = 0
    try:
        with _open(url, timeout=30, accept="application/octet-stream") as r, open(path, "wb") as f:
            total = int(r.headers.get("Content-Length") or size or 0)
            while True:
                if cancelled():
                    raise UpdateError("Descarga cancelada.")
                chunk = r.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except UpdateError:
        _rm(path)
        raise
    except Exception as e:
        _rm(path)
        raise UpdateError(f"La descarga falló: {e}")
    if h.hexdigest().lower() != expected:
        _rm(path)
        raise UpdateError("El archivo descargado no coincide con el original. Se borró por seguridad; "
                          "inténtalo de nuevo.")
    return path


def install_windows(setup_path: str) -> None:
    """Abre el instalador en modo silencioso. No pide administrador (el instalador es por usuario)."""
    params = ["/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/ACTUALIZAR=1"]
    try:
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen([setup_path] + params, creationflags=flags, close_fds=True)
    except OSError as e:
        raise UpdateError(f"No pude abrir el instalador: {e}")


def install_linux(tar_path: str) -> str:
    """Reemplaza el ejecutable actual por el nuevo, de forma atómica, y deja una copia «.anterior»."""
    exe = sys.executable
    folder = os.path.dirname(exe)
    tmp = ""
    try:
        with tarfile.open(tar_path) as tf:
            member = next((m for m in tf.getmembers()
                           if m.isfile() and os.path.basename(m.name) == LINUX_BINARY), None)
            if member is None:
                raise UpdateError("El paquete descargado no trae el programa.")
            src = tf.extractfile(member)
            fd, tmp = tempfile.mkstemp(dir=folder, prefix=".EstudioTemas-nuevo-")
            with os.fdopen(fd, "wb") as f:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
        os.chmod(tmp, 0o755)
        try:
            os.replace(exe, exe + ".anterior")        # copia por si algo sale mal
        except OSError:
            pass
        os.replace(tmp, exe)                          # atómico
    except UpdateError:
        if tmp:
            _rm(tmp)
        raise
    except (OSError, tarfile.TarError) as e:
        if tmp:
            _rm(tmp)
        raise UpdateError(f"No pude instalar la versión nueva: {e}")
    return exe


def relaunch_env() -> dict:
    """Entorno limpio para abrir la versión nueva (sin restos de PyInstaller)."""
    env = os.environ.copy()
    for k in list(env):
        if k.startswith(("_PYI", "_MEI")):
            env.pop(k, None)
    if getattr(sys, "frozen", False) and sys.platform.startswith("linux"):
        # PyInstaller antepone su carpeta temporal a las librerías: se restaura el original
        orig = env.pop("LD_LIBRARY_PATH_ORIG", None)
        if orig is not None:
            env["LD_LIBRARY_PATH"] = orig
        else:
            env.pop("LD_LIBRARY_PATH", None)
    return env


def relaunch(exe: str) -> None:
    """Abre el programa de nuevo (Linux, tras reemplazarlo)."""
    try:
        subprocess.Popen([exe], env=relaunch_env(), start_new_session=True, close_fds=True)
    except OSError as e:
        raise UpdateError(f"No pude volver a abrir el Estudio: {e}")


# ---------------------------------------------------------------- novedades
def read_changelog(path: str) -> list[dict]:
    """Lee CHANGELOG.md -> [{'version','date','groups':[(sección,[líneas])]}], sin «Sin publicar»."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return []
    out, cur, group = [], None, None
    for line in text.splitlines():
        m = re.match(r"^##\s+\[([^\]]+)\](?:\s*-\s*(.+))?", line)
        if m:
            if m.group(1).lower().startswith("sin publicar"):
                cur = None
                continue
            cur = {"version": m.group(1), "date": (m.group(2) or "").strip(), "groups": []}
            out.append(cur)
            group = None
            continue
        if cur is None:
            continue
        m = re.match(r"^###\s+(.+)", line)
        if m:
            group = (m.group(1).strip(), [])
            cur["groups"].append(group)
            continue
        t = line.strip()
        if t.startswith(("- ", "* ")) and group is not None:
            group[1].append(t[2:].replace("*", "").replace("`", ""))
    return out


def changelog_for(entries: list[dict], version: str) -> dict | None:
    """La sección de esa versión o, si no existe, la primera publicada."""
    for e in entries:
        if e["version"] == version:
            return e
    return entries[0] if entries else None
