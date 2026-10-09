# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Captura en Linux con evdev.

El numpad se toma en exclusiva con EVIOCGRAB: sus teclas llegan solo a este
programa y el resto del sistema no las ve.

Los demás teclados solo se leen (sin bloquear nada) para detectar la
combinación del modo macros. Mientras el modo macros está activo se toman
también, y todas sus teclas se reenvían al sistema por el teclado virtual,
salvo la fila de números (1–0, - y =). El cambio se hace cuando no hay
ninguna tecla apretada, para que nada quede pegado.
En pausa se suelta el grab y el numpad vuelve a funcionar normal; al cerrar
el programa el kernel lo suelta solo.
"""
import errno
import os
import select
import threading
import time

from .capture import BackendError
from .keys import evdev_kid

OWN_PREFIX = "Numpad Macros"


def device_id(dev) -> str:
    return f"{dev.info.vendor:04x}:{dev.info.product:04x}:{dev.name}"


class EvdevBackend:
    name = "evdev"
    learns_device = True

    def __init__(self, engine, device: str = ""):
        try:
            import evdev  # noqa: F401
        except ImportError:
            raise BackendError("Falta el módulo «evdev» (instálalo con: pip install evdev, "
                               "o el paquete python-evdev de tu distribución)")
        self.engine = engine
        self.device = device
        self.learning_until = 0.0
        self.devs = {}            # ruta -> InputDevice abiertos
        self.grabbed = set()      # numpads tomados en exclusiva
        self.main_grabbed = set() # teclados principales tomados (modo macros)
        self.held = {}            # ruta -> teclas apretadas en ese teclado
        self._running = False
        self._thread = None
        self._force_scan = True
        self._warned_grab = False

    # -------------------------------------------------- API
    def start(self):
        import evdev
        paths = evdev.list_devices()
        if not paths:
            if os.path.isdir("/dev/input") and any(n.startswith("event") for n in os.listdir("/dev/input")):
                raise BackendError("falta dar permisos para leer el numpad "
                                   "(pestaña «Numpad y opciones» → «Dar permisos…»)")
            raise BackendError("No se encontraron dispositivos de entrada")
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="evdev", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def learn_device(self, seconds=15):
        self.learning_until = time.monotonic() + seconds
        self._force_scan = True

    def set_device(self, dev_id: str):
        self.device = dev_id
        self._force_scan = True

    def connected(self) -> bool:
        return any(self._matches(d) for d in self.devs.values())

    # -------------------------------------------------- interno
    def _matches(self, dev) -> bool:
        return bool(self.device) and device_id(dev) == self.device

    @staticmethod
    def _is_keyboard(dev) -> bool:
        from evdev import ecodes as e
        if dev.name.startswith(OWN_PREFIX):
            return False
        keys = dev.capabilities().get(e.EV_KEY, [])
        return e.KEY_KP0 in keys or e.KEY_A in keys or e.KEY_1 in keys

    def _scan(self, learning: bool):
        import evdev
        present = set(evdev.list_devices())
        for path in list(self.devs):
            if path not in present:
                self._close(path)
        for path in present:
            if path in self.devs:
                continue
            try:
                dev = evdev.InputDevice(path)
            except OSError:
                continue
            try:
                if self._is_keyboard(dev) and (learning or self._matches(dev)
                                               or self.engine.row_enabled()):
                    self.devs[path] = dev
                    continue
            except OSError:
                pass
            dev.close()
        # Fuera del modo aprendizaje solo quedan abiertos el numpad elegido y,
        # si se usa la fila de números, los demás teclados
        if not learning and not self.engine.row_enabled():
            for path, dev in list(self.devs.items()):
                if not self._matches(dev):
                    self._close(path)
        state = self.connected()
        if state != getattr(self, "_last_state", None):
            self._last_state = state
            self.engine.events.put(("device_state", state))

    def _close(self, path):
        dev = self.devs.pop(path, None)
        self.grabbed.discard(path)
        self.main_grabbed.discard(path)
        self.held.pop(path, None)
        if dev:
            try:
                dev.close()
            except OSError:
                pass

    def _sync_main(self, path, dev, want: bool):
        """Toma o suelta un teclado principal, solo si no tiene teclas apretadas."""
        if self.held.get(path) or want == (path in self.main_grabbed):
            return
        try:
            if want:
                dev.grab()
                self.main_grabbed.add(path)
            else:
                dev.ungrab()
                self.main_grabbed.discard(path)
        except OSError as ex:
            self.main_grabbed.discard(path)
            if want and not getattr(self, "_warned_main", False):
                self._warned_main = True
                self.engine.events.put(("error", "No se pudo tomar el teclado principal "
                                        f"({ex}); la fila de números también escribirá números"))

    def _sync_grab(self, learning: bool):
        want = self.engine.active and not learning
        want_main = want and self.engine.row_mode
        for path, dev in self.devs.items():
            if not self._matches(dev):
                self._sync_main(path, dev, want_main)
                continue
            if want and path not in self.grabbed:
                try:
                    dev.grab()
                    self.grabbed.add(path)
                except OSError as ex:
                    if not self._warned_grab:
                        self._warned_grab = True
                        msg = ("Otro programa ya tiene tomado el numpad"
                               if ex.errno == errno.EBUSY else f"No se pudo tomar el numpad: {ex}")
                        self.engine.events.put(("error", msg))
            elif not want and path in self.grabbed:
                try:
                    dev.ungrab()
                except OSError:
                    pass
                self.grabbed.discard(path)
                self.engine.release_all()

    def _loop(self):
        from evdev import ecodes as e
        from .send_linux import emit
        next_scan = 0.0
        was_learning = False
        try:
            while self._running:
                now = time.monotonic()
                learning = now < self.learning_until
                if learning != was_learning:
                    if was_learning:
                        self.engine.events.put(("device_timeout",))
                    was_learning = learning
                    self._force_scan = True
                if self._force_scan or now >= next_scan:
                    self._force_scan = False
                    self._scan(learning)
                    next_scan = now + 2.0
                self._sync_grab(learning)
                if not self.devs:
                    time.sleep(0.2)
                    continue
                fds = {dev.fd: (path, dev) for path, dev in self.devs.items()}
                try:
                    ready, _, _ = select.select(list(fds), [], [], 0.2)
                except (OSError, ValueError):
                    self._force_scan = True
                    continue
                for fd in ready:
                    path, dev = fds[fd]
                    try:
                        events = list(dev.read())
                    except OSError:                       # desconectado
                        self._close(path)
                        self._force_scan = True
                        continue
                    is_pad = self._matches(dev)
                    for ev in events:
                        if ev.type != e.EV_KEY:
                            continue
                        held = self.held.setdefault(path, set())
                        if ev.value == 1:
                            held.add(ev.code)
                        elif ev.value == 0:
                            held.discard(ev.code)
                        if learning and ev.value == 1:
                            self.device = device_id(dev)
                            self.learning_until = 0
                            was_learning = False
                            learning = False
                            self._force_scan = True
                            self.engine.events.put(("device", self.device))
                            continue
                        down = ev.value != 0              # 1 = presionar, 2 = repetición
                        if not learning and not is_pad:
                            # teclado principal
                            consumed = self.engine.main_key(evdev_kid(ev.code), down)
                            if path in self.main_grabbed and not consumed:
                                try:
                                    emit(ev.code, ev.value)
                                except Exception as ex:
                                    self.engine.events.put(("error", str(ex)))
                            continue
                        if learning or path not in self.grabbed:
                            continue                      # el sistema ya recibió la tecla
                        if not self.engine.decide(evdev_kid(ev.code), down):
                            try:
                                emit(ev.code, ev.value)   # devolverla al sistema
                            except Exception as ex:
                                self.engine.events.put(("error", str(ex)))
        except Exception as ex:
            self.engine.events.put(("error", f"La captura se detuvo: {ex}"))
        finally:
            for path in list(self.devs):
                dev = self.devs.get(path)
                if (path in self.grabbed or path in self.main_grabbed) and dev:
                    try:
                        dev.ungrab()
                    except OSError:
                        pass
                self._close(path)
            self.engine.release_all()
