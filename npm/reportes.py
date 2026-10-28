# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Registro de errores y reportes para el creador.

- Todo error queda anotado en ``registro.log`` (carpeta de configuración), con los últimos pasos
  que hizo el usuario antes del fallo.
- Si el usuario lo permite, el reporte se envía solo al bot del creador (Centinela), que lo revisa,
  lo agrupa con los iguales y lo publica en un canal privado de Discord. La app nunca lleva la
  dirección del canal: así nadie puede sacarla del programa y llenarlo de spam.
- Antes de salir, el reporte se limpia de datos personales: el nombre de usuario y la carpeta
  personal se reemplazan, y de los archivos solo queda la extensión.
- Si no hay internet (o el bot no responde) el reporte queda en cola y se reintenta más tarde.

Formato del envío: ver docs/REPORTES.md.
"""
import collections
import hashlib
import json
import logging
import logging.handlers
import os
import platform
import re
import sys
import threading
import time
import traceback
import urllib.request
import uuid

from . import __version__
from .config import config_dir

# Dirección del bot que recibe los reportes. Vacía = aún no hay bot: los reportes quedan en cola
# (y se envían solos en cuanto una versión nueva traiga la dirección). NM_REPORT_URL la cambia
# para pruebas.
ENDPOINT = ""
POW_BITS = 18                     # prueba de trabajo (~0,1–0,5 s): hace caro mandar spam en masa
MAX_QUEUE = 20
MAX_REPORT = 60_000               # bytes
RESEND_AFTER = 24 * 3600          # el mismo error, en la misma versión, como mucho una vez al día

log = logging.getLogger("numpadmacros")
_steps = collections.deque(maxlen=30)
_lock = threading.Lock()
_state = {"app": None, "asked": False, "sending": False}


def endpoint() -> str:
    return os.environ.get("NM_REPORT_URL", ENDPOINT).strip()


def _dir(*parts):
    p = os.path.join(config_dir(), *parts)
    os.makedirs(os.path.dirname(p) if parts and "." in parts[-1] else p, exist_ok=True)
    return p


def log_path() -> str:
    return _dir("registro.log")


# ================================================================ registro local
def setup():
    """Registro en archivo (se recorta solo: 2 × 300 KB) y captura de errores no atrapados."""
    if getattr(setup, "done", False):
        return
    setup.done = True
    try:
        h = logging.handlers.RotatingFileHandler(log_path(), maxBytes=300_000, backupCount=1, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
    except OSError:
        pass
    log.info("Numpad Macros %s · %s", __version__, system_text())

    prev = sys.excepthook

    def hook(t, v, tb):
        capture((t, v, tb), "principal")
        prev(t, v, tb)
    sys.excepthook = hook

    def thread_hook(args):
        if args.exc_type is SystemExit:
            return
        capture((args.exc_type, args.exc_value, args.exc_traceback),
                f"hilo {getattr(args.thread, 'name', '?')}")
    threading.excepthook = thread_hook


def attach(app):
    """Conecta los reportes con la ventana (errores de Tk, avisos y el diálogo de permiso)."""
    _state["app"] = app

    def tk_hook(t, v, tb):
        traceback.print_exception(t, v, tb)
        capture((t, v, tb), "ventana")
    app.root.report_callback_exception = tk_hook
    # reintentar lo que quedó en cola (al abrir y cada 30 minutos)
    def retry():
        flush_async()
        try:
            app.root.after(30 * 60 * 1000, retry)
        except Exception:
            pass
    try:
        app.root.after(20_000, retry)
    except Exception:
        pass


def paso(text: str):
    """Anota un paso del usuario (se envía con el reporte para entender qué pasó antes del error)."""
    _steps.append(time.strftime("%H:%M:%S ") + text)
    log.info("· %s", text)


# ================================================================ datos del equipo
def system_text() -> str:
    try:
        if sys.platform.startswith("linux"):
            name = ""
            try:
                with open("/etc/os-release", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            name = line.split("=", 1)[1].strip().strip('"')
            except OSError:
                pass
            desk = os.environ.get("XDG_CURRENT_DESKTOP", "") or "?"
            sess = os.environ.get("XDG_SESSION_TYPE", "") or "?"
            return f"{name or 'Linux'} · kernel {platform.release()} · {desk} ({sess})"
        if sys.platform == "win32":
            return f"Windows {platform.release()} ({platform.version()})"
        if sys.platform == "darwin":
            return f"macOS {platform.mac_ver()[0]} ({platform.machine()})"
    except Exception:
        pass
    return platform.platform()


def install_id() -> str:
    """Número al azar de esta instalación (no dice nada de la persona): sirve para saber si
    varios reportes vienen del mismo equipo y para que el bot limite los envíos."""
    p = _dir("reportes", "instalacion.txt")
    try:
        with open(p, encoding="utf-8") as f:
            v = f.read().strip()
            if re.fullmatch(r"[0-9a-f]{32}", v):
                return v
    except OSError:
        pass
    v = uuid.uuid4().hex
    try:
        with open(p, "w", encoding="utf-8") as f:
            f.write(v)
    except OSError:
        pass
    return v


# ================================================================ limpieza de datos personales
def _private_bits():
    home = os.path.expanduser("~")
    user = os.path.basename(home.rstrip("/\\")) or ""
    try:
        import getpass
        user2 = getpass.getuser()
    except Exception:
        user2 = ""
    return home, {u for u in (user, user2) if u and len(u) > 2 and u.lower() not in ("root", "user", "usuario")}


_EXTS = ("mp3|wav|ogg|oga|flac|m4a|aac|opus|aif|aiff|wma|mp4|mkv|webm|mov|png|jpe?g|gif|webp|bmp|svg|txt|json|"
         "npt|nptproj|nptj|spl|zip|7z|rar|pdf|docx?|xlsx?|csv|key|npkey|log")
# rutas entre comillas (pueden tener espacios) y rutas sueltas (sin espacios)
_QFILE = re.compile(r"(['\"])(~?)((?:[A-Za-z]:)?[\\/][^'\"\n]*?)\.(" + _EXTS + r")\1", re.IGNORECASE)
_FILE = re.compile(r"(?<![…\w])(~?)((?:[A-Za-z]:)?[\\/][^\s'\"<>|*?]*)\.(" + _EXTS + r")\b", re.IGNORECASE)


def clean(text: str) -> str:
    """Quita del texto la carpeta personal, el nombre de usuario y los nombres de los archivos
    del usuario (deja la extensión: «~/…/archivo.mp3»). Las rutas del propio programa quedan."""
    if not text:
        return ""
    home, users = _private_bits()
    out = text
    if home and len(home) > 3:
        out = out.replace(home, "~")
    # rutas del programa empaquetado (_MEI…/npm/x.py) -> npm/x.py
    out = re.sub(r"[^\s'\"]*[\\/]_MEI[^\\/]*[\\/]", "", out)

    out = _QFILE.sub(lambda m: m.group(1) + ("~/…/archivo." if m.group(2) else "…/archivo.")
                     + m.group(4).lower() + m.group(1), out)
    out = _FILE.sub(lambda m: ("~/…/archivo." if m.group(1) else "…/archivo.") + m.group(3).lower(), out)
    for u in users:
        out = re.sub(re.escape(u), "<usuario>", out, flags=re.IGNORECASE)
    return out


# ================================================================ armar el reporte
def fingerprint(exc_type, tb) -> str:
    """Huella del error: el tipo y por dónde pasó en el código (sin números de línea, para que el
    mismo error se agrupe aunque cambie un poco el archivo entre versiones)."""
    frames = traceback.extract_tb(tb) if tb else []
    sig = [getattr(exc_type, "__name__", str(exc_type))]
    for fr in frames[-6:]:
        fn = re.sub(r".*[\\/](npm|tools)[\\/]", r"\1/", fr.filename.replace("\\", "/"))
        sig.append(f"{os.path.basename(fn)}:{fr.name}")
    return hashlib.sha1("|".join(sig).encode()).hexdigest()[:12]


def _context() -> dict:
    app = _state.get("app")
    ctx = {}
    if app is None:
        return ctx
    for key, fn in (
            ("tema", lambda: app.theme.get("name")),
            ("vista", lambda: app.left_view),
            ("pestaña", lambda: app.nb.tab(app.nb.select(), "text")),
            ("captura", lambda: app.cfg.get("mode") or "?"),
            ("numpad_elegido", lambda: bool(app.cfg.get("device"))),
            ("solo_celular", lambda: bool(app.cfg.get("phone", {}).get("only"))),
            ("activo", lambda: bool(app.engine.active)),
            ("bancos", lambda: len(app.cfg.get("banks", []))),
            ("sonidos", lambda: len(app.cfg.get("library", []))),
            ("ventana", lambda: f"{app.root.winfo_width()}×{app.root.winfo_height()} "
                                f"(pantalla {app.root.winfo_screenwidth()}×{app.root.winfo_screenheight()})"),
            ("celulares", lambda: len(getattr(app.remote, "clients", []) or []) if getattr(app, "remote", None) else 0),
            ("betas", lambda: bool(app.cfg.get("updates", {}).get("beta")))):
        try:
            ctx[key] = fn()
        except Exception:
            pass
    return ctx


def _log_tail(n=80) -> str:
    try:
        with open(log_path(), encoding="utf-8", errors="replace") as f:
            return "".join(collections.deque(f, maxlen=n))
    except OSError:
        return ""


def build(kind: str, exc_info=None, where: str = "", description: str = "", contact: str = "",
          with_log: bool = True) -> dict:
    rep = {"app": "NumpadMacros", "version": __version__, "tipo": kind, "fecha": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "sistema": system_text(), "python": platform.python_version(),
           "empaquetada": bool(getattr(sys, "frozen", False)), "instalacion": install_id(),
           "contexto": _context(), "pasos": list(_steps)}
    if exc_info:
        t, v, tb = exc_info
        rep["huella"] = fingerprint(t, tb)
        rep["error"] = clean(f"{getattr(t, '__name__', t)}: {v}")[:500]
        frames = traceback.extract_tb(tb) if tb else []
        if frames:
            fr = frames[-1]
            fn = re.sub(r".*[\\/](npm|tools)[\\/]", r"\1/", fr.filename.replace("\\", "/"))
            rep["donde"] = clean(f"{fn}:{fr.lineno} en {fr.name}")
        rep["traza"] = clean("".join(traceback.format_exception(t, v, tb)))[-12_000:]
        rep["hilo"] = where
    else:
        rep["huella"] = "manual-" + hashlib.sha1((description or str(time.time())).encode()).hexdigest()[:6]
    if description:
        rep["descripcion"] = clean(description)[:3000]
    if contact:
        rep["contacto"] = contact.strip()[:80]
    if with_log:
        rep["registro"] = clean(_log_tail())[-20_000:]
    rep["pasos"] = [clean(s) for s in rep["pasos"]]
    return rep


def as_text(rep: dict) -> str:
    """El reporte como texto legible (lo que el usuario ve antes de enviarlo y lo que se copia)."""
    lines = [f"Numpad Macros {rep['version']} · {rep['tipo']} · {rep['fecha']}",
             f"Sistema: {rep['sistema']} · Python {rep['python']}" + (" · app compilada" if rep["empaquetada"] else "")]
    if rep.get("error"):
        lines += ["", "Error: " + rep["error"]]
        if rep.get("donde"):
            lines.append("Dónde: " + rep["donde"])
    if rep.get("descripcion"):
        lines += ["", "Lo que pasó (según el usuario):", rep["descripcion"]]
    if rep.get("contexto"):
        lines += ["", "Estado: " + ", ".join(f"{k} = {v}" for k, v in rep["contexto"].items())]
    if rep.get("pasos"):
        lines += ["", "Últimos pasos:"] + ["  " + s for s in rep["pasos"][-12:]]
    if rep.get("traza"):
        lines += ["", rep["traza"].rstrip()]
    if rep.get("registro"):
        lines += ["", "Registro (últimas líneas):", rep["registro"].rstrip()]
    return "\n".join(lines)


# ================================================================ captura
def capture(exc_info, where: str = ""):
    """Anota un error y, según lo que eligió el usuario, lo envía, pregunta o solo lo guarda."""
    try:
        t, v, tb = exc_info
        if t in (KeyboardInterrupt, SystemExit):
            return
        log.error("Error (%s): %s", where, "".join(traceback.format_exception(t, v, tb)).rstrip())
        rep = build("error", exc_info, where)
        if _recently_sent(rep["huella"]):
            log.info("El mismo error ya se informó hoy (%s): no se vuelve a enviar.", rep["huella"])
            return
        mode = _mode()
        if mode == "nunca":
            return
        if mode == "siempre":
            send(rep)
            _toast("Hubo un error: se envió un reporte al creador para arreglarlo.")
            return
        app = _state.get("app")
        if app is None or _state["asked"]:
            _save(rep)                              # sin ventana o ya preguntó en esta sesión: queda en cola
            return
        _state["asked"] = True
        try:
            app.root.after(0, lambda: _ask(rep))
        except Exception:
            _save(rep)
    except Exception:
        pass                                        # el reporte nunca debe causar otro error


def _mode() -> str:
    app = _state.get("app")
    try:
        return app.cfg.setdefault("reportes", {}).get("modo", "preguntar")
    except Exception:
        return "preguntar"


def set_mode(mode: str):
    app = _state.get("app")
    if app is None:
        return
    with app.engine.lock:
        app.cfg.setdefault("reportes", {})["modo"] = mode
    try:
        app._save()
    except Exception:
        pass


def _toast(text):
    app = _state.get("app")
    if app is not None:
        try:
            app.root.after(0, lambda: app._show_toast(text))
        except Exception:
            pass


def _ask(rep):
    from .dialogs import ask_report        # pregunta con la vista del reporte
    choice = ask_report(_state["app"], rep)
    if choice in ("siempre", "esta"):
        if choice == "siempre":
            set_mode("siempre")
        send(rep)
    elif choice == "nunca":
        set_mode("nunca")
        _save(rep, queue=False)
    else:
        _save(rep, queue=False)


# ================================================================ cola y envío
def _queue_dir():
    return _dir("reportes", "cola")


def _sent_path():
    return _dir("reportes", "enviados.json")


def _recently_sent(huella: str) -> bool:
    try:
        with open(_sent_path(), encoding="utf-8") as f:
            data = json.load(f)
        return time.time() - data.get(f"{__version__}:{huella}", 0) < RESEND_AFTER
    except (OSError, ValueError):
        return False


def _mark_sent(huella: str):
    p = _sent_path()
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    data[f"{__version__}:{huella}"] = time.time()
    data = dict(sorted(data.items(), key=lambda kv: kv[1])[-200:])
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass


def _save(rep: dict, queue: bool = True) -> str | None:
    """Guarda el reporte: en la cola (para enviar) o en «guardados» (solo para el usuario)."""
    folder = _queue_dir() if queue else _dir("reportes", "guardados")
    name = time.strftime("%Y%m%d-%H%M%S-") + rep.get("huella", "x") + ".json"
    path = os.path.join(folder, name)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False)
        files = sorted(os.listdir(folder))
        for old in files[:-MAX_QUEUE]:
            os.remove(os.path.join(folder, old))
        return path
    except OSError:
        return None


def last_report_text() -> str:
    """El último reporte guardado o en cola, como texto (para «Copiar el último reporte»)."""
    best = None
    for sub in ("cola", "guardados"):
        d = _dir("reportes", sub)
        for n in os.listdir(d):
            p = os.path.join(d, n)
            if best is None or os.path.getmtime(p) > os.path.getmtime(best):
                best = p
    if not best:
        return ""
    try:
        with open(best, encoding="utf-8") as f:
            return as_text(json.load(f))
    except (OSError, ValueError):
        return ""


def pending() -> int:
    try:
        return len(os.listdir(_queue_dir()))
    except OSError:
        return 0


def send(rep: dict):
    """Pone el reporte en la cola y la envía en segundo plano."""
    _save(rep)
    flush_async()


def flush_async(done=None):
    if _state["sending"]:
        return
    _state["sending"] = True

    def run():
        try:
            res = flush()
        finally:
            _state["sending"] = False
        if done:
            done(res)
    threading.Thread(target=run, daemon=True, name="reportes").start()


def flush() -> tuple[int, int]:
    """Envía lo que hay en la cola. Devuelve (enviados, que quedan)."""
    url = endpoint()
    folder = _queue_dir()
    sent = 0
    if not url:
        return 0, pending()
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        try:
            with open(path, encoding="utf-8") as f:
                rep = json.load(f)
        except (OSError, ValueError):
            _rm(path)
            continue
        status = _post(url, rep)
        if status == "ok" or status == "rechazado":
            _rm(path)
            if status == "ok":
                sent += 1
                if rep.get("tipo") == "error":
                    _mark_sent(rep.get("huella", ""))
        else:
            break                                   # sin conexión o bot ocupado: se reintenta después
    return sent, pending()


def _rm(path):
    try:
        os.remove(path)
    except OSError:
        pass


def proof_of_work(body: bytes, bits: int = POW_BITS) -> str:
    """Número que hace que sha256(cuerpo + número) empiece con `bits` ceros. Al bot le cuesta nada
    comprobarlo; a quien quiera mandar miles de reportes falsos le cuesta tiempo de CPU."""
    target = 1 << (256 - bits)
    base = hashlib.sha256(body)
    n = 0
    while True:
        h = base.copy()
        h.update(str(n).encode())
        if int.from_bytes(h.digest(), "big") < target:
            return str(n)
        n += 1


def _post(url: str, rep: dict) -> str:
    """'ok', 'rechazado' (el bot no lo quiere: no reintentar) u 'otra-vez'."""
    body = json.dumps(rep, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_REPORT:                       # se recorta el registro antes que el error
        rep = dict(rep, registro=(rep.get("registro") or "")[-5_000:], traza=(rep.get("traza") or "")[-8_000:])
        body = json.dumps(rep, ensure_ascii=False, separators=(",", ":")).encode("utf-8")[:MAX_REPORT]
    nonce = proof_of_work(body)
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "User-Agent": f"NumpadMacros/{__version__}",
        "X-NM-Version": __version__, "X-NM-Prueba": nonce})
    try:
        from .updater import _context
        with urllib.request.urlopen(req, timeout=15, context=_context()) as r:
            return "ok" if 200 <= r.status < 300 else "otra-vez"
    except urllib.error.HTTPError as e:
        if e.code in (400, 403, 410, 413, 422):     # formato o versión rechazados: no insistir
            log.info("El bot rechazó un reporte (%s).", e.code)
            return "rechazado"
        return "otra-vez"                           # 429 (demasiados) o 5xx: más tarde
    except Exception:
        return "otra-vez"
