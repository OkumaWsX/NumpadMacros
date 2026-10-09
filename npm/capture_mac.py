# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Captura en macOS con IOKit (IOHIDManager), usando ctypes.

El numpad elegido se abre con kIOHIDOptionsTypeSeizeDevice: sus teclas llegan
solo a este programa. En pausa se vuelve a abrir sin exclusividad y macOS lo
usa normal. Necesita permiso de "Monitoreo de entrada" (y de "Accesibilidad"
para enviar atajos) para la app que ejecuta Python.
"""
import ctypes
import ctypes.util
import threading
import time

from .capture import BackendError
from .keys import hid_kid

c_void_p, c_int32, c_uint32, c_long, c_bool = (ctypes.c_void_p, ctypes.c_int32,
                                               ctypes.c_uint32, ctypes.c_long, ctypes.c_bool)
UTF8 = 0x08000100
kCFNumberSInt32Type = 3
SEIZE = 0x01
ERRORS = {
    0xE00002E2: "macOS no dio permiso. Ve a Ajustes del Sistema → Privacidad y seguridad → "
                "Monitoreo de entrada y activa la app desde la que abres el programa (Terminal o Python). "
                "Si sigue fallando, macOS puede exigir abrirlo como administrador (sudo).",
    0xE00002C5: "Otro programa tiene el numpad en uso exclusivo (¿Karabiner-Elements?).",
}

_cf = _io = None
CALLBACK = ctypes.CFUNCTYPE(None, c_void_p, c_int32, c_void_p, c_void_p)
# CGEventTap: recibe las teclas de todos los teclados (fila de números / modo macros)
TAP_CALLBACK = ctypes.CFUNCTYPE(c_void_p, c_void_p, c_uint32, c_void_p, c_void_p)
_cg = None


def _cg_lib():
    global _cg
    if _cg is None:
        cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("ApplicationServices"))
        cg.CGEventTapCreate.argtypes = [c_uint32, c_uint32, c_uint32, ctypes.c_uint64,
                                        TAP_CALLBACK, c_void_p]
        cg.CGEventTapCreate.restype = c_void_p
        cg.CGEventTapEnable.argtypes = [c_void_p, c_bool]
        cg.CGEventGetIntegerValueField.argtypes = [c_void_p, c_uint32]
        cg.CGEventGetIntegerValueField.restype = ctypes.c_int64
        cg.CGEventGetFlags.argtypes = [c_void_p]
        cg.CGEventGetFlags.restype = ctypes.c_uint64
        cg.CFMachPortCreateRunLoopSource.argtypes = [c_void_p, c_void_p, c_long]
        cg.CFMachPortCreateRunLoopSource.restype = c_void_p
        cg.CFRunLoopAddSource.argtypes = [c_void_p, c_void_p, c_void_p]
        cg.CFRunLoopRemoveSource.argtypes = [c_void_p, c_void_p, c_void_p]
        cg.CFMachPortInvalidate.argtypes = [c_void_p]
        cg.CFRelease.argtypes = [c_void_p]
        _cg = cg
    return _cg


def _libs():
    global _cf, _io
    if _cf is not None:
        return _cf, _io
    cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
    io = ctypes.cdll.LoadLibrary(ctypes.util.find_library("IOKit"))
    cf.CFStringCreateWithCString.argtypes = [c_void_p, ctypes.c_char_p, c_uint32]
    cf.CFStringCreateWithCString.restype = c_void_p
    cf.CFStringGetCString.argtypes = [c_void_p, ctypes.c_char_p, c_long, c_uint32]
    cf.CFStringGetCString.restype = c_bool
    cf.CFNumberCreate.argtypes = [c_void_p, ctypes.c_int, c_void_p]
    cf.CFNumberCreate.restype = c_void_p
    cf.CFNumberGetValue.argtypes = [c_void_p, ctypes.c_int, c_void_p]
    cf.CFNumberGetValue.restype = c_bool
    cf.CFGetTypeID.argtypes = [c_void_p]
    cf.CFGetTypeID.restype = c_long
    cf.CFStringGetTypeID.restype = c_long
    cf.CFNumberGetTypeID.restype = c_long
    cf.CFDictionaryCreateMutable.argtypes = [c_void_p, c_long, c_void_p, c_void_p]
    cf.CFDictionaryCreateMutable.restype = c_void_p
    cf.CFDictionarySetValue.argtypes = [c_void_p, c_void_p, c_void_p]
    cf.CFRelease.argtypes = [c_void_p]
    cf.CFSetGetCount.argtypes = [c_void_p]
    cf.CFSetGetCount.restype = c_long
    cf.CFRunLoopGetCurrent.restype = c_void_p
    cf.CFRunLoopRunInMode.argtypes = [c_void_p, ctypes.c_double, c_bool]
    cf.CFRunLoopRunInMode.restype = c_int32

    io.IOHIDManagerCreate.argtypes = [c_void_p, c_uint32]
    io.IOHIDManagerCreate.restype = c_void_p
    io.IOHIDManagerSetDeviceMatching.argtypes = [c_void_p, c_void_p]
    io.IOHIDManagerRegisterInputValueCallback.argtypes = [c_void_p, CALLBACK, c_void_p]
    io.IOHIDManagerScheduleWithRunLoop.argtypes = [c_void_p, c_void_p, c_void_p]
    io.IOHIDManagerUnscheduleFromRunLoop.argtypes = [c_void_p, c_void_p, c_void_p]
    io.IOHIDManagerOpen.argtypes = [c_void_p, c_uint32]
    io.IOHIDManagerOpen.restype = c_int32
    io.IOHIDManagerClose.argtypes = [c_void_p, c_uint32]
    io.IOHIDManagerClose.restype = c_int32
    io.IOHIDManagerCopyDevices.argtypes = [c_void_p]
    io.IOHIDManagerCopyDevices.restype = c_void_p
    io.IOHIDValueGetElement.argtypes = [c_void_p]
    io.IOHIDValueGetElement.restype = c_void_p
    io.IOHIDValueGetIntegerValue.argtypes = [c_void_p]
    io.IOHIDValueGetIntegerValue.restype = c_long
    io.IOHIDElementGetUsagePage.argtypes = [c_void_p]
    io.IOHIDElementGetUsagePage.restype = c_uint32
    io.IOHIDElementGetUsage.argtypes = [c_void_p]
    io.IOHIDElementGetUsage.restype = c_uint32
    io.IOHIDElementGetDevice.argtypes = [c_void_p]
    io.IOHIDElementGetDevice.restype = c_void_p
    io.IOHIDDeviceGetProperty.argtypes = [c_void_p, c_void_p]
    io.IOHIDDeviceGetProperty.restype = c_void_p
    _cf, _io = cf, io
    return cf, io


class IOKitBackend:
    name = "iokit"
    learns_device = True

    def __init__(self, engine, device: str = ""):
        try:
            self.cf, self.io = _libs()
        except OSError as e:
            raise BackendError(f"No se pudo cargar IOKit: {e}")
        self.engine = engine
        self.device = device
        self.learning_until = 0.0
        self._running = False
        self._thread = None
        self._mgr = None
        self._state = None          # (aprendiendo, exclusivo, dispositivo) del manager abierto
        self._seized = False
        self._cb = CALLBACK(self._on_value)
        self._tap_cb = TAP_CALLBACK(self._on_tap)
        self._tap = self._tap_src = None
        self._tap_warned = False
        self._cfstr = {}
        self._connected = False
        self._started = threading.Event()
        self._error = None

    # -------------------------------------------------- API
    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="iokit", daemon=True)
        self._thread.start()
        self._started.wait(3)
        if self._error:
            raise BackendError(self._error)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def learn_device(self, seconds=15):
        self.learning_until = time.monotonic() + seconds

    def set_device(self, dev_id: str):
        self.device = dev_id

    def connected(self) -> bool:
        return self._connected

    # -------------------------------------------------- CoreFoundation
    def _s(self, text: str):
        if text not in self._cfstr:
            self._cfstr[text] = self.cf.CFStringCreateWithCString(None, text.encode(), UTF8)
        return self._cfstr[text]

    def _num(self, value: int):
        v = c_int32(value)
        return self.cf.CFNumberCreate(None, kCFNumberSInt32Type, ctypes.byref(v))

    def _matching(self, learning: bool):
        cf = self.cf
        keycb = c_void_p.in_dll(cf, "kCFTypeDictionaryKeyCallBacks")
        valcb = c_void_p.in_dll(cf, "kCFTypeDictionaryValueCallBacks")
        d = cf.CFDictionaryCreateMutable(None, 0, ctypes.byref(keycb), ctypes.byref(valcb))
        pairs = [("DeviceUsagePage", 1), ("DeviceUsage", 6)]       # teclados
        if not learning:
            vid, pid = (int(x, 16) for x in self.device.split(":", 2)[:2])
            pairs += [("VendorID", vid), ("ProductID", pid)]
        for k, v in pairs:
            n = self._num(v)
            cf.CFDictionarySetValue(d, self._s(k), n)
            cf.CFRelease(n)
        return d

    def _prop_int(self, dev, key) -> int:
        ref = self.io.IOHIDDeviceGetProperty(dev, self._s(key))
        out = c_int32(0)
        if ref and self.cf.CFGetTypeID(ref) == self.cf.CFNumberGetTypeID():
            self.cf.CFNumberGetValue(ref, kCFNumberSInt32Type, ctypes.byref(out))
        return out.value

    def _prop_str(self, dev, key) -> str:
        ref = self.io.IOHIDDeviceGetProperty(dev, self._s(key))
        if ref and self.cf.CFGetTypeID(ref) == self.cf.CFStringGetTypeID():
            buf = ctypes.create_string_buffer(256)
            if self.cf.CFStringGetCString(ref, buf, 256, UTF8):
                return buf.value.decode("utf-8", "replace").replace(":", " ")
        return ""

    # -------------------------------------------------- manager
    def _close_mgr(self):
        if self._mgr:
            loop = self.cf.CFRunLoopGetCurrent()
            mode = c_void_p.in_dll(self.cf, "kCFRunLoopDefaultMode")
            self.io.IOHIDManagerUnscheduleFromRunLoop(self._mgr, loop, mode)
            self.io.IOHIDManagerClose(self._mgr, 0)
            self.cf.CFRelease(self._mgr)
        self._mgr = None
        self._seized = False

    def _open_mgr(self, learning: bool, seize: bool):
        self._close_mgr()
        if not learning and not self.device:
            return
        io, cf = self.io, self.cf
        try:
            d = self._matching(learning)
        except ValueError:
            self.engine.events.put(("error", "El numpad guardado no es válido; vuelve a detectarlo."))
            return
        mgr = io.IOHIDManagerCreate(None, 0)
        io.IOHIDManagerSetDeviceMatching(mgr, d)
        cf.CFRelease(d)
        io.IOHIDManagerRegisterInputValueCallback(mgr, self._cb, None)
        mode = c_void_p.in_dll(cf, "kCFRunLoopDefaultMode")
        io.IOHIDManagerScheduleWithRunLoop(mgr, cf.CFRunLoopGetCurrent(), mode)
        res = io.IOHIDManagerOpen(mgr, SEIZE if seize else 0) & 0xFFFFFFFF
        if res and seize:
            self.engine.events.put(("error", ERRORS.get(res, f"No se pudo tomar el numpad (IOKit 0x{res:08X})")))
            io.IOHIDManagerClose(mgr, 0)
            res = io.IOHIDManagerOpen(mgr, 0) & 0xFFFFFFFF
            seize = False
        if res:
            self.engine.events.put(("error", ERRORS.get(res, f"IOKit no abrió el teclado (0x{res:08X})")))
        self._mgr = mgr
        self._seized = seize and not res

    def _count(self) -> int:
        if not self._mgr:
            return 0
        s = self.io.IOHIDManagerCopyDevices(self._mgr)
        if not s:
            return 0
        n = self.cf.CFSetGetCount(s)
        self.cf.CFRelease(s)
        return n

    # -------------------------------------------------- eventos
    def _on_value(self, _ctx, _result, _sender, value):
        try:
            io = self.io
            el = io.IOHIDValueGetElement(value)
            if io.IOHIDElementGetUsagePage(el) != 0x07:
                return
            usage = io.IOHIDElementGetUsage(el)
            if usage < 0x04 or usage > 0xE7:
                return
            pressed = io.IOHIDValueGetIntegerValue(value) != 0
            if time.monotonic() < self.learning_until:
                if pressed:
                    dev = io.IOHIDElementGetDevice(el)
                    vid, pid = self._prop_int(dev, "VendorID"), self._prop_int(dev, "ProductID")
                    self.device = f"{vid:04x}:{pid:04x}:{self._prop_str(dev, 'Product')}"
                    self.learning_until = 0
                    self.engine.events.put(("device", self.device))
                return
            if not self._seized:
                return                    # en pausa: macOS ya recibió la tecla
            if not self.engine.decide(hid_kid(usage), pressed):
                from .send_mac import HID_TO_MAC, post_key
                code = HID_TO_MAC.get(usage)
                if code is not None:
                    post_key(code, pressed)
        except Exception as ex:          # nunca dejar que una excepción salte a IOKit
            self.engine.events.put(("error", str(ex)))

    # -------------------------------------------------- teclado principal (CGEventTap)
    def _on_tap(self, _proxy, etype, event, _ctx):
        try:
            cg = _cg_lib()
            if etype in (0xFFFFFFFE, 0xFFFFFFFF):        # macOS desactivó el tap: reactivar
                if self._tap:
                    cg.CGEventTapEnable(self._tap, True)
                return event
            from .send_mac import MAC_TO_KID, MARKER, USERDATA_FIELD, flags_to_mods
            if cg.CGEventGetIntegerValueField(event, USERDATA_FIELD) == MARKER:
                return event                              # evento enviado por la propia app
            kid = MAC_TO_KID.get(cg.CGEventGetIntegerValueField(event, 9))   # kCGKeyboardEventKeycode
            if kid is None:
                return event
            mods = flags_to_mods(cg.CGEventGetFlags(event))
            if self.engine.main_key(kid, etype == 10, mods):                 # 10 = KeyDown
                return None
        except Exception as ex:
            self.engine.events.put(("error", str(ex)))
        return event

    def _sync_tap(self):
        want = self.engine.row_enabled()
        if want == (self._tap is not None):
            return
        cg = _cg_lib()
        mode = c_void_p.in_dll(self.cf, "kCFRunLoopDefaultMode")
        loop = self.cf.CFRunLoopGetCurrent()
        if want:
            mask = (1 << 10) | (1 << 11)                  # KeyDown, KeyUp
            tap = cg.CGEventTapCreate(1, 0, 0, mask, self._tap_cb, None)   # sesión, al inicio, puede bloquear
            if not tap:
                if not self._tap_warned:
                    self._tap_warned = True
                    self.engine.events.put(("error", "Para usar la fila de números, activa Numpad Macros "
                                            "en Ajustes del Sistema → Privacidad y seguridad → Accesibilidad"))
                return
            self._tap = tap
            self._tap_src = cg.CFMachPortCreateRunLoopSource(None, tap, 0)
            cg.CFRunLoopAddSource(loop, self._tap_src, mode)
            cg.CGEventTapEnable(tap, True)
        else:
            cg.CGEventTapEnable(self._tap, False)
            cg.CFRunLoopRemoveSource(loop, self._tap_src, mode)
            cg.CFMachPortInvalidate(self._tap)
            cg.CFRelease(self._tap_src)
            cg.CFRelease(self._tap)
            self._tap = self._tap_src = None

    def _loop(self):
        self._started.set()
        next_check = 0.0
        was_learning = False
        try:
            while self._running:
                now = time.monotonic()
                learning = now < self.learning_until
                if was_learning and not learning and self.learning_until:
                    self.engine.events.put(("device_timeout",))
                    self.learning_until = 0
                was_learning = learning
                want = (learning, self.engine.active and not learning, self.device)
                if want != self._state:
                    self._state = want
                    self._open_mgr(learning, want[1])
                    if not want[1]:
                        self.engine.release_all()
                    next_check = 0
                if now >= next_check:
                    try:
                        self._sync_tap()
                    except Exception as ex:
                        self.engine.events.put(("error", f"Fila de números: {ex}"))
                    state = (not learning) and self._count() > 0
                    if state != self._connected:
                        self._connected = state
                        self.engine.events.put(("device_state", state))
                    next_check = now + 2.0
                mode = c_void_p.in_dll(self.cf, "kCFRunLoopDefaultMode")
                self.cf.CFRunLoopRunInMode(mode, 0.25, False)
        except Exception as ex:
            self.engine.events.put(("error", f"La captura se detuvo: {ex}"))
        finally:
            self._close_mgr()
            if self._tap is not None:
                try:
                    _cg_lib().CGEventTapEnable(self._tap, False)
                except Exception:
                    pass
            self.engine.release_all()
