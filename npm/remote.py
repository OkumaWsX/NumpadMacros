# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Conexión con la app del celular (Wi-Fi, cable USB y Bluetooth).

Un solo protocolo para los tres caminos (ver docs/PROTOCOLO_CELULAR.md):
mensajes JSON de una línea. Wi-Fi y USB usan TCP (el USB es la red que crea
«Compartir conexión por USB» del celular); Bluetooth usa RFCOMM.

Hilos:
- TCP: acepta conexiones en el puerto 47800.
- UDP: responde a «descubrir» en el puerto 47801.
- Bluetooth: según el sistema (npm/remote_bt.py).
- Uno por celular conectado, más uno que envía lo que está sonando.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import socket
import sys
import threading
import time

from . import __version__
from .soundboard import AUDIO_EXT
from .theme import BUTTON_COLORS
from .keys import (VIRTUAL_COLS, VIRTUAL_ROWS, NUMPAD_LAYOUT, PHONE_COUNTS, PHONE_IDS, ROW_LAYOUT, phone_count,
                   phone_layout)

TCP_PORT = 47800
UDP_PORT = 47801
PROTO = 1
MAX_LINE = 1 << 20
MAX_UPLOAD = 50 * 1024 * 1024
MAX_PIN_TRIES = 5
ACT_TYPES = ("file", "keys", "sound_stop", "bank_next", "bank_prev", "bank_go")
MODES = ("overlap", "restart", "toggle", "hold")
DEFAULT = {"enabled": True, "name": "", "pc_id": "", "devices": [],
           "bluetooth": True, "port": TCP_PORT}


def settings(cfg: dict) -> dict:
    """cfg["remote"] completo (crea lo que falte)."""
    r = cfg.setdefault("remote", {})
    for k, v in DEFAULT.items():
        r.setdefault(k, list(v) if isinstance(v, list) else v)
    if not r["pc_id"]:
        r["pc_id"] = secrets.token_hex(8)
    return r


def pc_name(cfg: dict) -> str:
    return settings(cfg).get("name") or socket.gethostname().split(".")[0] or "Mi PC"


def lib_id(path: str) -> str:
    return hashlib.sha1(os.path.normcase(os.path.abspath(path)).encode("utf-8")).hexdigest()[:10]


def local_ips() -> list[str]:
    """IPv4 del PC (sin 127.x), la de la ruta principal primero."""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.append(info[4][0])
    except OSError:
        pass
    if sys.platform.startswith("linux"):
        try:
            import fcntl
            import struct
            for _idx, name in socket.if_nameindex():
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    try:
                        raw = fcntl.ioctl(s.fileno(), 0x8915, struct.pack("256s", name[:15].encode()))
                        ips.append(socket.inet_ntoa(raw[20:24]))
                    except OSError:
                        pass
        except (ImportError, OSError):
            pass
    out = []
    for ip in ips:
        if ip and not ip.startswith("127.") and ip not in out:
            out.append(ip)
    return out


def qr_text(cfg: dict, pin: str) -> str:
    r = settings(cfg)
    name = re.sub(r"[^\w\-. ]", "", pc_name(cfg)).replace(" ", "%20")
    return (f"nmacros://vincular?h={','.join(local_ips())}&p={r['port']}&c={pin}"
            f"&n={name}&id={r['pc_id']}")


def clean_name(name: str) -> str:
    base = os.path.basename(str(name or "")).strip()
    base = re.sub(r"[^\w\-. áéíóúñÁÉÍÓÚÑüÜ]", "_", base)[:80].strip(" .")
    return base or "sonido"


class _Upload:
    def __init__(self, path, size, title):
        self.path, self.size, self.title = path, size, title
        self.tmp = path + ".parcial"
        self.f = open(self.tmp, "wb")
        self.got = 0
        self.seq = 0
        self.sha = hashlib.sha256()

    def abort(self):
        try:
            self.f.close()
            os.remove(self.tmp)
        except OSError:
            pass


class Session:
    """Un celular conectado."""

    def __init__(self, server, sock, transport: str, addr: str):
        self.server, self.sock, self.transport, self.addr = server, sock, transport, addr
        self.wlock = threading.Lock()
        self.dev = ""
        self.name = "Celular"
        self.authed = False
        self.nonce = secrets.token_hex(16)
        self.tries = 0
        self.upload: _Upload | None = None
        self.held: set[str] = set()
        self.closed = False
        self.connected_at = time.time()

    # ------------------------------------------------------------ envío
    def send(self, obj) -> bool:
        data = (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            with self.wlock:
                self.sock.sendall(data)
            return True
        except OSError:
            self.close()
            return False

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.sock.close()
        except OSError:
            pass

    # ------------------------------------------------------------ lectura
    def run(self):
        buf = b""
        try:
            while not self.closed:
                chunk = self.sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if line.strip():
                        self._line(line)
                if len(buf) > MAX_LINE:
                    break
        except OSError:
            pass
        finally:
            self.close()
            self.server._gone(self)

    def _line(self, line: bytes):
        try:
            msg = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return
        if not isinstance(msg, dict):
            return
        t = msg.get("t")
        try:
            if not self.authed:
                self._login(t, msg)
            else:
                handler = getattr(self, "_m_" + str(t), None)
                if handler:
                    handler(msg)
        except Exception as e:      # un mensaje raro no debe tumbar la conexión
            self.send({"t": "aviso", "text": f"Error en el PC: {e}", "bad": True})

    # ------------------------------------------------------------ entrada
    def _login(self, t, msg):
        srv = self.server
        if t == "hola":
            self.dev = str(msg.get("dev", ""))[:64]
            self.name = str(msg.get("name", "Celular"))[:60] or "Celular"
            if not srv.enabled():
                self.send({"t": "rechazado", "why": "desactivado"})
                self.close()
                return
            self.send({"t": "reto", "nonce": self.nonce, "pc": srv.pc_id(), "name": srv.name(),
                       "app": __version__, "known": srv.find_device(self.dev) is not None})
        elif t == "prueba":
            dev = srv.find_device(self.dev)
            if not dev:
                self.send({"t": "rechazado", "why": "olvidado"})
                self.close()
                return
            mac = str(msg.get("mac", ""))
            want = dev.get("token", "")
            ok = bool(want) and hmac.compare_digest(
                hmac.new(want.encode(), self.nonce.encode(), hashlib.sha256).hexdigest(), mac)
            if not ok:
                self.send({"t": "rechazado", "why": "prueba"})
                self.close()
                return
            self._enter(None)
        elif t == "codigo":
            if str(msg.get("code", "")) == srv.pin and srv.pin:
                token = secrets.token_hex(32)
                srv.remember(self.dev, self.name, token, self.transport)
                srv.new_pin()
                self._enter(token)
            else:
                self.tries += 1
                if self.tries >= MAX_PIN_TRIES:
                    srv.new_pin()
                    self.send({"t": "rechazado", "why": "codigo"})
                    self.close()
                else:
                    self.send({"t": "aviso", "text": "Código incorrecto", "bad": True,
                               "code_wrong": True, "left": MAX_PIN_TRIES - self.tries})

    def _enter(self, token):
        self.authed = True
        srv = self.server
        srv.touch(self.dev, self.transport)
        hello = {"t": "bienvenido", "pc": srv.pc_id(), "name": srv.name()}
        if token:
            hello["token"] = token
        self.nonce = ""
        self.send(hello)
        self.send(srv.state())
        self.send(srv.library())
        th = srv.theme_msg()
        if th:
            self.send(th)
        srv._changed("devices")

    # ------------------------------------------------------------ mensajes
    def _m_ping(self, msg):
        self.send({"t": "pong", "n": msg.get("n")})

    def _m_pedir(self, msg):
        what = msg.get("what")
        if what == "estado":
            self.send(self.server.state())
        elif what == "biblioteca":
            self.send(self.server.library())

    def _m_tecla(self, msg):
        kid = str(msg.get("key", ""))
        down = bool(msg.get("down"))
        if down:
            self.held.add(kid)
        else:
            self.held.discard(kid)
        self.server.engine.remote_key(kid, down)
        if down:
            from .keys import key_label
            self.server._log(f"{self.name}: {key_label(kid)}")

    def _m_banco(self, msg):
        self.server.engine.set_bank(int(msg.get("i", 0)))

    def _m_detener(self, _msg):
        if self.server.board:
            self.server.board.stop_all()

    def _m_volumen(self, msg):
        v = min(2.0, max(0.0, float(msg.get("v", 1.0))))
        with self.server.engine.lock:
            self.server.cfg["audio"]["volume"] = v
        self.server._changed("volume", v)
        self.server.broadcast(self.server.state(), skip=self)

    def _m_escuchar(self, msg):
        path = self.server.path_of(str(msg.get("lib", "")))
        if path:
            self.server.engine.preview(path)

    def _m_botones(self, _msg):
        """Antes se podía elegir cuántas teclas virtuales había; ahora son siempre 30."""
        self.send(self.server.state())

    def _m_asignar(self, msg):
        err = self.server.assign(msg.get("layer"), str(msg.get("key", "")), msg.get("act"))
        if err:
            self.send({"t": "aviso", "text": err, "bad": True})

    def _m_subir_ini(self, msg):
        if self.upload:
            self.upload.abort()
            self.upload = None
        size = int(msg.get("size", 0))
        name = clean_name(msg.get("name", "sonido"))
        if not name.lower().endswith(AUDIO_EXT):
            self.send({"t": "subida", "ok": False,
                       "why": "Formato no compatible (usa MP3, WAV, OGG, OPUS o FLAC)"})
            return
        if size <= 0 or size > MAX_UPLOAD:
            self.send({"t": "subida", "ok": False, "why": "El archivo pesa más de 50 MB"})
            return
        folder = self.server.upload_dir()
        os.makedirs(folder, exist_ok=True)
        stem, ext = os.path.splitext(name)
        path = os.path.join(folder, name)
        n = 2
        while os.path.exists(path):
            path = os.path.join(folder, f"{stem} ({n}){ext}")
            n += 1
        title = str(msg.get("title") or stem).strip()[:80] or stem
        self.upload = _Upload(path, size, title)
        self.send({"t": "subida", "ok": True, "recibido": 0})

    def _m_subir_parte(self, msg):
        up = self.upload
        if not up:
            self.send({"t": "subida", "ok": False, "why": "No hay ninguna subida en curso"})
            return
        data = base64.b64decode(str(msg.get("data", "")), validate=False)
        if up.got + len(data) > up.size or len(data) > 256 * 1024:
            up.abort()
            self.upload = None
            self.send({"t": "subida", "ok": False, "why": "El archivo llegó más grande de lo anunciado"})
            return
        up.f.write(data)
        up.sha.update(data)
        up.got += len(data)
        self.send({"t": "subida", "ok": True, "recibido": up.got})

    def _m_subir_fin(self, msg):
        up = self.upload
        self.upload = None
        if not up:
            self.send({"t": "subida", "ok": False, "why": "No hay ninguna subida en curso"})
            return
        up.f.close()
        want = str(msg.get("sha256", "")).lower()
        if up.got != up.size or (want and want != up.sha.hexdigest()):
            up.abort()
            self.send({"t": "subida", "ok": False, "why": "El archivo llegó incompleto, vuelve a intentarlo"})
            return
        os.replace(up.tmp, up.path)
        lid = self.server.add_to_library(up.path, up.title)
        assign = msg.get("assign")
        if isinstance(assign, dict):
            act = dict(assign.get("act") or {"type": "file", "mode": "overlap", "volume": 1.0})
            act["type"] = "file"
            act["lib"] = lid
            err = self.server.assign(assign.get("layer"), str(assign.get("key", "")), act)
            if err:
                self.send({"t": "aviso", "text": err, "bad": True})
        self.send({"t": "subida", "ok": True, "fin": True, "lib": lid, "title": up.title})
        self.server._log(f"{self.name} subió «{up.title}»")


class RemoteServer:
    """Servidor para la app del celular."""

    def __init__(self, cfg: dict, engine, board=None, notify=None, save=None, upload_dir=None):
        self.cfg = cfg
        self.engine = engine
        self.board = board
        self.notify = notify or (lambda *a: None)       # avisos hacia la ventana
        self.save = save or (lambda: None)
        self._upload_dir = upload_dir
        self.sessions: list[Session] = []
        self.lock = threading.RLock()
        self.pin = ""
        self.new_pin()
        self.running = False
        self.errors: dict[str, str] = {}               # camino -> por qué no funciona
        self.log: list[str] = []
        self._socks = []
        self._bt = None
        settings(cfg)

    # ------------------------------------------------------------ datos
    def enabled(self) -> bool:
        return bool(settings(self.cfg).get("enabled", True))

    def pc_id(self) -> str:
        return settings(self.cfg)["pc_id"]

    def name(self) -> str:
        return pc_name(self.cfg)

    def new_pin(self):
        self.pin = f"{secrets.randbelow(10000):04d}"
        self._changed("pin", self.pin)

    def upload_dir(self) -> str:
        if self._upload_dir:
            return self._upload_dir
        from .config import config_dir
        return os.path.join(config_dir(), "Sonidos del celular")

    def find_device(self, dev: str):
        if not dev:
            return None
        for d in settings(self.cfg)["devices"]:
            if d.get("id") == dev:
                return d
        return None

    def remember(self, dev, name, token, transport):
        with self.engine.lock:
            devs = settings(self.cfg)["devices"]
            devs[:] = [d for d in devs if d.get("id") != dev]
            devs.append({"id": dev, "name": name, "token": token, "transport": transport,
                         "last": time.time()})
        self.save()
        self._log(f"Se vinculó {name}")

    def touch(self, dev, transport):
        d = self.find_device(dev)
        if d:
            with self.engine.lock:
                d["last"] = time.time()
                d["transport"] = transport
            self.save()

    def forget(self, dev):
        with self.engine.lock:
            devs = settings(self.cfg)["devices"]
            devs[:] = [d for d in devs if d.get("id") != dev]
        self.save()
        for s in list(self.sessions):
            if s.dev == dev:
                s.send({"t": "rechazado", "why": "olvidado"})
                s.close()
        self._changed("devices")

    # ------------------------------------------------------------ estado
    def _act_out(self, act):
        if not act or act.get("type", "none") == "none":
            return None
        t = act["type"]
        out = {"type": t}
        if t == "file":
            from .soundboard import title_of
            out.update(title=act.get("title") or title_of(act.get("path", "")),
                       mode=act.get("mode", "overlap"), volume=float(act.get("volume", 1.0)),
                       lib=lib_id(act.get("path", "")) if act.get("path") else "")
        elif t == "keys":
            out["combo"] = act.get("combo", "")
        elif t == "bank_go":
            out["bank"] = int(act.get("bank", 1))
        if "color" in act:
            out["color"] = act["color"]
        return out

    def _layer_out(self, layer):
        out = {}
        for kid, act in layer.items():
            a = self._act_out(act)
            if a:
                out[kid] = a
        return out

    def state(self) -> dict:
        with self.engine.lock:
            cfg = self.cfg
            return {"t": "estado", "active": cfg["active_bank"],
                    "volume": float(cfg["audio"].get("volume", 1.0)),
                    "banks": [{"name": b["name"], "keys": self._layer_out(b["keys"])}
                              for b in cfg["banks"]],
                    "global": self._layer_out(cfg["global"]),
                    "keys": [[k, v[0], v[1], v[2], v[3], v[4]] for k, v in NUMPAD_LAYOUT.items()],
                    "groups": self._groups(),
                    "phone": {"count": phone_count(cfg), "only": bool(cfg.get("phone", {}).get("only")),
                              "counts": list(PHONE_COUNTS)},
                    "paused": not self.engine.active}

    def _groups(self):
        """Grupos de teclas que el celular puede mostrar: las teclas virtuales (solo
        ellas en el modo «solo celular»), el numpad y la fila de números."""
        n = phone_count(self.cfg)
        cel = {"id": "celular", "name": "Virtuales", "cols": VIRTUAL_COLS, "rows": VIRTUAL_ROWS,
               "keys": [[k, v[0], v[1], v[2], 1, 1] for k, v in phone_layout(n).items()]}
        if self.cfg.get("phone", {}).get("only"):
            return [cel]
        g = [cel, {"id": "numpad", "name": "Numpad", "cols": 4, "rows": 5,
              "keys": [[k, v[0], v[1], v[2], v[3], v[4]] for k, v in NUMPAD_LAYOUT.items()]}]
        if self.cfg.get("row_mode", {}).get("enabled", True):
            g.append({"id": "fila", "name": "Fila 1–0", "cols": 6, "rows": 2,
                      "keys": [[k, v[0], v[1], v[2], 1, 1] for k, v in ROW_LAYOUT.items()]})
        return g

    def library(self) -> dict:
        with self.engine.lock:
            items = [{"lib": lib_id(x["path"]), "title": x.get("title") or os.path.basename(x["path"]),
                      "lufs": x.get("lufs")} for x in self.cfg.get("library", [])]
        return {"t": "biblioteca", "items": items}

    def path_of(self, lid: str):
        with self.engine.lock:
            for x in self.cfg.get("library", []):
                if lib_id(x["path"]) == lid:
                    return x["path"]
        return None

    def add_to_library(self, path, title) -> str:
        from .library import add
        with self.engine.lock:
            add(self.cfg, [path], title)
        self.save()
        self._changed("library")
        self.broadcast(self.library())
        return lib_id(path)

    def assign(self, layer, kid, act):
        """Cambia una tecla desde el celular. Devuelve un mensaje de error o None."""
        if kid not in NUMPAD_LAYOUT and kid not in ROW_LAYOUT \
                and kid not in PHONE_IDS and kid not in self.cfg.get("extra_keys", []):
            return "Esa tecla no existe"
        with self.engine.lock:
            if layer == "global":
                target = self.cfg["global"]
            else:
                try:
                    target = self.cfg["banks"][int(layer)]["keys"]
                except (TypeError, ValueError, IndexError):
                    return "Ese banco ya no existe"
            if not act:
                target.pop(kid, None)
            else:
                t = act.get("type")
                if t not in ACT_TYPES:
                    return "Acción desconocida"
                new = {"type": t}
                if t == "file":
                    path = self.path_of(str(act.get("lib", "")))
                    if not path:
                        return "Ese sonido ya no está en la biblioteca del PC"
                    from .soundboard import title_of
                    old = target.get(kid) or {}
                    title = next((x.get("title") for x in self.cfg.get("library", [])
                                  if x["path"] == path), None) or title_of(path)
                    mode = act.get("mode", "overlap")
                    new.update(path=path, title=title,
                               mode=mode if mode in MODES else "overlap",
                               volume=min(2.0, max(0.0, float(act.get("volume", 1.0)))),
                               speakers=old.get("speakers", True), mic=old.get("mic", True))
                elif t == "keys":
                    from .keys import parse_combo
                    combo = str(act.get("combo", "")).lower()
                    try:
                        parse_combo(combo)
                    except ValueError as e:
                        return f"Atajo no válido: {e}"
                    new["combo"] = combo
                elif t == "bank_go":
                    new["bank"] = max(1, int(act.get("bank", 1)))
                if isinstance(act.get("color"), int) and 0 <= act["color"] < len(BUTTON_COLORS):
                    new["color"] = act["color"]
                target[kid] = new
        self.save()
        self._changed("keys", layer, kid)
        self.broadcast(self.state())
        return None

    # ------------------------------------------------------------ envío a todos
    def broadcast(self, obj, skip=None):
        for s in list(self.sessions):
            if s.authed and s is not skip:
                s.send(obj)

    def state_changed(self):
        """La ventana cambió bancos/teclas/volumen: avisar a los celulares."""
        self.broadcast(self.state())

    def theme_msg(self):
        """Tema del PC para el celular (si está activada la opción)."""
        sel = self.cfg.get("theme") or {}
        if not sel.get("phone", True):
            return None
        from . import themes
        th = themes.current(self.cfg)
        return {"t": "tema", "nombre": th["name"], "colores": th["colors"]}

    def theme_changed(self):
        msg = self.theme_msg() or {"t": "tema", "nombre": "", "colores": {}}
        self.broadcast(msg)

    def library_changed(self):
        self.broadcast(self.library())

    def connected(self) -> list[Session]:
        return [s for s in self.sessions if s.authed and not s.closed]

    # ------------------------------------------------------------ hilos
    def start(self):
        if self.running:
            return
        self.running = True
        self.errors = {}
        port = int(settings(self.cfg).get("port", TCP_PORT))
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("0.0.0.0", port))
            srv.listen(8)
            self._socks.append(srv)
            threading.Thread(target=self._accept, args=(srv, "wifi"), name="celular-tcp",
                             daemon=True).start()
        except OSError as e:
            self.errors["wifi"] = f"No pude abrir el puerto {port}: {e}"
        try:
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            udp.bind(("0.0.0.0", UDP_PORT))
            self._socks.append(udp)
            threading.Thread(target=self._discovery, args=(udp,), name="celular-udp",
                             daemon=True).start()
        except OSError as e:
            self.errors["descubrir"] = f"No pude abrir el puerto {UDP_PORT}: {e}"
        if settings(self.cfg).get("bluetooth", True):
            try:
                from .remote_bt import start_bluetooth
                self._bt = start_bluetooth(self._bt_client)
            except Exception as e:
                self._bt = None
                self.errors["bluetooth"] = str(e)
        threading.Thread(target=self._playing_loop, name="celular-sonando", daemon=True).start()
        self._changed("server")

    def stop(self):
        self.running = False
        for s in self._socks:
            try:
                s.close()
            except OSError:
                pass
        self._socks = []
        if self._bt:
            try:
                self._bt.close()
            except Exception:
                pass
            self._bt = None
        for s in list(self.sessions):
            s.close()
        self.sessions = []
        self._changed("server")

    def _accept(self, srv, transport):
        while self.running:
            try:
                sock, addr = srv.accept()
            except OSError:
                return
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            tr = "usb" if _looks_usb(addr[0]) else transport
            self._start_session(sock, tr, addr[0])

    def _bt_client(self, sock, addr):
        self._start_session(sock, "bluetooth", addr)

    def _start_session(self, sock, transport, addr):
        s = Session(self, sock, transport, addr)
        with self.lock:
            self.sessions.append(s)
        threading.Thread(target=s.run, name="celular", daemon=True).start()

    def _gone(self, s):
        with self.lock:
            if s in self.sessions:
                self.sessions.remove(s)
        if s.upload:
            s.upload.abort()
        for kid in list(s.held):            # suelta lo que quedó apretado
            self.engine.remote_key(kid, False)
        if s.authed:
            self._log(f"{s.name} se desconectó")
            self._changed("devices")

    def _discovery(self, udp):
        while self.running:
            try:
                data, addr = udp.recvfrom(2048)
            except OSError:
                return
            if not self.enabled():
                continue
            try:
                msg = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                continue
            if not isinstance(msg, dict) or msg.get("t") != "descubrir":
                continue
            reply = {"t": "pc", "v": PROTO, "id": self.pc_id(), "name": self.name(),
                     "port": int(settings(self.cfg).get("port", TCP_PORT)), "app": __version__,
                     "os": {"win32": "windows", "darwin": "mac"}.get(sys.platform, "linux")}
            try:
                udp.sendto(json.dumps(reply).encode("utf-8"), addr)
            except OSError:
                pass

    def _playing_loop(self):
        idle_sent = True
        while self.running:
            time.sleep(0.1)
            if not self.connected() or not self.board:
                continue
            try:
                prog = self.board.progress()
            except Exception:
                prog = {}
            keys = {}
            for tag, p in prog.items():
                kid = str(tag).split("|", 1)[0]
                if kid in NUMPAD_LAYOUT or kid in ROW_LAYOUT \
                        or kid in PHONE_IDS or kid in self.cfg.get("extra_keys", []):
                    keys[kid] = round(max(keys.get(kid, 0.0), p), 3)
            if not keys and idle_sent:
                continue
            level = None
            try:
                lv = (self.board.levels() or {}).get("spk")
                if lv and lv[1] > -100:
                    level = round(lv[1], 1)
            except Exception:
                pass
            self.broadcast({"t": "sonando", "keys": keys, "level": level})
            idle_sent = not keys

    # ------------------------------------------------------------ avisos a la ventana
    def _log(self, text):
        self.log.append(time.strftime("%H:%M ") + text)
        del self.log[:-50]
        self._changed("log")

    def _changed(self, *what):
        try:
            self.notify(*what)
        except Exception:
            pass


def _looks_usb(ip: str) -> bool:
    """Las redes de «Compartir conexión por USB» de Android suelen ser 192.168.42.x
    (y en Samsung/otros 192.168.4x.x o 10.x de interfaces rndis/usb/ncm)."""
    if ip.startswith("192.168.42.") or ip.startswith("192.168.44."):
        return True
    try:
        if sys.platform.startswith("linux"):
            import subprocess
            out = subprocess.run(["ip", "-o", "route", "get", ip], capture_output=True, text=True,
                                 timeout=1).stdout
            m = re.search(r"\bdev (\S+)", out)
            if m and re.match(r"(usb|rndis|enx|ncm|enp\S*u\d)", m.group(1)):
                return True
    except Exception:
        pass
    return False
