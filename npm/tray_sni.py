"""Icono de bandeja para Linux con menú (StatusNotifierItem + DBusMenu).

pystray en Linux, sin GTK/AppIndicator (como en la app empaquetada), cae al
modo «xorg», que no tiene menú: en KDE, GNOME (con la extensión AppIndicator),
XFCE, Cinnamon, etc. el icono aparecía pero no mostraba Mostrar / Pausar /
Salir. Este módulo habla directo por D-Bus el mismo protocolo que usan las
apps de KDE y de Electron, así el escritorio dibuja el menú nativo al hacer
clic derecho. Solo usa `jeepney` (Python puro, sin GTK).

Uso:
    tray = SniTray("NumpadMacros", "Numpad Macros", pil_image, menu_fn, on_activate)
    tray.start()          # False si no hay bandeja compatible (usar otra cosa)
    tray.update_menu()    # tras cambiar un texto (Pausar ↔ Reanudar)
    tray.stop()

`menu_fn()` devuelve una lista de (texto, función) o None para un separador.
Las funciones se llaman desde el hilo de D-Bus: que solo encolen trabajo.
"""
from __future__ import annotations

import os
import threading

WATCHER = "org.kde.StatusNotifierWatcher"
ITEM_IFACE = "org.kde.StatusNotifierItem"
ITEM_PATH = "/StatusNotifierItem"
MENU_IFACE = "com.canonical.dbusmenu"
MENU_PATH = "/MenuBar"
PROPS = "org.freedesktop.DBus.Properties"
INTRO = "org.freedesktop.DBus.Introspectable"

_INTROSPECT = {
    ITEM_PATH: f"""<node>
 <interface name="{ITEM_IFACE}">
  <property name="Category" type="s" access="read"/>
  <property name="Id" type="s" access="read"/>
  <property name="Title" type="s" access="read"/>
  <property name="Status" type="s" access="read"/>
  <property name="WindowId" type="i" access="read"/>
  <property name="IconName" type="s" access="read"/>
  <property name="IconPixmap" type="a(iiay)" access="read"/>
  <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
  <property name="ItemIsMenu" type="b" access="read"/>
  <property name="Menu" type="o" access="read"/>
  <method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
  <signal name="NewTitle"/><signal name="NewIcon"/><signal name="NewToolTip"/>
  <signal name="NewStatus"><arg type="s"/></signal>
 </interface>
</node>""",
    MENU_PATH: f"""<node>
 <interface name="{MENU_IFACE}">
  <property name="Version" type="u" access="read"/>
  <property name="TextDirection" type="s" access="read"/>
  <property name="Status" type="s" access="read"/>
  <property name="IconThemePath" type="as" access="read"/>
  <method name="GetLayout"><arg type="i" direction="in"/><arg type="i" direction="in"/>
   <arg type="as" direction="in"/><arg type="u" direction="out"/><arg type="(ia{{sv}}av)" direction="out"/></method>
  <method name="GetGroupProperties"><arg type="ai" direction="in"/><arg type="as" direction="in"/>
   <arg type="a(ia{{sv}})" direction="out"/></method>
  <method name="GetProperty"><arg type="i" direction="in"/><arg type="s" direction="in"/>
   <arg type="v" direction="out"/></method>
  <method name="Event"><arg type="i" direction="in"/><arg type="s" direction="in"/>
   <arg type="v" direction="in"/><arg type="u" direction="in"/></method>
  <method name="EventGroup"><arg type="a(isvu)" direction="in"/><arg type="ai" direction="out"/></method>
  <method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
  <method name="AboutToShowGroup"><arg type="ai" direction="in"/><arg type="ai" direction="out"/>
   <arg type="ai" direction="out"/></method>
  <signal name="ItemsPropertiesUpdated"><arg type="a(ia{{sv}})"/><arg type="a(ias)"/></signal>
  <signal name="LayoutUpdated"><arg type="u"/><arg type="i"/></signal>
 </interface>
</node>""",
}


def _pixmaps(image):
    """Imagen PIL → lista de (ancho, alto, bytes ARGB32 big-endian) en varios tamaños."""
    out = []
    try:
        from PIL import Image
        src = image.convert("RGBA")
        for size in (16, 22, 24, 32, 48, 64):
            im = src.resize((size, size), Image.LANCZOS) if src.size != (size, size) else src
            r, g, b, a = im.split()
            argb = Image.merge("RGBA", (a, r, g, b)).tobytes()
            out.append((size, size, argb))
    except Exception:
        pass
    return out


class SniTray:
    HAS_MENU = True

    def __init__(self, ident, title, image, menu_fn, on_activate=None, on_secondary=None):
        self.ident = ident
        self.title = title
        self.pix = _pixmaps(image) if image is not None else []
        self.menu_fn = menu_fn
        self.on_activate = on_activate
        self.on_secondary = on_secondary
        self.conn = None
        self.name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        self.revision = 1
        self._items = {}            # id → función
        self._send_lock = threading.Lock()
        self._thread = None
        self._running = False
        self._pending = {}          # serial → Event (respuestas que esperamos)

    # ------------------------------------------------------------------ arranque
    def start(self) -> bool:
        """Se registra en la bandeja. False si no hay D-Bus o ninguna bandeja SNI."""
        try:
            import jeepney  # noqa: F401  (comprobar que está)
            from jeepney.bus_messages import message_bus, MatchRule
            from jeepney.io.blocking import open_dbus_connection
        except Exception:
            return False
        if not os.environ.get("DBUS_SESSION_BUS_ADDRESS") and not os.environ.get("XDG_RUNTIME_DIR"):
            return False
        try:
            conn = open_dbus_connection(bus="SESSION")
        except Exception:
            return False
        try:
            has = conn.send_and_get_reply(message_bus.NameHasOwner(WATCHER), timeout=3).body[0]
            if not has:
                conn.close()
                return False
            conn.send_and_get_reply(message_bus.RequestName(self.name, 4), timeout=3)   # 4 = no esperar en cola
            rule = MatchRule(type="signal", sender="org.freedesktop.DBus", interface="org.freedesktop.DBus",
                             member="NameOwnerChanged", path="/org/freedesktop/DBus")
            rule.add_arg_condition(0, WATCHER)
            conn.send_and_get_reply(message_bus.AddMatch(rule), timeout=3)
            self.conn = conn
            self._running = True
            self._thread = threading.Thread(target=self._loop, name="bandeja-sni", daemon=True)
            self._thread.start()
            ok = self._register(wait=3.0)
        except Exception:
            ok = False
        if not ok:
            self.stop()
        return ok

    def _register(self, wait=0.0):
        """Se anota en la bandeja. Con `wait` espera la respuesta (la recibe el hilo de D-Bus,
        que mientras tanto ya atiende las preguntas que hace la barra al ver el icono)."""
        from jeepney import DBusAddress, new_method_call
        watcher = DBusAddress("/StatusNotifierWatcher", bus_name=WATCHER, interface=WATCHER)
        msg = new_method_call(watcher, "RegisterStatusNotifierItem", "s", (self.name,))
        done = threading.Event()
        with self._send_lock:
            serial = next(self.conn.outgoing_serial)
            self._pending[serial] = done
            self.conn.send(msg, serial=serial)
        if not wait:
            return True
        if not done.wait(wait):
            self._pending.pop(serial, None)
            return False
        return bool(getattr(done, "ok", False))

    def stop(self):
        self._running = False
        conn, self.conn = self.conn, None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    def update_menu(self):
        """Avisa al escritorio que el menú cambió (por ejemplo Pausar ↔ Reanudar)."""
        if not self.conn:
            return
        from jeepney import DBusAddress, new_signal
        self.revision += 1
        try:
            self._send(new_signal(DBusAddress(MENU_PATH, interface=MENU_IFACE), "LayoutUpdated", "ui",
                                  (self.revision, 0)))
        except Exception:
            pass

    # ------------------------------------------------------------------ D-Bus
    def _send(self, msg):
        conn = self.conn
        if conn is None:
            return
        with self._send_lock:
            conn.send(msg)

    def _loop(self):
        from jeepney import MessageType, HeaderFields
        while self._running:
            conn = self.conn
            if conn is None:
                break
            try:
                msg = conn.receive()
            except Exception:
                break
            h = msg.header
            try:
                if h.message_type in (MessageType.method_return, MessageType.error):
                    ev = self._pending.pop(h.fields.get(HeaderFields.reply_serial), None)
                    if ev is not None:
                        ev.ok = h.message_type == MessageType.method_return
                        ev.set()
                elif h.message_type == MessageType.method_call:
                    self._dispatch(msg)
                elif (h.message_type == MessageType.signal
                      and h.fields.get(HeaderFields.member) == "NameOwnerChanged"
                      and len(msg.body) >= 3 and msg.body[0] == WATCHER and msg.body[2]):
                    self._register()        # se reinició la barra (p. ej. plasmashell)
            except Exception as e:
                try:
                    from jeepney import new_error
                    self._send(new_error(msg, "org.freedesktop.DBus.Error.Failed", "s", (str(e),)))
                except Exception:
                    pass
        self._running = False

    def _reply(self, msg, sig=None, body=()):
        from jeepney import new_method_return
        self._send(new_method_return(msg, sig, body))

    def _error(self, msg, name, text):
        from jeepney import new_error
        self._send(new_error(msg, name, "s", (text,)))

    def _dispatch(self, msg):
        from jeepney import HeaderFields
        f = msg.header.fields
        path = f.get(HeaderFields.path)
        iface = f.get(HeaderFields.interface)
        member = f.get(HeaderFields.member)
        body = msg.body
        if iface == INTRO or (iface is None and member == "Introspect"):
            xml = _INTROSPECT.get(path, "<node>" + "".join(
                f'<node name="{p.strip("/")}"/>' for p in _INTROSPECT if path == "/") + "</node>")
            return self._reply(msg, "s", (xml,))
        if iface == "org.freedesktop.DBus.Peer":
            if member == "Ping":
                return self._reply(msg)
            return self._reply(msg, "s", ("numpadmacros",))
        props = self._item_props() if path == ITEM_PATH else self._menu_props() if path == MENU_PATH else None
        if props is None:
            return self._error(msg, "org.freedesktop.DBus.Error.UnknownObject", path or "")
        if iface == PROPS:
            if member == "GetAll":
                return self._reply(msg, "a{sv}", (props,))
            if member == "Get":
                name = body[1]
                if name in props:
                    return self._reply(msg, "v", (props[name],))
                return self._error(msg, "org.freedesktop.DBus.Error.UnknownProperty", name)
            if member == "Set":
                return self._error(msg, "org.freedesktop.DBus.Error.PropertyReadOnly", body[1])
        if path == ITEM_PATH:
            return self._item_call(msg, member, body)
        return self._menu_call(msg, member, body)

    # ------------------------------------------------------------------ StatusNotifierItem
    def _item_props(self):
        pix = [(w, h, data) for w, h, data in self.pix]
        return {
            "Category": ("s", "ApplicationStatus"),
            "Id": ("s", self.ident),
            "Title": ("s", self.title),
            "Status": ("s", "Active"),
            "WindowId": ("i", 0),
            "IconName": ("s", ""),
            "IconThemePath": ("s", ""),
            "IconPixmap": ("a(iiay)", pix),
            "OverlayIconName": ("s", ""),
            "OverlayIconPixmap": ("a(iiay)", []),
            "AttentionIconName": ("s", ""),
            "AttentionIconPixmap": ("a(iiay)", []),
            "AttentionMovieName": ("s", ""),
            "ToolTip": ("(sa(iiay)ss)", ("", [], self.title, "")),
            "ItemIsMenu": ("b", False),
            "Menu": ("o", MENU_PATH),
        }

    def _item_call(self, msg, member, body):
        if member == "Activate":
            self._reply(msg)
            if self.on_activate:
                self.on_activate()
        elif member == "SecondaryActivate":
            self._reply(msg)
            if self.on_secondary:
                self.on_secondary()
        elif member in ("ContextMenu", "Scroll", "ProvideXdgActivationToken"):
            self._reply(msg)
        else:
            self._error(msg, "org.freedesktop.DBus.Error.UnknownMethod", member or "")

    # ------------------------------------------------------------------ DBusMenu
    def _menu_props(self):
        return {
            "Version": ("u", 3),
            "TextDirection": ("s", "ltr"),
            "Status": ("s", "normal"),
            "IconThemePath": ("as", []),
        }

    def _entries(self):
        """[(id, propiedades)] de los elementos del menú, y guarda las funciones por id."""
        items, funcs = [], {}
        try:
            spec = list(self.menu_fn())
        except Exception:
            spec = []
        for n, entry in enumerate(spec, start=1):
            if entry is None:
                items.append((n, {"type": ("s", "separator")}))
                continue
            label, func = entry[0], entry[1]
            props = {"label": ("s", label.replace("_", "__")), "enabled": ("b", True),
                     "visible": ("b", True)}
            items.append((n, props))
            funcs[n] = func
        self._items = funcs
        return items

    def _layout(self):
        children = [("(ia{sv}av)", (i, p, [])) for i, p in self._entries()]
        root = (0, {"children-display": ("s", "submenu")}, children)
        return root

    def _menu_call(self, msg, member, body):
        if member == "GetLayout":
            parent = body[0] if body else 0
            root = self._layout()
            if parent:
                for v in root[2]:
                    if v[1][0] == parent:
                        root = v[1]
                        break
            return self._reply(msg, "u(ia{sv}av)", (self.revision, root))
        if member == "GetGroupProperties":
            want = set(body[0]) if body and body[0] else None
            out = [(i, p) for i, p in self._entries() if want is None or i in want]
            return self._reply(msg, "a(ia{sv})", (out,))
        if member == "GetProperty":
            ident, name = body
            for i, p in self._entries():
                if i == ident and name in p:
                    return self._reply(msg, "v", (p[name],))
            return self._error(msg, "org.freedesktop.DBus.Error.InvalidArgs", name)
        if member == "Event":
            self._reply(msg)
            self._clicked(body[0], body[1])
            return None
        if member == "EventGroup":
            self._reply(msg, "ai", ([],))
            for ev in body[0]:
                self._clicked(ev[0], ev[1])
            return None
        if member == "AboutToShow":
            return self._reply(msg, "b", (False,))
        if member == "AboutToShowGroup":
            return self._reply(msg, "aiai", ([], []))
        return self._error(msg, "org.freedesktop.DBus.Error.UnknownMethod", member or "")

    def _clicked(self, ident, event):
        if event != "clicked":
            return
        if not self._items:
            self._entries()
        func = self._items.get(ident)
        if func:
            func()
