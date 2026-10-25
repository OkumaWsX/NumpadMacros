# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Catálogo de temas en línea (repositorio NumpadMacros-Temas).

Cómo funciona:
1. fetch(): baja catalogo.json (solo una consulta, sin enviar datos del usuario) y lo guarda en la
   carpeta de configuración. Sin internet se usa la última copia guardada (cached()).
2. entries(): los temas que esta versión de la app puede usar (``requiere_app``).
3. installed_for(): qué tema instalado corresponde a una entrada (mismo nombre y misma firma).
4. Download: baja un tema en segundo plano con progreso, se puede cancelar, reintenta solo si se
   corta (continuando donde quedó) y SOLO instala si la huella SHA256 y la firma son correctas.
   Mientras tanto nada se toca: el archivo baja a una carpeta temporal aparte.

El sello Oficial/Creador/Comunidad y el autor salen siempre de la firma del archivo, nunca del catálogo.
Un tema «creador» (streamers, artistas) lo revisa y firma OkumaWsX con la clave oficial: su archivo
tiene que traer la firma oficial, igual que uno «oficial»; el nombre del creador es solo de la ficha.
"""
import hashlib
import json
import os
import queue
import re
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import __version__, npt, themes
from .config import config_dir

URL = "https://raw.githubusercontent.com/OkumaWsX/NumpadMacros-Temas/main/catalogo.json"
FORMATO = 1                       # formato del catálogo que entiende esta versión
CACHE = "catalogo-temas.json"
STALL = 20                        # segundos sin recibir datos = conexión cortada
RETRIES = (2, 5, 10)              # esperas entre reintentos automáticos
CHUNK = 32 * 1024


class CatalogError(RuntimeError):
    pass


def catalog_url() -> str:
    """URL del catálogo. NUMPADMACROS_TEMAS_URL permite probar con uno local (carpeta, archivo o http)."""
    u = os.environ.get("NUMPADMACROS_TEMAS_URL", "").strip() or URL
    if os.path.isdir(u):
        u = os.path.join(u, "catalogo.json")
    if os.path.exists(u):
        return "file://" + urllib.request.pathname2url(os.path.abspath(u))
    return u


def file_url(entry: dict) -> str:
    """URL del archivo de un tema (relativa a donde está el catálogo)."""
    return urllib.parse.urljoin(catalog_url(), urllib.parse.quote(entry["archivo"]))


def _open(url, timeout=STALL, headers=None):
    from .updater import _context
    req = urllib.request.Request(url, headers={"User-Agent": f"NumpadMacros/{__version__}", **(headers or {})})
    if url.startswith("file:"):
        return urllib.request.urlopen(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout, context=_context())


def _cache_path() -> str:
    return os.path.join(config_dir(), CACHE)


def _valid(cat) -> bool:
    return isinstance(cat, dict) and cat.get("formato") == FORMATO and isinstance(cat.get("temas"), list)


def cached() -> dict | None:
    """La última copia guardada del catálogo (con «obtenido»: cuándo se bajó), o None."""
    try:
        with open(_cache_path(), encoding="utf-8") as f:
            cat = json.load(f)
    except (OSError, ValueError):
        return None
    return cat if _valid(cat) else None


def fetch(timeout: float = 15) -> dict:
    """Baja el catálogo y lo guarda. CatalogError si no se pudo (entonces usar cached())."""
    try:
        with _open(catalog_url(), timeout=timeout, headers={"Accept": "application/json"}) as r:
            cat = json.loads(r.read(4 * 1024 * 1024).decode("utf-8"))
    except Exception as e:
        raise CatalogError(f"No pude consultar el catálogo de temas: {e}")
    if not _valid(cat):
        raise CatalogError("El catálogo de temas tiene un formato que esta versión no conoce. "
                           "Actualiza Numpad Macros.")
    cat["obtenido"] = time.time()
    path = _cache_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cat, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        pass
    return cat


def _ver(v) -> tuple:
    from .updater import parse_version
    return parse_version(str(v or "0"))


def entries(cat: dict | None) -> list[dict]:
    """Temas del catálogo que esta versión de la app puede mostrar."""
    out = []
    for e in (cat or {}).get("temas", []):
        if not isinstance(e, dict) or not all(isinstance(e.get(k), str) for k in ("id", "nombre", "archivo", "sha256")):
            continue
        if e.get("origen") not in ("oficial", "creador", "comunidad") or not isinstance(e.get("colores"), dict):
            continue
        a = e["archivo"]
        if a.startswith("/") or "//" in a or ".." in a or ":" in a or "\\" in a:
            continue                      # la ruta del tema no puede salir de la carpeta del catálogo
        if _ver(e.get("requiere_app")) > _ver(__version__):
            continue                      # usa algo que esta versión no sabe dibujar
        out.append(e)
    return out


# ------------------------------------------------------------------------------- creadores y redes
# Redes que se muestran en la ficha de un creador: nombre visible y dominios oficiales. El catálogo no
# está firmado, así que la app comprueba otra vez cada enlace (lo mismo que el armador al publicarlo)
# y jamás abre uno que no pase: https, sin usuario ni puerto, y un host que sea EL dominio oficial de
# esa red o un subdominio suyo (twitch.tv.evil.com no lo es).
REDES = {"twitch": ("Twitch", ("twitch.tv",)),
         "youtube": ("YouTube", ("youtube.com", "youtu.be")),
         "tiktok": ("TikTok", ("tiktok.com",)),
         "kick": ("Kick", ("kick.com",)),
         "instagram": ("Instagram", ("instagram.com",)),
         "x": ("X", ("x.com", "twitter.com")),
         "facebook": ("Facebook", ("facebook.com",)),
         "discord": ("Discord", ("discord.gg", "discord.com"))}
BIO_MAX = 300
URL_MAX = 300


def red_url_valida(red, url) -> bool:
    """¿Es ``url`` un enlace seguro al dominio oficial de la red ``red``?"""
    if not isinstance(red, str) or red not in REDES or not isinstance(url, str) or not url or len(url) > URL_MAX:
        return False
    if not url.isascii() or any(c.isspace() or ord(c) < 32 or ord(c) == 127 or c in "\\<>\"'`" for c in url):
        return False
    try:
        p = urllib.parse.urlsplit(url)
        port = p.port
    except ValueError:
        return False
    host = (p.hostname or "").lower()
    if p.scheme != "https" or port is not None or "@" in p.netloc or p.username or p.password:
        return False
    if p.netloc.lower() != host:                 # nada raro entre el https:// y el nombre del sitio
        return False
    return any(host == d or host.endswith("." + d) for d in REDES[red][1])


# Foto de perfil del creador. Igual que todo lo del catálogo, no es de fiar: la ruta tiene que ser relativa
# (si no, urljoin podría mandarnos a otro servidor), la huella y el tamaño se comprueban al bajarla, y la
# imagen se mide antes de decodificarla (nada de bombas de descompresión).
AVATAR_MAX = 200 * 1024                     # bytes
AVATAR_PX = (64, 512)                       # lado mínimo y máximo
AVATAR_ASPECTO = 1.1                        # lado mayor / lado menor
AVATAR_CACHE = "creadores-cache"            # carpeta (dentro de la de configuración) con <sha256>.img
AVATAR_KEEP = 24                            # cuántas fotos se guardan como máximo
_AVATAR_RUTA = re.compile(r"^(?!.*\.\.)[A-Za-z0-9][A-Za-z0-9._/-]{0,200}\.(png|jpe?g)$", re.I)
_SHA = re.compile(r"^[0-9a-f]{64}$")


def avatar_valido(av) -> dict | None:
    """``{"archivo", "sha256", "tamano"}`` ya limpio, o None si no sirve (ruta rara, huella mal escrita,
    tamaño que pasa el límite…)."""
    if not isinstance(av, dict):
        return None
    ruta, sha, tam = av.get("archivo"), av.get("sha256"), av.get("tamano")
    if (not isinstance(ruta, str) or not _AVATAR_RUTA.match(ruta) or "//" in ruta
            or not isinstance(sha, str) or not _SHA.match(sha.lower())
            or isinstance(tam, bool) or not isinstance(tam, int) or not 0 < tam <= AVATAR_MAX):
        return None
    return {"archivo": ruta, "sha256": sha.lower(), "tamano": tam}


def avatar_url(av: dict) -> str:
    """URL de la foto (relativa a donde está el catálogo, igual que ``file_url``)."""
    return urllib.parse.urljoin(catalog_url(), urllib.parse.quote(av["archivo"]))


def _avatar_dir() -> str:
    return os.path.join(config_dir(), AVATAR_CACHE)


def avatar_path(sha: str) -> str:
    return os.path.join(_avatar_dir(), sha + ".img")


def _avatar_check(data: bytes, av: dict) -> None:
    """Lanza ValueError si ``data`` no es la foto que dice el catálogo o no es una imagen aceptable."""
    if len(data) > AVATAR_MAX or len(data) != av["tamano"]:
        raise ValueError("el tamaño de la foto no coincide con el catálogo")
    if hashlib.sha256(data).hexdigest() != av["sha256"]:
        raise ValueError("la huella de la foto no coincide con el catálogo")
    try:
        from PIL import Image
        import io
        with Image.open(io.BytesIO(data)) as im:        # solo lee la cabecera: aún no decodifica
            fmt, (w, h) = im.format, im.size
    except Exception as e:
        raise ValueError(f"la foto no es una imagen válida ({e})")
    lo, hi = AVATAR_PX
    if fmt not in ("PNG", "JPEG") or min(w, h) < lo or max(w, h) > hi or max(w, h) > min(w, h) * AVATAR_ASPECTO:
        raise ValueError("la foto no es un PNG o JPEG cuadrado de 64 a 512 px")


def avatar_get(av: dict, timeout: float = 15) -> str:
    """Deja la foto del creador en la caché y devuelve su ruta (se usa en un hilo, no en el de Tk).
    Si ya está en la caché y su huella sigue bien, no toca la red. ValueError/OSError si no se pudo:
    entonces la app se queda con la inicial."""
    path = avatar_path(av["sha256"])
    try:
        with open(path, "rb") as f:
            data = f.read(AVATAR_MAX + 1)
        _avatar_check(data, av)
        return path
    except (OSError, ValueError):
        pass                                    # no está, o alguien la tocó: se baja de nuevo
    with _open(avatar_url(av), timeout=timeout) as r:
        data = r.read(AVATAR_MAX + 1)           # nunca más de lo permitido, venga lo que venga
    _avatar_check(data, av)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".nuevo"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)
    _avatar_prune(path)
    return path


def _avatar_prune(keep_path: str) -> None:
    """Deja solo las fotos más recientes en la caché."""
    try:
        files = [os.path.join(_avatar_dir(), n) for n in os.listdir(_avatar_dir()) if n.endswith(".img")]
        files.sort(key=os.path.getmtime, reverse=True)
        for old in files[AVATAR_KEEP:]:
            if old != keep_path:
                os.remove(old)
    except OSError:
        pass


def creator_info(entry: dict | None) -> dict | None:
    """Datos del creador de una entrada («creador_info»), ya limpios: ``{"nombre", "bio", "redes",
    "avatar"}`` con ``redes = [{"red", "nombre", "url"}]`` solo con las que pasan la validación (sin
    repetir una red) y ``avatar`` = ``{"archivo", "sha256", "tamano"}`` o None. None si la entrada no
    trae nada utilizable."""
    info = (entry or {}).get("creador_info")
    if not isinstance(info, dict):
        return None
    name = info.get("nombre")
    bio = info.get("bio")
    nets, seen = [], set()
    raw = info.get("redes")
    for r in (raw if isinstance(raw, list) else [])[:len(REDES)]:
        if not isinstance(r, dict):
            continue
        red, url = r.get("red"), r.get("url")
        if not red_url_valida(red, url) or red in seen:
            continue
        seen.add(red)
        nets.append({"red": red, "nombre": REDES[red][0], "url": url})
    return {"nombre": name.strip()[:40] if isinstance(name, str) else "",
            "bio": " ".join(bio.split())[:BIO_MAX] if isinstance(bio, str) else "",
            "redes": nets, "avatar": avatar_valido(info.get("avatar"))}


def _same_theme(entry: dict, th: dict) -> bool:
    if th.get("builtin") or th.get("name", "").casefold() != entry["nombre"].casefold():
        return False
    if entry["origen"] in ("oficial", "creador"):      # los dos van firmados con la clave oficial
        return bool(th.get("official"))
    key = th.get("author_key") or ""
    return (not th.get("official")) and bool(key) and npt.fingerprint(key) == entry.get("huella_autor")


def installed_for(entry: dict, installed: list[dict]) -> dict | None:
    """El tema instalado que corresponde a una entrada del catálogo (o None)."""
    return next((t for t in installed if _same_theme(entry, t)), None)


def has_update(entry: dict, th: dict | None) -> bool:
    return th is not None and _ver(entry.get("version")) > _ver(th.get("version"))


# ------------------------------------------------------------------------------- descargas
class Download:
    """Baja e instala un tema en un hilo. Los avisos llegan por ``events`` (una cola):
    ("progress", hechos, total) · ("retry", intento, de, espera) · ("done", tema) ·
    ("error", mensaje) · ("cancelled",)."""

    def __init__(self, entry: dict, replace: dict | None = None):
        self.entry = entry
        self.replace = replace                  # tema instalado que se reemplaza (actualización)
        self.events: queue.Queue = queue.Queue()
        self.done = 0
        self.total = int(entry.get("tamano") or 0)
        self.state = "bajando"                  # bajando · reintentando · listo · error · cancelado
        self.error = ""
        self._cancel = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def cancel(self):
        self._cancel.set()

    @property
    def fraction(self) -> float:
        return min(1.0, self.done / self.total) if self.total else 0.0

    def _run(self):
        folder = tempfile.mkdtemp(prefix="numpadmacros-tema-")
        part = os.path.join(folder, "tema.part")
        try:
            attempt = 0
            while True:
                try:
                    self._download(part)
                    break
                except _Cancelled:
                    raise
                except _Fatal:
                    raise
                except Exception as e:          # corte de red, servidor caído, tiempo agotado…
                    if attempt >= len(RETRIES):
                        raise _Fatal(_friendly(e))
                    wait = RETRIES[attempt]
                    attempt += 1
                    self.state = "reintentando"
                    self.events.put(("retry", attempt, len(RETRIES), wait))
                    if self._cancel.wait(wait):
                        raise _Cancelled()
                    self.state = "bajando"
            theme = self._verify_and_install(part)
            self.state = "listo"
            self.events.put(("done", theme))
        except _Cancelled:
            self.state = "cancelado"
            self.events.put(("cancelled",))
        except _Fatal as e:
            self.state = "error"
            self.error = str(e)
            self.events.put(("error", str(e)))
        except Exception as e:
            self.state = "error"
            self.error = _friendly(e)
            self.events.put(("error", self.error))
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def _download(self, part):
        """Baja (o continúa) el archivo en ``part``."""
        have = os.path.getsize(part) if os.path.exists(part) else 0
        url = file_url(self.entry)
        headers = {"Range": f"bytes={have}-"} if have and not url.startswith("file:") else {}
        with _open(url, timeout=STALL, headers=headers) as r:
            status = getattr(r, "status", 200)
            if have and status != 206:          # el servidor no permite continuar: desde cero
                have = 0
            mode = "ab" if have else "wb"
            self.done = have
            length = r.headers.get("Content-Length")
            if length and not self.total:
                self.total = have + int(length)
            with open(part, mode) as f:
                while True:
                    if self._cancel.is_set():
                        raise _Cancelled()
                    chunk = r.read(CHUNK)
                    if not chunk:
                        break
                    f.write(chunk)
                    self.done += len(chunk)
                    if self.done > npt.MAX_SIZE:
                        raise _Fatal("El archivo es más grande de lo permitido para un tema.")
                    self.events.put(("progress", self.done, self.total))
        if self.total and self.done < self.total:
            raise ConnectionError("la descarga quedó incompleta")

    def _verify_and_install(self, part) -> dict:
        with open(part, "rb") as f:
            data = f.read()
        if hashlib.sha256(data).hexdigest() != self.entry["sha256"].lower():
            raise _Fatal("El archivo descargado no coincide con el original. Se borró por seguridad; "
                         "inténtalo de nuevo.")
        try:
            r = npt.read(data)
        except npt.NptError as e:
            raise _Fatal(f"El tema descargado no es válido: {e}")
        # el sello lo da la firma: si el catálogo dice «oficial» o «creador», el archivo tiene que traer
        # la firma oficial (así nadie se hace pasar por creador); si dice «comunidad», no puede traerla
        if (self.entry["origen"] in ("oficial", "creador")) != r.official:
            raise _Fatal("La firma del tema no coincide con el catálogo. No se instaló.")
        if self._cancel.is_set():
            raise _Cancelled()
        os.makedirs(themes.themes_dir(), exist_ok=True)
        theme = r.to_dict(images=False)
        theme.update(official=r.official, builtin=False, sha256=hashlib.sha256(data).hexdigest())
        if self.replace and self.replace.get("file"):
            dest = os.path.join(themes.themes_dir(), self.replace["file"])      # actualizar: mismo archivo
        else:
            # el mismo tema (nombre y firma) que ya tengas se reemplaza: nunca queda una copia «(2)»
            _, twin = themes.plan_install(theme, themes.installed_with_sha())
            dest = os.path.join(themes.themes_dir(), twin["file"]) if twin else themes.free_path(r.theme.name)
        themes.write_atomic(dest, data)         # de una vez: nunca queda un tema a medias
        theme.update(file=os.path.basename(dest))
        return theme


class _Cancelled(Exception):
    pass


class _Fatal(Exception):
    """Error que no se arregla reintentando (huella o firma incorrecta, archivo enorme…)."""


def _friendly(e) -> str:
    if isinstance(e, _Fatal):
        return str(e)
    if isinstance(e, urllib.error.HTTPError):
        return f"El servidor respondió con un error ({e.code}). Tu tema actual no cambió."
    if isinstance(e, OSError) and getattr(e, "errno", None) == 28:
        return "No hay espacio en el disco. Tu tema actual no cambió."
    if isinstance(e, PermissionError):
        return "No hay permiso para guardar el tema. Tu tema actual no cambió."
    return "Se perdió la conexión. Tu tema actual no cambió."
