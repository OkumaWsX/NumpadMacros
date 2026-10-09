# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Captura de teclas en Windows.

InterceptionBackend: usa el driver Interception. Sabe de qué teclado viene cada
pulsación, así que solo intercepta el numpad elegido; los demás teclados ni
siquiera pasan por este programa.

HookBackend: sin driver. Usa un hook de teclado de bajo nivel y captura las
teclas numéricas de *cualquier* teclado.

En ambos casos, al cerrar el programa Windows vuelve a recibir todo normal.
"""
import ctypes
import os
import sys
import threading
import time

from .capture import BackendError
from .keys import NUMPAD_IDS, key_id


def _app_dirs():
    dirs = []
    if getattr(sys, "frozen", False):            # .exe hecho con PyInstaller
        dirs.append(os.path.dirname(sys.executable))
        dirs.append(getattr(sys, "_MEIPASS", ""))
    here = os.path.dirname(os.path.abspath(__file__))
    dirs += [os.path.dirname(here), here]
    out = []
    for d in dirs:
        if d:
            out += [d, os.path.join(d, "lib")]
    return out


def find_interception_dll():
    for d in _app_dirs():
        p = os.path.join(d, "interception.dll")
        if os.path.isfile(p):
            return p
    return None


# ====================================================================== Interception
class InterceptionBackend:
    name = "interception"
    learns_device = True
    MAX_KB = 10
    KEY_UP, KEY_E0, KEY_E1 = 0x01, 0x02, 0x04
    FILTER_ALL, FILTER_NONE = 0xFFFF, 0x0000

    def __init__(self, engine, hwid: str = ""):
        if sys.platform != "win32":
            raise BackendError("Interception solo existe en Windows")
        path = find_interception_dll()
        if not path:
            raise BackendError("No encuentro interception.dll junto al programa")
        dll = ctypes.CDLL(path)
        dll.interception_create_context.restype = ctypes.c_void_p
        dll.interception_destroy_context.argtypes = [ctypes.c_void_p]
        self.PRED = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int)
        dll.interception_set_filter.argtypes = [ctypes.c_void_p, self.PRED, ctypes.c_ushort]
        dll.interception_wait_with_timeout.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        dll.interception_wait_with_timeout.restype = ctypes.c_int
        dll.interception_receive.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
        dll.interception_send.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
        dll.interception_get_hardware_id.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
        dll.interception_get_hardware_id.restype = ctypes.c_uint
        dll.interception_is_keyboard.argtypes = [ctypes.c_int]
        self.dll = dll
        self.engine = engine
        self.hwid = hwid
        self.targets: set[int] = set()
        self.learning_until = 0.0
        self._running = False
        self._thread = None
        self._ctx = None
        self._filter_cb = None                   # referencia viva al callback
        self._started = threading.Event()
        self._start_error = None

    # -------------------------------------------------- API para la GUI
    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="interception", daemon=True)
        self._thread.start()
        self._started.wait(3)
        if self._start_error:
            raise BackendError(self._start_error)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def learn_device(self, seconds=15):
        """La próxima tecla que se presione en cualquier teclado define el numpad."""
        self.learning_until = time.monotonic() + seconds

    def set_device(self, hwid: str):
        self.hwid = hwid
        self._next_scan = 0

    def connected(self) -> bool:
        return bool(self.targets)

    # -------------------------------------------------- hilo de captura
    def _hw(self, dev: int) -> str:
        buf = ctypes.create_unicode_buffer(512)
        n = self.dll.interception_get_hardware_id(self._ctx, dev, buf, ctypes.sizeof(buf))
        return buf.value if n else ""

    def _apply_filter(self, devices: set[int]):
        ctx = self._ctx
        self._filter_cb = self.PRED(lambda d: 1 if 1 <= d <= self.MAX_KB else 0)
        self.dll.interception_set_filter(ctx, self._filter_cb, self.FILTER_NONE)
        if devices:
            self._filter_cb = self.PRED(lambda d: 1 if d in devices else 0)
            self.dll.interception_set_filter(ctx, self._filter_cb, self.FILTER_ALL)

    def _scan(self, learning: bool):
        found = set()
        if self.hwid:
            want = self.hwid.lower()
            for d in range(1, self.MAX_KB + 1):
                if self._hw(d).lower() == want:
                    found.add(d)
        # Con la fila de números activada también se reciben los demás teclados
        # (solo para la combinación del modo macros y las teclas 1–0, - y =)
        need_all = learning or self.engine.row_enabled()
        all_kb = {d for d in range(1, self.MAX_KB + 1) if self._hw(d)} if need_all else set()
        wanted = all_kb | found
        if found != self.targets or wanted != self._filtered:
            if found != self.targets:
                self.engine.events.put(("device_state", bool(found)))
            self.targets = found
            self._apply_filter(wanted)
            self._filtered = wanted

    def _loop(self):
        ctx = self.dll.interception_create_context()
        if not ctx:
            self._start_error = ("El driver Interception no está instalado "
                                 "(o falta reiniciar después de instalarlo)")
            self._started.set()
            return
        self._ctx = ctx
        self._filtered: set[int] = set()
        self._next_scan = 0
        self._started.set()
        stroke = ctypes.create_string_buffer(32)   # InterceptionStroke = 20 bytes
        was_learning = False
        try:
            while self._running:
                now = time.monotonic()
                learning = now < self.learning_until
                if learning != was_learning:
                    self._next_scan = 0
                    if was_learning and not learning:
                        self.engine.events.put(("device_timeout",))
                    was_learning = learning
                if now >= self._next_scan:
                    self._scan(learning)
                    self._next_scan = now + 2.0
                dev = self.dll.interception_wait_with_timeout(ctx, 100)
                if dev <= 0:
                    continue
                if self.dll.interception_receive(ctx, dev, stroke, 1) <= 0:
                    continue
                if not self.dll.interception_is_keyboard(dev):
                    self.dll.interception_send(ctx, dev, stroke, 1)
                    continue
                code = int.from_bytes(stroke.raw[0:2], "little")
                state = int.from_bytes(stroke.raw[2:4], "little")
                down = not (state & self.KEY_UP)
                if self.learning_until and time.monotonic() < self.learning_until:
                    self.dll.interception_send(ctx, dev, stroke, 1)
                    if down:
                        self.learning_until = 0
                        hw = self._hw(dev)
                        self.hwid = hw
                        self._next_scan = 0
                        was_learning = False
                        self.engine.events.put(("device", hw))
                    continue
                if dev not in self.targets:
                    # teclado principal: solo se consume lo que pide el modo macros
                    if not (state & self.KEY_E1) and \
                            self.engine.main_key(key_id(code, bool(state & self.KEY_E0)), down):
                        continue
                    self.dll.interception_send(ctx, dev, stroke, 1)
                    continue
                consume = False
                if state & self.KEY_E1:
                    consume = False
                elif state & self.KEY_E0 and code in (0x2A, 0x36):
                    consume = self.engine.active         # "shift falso" del numpad
                else:
                    consume = self.engine.decide(key_id(code, bool(state & self.KEY_E0)), down)
                if not consume:
                    self.dll.interception_send(ctx, dev, stroke, 1)
        except Exception as e:
            self.engine.events.put(("error", f"La captura se detuvo: {e}"))
            self.engine.events.put(("device_state", False))
        finally:
            self.engine.release_all()
            self.dll.interception_destroy_context(ctx)   # quita todos los filtros
            self._ctx = None


# ====================================================================== Hook sin driver
class HookBackend:
    name = "hook"
    learns_device = False

    def __init__(self, engine):
        if sys.platform != "win32":
            raise BackendError("El hook de teclado solo existe en Windows")
        from ctypes import wintypes as wt
        self.wt = wt
        self.engine = engine
        self._thread = None
        self._tid = 0
        self._started = threading.Event()
        self._start_error = None

    def start(self):
        self._thread = threading.Thread(target=self._loop, name="hook", daemon=True)
        self._thread.start()
        self._started.wait(3)
        if self._start_error:
            raise BackendError(self._start_error)

    def stop(self):
        if self._tid:
            ctypes.windll.user32.PostThreadMessageW(self._tid, 0x0012, 0, 0)  # WM_QUIT
        if self._thread:
            self._thread.join(timeout=2)

    def learn_device(self, seconds=15):
        pass

    def set_device(self, hwid):
        pass

    def connected(self) -> bool:
        return True

    def _loop(self):
        wt = self.wt
        u32 = ctypes.WinDLL("user32", use_last_error=True)
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [("vkCode", wt.DWORD), ("scanCode", wt.DWORD), ("flags", wt.DWORD),
                        ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

        LRESULT = ctypes.c_ssize_t
        HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)
        u32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD]
        u32.SetWindowsHookExW.restype = wt.HHOOK
        u32.CallNextHookEx.argtypes = [wt.HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM]
        u32.CallNextHookEx.restype = LRESULT
        u32.UnhookWindowsHookEx.argtypes = [wt.HHOOK]
        u32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
        k32.GetModuleHandleW.restype = wt.HMODULE
        k32.GetModuleHandleW.argtypes = [wt.LPCWSTR]

        LLKHF_EXTENDED, LLKHF_INJECTED, LLKHF_UP = 0x01, 0x10, 0x80
        VK_NUMLOCK, VK_PAUSE = 0x90, 0x13
        engine = self.engine

        def proc(n_code, w_param, l_param):
            if n_code == 0:
                kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if not (kb.flags & LLKHF_INJECTED) and kb.vkCode != VK_PAUSE:
                    if kb.vkCode == VK_NUMLOCK:
                        kid = "45"
                    else:
                        kid = key_id(kb.scanCode, bool(kb.flags & LLKHF_EXTENDED))
                    down = not (kb.flags & LLKHF_UP)
                    try:
                        if kid in NUMPAD_IDS:
                            if engine.decide(kid, down):
                                return 1
                        elif engine.main_key(kid, down):    # fila de números / modo macros
                            return 1
                    except Exception:
                        pass
            return u32.CallNextHookEx(None, n_code, w_param, l_param)

        self._proc = HOOKPROC(proc)
        hook = u32.SetWindowsHookExW(13, self._proc, k32.GetModuleHandleW(None), 0)  # WH_KEYBOARD_LL
        if not hook:
            self._start_error = f"No se pudo instalar el hook (error {ctypes.get_last_error()})"
            self._started.set()
            return
        self._tid = k32.GetCurrentThreadId()
        self._started.set()
        msg = wt.MSG()
        try:
            while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                pass
        finally:
            u32.UnhookWindowsHookEx(hook)
            engine.release_all()
