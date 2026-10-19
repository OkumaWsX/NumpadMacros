# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Bluetooth (RFCOMM, «puerto serie») para la app del celular.

`start_bluetooth(on_client)` empieza a escuchar y devuelve un objeto con
`.close()`. `on_client(sock, addr)` recibe cada celular con un objeto que
tiene recv/sendall/close, igual que un socket TCP.

- Linux: socket RFCOMM del sistema (o por ctypes si Python no lo trae).
- Windows: socket RFCOMM de Python + registro del servicio (SDP) con WSASetService.
- macOS: IOBluetooth (pyobjc).

El celular busca el servicio por UUID; si el sistema no lo publica, se conecta
directo al canal 22.
"""
import ctypes
import queue
import socket
import sys
import threading
import uuid

SERVICE_UUID = uuid.UUID("8f3c6a52-5e0b-4c6e-9b7b-1d2a9f0e7a12")
CHANNEL = 22
NAME = "Numpad Macros"


class BluetoothError(RuntimeError):
    pass


def start_bluetooth(on_client):
    if sys.platform.startswith("linux"):
        return _LinuxServer(on_client)
    if sys.platform == "win32":
        return _WindowsServer(on_client)
    if sys.platform == "darwin":
        return _MacServer(on_client)
    raise BluetoothError("Bluetooth no está disponible en este sistema")


# ====================================================================== Linux
AF_BLUETOOTH, BTPROTO_RFCOMM = 31, 3


class _sockaddr_rc(ctypes.Structure):
    _fields_ = [("family", ctypes.c_ushort), ("bdaddr", ctypes.c_ubyte * 6),
                ("channel", ctypes.c_ubyte)]


class _LinuxServer:
    def __init__(self, on_client):
        self.on_client = on_client
        self.closed = False
        self._native = hasattr(socket, "BTPROTO_RFCOMM")
        self._libc = None
        try:
            if self._native:
                self.sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM,
                                          socket.BTPROTO_RFCOMM)
                self.sock.bind((socket.BDADDR_ANY, CHANNEL))
                self.sock.listen(4)
                self.fd = self.sock.fileno()
            else:
                self._libc = ctypes.CDLL(None, use_errno=True)
                fd = self._libc.socket(AF_BLUETOOTH, socket.SOCK_STREAM, BTPROTO_RFCOMM)
                if fd < 0:
                    raise OSError(ctypes.get_errno(), "socket")
                addr = _sockaddr_rc(AF_BLUETOOTH, (ctypes.c_ubyte * 6)(), CHANNEL)
                if self._libc.bind(fd, ctypes.byref(addr), ctypes.sizeof(addr)) < 0 or \
                        self._libc.listen(fd, 4) < 0:
                    err = ctypes.get_errno()
                    self._libc.close(fd)
                    raise OSError(err, "bind")
                self.fd = fd
        except OSError as e:
            if e.errno in (97, 93):    # EAFNOSUPPORT / EPROTONOSUPPORT
                raise BluetoothError("Este PC no tiene Bluetooth (o está apagado)")
            if e.errno == 98:          # EADDRINUSE
                raise BluetoothError(f"El canal Bluetooth {CHANNEL} ya lo usa otro programa")
            raise BluetoothError(f"No pude abrir Bluetooth: {e}")
        _try_sdptool()
        threading.Thread(target=self._loop, name="celular-bt", daemon=True).start()

    def _accept(self):
        if self._native:
            s, addr = self.sock.accept()
            return s, addr[0]
        addr = _sockaddr_rc()
        ln = ctypes.c_uint(ctypes.sizeof(addr))
        fd = self._libc.accept(self.fd, ctypes.byref(addr), ctypes.byref(ln))
        if fd < 0:
            raise OSError(ctypes.get_errno(), "accept")
        mac = ":".join(f"{b:02X}" for b in reversed(bytes(addr.bdaddr)))
        return socket.socket(fileno=fd), mac

    def _loop(self):
        while not self.closed:
            try:
                s, mac = self._accept()
            except OSError:
                if self.closed:
                    return
                continue
            self.on_client(s, mac)

    def close(self):
        self.closed = True
        try:
            if self._native:
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
            else:
                self._libc.shutdown(self.fd, 2)
                self._libc.close(self.fd)
        except OSError:
            pass


def _try_sdptool():
    """Publica el servicio con sdptool si existe (BlueZ en modo compatible).
    Si no, el celular usa el canal 22 directamente."""
    import shutil
    import subprocess
    tool = shutil.which("sdptool")
    if not tool:
        return
    try:
        subprocess.run([tool, "add", f"--channel={CHANNEL}", "SP"], capture_output=True, timeout=3)
    except Exception:
        pass


# ====================================================================== Windows
class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]

    @classmethod
    def of(cls, u: uuid.UUID):
        b = u.bytes
        return cls(int.from_bytes(b[0:4], "big"), int.from_bytes(b[4:6], "big"),
                   int.from_bytes(b[6:8], "big"), (ctypes.c_ubyte * 8)(*b[8:16]))


class _SOCKADDR_BTH(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("addressFamily", ctypes.c_ushort), ("btAddr", ctypes.c_ulonglong),
                ("serviceClassId", _GUID), ("port", ctypes.c_uint32)]


class _SOCKET_ADDRESS(ctypes.Structure):
    _fields_ = [("lpSockaddr", ctypes.c_void_p), ("iSockaddrLength", ctypes.c_int)]


class _CSADDR_INFO(ctypes.Structure):
    _fields_ = [("LocalAddr", _SOCKET_ADDRESS), ("RemoteAddr", _SOCKET_ADDRESS),
                ("iSocketType", ctypes.c_int), ("iProtocol", ctypes.c_int)]


class _WSAQUERYSETW(ctypes.Structure):
    _fields_ = [("dwSize", ctypes.c_uint32), ("lpszServiceInstanceName", ctypes.c_wchar_p),
                ("lpServiceClassId", ctypes.POINTER(_GUID)), ("lpVersion", ctypes.c_void_p),
                ("lpszComment", ctypes.c_wchar_p), ("dwNameSpace", ctypes.c_uint32),
                ("lpNSProviderId", ctypes.c_void_p), ("lpszContext", ctypes.c_wchar_p),
                ("dwNumberOfProtocols", ctypes.c_uint32), ("lpafpProtocols", ctypes.c_void_p),
                ("lpszQueryString", ctypes.c_wchar_p), ("dwNumberOfCsAddrs", ctypes.c_uint32),
                ("lpcsaBuffer", ctypes.POINTER(_CSADDR_INFO)), ("dwOutputFlags", ctypes.c_uint32),
                ("lpBlob", ctypes.c_void_p)]


class _WindowsServer:
    NS_BTH, AF_BTH, RNRSERVICE_REGISTER, RNRSERVICE_DELETE = 16, 32, 0, 2

    def __init__(self, on_client):
        self.on_client = on_client
        self.closed = False
        if not hasattr(socket, "BTPROTO_RFCOMM"):
            raise BluetoothError("Esta versión de Python no trae Bluetooth")
        try:
            self.sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM,
                                      socket.BTPROTO_RFCOMM)
            any_addr = getattr(socket, "BDADDR_ANY", "00:00:00:00:00:00")
            try:
                self.sock.bind((any_addr, CHANNEL))
            except OSError:
                self.sock.bind((any_addr, 0))       # que Windows elija el canal
            self.sock.listen(4)
        except OSError as e:
            raise BluetoothError(f"No pude abrir Bluetooth (¿está encendido?): {e}")
        self._qs = None
        try:
            self._register()
        except Exception as e:
            self.sdp_error = str(e)
        threading.Thread(target=self._loop, name="celular-bt", daemon=True).start()

    def _register(self):
        addr, port = self.sock.getsockname()[:2]
        bt = int(str(addr).replace(":", "") or "0", 16)
        self._guid = _GUID.of(SERVICE_UUID)
        self._sa = _SOCKADDR_BTH(self.AF_BTH, bt, _GUID(), port)
        self._cs = _CSADDR_INFO()
        self._cs.LocalAddr = _SOCKET_ADDRESS(ctypes.addressof(self._sa), ctypes.sizeof(self._sa))
        self._cs.RemoteAddr = _SOCKET_ADDRESS(ctypes.addressof(self._sa), ctypes.sizeof(self._sa))
        self._cs.iSocketType = socket.SOCK_STREAM
        self._cs.iProtocol = BTPROTO_RFCOMM
        qs = _WSAQUERYSETW()
        qs.dwSize = ctypes.sizeof(qs)
        qs.lpszServiceInstanceName = NAME
        qs.lpServiceClassId = ctypes.pointer(self._guid)
        qs.lpszComment = "Botonera Numpad Macros"
        qs.dwNameSpace = self.NS_BTH
        qs.dwNumberOfCsAddrs = 1
        qs.lpcsaBuffer = ctypes.pointer(self._cs)
        ws2 = ctypes.WinDLL("ws2_32")
        if ws2.WSASetServiceW(ctypes.byref(qs), self.RNRSERVICE_REGISTER, 0) != 0:
            raise OSError(ws2.WSAGetLastError(), "WSASetService")
        self._qs = qs

    def _loop(self):
        while not self.closed:
            try:
                s, addr = self.sock.accept()
            except OSError:
                if self.closed:
                    return
                continue
            self.on_client(s, str(addr[0]) if isinstance(addr, tuple) else str(addr))

    def close(self):
        self.closed = True
        if self._qs is not None:
            try:
                ctypes.WinDLL("ws2_32").WSASetServiceW(ctypes.byref(self._qs),
                                                       self.RNRSERVICE_DELETE, 0)
            except Exception:
                pass
        try:
            self.sock.close()
        except OSError:
            pass


# ====================================================================== macOS
class _MacChannelSocket:
    """Envuelve un canal RFCOMM de IOBluetooth con la forma de un socket."""

    def __init__(self, channel):
        self.channel = channel
        self.q: queue.Queue = queue.Queue()
        self.closed = False

    def feed(self, data: bytes):
        self.q.put(data)

    def ended(self):
        self.q.put(b"")

    def recv(self, _n):
        if self.closed:
            return b""
        return self.q.get()

    def sendall(self, data: bytes):
        if self.closed:
            raise OSError("canal cerrado")
        mtu = max(64, int(self.channel.getMTU() or 127))
        for i in range(0, len(data), mtu):
            part = data[i:i + mtu]
            if self.channel.writeSync_length_(part, len(part)) != 0:
                raise OSError("no se pudo enviar por Bluetooth")

    def close(self):
        if not self.closed:
            self.closed = True
            self.q.put(b"")
            try:
                self.channel.closeChannel()
            except Exception:
                pass

    def setsockopt(self, *a):
        pass


class _MacServer:
    def __init__(self, on_client):
        try:
            import objc                      # noqa: F401
            import IOBluetooth
            from Foundation import NSObject
        except ImportError:
            raise BluetoothError("Falta el módulo IOBluetooth (pyobjc) para usar Bluetooth")
        self.on_client = on_client
        self.socks = {}
        server = self

        class _Delegate(NSObject):
            def newChannel_channel_(self, notification, channel):
                s = _MacChannelSocket(channel)
                server.socks[id(channel)] = s
                channel.setDelegate_(self)
                server.on_client(s, str(channel.getDevice().addressString()))

            def rfcommChannelData_data_length_(self, channel, data, length):
                s = server.socks.get(id(channel))
                if s:
                    s.feed(bytes(data[:length]) if not isinstance(data, bytes) else data[:length])

            def rfcommChannelClosed_(self, channel):
                s = server.socks.pop(id(channel), None)
                if s:
                    s.ended()

        self.delegate = _Delegate.alloc().init()
        uuid_bytes = SERVICE_UUID.bytes
        sdp_uuid = IOBluetooth.IOBluetoothSDPUUID.uuidWithBytes_length_(uuid_bytes, 16)
        l2cap = IOBluetooth.IOBluetoothSDPUUID.uuid16_(0x0100)
        rfcomm = IOBluetooth.IOBluetoothSDPUUID.uuid16_(0x0003)
        record = {
            "0001 - ServiceClassIDList": [sdp_uuid, IOBluetooth.IOBluetoothSDPUUID.uuid16_(0x1101)],
            "0004 - ProtocolDescriptorList": [
                [l2cap],
                [rfcomm, {"DataElementType": 1, "DataElementSize": 1,
                          "DataElementValue": CHANNEL}]],
            "0100 - ServiceName*": NAME,
        }
        self.record = IOBluetooth.IOBluetoothSDPServiceRecord.publishedServiceRecordWithDictionary_(record)
        if self.record is None:
            raise BluetoothError("macOS no permitió publicar el servicio Bluetooth")
        res = self.record.getRFCOMMChannelID_(None)
        status, ch = res if isinstance(res, tuple) else (0, CHANNEL)
        self.notif = IOBluetooth.IOBluetoothRFCOMMChannel.\
            registerForChannelOpenNotifications_selector_withChannelID_direction_(
                self.delegate, b"newChannel:channel:", int(ch or CHANNEL), 1)

    def close(self):
        try:
            if self.notif:
                self.notif.unregister()
            if self.record:
                self.record.removeServiceRecord()
        except Exception:
            pass
        for s in list(self.socks.values()):
            s.close()
