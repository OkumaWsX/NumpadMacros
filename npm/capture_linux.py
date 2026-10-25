# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Captura en Linux con evdev.

El numpad se toma en exclusiva con EVIOCGRAB: sus teclas llegan solo a este
programa y el resto del sistema no las ve.

Los demás teclados también se toman (también en pausa), para que la
combinación que activa o pausa el modo macros no le llegue al programa que
está al frente. Cada teclado tomado tiene su copia virtual (uinput, con sus
mismas teclas y tipos de evento) y todo lo que llega se reenvía por ella,
salvo esa combinación y, con el modo macros activo, la fila de números
(1–0, - y =). Los dispositivos que además mueven un puntero (mouse, touchpad,
rueda: EV_REL / EV_ABS) nunca se toman, solo se leen, igual que todos si la
copia virtual no se puede crear: la combinación funciona, pero el programa
del frente también la recibe.
El cambio se hace cuando no hay ninguna tecla apretada, para que nada quede
pegado. En pausa se suelta el numpad y vuelve a funcionar normal; al cerrar
el programa el kernel suelta todo solo.
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
        self.main_grabbed = set() # teclados principales tomados
        self.fwd = {}             # ruta -> copia virtual (uinput) de ese teclado tomado
        self.fwd_down = {}        # ruta -> teclas reenviadas que siguen apretadas
        self._retry = {}          # ruta -> no volver a intentar tomarlo antes de este momento
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
        return any(self._matches(d) for d in list(self.devs.values()))   # el hilo de captura lo modifica

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
                                               or self.engine.main_wanted()):
                    self.devs[path] = dev
                    continue
            except OSError:
                pass
            dev.close()
        # Fuera del modo aprendizaje solo quedan abiertos el numpad elegido y,
        # si hay combinación del modo macros, los demás teclados
        if not learning and not self.engine.main_wanted():
            for path, dev in list(self.devs.items()):
                if not self._matches(dev):
                    self._close(path)
        state = self.connected()
        if state != getattr(self, "_last_state", None):
            self._last_state = state
            self.engine.events.put(("device_state", state))

    def _close(self, path):
        """Cerrar (o desconectado): lo que quedó apretado se suelta en el motor y en
        el sistema, para que no quede pegado (Ctrl, la combinación, una tecla de la fila)."""
        from .send_linux import emit
        dev = self.devs.get(path)
        is_pad = dev is not None and self._matches(dev)
        for code in sorted(self.held.get(path) or ()):
            kid = evdev_kid(code)
            try:
                if not is_pad:
                    self.engine.main_key(kid, False)
                elif path in self.grabbed and not self.engine.decide(kid, False):
                    emit(code, 0)                     # se había devuelto al sistema
            except Exception:
                pass
        self._drop_forward(path)
        self.devs.pop(path, None)
        self.grabbed.discard(path)
        self.main_grabbed.discard(path)
        self.held.pop(path, None)
        self._retry.pop(path, None)
        if dev:
            try:
                dev.close()
            except OSError:
                pass

    def _drop_forward(self, path):
        """Suelta en el sistema lo reenviado que sigue apretado y cierra la copia virtual."""
        ui = self.fwd.pop(path, None)
        down = self.fwd_down.pop(path, set())
        if not ui:
            return
        from evdev import ecodes as e
        try:
            for code in sorted(down):
                ui.write(e.EV_KEY, code, 0)
            if down:
                ui.syn()
        except Exception:
            pass
        try:
            ui.close()
        except Exception:
            pass

    def _forward(self, path, etype, code, value):
        """Reenviar un evento del teclado tomado por su copia virtual."""
        ui = self.fwd.get(path)
        if not ui:
            return
        from evdev import ecodes as e
        try:
            ui.write(etype, code, value)
        except Exception as ex:
            self.engine.events.put(("error", str(ex)))
            return
        if etype == e.EV_KEY:
            down = self.fwd_down.setdefault(path, set())
            (down.add if value else down.discard)(code)

    def _mask(self, path):
        """Toque de Ctrl entre medio, para que soltar Alt o Win no abra el menú del escritorio."""
        from evdev import ecodes as e
        ui = self.fwd.get(path)
        if not ui:
            return
        try:
            for v in (1, 0):
                ui.write(e.EV_KEY, e.KEY_LEFTCTRL, v)
                ui.syn()
        except Exception:
            pass

    @staticmethod
    def _points(dev) -> bool:
        """También mueve un puntero (mouse, touchpad, rueda): no se toma."""
        from evdev import ecodes as e
        caps = dev.capabilities()
        return e.EV_REL in caps or e.EV_ABS in caps

    def _warn_main(self, msg):
        if not getattr(self, "_warned_main", False):
            self._warned_main = True
            self.engine.events.put(("error", msg + ": la combinación del modo macros también le "
                                    "llegará al programa del frente"))

    def _sync_main(self, path, dev, want: bool):
        """Toma o suelta un teclado principal, solo si no tiene teclas apretadas."""
        if self.held.get(path) or want == (path in self.main_grabbed):
            return
        if not want:
            try:
                dev.ungrab()
            except OSError:
                pass
            self.main_grabbed.discard(path)
            self._drop_forward(path)
            return
        if time.monotonic() < self._retry.get(path, 0.0):
            return
        try:
            if self._points(dev):
                self._retry[path] = float("inf")           # nunca: solo se lee
                return
        except OSError:
            return
        from . import send_linux
        try:
            self.fwd[path] = send_linux.clone(dev)        # primero la copia: sin ella dejaría de escribir
        except Exception as ex:
            self._retry[path] = time.monotonic() + 5.0
            self._warn_main(f"Teclado virtual no disponible ({ex})")
            return
        try:
            dev.grab()
            self.main_grabbed.add(path)
        except OSError as ex:
            self._drop_forward(path)
            self._retry[path] = time.monotonic() + 5.0
            self._warn_main("Otro programa ya tiene tomado el teclado principal" if ex.errno == errno.EBUSY
                            else f"No se pudo tomar el teclado principal ({ex})")

    def _sync_grab(self, learning: bool):
        want = self.engine.active and not learning
        want_main = not learning and self.engine.main_wanted()
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
                            # teclado principal tomado: se reenvía todo lo demás (SYN, MSC, LED…)
                            if not is_pad and path in self.main_grabbed:
                                self._forward(path, ev.type, ev.code, ev.value)
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
                            mask, self.engine.mask_pending = self.engine.mask_pending, False
                            if path in self.main_grabbed:
                                if not consumed:
                                    self._forward(path, e.EV_KEY, ev.code, ev.value)
                                elif mask:
                                    self._mask(path)
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
