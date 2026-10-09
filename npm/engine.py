# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Motor: decide qué hacer con cada tecla del numpad.

`decide()` se llama desde el hilo de captura y debe responder al instante
(solo consulta diccionarios). Las acciones lentas (sonidos, enviar teclas)
se encolan y las ejecuta un hilo trabajador aparte.
"""
import queue
import threading
import time

from .keys import MOD_KIDS, ROW_IDS, parse_toggle

BANK_TYPES = ("bank_next", "bank_prev", "bank_go")


def needs_release(act) -> bool:
    """Acciones que también hacen algo al soltar la tecla."""
    if not act:
        return False
    return act["type"] == "keys" or (act["type"] == "file" and act.get("mode") == "hold")


class Engine:
    def __init__(self, cfg: dict, sender=None, on_save=None, soundboard=None):
        self.cfg = cfg
        self.soundboard = soundboard
        self.sender = sender
        self.on_save = on_save              # callback para persistir cambios
        self.lock = threading.RLock()
        self.active = True                  # False = pausado (numpad normal)
        self.capture_next = False           # la GUI espera "presiona una tecla"
        self.events: queue.Queue = queue.Queue()   # avisos hacia la GUI
        self._jobs: queue.Queue = queue.Queue()
        self._pressed: dict[str, dict | None] = {}  # teclas que consumimos
        self._passed: set[str] = set()              # teclas que dejamos pasar
        self.row_mode = False                       # modo macros de la fila de números
        self._mods_down: set[str] = set()           # modificadores apretados (ids)
        self._toggle_held = False
        self._toggle = None
        self._toggle_src = None
        self._worker = threading.Thread(target=self._work, name="acciones", daemon=True)
        self._worker.start()

    # ------------------------------------------------------------ estado
    @property
    def bank(self) -> int:
        return self.cfg["active_bank"]

    def set_bank(self, idx: int, notify=True):
        with self.lock:
            n = len(self.cfg["banks"])
            idx %= n
            if idx != self.cfg["active_bank"]:
                self.cfg["active_bank"] = idx
                if self.on_save:
                    self._jobs.put(("save",))
            if notify:
                self.events.put(("bank", idx, self.cfg["banks"][idx]["name"]))

    def set_active(self, value: bool):
        with self.lock:
            self.active = value
        self.events.put(("active", value))

    def resolve(self, kid: str):
        """Acción de la tecla: primero la capa Global, luego el banco activo."""
        act = self.cfg["global"].get(kid)
        if act and act.get("type", "none") != "none":
            return act
        act = self.cfg["banks"][self.cfg["active_bank"]]["keys"].get(kid)
        if act and act.get("type", "none") != "none":
            return act
        return None

    # ------------------------------------------------------------ fila de números
    def row_enabled(self) -> bool:
        return bool(self.cfg.get("row_mode", {}).get("enabled"))

    def set_row_mode(self, value: bool):
        with self.lock:
            self.row_mode = bool(value) and self.row_enabled()
        self.events.put(("row_mode", self.row_mode))

    def _parsed_toggle(self):
        src = self.cfg.get("row_mode", {}).get("toggle", "")
        if src != self._toggle_src:
            self._toggle_src = src
            try:
                self._toggle = parse_toggle(src)
            except ValueError:
                self._toggle = None
        return self._toggle

    def main_key(self, kid: str, down: bool, mods=None) -> bool:
        """Tecla del teclado principal. True = consumirla.

        Solo se consumen: la tecla de la combinación que activa el modo macros y,
        con el modo activo, las teclas de la fila de números (1–0, - y =).
        `mods` (conjunto de nombres) lo entrega macOS; en los demás sistemas los
        modificadores se siguen aquí mismo.
        """
        with self.lock:
            if kid in MOD_KIDS:
                if mods is None:
                    (self._mods_down.add if down else self._mods_down.discard)(kid)
                return False
            # una tecla de la fila que ya empezamos a manejar termina por el mismo camino
            if kid in self._pressed or kid in self._passed:
                return self.decide(kid, down)
            if not self.row_enabled():
                return False
            tog = self._parsed_toggle()
            if tog and kid == tog[1]:
                if not down:
                    if self._toggle_held:
                        self._toggle_held = False
                        return True
                    return False
                if self._toggle_held:                 # autorepetición
                    return True
                current = frozenset(mods) if mods is not None else \
                    frozenset(MOD_KIDS[k] for k in self._mods_down)
                if current == tog[0]:
                    self._toggle_held = True
                    self.set_row_mode(not self.row_mode)
                    return True
                return False
            if kid in ROW_IDS and down and self.row_mode:
                return self.decide(kid, True)
            return False

    # ------------------------------------------------------------ captura
    def decide(self, kid: str, down: bool) -> bool:
        """True = consumir la tecla (el sistema no la ve). False = dejarla pasar."""
        with self.lock:
            if down:
                if kid in self._pressed:          # autorepetición de una tecla nuestra
                    return True
                if kid in self._passed:           # autorepetición de una que dejamos pasar
                    return False
                if self.capture_next:
                    self.capture_next = False
                    self._pressed[kid] = None
                    self.events.put(("captured", kid))
                    return True
                if not self.active:
                    self._passed.add(kid)
                    return False
                act = self.resolve(kid)
                self.events.put(("key", kid, True))
                if act is None:
                    if self.cfg.get("block_unassigned", True):
                        self._pressed[kid] = None
                        return True
                    self._passed.add(kid)
                    return False
                self._pressed[kid] = act
                t = act["type"]
                if t in BANK_TYPES:
                    n = len(self.cfg["banks"])
                    if t == "bank_next":
                        self.set_bank(self.bank + 1)
                    elif t == "bank_prev":
                        self.set_bank(self.bank - 1)
                    else:
                        self.set_bank(min(max(int(act.get("bank", 1)) - 1, 0), n - 1))
                else:
                    self._jobs.put(("down", act, kid))
                return True
            # ---- soltar
            if kid in self._passed:
                self._passed.discard(kid)
                return False
            if kid in self._pressed:
                act = self._pressed.pop(kid)
                self.events.put(("key", kid, False))
                if needs_release(act):
                    self._jobs.put(("up", act, kid))
                return True
            return False   # se presionó antes de abrir el programa

    def release_all(self):
        """Suelta atajos y sonidos "mientras se mantiene" (al pausar o salir)."""
        with self.lock:
            held = [(k, a) for k, a in self._pressed.items() if needs_release(a)]
            self._pressed.clear()
            self._passed.clear()
        for kid, a in held:
            self._jobs.put(("up", a, kid))

    # ------------------------------------------------------------ acciones
    def run_action(self, act: dict, kid: str = "prueba"):
        """Probar una acción desde la ventana."""
        if act.get("type") == "keys":
            self._jobs.put(("down", act, kid))
            self._jobs.put(("up", act, kid))
        elif act.get("type") not in BANK_TYPES:
            act = dict(act, mode="restart") if act.get("mode") == "hold" else act
            self._jobs.put(("down", act, kid))

    def preview(self, path: str):
        """Escuchar un sonido solo por los audífonos (pestaña Sonidos)."""
        self._jobs.put(("down", {"type": "file", "path": path, "mic": False,
                                 "speakers": True, "mode": "restart"}, "vista-previa"))

    def stop(self):
        self.release_all()
        self._jobs.put(None)
        self._worker.join(timeout=2)

    def _work(self):
        while True:
            job = self._jobs.get()
            if job is None:
                return
            try:
                self._do(job)
            except Exception as e:  # nunca matar el hilo por un error puntual
                self.events.put(("error", str(e)))

    @staticmethod
    def _tag(act, kid):
        return f"{kid}|{act.get('path', '')}"

    def _do(self, job):
        if job[0] == "save":
            with self.lock:
                if self.on_save:
                    self.on_save()
            return
        kind, act, kid = job
        t = act["type"]
        if t == "file":
            if not self.soundboard:
                raise RuntimeError("La reproducción de audio no está disponible")
            tag = self._tag(act, kid)
            if kind == "up":
                self.soundboard.stop_tag(tag)
                return
            title = self.soundboard.play(act.get("path", ""), act.get("volume", 1.0),
                                         act.get("speakers", True), act.get("mic", True),
                                         tag=tag, mode=act.get("mode", "overlap"))
            self.events.put(("played", title) if title else ("stopped", act.get("title", "")))
        elif t == "sound_stop":
            if self.soundboard:
                self.soundboard.stop_all()
        elif t == "keys":
            if not self.sender:
                raise RuntimeError("Envío de teclas no disponible")
            if kind == "down":
                self.sender.press(act["combo"])
            else:
                self.sender.release(act["combo"])
                time.sleep(0.005)
