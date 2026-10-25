# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Actualizaciones: busca versiones nuevas en GitHub y las instala.

Cómo funciona:
1. check(): pregunta a GitHub cuál es la última Release publicada (una vez al
   día, sin enviar ningún dato del usuario) y la compara con __version__.
2. download(): descarga el archivo de este sistema y lo verifica con la huella
   SHA256 publicada en la Release (SHA256SUMS.txt). Si no coincide, se borra.
3. install(): Windows -> abre el instalador en modo silencioso (/ACTUALIZAR=1),
   que reemplaza el programa sin tocar drivers y vuelve a abrir la app.
   Linux -> reemplaza el ejecutable (deja copia del anterior) y se reinicia.
   macOS / versión portátil / código fuente -> abre la página de descarga.

La configuración, los bancos y los sonidos viven en otra carpeta y no se tocan.
"""
import hashlib
import json
import os
import re
import ssl
import sys
import tarfile
import tempfile
import time
import urllib.request

from . import __version__
from .about import REPO

API = os.environ.get("NUMPADMACROS_API", f"https://api.github.com/repos/{REPO}/releases?per_page=30")
RELEASES_URL = f"https://github.com/{REPO}/releases"
ASSET = {"win32": "NumpadMacros-Windows-Setup.exe",
         "linux": "NumpadMacros-Linux.tar.gz",
         "darwin": "NumpadMacros-macOS.zip"}
SUMS = "SHA256SUMS.txt"
IMPORTANT = "<!-- importante -->"
CHECK_EVERY = 24 * 3600


class UpdateError(RuntimeError):
    pass


def platform_key() -> str:
    if sys.platform == "win32":
        return "win32"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def parse_version(text: str) -> tuple:
    nums = re.findall(r"\d+", (text or "").lstrip("vV").split("-")[0])
    return tuple(int(n) for n in nums[:3]) + (0,) * (3 - len(nums[:3]))


def newer(a: str, b: str) -> bool:
    """¿a es más nueva que b?"""
    return parse_version(a) > parse_version(b)


ESTUDIO_TAG = "estudio-v"        # las Releases del Estudio de Temas (programa aparte, mismo repositorio)


class Release:
    def __init__(self, data: dict):
        self.tag = data.get("tag_name", "") or ""
        if self.tag.startswith(ESTUDIO_TAG):
            self.version = self.tag[len(ESTUDIO_TAG):]
            self.name = data.get("name") or f"Estudio de Temas {self.version}"
        else:
            self.version = self.tag.lstrip("vV")
            self.name = data.get("name") or f"Numpad Macros {self.version}"
        body = data.get("body") or ""
        self.important = IMPORTANT in body
        self.notes = body.replace(IMPORTANT, "").strip()
        self.url = data.get("html_url") or RELEASES_URL
        self.prerelease = bool(data.get("prerelease"))
        self.published = (data.get("published_at") or "")[:10]
        self.assets = {a["name"]: (a["browser_download_url"], int(a.get("size") or 0))
                       for a in data.get("assets") or []}

    def asset(self):
        """(url, tamaño) del archivo para este sistema, o None."""
        return self.assets.get(ASSET[platform_key()])

    def notes_lines(self) -> list[tuple[str, str]]:
        """Las notas como [(sección, texto)] para mostrarlas en la ventana."""
        out, section = [], ""
        for line in self.notes.splitlines():
            t = line.strip()
            if t.startswith("#"):
                section = t.lstrip("#").strip()
            elif t.startswith(("-", "*")):
                out.append((section, t[1:].strip().replace("*", "").replace("`", "")))
        return out


def _context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _open(url, timeout=10, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={
        "User-Agent": f"NumpadMacros/{__version__}", "Accept": accept})
    return urllib.request.urlopen(req, timeout=timeout, context=_context())


def _releases() -> list:
    """La lista de Releases del repositorio (de Numpad Macros y del Estudio de Temas)."""
    try:
        with _open(API) as r:
            data = json.load(r)
    except Exception as e:
        raise UpdateError(f"No pude consultar GitHub: {e}")
    if not isinstance(data, list):
        raise UpdateError("GitHub respondió algo inesperado.")
    return data


def _best(data: list, beta: bool, estudio: bool = False) -> Release | None:
    """La más nueva de Numpad Macros (etiquetas vX.Y.Z) o, con estudio=True, del Estudio
    (estudio-vX.Y.Z). Betas solo si beta=True; nunca borradores."""
    best = None
    for item in data:
        if not isinstance(item, dict) or item.get("draft") or (item.get("prerelease") and not beta):
            continue
        rel = Release(item)
        is_estudio = rel.tag.startswith(ESTUDIO_TAG)
        if is_estudio != estudio or not re.match(r"^\d", rel.version or ""):
            continue                          # p. ej. «estudio-v1.0.0» es otro programa
        if best is None or newer(rel.version, best.version):
            best = rel
    return best


def fetch_latest(beta: bool = False) -> Release | None:
    """La versión más nueva publicada de Numpad Macros (con betas solo si beta=True)."""
    return _best(_releases(), beta)


def fetch_latest_estudio(beta: bool = False) -> Release | None:
    """La versión más nueva publicada del Estudio de Temas (sus propias Releases «estudio-v…»)."""
    return _best(_releases(), beta, estudio=True)


def due(upd: dict) -> bool:
    """¿Toca buscar automáticamente? (una vez al día)"""
    return bool(upd.get("auto", True)) and time.time() - float(upd.get("last_check", 0)) > CHECK_EVERY


def check(upd: dict, current: str = __version__, manual: bool = False) -> Release | None:
    """Devuelve la Release si hay una versión nueva que mostrar al usuario."""
    rel = fetch_latest(bool(upd.get("beta")))
    upd["last_check"] = time.time()
    if not rel or not newer(rel.version, current):
        return None
    if not manual and upd.get("skip") == rel.version and not rel.important:
        return None
    return rel


# ---------------------------------------------------------------- instalación
def install_kind() -> str:
    """'installer' (Windows instalado), 'binary' (Linux) o 'manual'."""
    if not getattr(sys, "frozen", False):
        return "manual"                       # ejecutando desde el código
    exe_dir = os.path.dirname(sys.executable)
    if sys.platform == "win32":
        return "installer" if os.path.exists(os.path.join(exe_dir, "unins000.exe")) else "manual"
    if sys.platform.startswith("linux"):
        return "binary" if os.access(exe_dir, os.W_OK) and os.access(sys.executable, os.W_OK) else "manual"
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


def download(rel: Release, progress=None, cancelled=lambda: False, name: str | None = None) -> str:
    """Descarga y verifica el archivo de este sistema (u otro de la Release, por nombre).
    Devuelve la ruta."""
    name = name or ASSET[platform_key()]
    hit = rel.assets.get(name)
    if not hit:
        raise UpdateError("Esta versión no trae archivo para tu sistema.")
    url, size = hit
    expected = _expected_hash(rel, name)
    if not expected:
        raise UpdateError("La versión no trae huella de seguridad (SHA256SUMS.txt): no se instala.")
    folder = tempfile.mkdtemp(prefix="numpadmacros-upd-")
    path = os.path.join(folder, name)
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


def _rm(path):
    try:
        os.remove(path)
    except OSError:
        pass
    try:
        os.rmdir(os.path.dirname(path))   # la carpeta temporal, si quedó vacía
    except OSError:
        pass


def install_windows(setup_path: str):
    """Abre el instalador en modo silencioso (Windows pide permiso una vez)."""
    import ctypes
    params = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /ACTUALIZAR=1"
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", setup_path, params, None, 1)
    if r <= 32:
        raise UpdateError("No se instaló: Windows no dio permiso." if r == 5 else
                          f"No pude abrir el instalador (código {r}).")


def install_linux(tar_path: str) -> str:
    """Reemplaza el ejecutable por el nuevo. Devuelve su ruta."""
    exe = sys.executable
    folder = os.path.dirname(exe)
    with tarfile.open(tar_path) as tf:
        member = next((m for m in tf.getmembers()
                       if m.isfile() and os.path.basename(m.name) == "NumpadMacros"), None)
        if member is None:
            raise UpdateError("El paquete descargado no trae el programa.")
        src = tf.extractfile(member)
        fd, tmp = tempfile.mkstemp(dir=folder, prefix=".NumpadMacros-nuevo-")
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
    os.replace(tmp, exe)
    return exe


def relaunch_env():
    """Entorno limpio para abrir la versión nueva (sin restos de PyInstaller)."""
    from .soundboard import clean_env
    env = clean_env()
    for k in list(env):
        if k.startswith(("_PYI", "_MEI")):
            env.pop(k, None)
    return env


# ---------------------------------------------------------------- Estudio de Temas
# El Estudio (editor de temas) es un programa aparte, con sus propias Releases en este mismo
# repositorio (etiquetas «estudio-vX.Y.Z», cada una con su SHA256SUMS.txt; las publica
# .github/workflows/publicar-estudio.yml). Su versión es la de la etiqueta.
ESTUDIO_ASSET = {"win32": "EstudioTemas-Windows-Setup.exe",
                 "linux": "EstudioTemas-Linux.tar.gz",
                 "darwin": "EstudioTemas-macOS.zip"}
ESTUDIO_EXE = "EstudioTemas-NumpadMacros"
ESTUDIO_DESKTOP = "estudio-temas-numpad-macros"            # el mismo que usa el propio Estudio
ESTUDIO_UNINST = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{3B7E2C9A-41D6-4F8B-9E25-6A0C17D4B8F3}_is1"


def _linux_estudio_bin() -> str:
    return os.path.join(os.path.expanduser("~"), ".local", "bin", "estudio-temas")


def _desktop_exec(app_id: str) -> str:
    """La ruta del Exec= de un acceso del menú de Linux (o "")."""
    from .desktop_linux import data_dir
    try:
        with open(os.path.join(data_dir(), "applications", f"{app_id}.desktop"), encoding="utf-8") as f:
            for line in f:
                if line.startswith("Exec="):
                    return line[5:].strip().strip('"')
    except OSError:
        pass
    return ""


def estudio_installed() -> tuple[str, str] | None:
    """(ruta, versión) del Estudio instalado, o None. La versión es "" si no se conoce."""
    if sys.platform == "win32":
        try:
            import winreg
        except ImportError:
            return None
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, ESTUDIO_UNINST) as k:
                    folder = winreg.QueryValueEx(k, "InstallLocation")[0]
                    try:
                        ver = winreg.QueryValueEx(k, "DisplayVersion")[0]
                    except OSError:
                        ver = ""
                    exe = os.path.join(folder, ESTUDIO_EXE + ".exe")
                    if os.path.isfile(exe):       # desinstalado a mano: el registro puede quedar
                        return exe, str(ver)
            except OSError:
                continue
        return None
    if sys.platform == "darwin":
        for base in ("/Applications", os.path.expanduser("~/Applications")):
            app = os.path.join(base, "Estudio de Temas.app")
            if os.path.isdir(app):
                return app, ""
        return None
    for exe in (_linux_estudio_bin(), _desktop_exec(ESTUDIO_DESKTOP)):
        if exe and os.path.isfile(exe):
            try:                              # versión anotada al instalarlo (junto al programa)
                with open(exe + ".version", encoding="utf-8") as f:
                    ver = f.read().strip()
            except OSError:
                ver = ""
            return exe, ver
    return None


CHOICE_FILE = "estudio-eleccion"          # Linux: lo deja instalar_linux.sh en la carpeta de config


def take_installer_choice() -> bool | None:
    """Lo que eligió el usuario sobre el Estudio en el instalador (una sola vez: después se
    borra). None si no hay nada que leer."""
    if sys.platform != "win32":
        from .config import config_dir
        path = os.path.join(config_dir(), CHOICE_FILE)
        try:
            with open(path, encoding="utf-8") as f:
                value = f.read().strip()
        except OSError:
            return None
        _rm_file(path)
        return value == "1"
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\NumpadMacros", 0,
                            winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
            value = winreg.QueryValueEx(k, "EstudioTemas")[0]
            winreg.DeleteValue(k, "EstudioTemas")
        return bool(value)
    except OSError:
        return None


def estudio_version(rel: Release | None) -> str:
    """Versión del Estudio de una Release suya ("" si no es del Estudio o no trae el archivo
    de este sistema)."""
    if rel is None or not rel.tag.startswith(ESTUDIO_TAG) or ESTUDIO_ASSET[platform_key()] not in rel.assets:
        return ""
    return rel.version if re.fullmatch(r"\d+(\.\d+){0,2}", rel.version) else ""


def estudio_can_install() -> bool:
    """¿La app puede instalar el Estudio sola? (en macOS se abre la página de descarga)"""
    return sys.platform == "win32" or sys.platform.startswith("linux")


def check_estudio(rel: Release | None) -> str | None:
    """Versión nueva del Estudio en su Release (si el instalado es más antiguo o de versión
    desconocida), o None. Si el Estudio no está instalado, también None."""
    have = estudio_installed()
    if rel is None or have is None:
        return None
    ver = estudio_version(rel)
    if not ver:
        return None
    return ver if (not have[1] or newer(ver, have[1])) else None


def check_all(upd: dict, current: str = __version__, manual: bool = False):
    """Como check(), pero también busca el Estudio si upd["estudio"] está activo.
    Devuelve (Release de Numpad Macros o None, Release del Estudio o None, versión del Estudio).
    Una sola consulta a GitHub para los dos."""
    beta = bool(upd.get("beta"))
    data = _releases()
    rel = _best(data, beta)
    upd["last_check"] = time.time()
    est_rel = _best(data, beta, estudio=True) if upd.get("estudio") else None
    try:
        est_ver = check_estudio(est_rel)
    except Exception:                     # un fallo con el Estudio no oculta la versión de Numpad Macros
        est_ver = None
    app = rel if rel and newer(rel.version, current) else None
    if app and not manual and upd.get("skip") == app.version and not app.important:
        app = None
    return app, (est_rel if est_ver else None), est_ver


def install_estudio(rel: Release, version: str, progress=None) -> str:
    """Descarga el Estudio de la Release, lo verifica e instala (o actualiza).
    Devuelve la ruta del programa instalado."""
    name = ESTUDIO_ASSET[platform_key()]
    path = download(rel, progress, name=name)
    try:
        if sys.platform == "win32":
            import subprocess
            # Se instala solo para este usuario (no pide permisos); cierra el Estudio si está abierto
            r = subprocess.run([path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=600)
            if r.returncode != 0:
                raise UpdateError(f"El instalador del Estudio terminó con error (código {r.returncode}).")
            have = estudio_installed()
            return have[0] if have else ""
        return _install_estudio_linux(path, version)
    finally:
        _rm(path)


def _install_estudio_linux(tar_path: str, version: str) -> str:
    have = estudio_installed()
    exe = have[0] if have and os.access(os.path.dirname(have[0]), os.W_OK) else _linux_estudio_bin()
    folder = os.path.dirname(exe)
    os.makedirs(folder, exist_ok=True)
    icon = None
    with tarfile.open(tar_path) as tf:
        members = [m for m in tf.getmembers() if m.isfile()]
        prog = next((m for m in members if os.path.basename(m.name) == ESTUDIO_EXE), None)
        if prog is None:
            raise UpdateError("El paquete del Estudio no trae el programa.")
        fd, tmp = tempfile.mkstemp(dir=folder, prefix=".estudio-nuevo-")
        try:
            with os.fdopen(fd, "wb") as f:
                src = tf.extractfile(prog)
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            os.chmod(tmp, 0o755)
            os.replace(tmp, exe)          # se puede reemplazar aunque el Estudio esté abierto
        except BaseException:
            _rm_file(tmp)
            raise
        ico = next((m for m in members if os.path.basename(m.name) == "icon-estudio.png"), None)
        if ico is not None:
            icon = os.path.join(tempfile.gettempdir(), "numpadmacros-icon-estudio.png")
            with open(icon, "wb") as f:
                f.write(tf.extractfile(ico).read())
    if version:
        with open(exe + ".version", "w", encoding="utf-8") as f:
            f.write(version + "\n")
    else:
        _rm_file(exe + ".version")        # sin versión conocida: no dejar la anterior (como instalar_linux.sh)
    if icon:                              # acceso en el menú, igual al que crea el propio Estudio
        try:
            from . import desktop_linux
            desktop_linux.install(ESTUDIO_DESKTOP, "Estudio de Temas · Numpad Macros",
                                  "Crear temas para Numpad Macros", exe, icon,
                                  "EstudioTemasNumpadMacros", categories="Graphics;Utility;",
                                  env=relaunch_env())
        except Exception:
            pass
        _rm_file(icon)
    return exe


def _rm_file(path):
    try:
        os.remove(path)
    except OSError:
        pass


# ---------------------------------------------------------------- novedades
def read_changelog(path: str) -> list[dict]:
    """Lee CHANGELOG.md -> [{'version','date','groups':[(sección,[líneas])]}]."""
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


# ---------------------------------------------------------------- VB-Cable
VBCABLE_URL = "https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack45.zip"


def install_vbcable(progress=None):
    """Windows: descarga VB-Cable de su sitio oficial y abre su instalador
    (Windows pide permiso; en su ventana se pulsa «Install Driver»)."""
    import zipfile
    folder = tempfile.mkdtemp(prefix="numpadmacros-vbcable-")
    zpath = os.path.join(folder, "vbcable.zip")
    try:
        with _open(VBCABLE_URL, timeout=30, accept="application/octet-stream") as r, open(zpath, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = r.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(os.path.join(folder, "vbcable"))
    except Exception as e:
        raise UpdateError(f"No pude descargar VB-Cable: {e}")
    setup = None
    for root, _dirs, files in os.walk(os.path.join(folder, "vbcable")):
        for name in files:
            if name.lower() == "vbcable_setup_x64.exe":
                setup = os.path.join(root, name)
    if not setup:
        raise UpdateError("El paquete de VB-Cable no trae su instalador.")
    import ctypes
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", setup, None, os.path.dirname(setup), 1)
    if r <= 32:
        raise UpdateError("Windows no dio permiso para instalar VB-Cable." if r == 5 else
                          f"No pude abrir el instalador de VB-Cable (código {r}).")
