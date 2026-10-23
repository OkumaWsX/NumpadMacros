# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Estudio de Temas para Numpad Macros: crea temas .npt firmados.

Un solo programa para todos. Si la clave oficial está en esta PC abre en modo
creador (temas oficiales); si no, en modo comunidad (temas con tu firma de autor).
"""
from __future__ import annotations

import hashlib
import io
import os
import sys
import threading
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _log_path() -> str:
    """Archivo donde se anota un error que cierra el programa (sin depender de nada más)."""
    d = os.environ.get("NPT_ESTUDIO_DIR")
    if not d:
        if sys.platform == "win32":
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
        elif sys.platform == "darwin":
            base = os.path.expanduser("~/Library/Application Support")
        else:
            base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        d = os.path.join(base, "NumpadMacros", "estudio")
    return os.path.join(d, "error.log")


def _fatal(text: str) -> None:
    """Anota el error, lo muestra en una ventana (si se puede) y cierra con código 1."""
    path = _log_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        path = ""
    try:
        sys.stderr.write(text)
    except Exception:
        pass
    if "--probar" in sys.argv:            # prueba automática: sin ventanas que esperen un clic
        sys.exit(1)
    try:
        from tkinter import messagebox as mb
        r = tk.Tk()
        r.withdraw()
        mb.showerror("Estudio de Temas", "El Estudio de Temas no pudo abrirse.\n\n"
                     + text.strip().splitlines()[-1][:300]
                     + (f"\n\nEl detalle quedó en:\n{path}\nEnvíalo en el Discord de soporte." if path else ""),
                     parent=r)
        r.destroy()
    except Exception:
        pass
    sys.exit(1)


_IMPORT_ERROR = ""
try:
    import logica as L  # noqa: E402
    import claves as K  # noqa: E402
    import vista as V  # noqa: E402
    from logica import npt  # noqa: E402
    from PIL import Image, ImageTk  # noqa: E402
except Exception:
    import traceback
    _IMPORT_ERROR = traceback.format_exc()

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception:          # sin la librería se elige la imagen con un botón
    TkinterDnD = None

VERSION = "1.0.0"
APP = "Estudio de Temas"
if _IMPORT_ERROR:
    _fatal(_IMPORT_ERROR)
FONT = V.FONT
BASE = 13 if sys.platform == "darwin" else 10
MONO = "Menlo" if sys.platform == "darwin" else ("Consolas" if sys.platform == "win32" else "DejaVu Sans Mono")
C = {"bg": "#14161b", "panel": "#1c1f26", "panel2": "#232730", "line": "#2e333d", "text": "#e9e9ec",
     "muted": "#8b909b", "acc": "#f2a33a", "on_acc": "#1a1306", "acc_dim": "#7a5520", "acc_bg": "#3a2c14",
     "ok": "#4cc38a", "bad": "#e5534b", "warn": "#e2b340", "sig": "#7e5fc4", "sig_bg": "#241d38",
     "sig_text": "#d9c9ff", "ok_bg": "#12261c", "ok_text": "#9fe6c3", "warn_bg": "#2a2412", "warn_text": "#f2d68a",
     "bad_bg": "#2e1514", "bad_text": "#ffb3ae"}
GROUPS = (
    ("Fondos", (("bg", "Fondo de la ventana"), ("panel", "Paneles"), ("panel2", "Campos y pestañas"),
                ("line", "Bordes"))),
    ("Texto", (("text", "Texto"), ("muted", "Texto secundario"))),
    ("Acento", (("acc", "Acento"), ("on_acc", "Texto sobre el acento"), ("acc_hover", "Al pasar el mouse"),
                ("acc_dim", "Atenuado (selección)"), ("acc_bg", "Fondo de avisos"))),
    ("Teclas", (("key", "Tecla libre"), ("key_set", "Con acción · fondo"), ("key_set_line", "Con acción · borde"),
                ("key_set_text", "Con acción · texto"), ("key_global", "Global · fondo"),
                ("key_global_line", "Global · borde"), ("key_global_text", "Global · texto"))),
    ("Estados", (("ok", "Activo / correcto"), ("on_ok", "Texto sobre activo"), ("bad", "Error"), ("warn", "Aviso"))),
)
LABELS = {k: v for _g, items in GROUPS for k, v in items}
PARENT_NAME = {"bg": "el fondo", "panel": "los paneles", "panel2": "los campos", "acc": "el acento",
               "key_set": "la tecla", "key_global": "la tecla global", "ok": "el botón ACTIVO"}
AUTO = ("acc_hover", "acc_dim", "acc_bg")
IMG_TYPES = [("Imágenes", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"), ("Todos", "*")]


def fnt(size=0, bold=False, mono=False):
    fam = MONO if mono else FONT
    return (fam, BASE + size, "bold") if bold else (fam, BASE + size)


class Scrollable(tk.Frame):
    """Columna con barra de desplazamiento (rueda del mouse en los 3 sistemas)."""

    def __init__(self, parent, bg, width=None):
        super().__init__(parent, bg=bg)
        self.cv = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, width=width or 10)
        self.sb = ttk.Scrollbar(self, orient="vertical", command=self.cv.yview)
        self.inner = tk.Frame(self.cv, bg=bg)
        self._win = self.cv.create_window(0, 0, anchor="nw", window=self.inner)
        self.cv.configure(yscrollcommand=self.sb.set)
        self.cv.pack(side="left", fill="both", expand=True)
        self.sb.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda e: self._region())
        self.cv.bind("<Configure>", self._on_width)
        self.bind("<Enter>", self._wheel_on)
        self.bind("<Leave>", self._wheel_off)
        Scrollable.all.append(self)

    all: list = []

    def _region(self):
        """Zona que se puede desplazar: nunca más baja que la columna. Si todo cabe, la rueda no mueve
        nada (si no, Tk deja «subir» el contenido aunque ya esté arriba del todo y queda un hueco)."""
        h = max(self.inner.winfo_reqheight(), self.cv.winfo_height())
        self.cv.configure(scrollregion=(0, 0, self.cv.winfo_width(), h))
        if self.inner.winfo_reqheight() <= self.cv.winfo_height():
            self.cv.yview_moveto(0)

    def _on_width(self, e):
        self.cv.itemconfigure(self._win, width=e.width)
        self._region()
        if not hasattr(self, "_base_w"):
            self._base_w = e.width
        if e.width != getattr(self, "_last_w", None):
            self._last_w = e.width
            # como mucho cada 50 ms (y siempre con el último ancho): al arrastrar el borde los textos
            # acompañan al panel sin trabar cada cuadro; si se esperara a soltar, al final saltarían
            if not getattr(self, "_wrap_job", None):
                self._wrap_job = self.after(50, self._rewrap)

    def _rewrap(self):
        """El panel es «responsivo»: los textos largos se reacomodan al nuevo ancho (sin deformarse)."""
        self._wrap_job = None
        extra = self._last_w - self._base_w
        stack = [self.inner]
        while stack:
            w = stack.pop()
            stack.extend(w.winfo_children())
            if isinstance(w, tk.Label):
                if not hasattr(w, "_wrap0"):
                    try:
                        w._wrap0 = int(str(w.cget("wraplength")) or 0)
                    except (tk.TclError, ValueError):
                        w._wrap0 = 0
                if w._wrap0 > 0:
                    w.configure(wraplength=max(120, w._wrap0 + extra))

    def moved(self) -> bool:
        """True si la columna cambió de lugar o de tamaño desde la última vez que se repintó."""
        top = self.winfo_toplevel()                  # posición dentro de la ventana (no en la pantalla)
        place = (self.winfo_rootx() - top.winfo_rootx(), self.winfo_rooty() - top.winfo_rooty(),
                 self.winfo_width(), self.winfo_height())
        if place == getattr(self, "_place", None):
            return False
        self._place = place
        return True

    def refresh(self):
        """Vuelve a pintar todo lo de adentro. En KDE (Wayland, XWayland) al mover una columna quedan
        partes sin dibujar que no se arreglan solas, y lo único que sirve es esconderla y mostrarla."""
        try:
            self.cv.itemconfigure(self._win, state="hidden")
            self.cv.update_idletasks()
            self.cv.itemconfigure(self._win, state="normal")
            self._region()
        except tk.TclError:
            pass

    def _wheel_on(self, _e):
        self.cv.bind_all("<MouseWheel>", self._wheel)
        self.cv.bind_all("<Button-4>", lambda e: self.cv.yview_scroll(-3, "units"))
        self.cv.bind_all("<Button-5>", lambda e: self.cv.yview_scroll(3, "units"))

    def _wheel_off(self, e):
        w = self.winfo_containing(e.x_root, e.y_root)
        if w is not None and str(w).startswith(str(self)):
            return                                   # sigue dentro (pasó a un elemento hijo)
        for s in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.cv.unbind_all(s)

    def _wheel(self, e):
        d = e.delta if sys.platform == "darwin" else (int(e.delta / 120) or (1 if e.delta > 0 else -1))
        self.cv.yview_scroll(-d, "units")


class Switch(tk.Frame):
    """Interruptor (encendido / apagado) con su texto."""

    def __init__(self, parent, text, command, value=True, bg=None):
        bg = bg or C["bg"]
        super().__init__(parent, bg=bg, cursor="hand2")
        self.value = value
        self.command = command
        self.cv = tk.Canvas(self, width=34, height=18, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.cv.pack(side="left")
        self.lbl = tk.Label(self, text=text, bg=bg, fg=C["muted"], font=fnt(-1), cursor="hand2")
        self.lbl.pack(side="left", padx=(6, 0))
        for w in (self, self.cv, self.lbl):
            w.bind("<Button-1>", self._toggle)
        self._paint()

    def _toggle(self, _e=None):
        self.set(not self.value)
        self.command(self.value)

    def set(self, value):
        self.value = bool(value)
        self._paint()

    def _paint(self):
        cv = self.cv
        cv.delete("all")
        on = self.value
        col = C["acc"] if on else C["line"]
        cv.create_oval(1, 1, 17, 17, fill=col, outline=col)
        cv.create_oval(17, 1, 33, 17, fill=col, outline=col)
        cv.create_rectangle(9, 1, 25, 17, fill=col, outline=col)
        x = 25 if on else 9
        cv.create_oval(x - 6, 3, x + 6, 15, fill=C["on_acc"] if on else C["muted"], outline="")
        self.lbl.configure(fg=C["text"] if on else C["muted"])


class Slider(tk.Canvas):
    """Control deslizable dibujado a mano, igual a como se veía con tk.Scale (barra oscura y un botón
    naranja). tk.Scale usa el naranja como fondo de toda su ventana: al redimensionar, si el sistema la
    limpia se veía el control entero naranja. Aquí el fondo es el del panel."""
    KNOB = 16
    HIGH = 10

    def __init__(self, parent, var, a, b, step, command):
        super().__init__(parent, width=40, height=self.HIGH, bg=parent.cget("bg"), highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=1)
        self.var, self.a, self.b, self.step, self.command = var, a, b, step, command
        self._state, self._hover = "normal", False           # width=40: sin él el Canvas pide ~380 px
        self._trace = var.trace_add("write", lambda *_: self._paint())
        self.bind("<Configure>", lambda e: self._paint())
        self.bind("<Button-1>", lambda e: (self.focus_set(), self._set_x(e.x)))
        self.bind("<B1-Motion>", lambda e: self._set_x(e.x))
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Left>", lambda e: self._set_value(self._value() - self.step))
        self.bind("<Right>", lambda e: self._set_value(self._value() + self.step))
        self.bind("<Destroy>", self._untrace)

    def configure(self, cnf=None, **kw):
        if "length" in kw:                                  # como en tk.Scale: el largo es el ancho
            kw["width"] = kw.pop("length")
        if "state" in kw:                                   # «disabled»: gris y sin responder
            self._state = kw.pop("state")
            self._paint()
        if cnf or kw:
            return super().configure(cnf, **kw)

    config = configure

    def _untrace(self, e):
        if e.widget is self:
            try:
                self.var.trace_remove("write", self._trace)
            except (tk.TclError, ValueError):
                pass

    def _value(self):
        try:
            return self.var.get()
        except (tk.TclError, ValueError):
            return self.a

    def _set_hover(self, on):
        self._hover = on
        self._paint()

    def _paint(self):
        w = self.winfo_width()
        if w <= 1:
            return
        span = (self.b - self.a) or 1
        x = round((L.clamp(self._value(), self.a, self.b) - self.a) / span * (w - self.KNOB))
        on = self._state != "disabled"
        self.delete("all")
        self.create_rectangle(0, 0, w, self.HIGH, fill=C["panel2"], width=0)
        knob = (("#ffb855" if self._hover else C["acc"]) if on else C["line"])
        self.create_rectangle(x, 0, x + self.KNOB, self.HIGH, fill=knob, width=0)

    def _set_x(self, x):
        w = self.winfo_width()
        frac = L.clamp((x - self.KNOB / 2) / max(1, w - self.KNOB), 0, 1)
        self._set_value(self.a + frac * (self.b - self.a))

    def _set_value(self, v):
        if self._state == "disabled":
            return
        v = L.clamp(self.a + round((v - self.a) / self.step) * self.step, self.a, self.b)
        if isinstance(self.step, int) and isinstance(self.a, int):
            v = int(v)
        if v != self._value():
            self.var.set(v)
            self.command()


# límites de ancho de los paneles laterales (así el contenido no se deforma)
PANEL_LIMITS = {"izq": (290, 480), "der": (320, 520)}
PANEL_DEFAULT = {"izq": 290, "der": 320}


class App:
    def __init__(self, root):
        self.root = root
        self.settings = K.load_settings()
        self.mode = K.mode()
        self.official = K.official_info()
        self.passwords: dict = {}           # contraseñas de esta sesión (no se guardan)
        self.themes = L.builtin_themes()
        self.screen = "edit"
        self.sel = "acc"
        self.slot_sel = "keys"
        self.sec_sel = "keys"
        self.template = "keys"
        self.project_path = None
        self.dirty = False
        self._cache: dict = {}
        self._toast_job = None
        self._quiet = False           # True mientras se rellenan los controles (no es un cambio del usuario)
        self._style()
        self.new_theme(initial=True)
        self._build()
        self.render()
        if self.mode == "comunidad":
            root.after(200, self.startup)

    # ================================================================ estado
    def new_theme(self, initial=False):
        base = self.themes[0]
        self.colors = dict(base["colores"])
        self.alpha: dict = {}
        self.window = {"opacidad": 100, "sin_usar": 100}
        self.meta = {"nombre": "Tema nuevo", "version": "1.0", "descripcion": ""}
        self.base_name = base["nombre"]
        self.auto = True
        self.images: dict = {}
        self.grad = {"on": False, "modo": "solido", "colores": [], "desde": "tl", "una_pieza": False,
                     "tinte": L.TINT_DEFAULT}
        self.sections: dict = {}
        self.gif_pause = True
        self.pal_img = L.to_png(L.sample_image())
        self.pal_name = "ejemplo-atardecer.png"
        self.palette = L.extract_palette(L.sample_image())
        self.pal_acc = L.pick_accent(self.palette)
        self.project_path = None
        self.dirty = False
        if not initial:
            self._load_into_widgets()

    def state(self) -> dict:
        return {"nombre": self.meta["nombre"], "version": self.meta["version"], "descripcion": self.meta["descripcion"],
                "base": self.base_name, "colores": self.colors, "alfa": self.alpha, "ventana": self.window,
                "auto": self.auto, "imagenes": self.images, "imagen_colores": self.pal_img,
                "imagen_colores_nombre": self.pal_name, "degradado": self.grad,
                "secciones": L.sections_clean(self.sections), "pausar_animaciones": self.gif_pause}

    def apply_state(self, s: dict):
        self.colors = {**self.themes[0]["colores"], **s.get("colores", {})}
        self.alpha = {k: int(v) for k, v in (s.get("alfa") or {}).items() if k in npt.ALPHA_TOKENS}
        w = s.get("ventana") or {}
        self.window = {"opacidad": int(w.get("opacidad", 100)), "sin_usar": int(w.get("sin_usar", 100))}
        self.meta = {"nombre": s.get("nombre", "Tema"), "version": str(s.get("version", "1.0")),
                     "descripcion": s.get("descripcion", "")}
        self.base_name = s.get("base", self.themes[0]["nombre"])
        self.auto = bool(s.get("auto", False))
        self.images = {k: v for k, v in (s.get("imagenes") or {}).items() if k in npt.IMAGE_SLOTS}
        g = s.get("degradado") or {}
        stops = [[str(c).lower(), L.clamp(int(p), 0, 100)] for c, p in (g.get("colores") or [])
                 if npt._HEX.match(str(c))]
        modo = g.get("modo") or ("degradado" if g.get("on") else "solido")
        if modo == "degradado" and len(stops) < 2 or modo == "imagen" and "fondo" not in self.images \
                or modo not in ("solido", "degradado", "imagen"):
            modo = "solido"
        try:
            tinte = L.clamp(int(g.get("tinte", L.TINT_DEFAULT)), 0, 90)
        except (TypeError, ValueError):
            tinte = L.TINT_DEFAULT
        self.grad = {"on": modo == "degradado", "modo": modo, "colores": stops[:5],
                     "desde": g.get("desde") if g.get("desde") in npt.GRADIENT_FROM else "tl",
                     "una_pieza": bool(g.get("una_pieza", False)), "tinte": tinte}
        self.sections = {}
        for k, v in (s.get("secciones") or {}).items():
            if k in npt.SECTIONS and isinstance(v, dict):
                self.sections[k] = {"fondo": L.clamp(int(v.get("fondo", 100)), 0, 100),
                                    "contenido": L.clamp(int(v.get("contenido", 100)), npt.SECTION_MIN_CONTENT, 100),
                                    "realce": bool(v.get("realce", False))}
        self.gif_pause = bool(s.get("pausar_animaciones", True))
        if s.get("imagen_colores"):
            self.pal_img = s["imagen_colores"]
            self.pal_name = s.get("imagen_colores_nombre", "imagen")
            self._set_palette_from_bytes(self.pal_img, self.pal_name, refresh=False)
        self._load_into_widgets()

    @property
    def author(self) -> str:
        if self.mode == "creador":
            return npt.OFFICIAL_NAME
        return (self.settings.get("nombre") or "").strip()

    def mark(self):
        self.dirty = True
        self._title()

    def _title(self):
        name = os.path.basename(self.project_path) if self.project_path else L.slug(self.meta["nombre"]) + L.PROJECT_EXT
        self.root.title(f"{APP} — {name}{' •' if self.dirty else ''}")

    # ================================================================ estilo
    def _style(self):
        r = self.root
        r.configure(bg=C["bg"])
        r.geometry("1420x900")
        r.minsize(1360, 640)
        s = ttk.Style(r)
        s.theme_use("clam")
        s.configure(".", background=C["panel"], foreground=C["text"], fieldbackground=C["panel2"],
                    bordercolor=C["line"], lightcolor=C["line"], darkcolor=C["line"], font=fnt())
        s.configure("TButton", background=C["panel2"], foreground=C["text"], padding=(11, 5))
        s.map("TButton", background=[("active", C["line"]), ("disabled", C["panel"])],
              foreground=[("disabled", C["muted"])])
        s.configure("Accent.TButton", background=C["acc"], foreground=C["on_acc"], font=fnt(0, True), padding=(14, 6))
        s.map("Accent.TButton", background=[("active", "#ffb855"), ("disabled", C["panel2"])],
              foreground=[("disabled", C["muted"])])
        s.configure("Nav.TButton", background=C["bg"], foreground=C["muted"], padding=(12, 6))
        s.map("Nav.TButton", background=[("active", C["panel2"])])
        s.configure("NavOn.TButton", background=C["acc"], foreground=C["on_acc"], font=fnt(0, True), padding=(12, 6))
        s.map("NavOn.TButton", background=[("active", "#ffb855")])
        s.configure("Small.TButton", background=C["panel2"], foreground=C["text"], padding=(4, 2), font=fnt(-1))
        s.map("Small.TButton", background=[("active", C["line"]), ("disabled", C["panel"])],
              foreground=[("disabled", C["muted"])])
        s.configure("Link.TButton", background=C["panel"], foreground=C["acc"], padding=(0, 0), borderwidth=0)
        s.map("Link.TButton", background=[("active", C["panel"])])
        for st, bg in (("TCheckbutton", C["panel"]), ("Bg.TCheckbutton", C["bg"])):
            s.configure(st, background=bg, foreground=C["text"])
            s.map(st, background=[("active", bg)],
                  indicatorcolor=[("selected", C["acc"]), ("!selected", C["panel2"])])
        s.configure("TCombobox", fieldbackground=C["panel2"], background=C["panel2"], foreground=C["text"],
                    arrowcolor=C["text"], selectbackground=C["panel2"], selectforeground=C["text"])
        s.map("TCombobox", fieldbackground=[("readonly", C["panel2"])], foreground=[("readonly", C["text"])])
        r.option_add("*TCombobox*Listbox.background", C["panel2"])
        r.option_add("*TCombobox*Listbox.foreground", C["text"])
        r.option_add("*TCombobox*Listbox.selectBackground", C["acc_dim"])
        s.configure("Vertical.TScrollbar", background=C["line"], troughcolor=C["panel"], arrowcolor=C["muted"],
                    bordercolor=C["panel"])

    def lbl(self, parent, text="", size=0, bold=False, color="text", bg="panel", wrap=0, mono=False, **kw):
        return tk.Label(parent, text=text, bg=C.get(bg, bg), fg=C.get(color, color), font=fnt(size, bold, mono),
                        justify="left", anchor="w", wraplength=wrap, **kw)

    def caps(self, parent, text, bg="panel"):
        return tk.Label(parent, text=text.upper(), bg=C[bg], fg=C["muted"], font=fnt(-1, True), anchor="w")

    def entry(self, parent, var, width=10):
        return tk.Entry(parent, textvariable=var, width=width, bg=C["panel2"], fg=C["text"],
                        insertbackground=C["text"], relief="flat", highlightthickness=1,
                        highlightbackground=C["line"], highlightcolor=C["acc"], font=fnt())

    def scale(self, parent, var, a, b, step, cmd):
        return Slider(parent, var, a, b, step, cmd)

    def _blank(self, w, h):
        if not hasattr(self, "_blanks"):
            self._blanks = {}
        if (w, h) not in self._blanks:
            self._blanks[(w, h)] = tk.PhotoImage(width=w, height=h)
        return self._blanks[(w, h)]

    def card(self, parent, bg="panel"):
        return tk.Frame(parent, bg=C[bg], highlightthickness=1, highlightbackground=C["line"], padx=12, pady=10)

    def chip(self, parent, text, kind="", bg="bg"):
        fg, b = {"sig": (C["sig_text"], C["sig_bg"]), "ok": (C["ok_text"], C["ok_bg"]),
                 "warn": (C["warn_text"], C["warn_bg"]), "bad": (C["bad_text"], C["bad_bg"])}.get(
            kind, (C["muted"], C[bg]))
        return tk.Label(parent, text=text, bg=b, fg=fg, font=fnt(-1, True), padx=8, pady=2,
                        highlightthickness=1, highlightbackground=C["line"] if not kind else fg)

    def toast(self, msg, kind="muted"):
        self.status.configure(text=msg, fg=C.get(kind, C["muted"]))
        if self._toast_job:
            self.root.after_cancel(self._toast_job)
        self._toast_job = self.root.after(6000, lambda: self.status.configure(text="Listo.", fg=C["muted"]))

    # ================================================================ armado
    def _build(self):
        r = self.root
        for w in r.winfo_children():
            w.destroy()
        r.columnconfigure(0, weight=1)
        r.rowconfigure(2, weight=1)
        head = tk.Frame(r, bg=C["bg"])
        head.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 6))
        tk.Label(head, text=APP, bg=C["bg"], fg=C["text"], font=fnt(8, True)).pack(side="left")
        tk.Label(head, text="para Numpad Macros", bg=C["bg"], fg=C["muted"], font=fnt(1)).pack(side="left", padx=(8, 14),
                                                                                              pady=(6, 0))
        if self.mode == "creador":
            self.chip(head, "● Firmando como OkumaWsX · oficial", "sig").pack(side="left", pady=(4, 0))
        else:
            self.author_chip = self.chip(head, "")
            self.author_chip.pack(side="left", pady=(4, 0))
        self.export_label = "Firmar y exportar .npt" if self.mode == "creador" else "Exportar .npt"
        ttk.Button(head, text=self.export_label, style="Accent.TButton", command=lambda: self.show("exp")).pack(
            side="right")
        ttk.Button(head, text="Guardar proyecto", command=self.save_project).pack(side="right", padx=6)
        ttk.Button(head, text="Abrir…", command=self.open_any).pack(side="right")
        ttk.Button(head, text="＋ Nuevo", command=self.ask_new).pack(side="right", padx=6)

        nav = tk.Frame(r, bg=C["bg"])
        nav.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        self.nav = {}
        key_title = "5 · Clave de firma" if self.mode == "creador" else "5 · Mi firma de autor"
        for sid, text in (("edit", "1 · Editar tema"), ("sec", "2 · Transparencia por sección"),
                          ("img", "3 · Imágenes y plantillas"), ("exp", "4 · Exportar"), ("key", key_title)):
            b = ttk.Button(nav, text=text, style="Nav.TButton", command=lambda s=sid: self.show(s))
            b.pack(side="left", padx=(0, 6))
            self.nav[sid] = b
        pan = self.settings.get("paneles") or {}
        self.panel_state = {}
        for side in ("izq", "der"):
            st = pan.get(side) or {}
            lo, hi = PANEL_LIMITS[side]
            try:
                w = L.clamp(int(st.get("ancho", PANEL_DEFAULT[side])), lo, hi)
            except (TypeError, ValueError):
                w = PANEL_DEFAULT[side]
            self.panel_state[side] = {"visible": st.get("visible", True) is not False, "ancho": w}
        self.panel_sides: dict = {"izq": [], "der": []}       # (panel, borde) de cada pantalla
        self.switch_box = tk.Frame(nav, bg=C["bg"])
        self.switch_box.pack(side="right")
        self.switches = {}
        for side, txt in (("der", "Panel derecho"), ("izq", "Panel izquierdo")):
            s = Switch(self.switch_box, txt, lambda v, sd=side: self.toggle_panel(sd, v),
                       value=self.panel_state[side]["visible"])
            s.pack(side="right", padx=(14, 0))
            self.switches[side] = s

        self.body = tk.Frame(r, bg=C["bg"], highlightthickness=1, highlightbackground=C["line"])
        self.body.grid(row=2, column=0, sticky="nsew", padx=16)
        self.body.rowconfigure(0, weight=1)
        self.body.columnconfigure(0, weight=1)
        self.views = {"edit": self._build_edit(), "sec": self._build_sec(), "img": self._build_img(),
                      "exp": self._build_exp(), "key": self._build_key()}
        self.status = tk.Label(r, text="Listo.", bg=C["bg"], fg=C["muted"], font=fnt(-1), anchor="w")
        self.status.grid(row=3, column=0, sticky="ew", padx=16, pady=(6, 10))
        self.show(self.screen)
        self._title()
        r.bind("<Configure>", self._on_root_configure, add="+")

    def _on_root_configure(self, ev):
        if ev.widget is not self.root:
            return
        size = (ev.width, ev.height)
        if size == getattr(self, "_root_size", None):
            return
        old = getattr(self, "_root_size", None)
        self._root_size = size
        # Arrastrando el borde de a poco las columnas quedan bien; solo un salto grande (maximizar, ajustar
        # a media pantalla, o un arrastre mientras la ventana estaba ocupada) deja partes sin pintar.
        if old and max(abs(size[0] - old[0]), abs(size[1] - old[1])) > 40:
            self._big_jump = True
        job = getattr(self, "_repaint_job", None)
        if job:
            self.root.after_cancel(job)
        self._repaint_job = self.root.after(100, self._repaint_if_jumped)

    def _repaint_if_jumped(self):
        self._repaint_job = None
        if getattr(self, "_big_jump", False):
            self._big_jump = False
            self._repaint_window()

    def _repaint_window(self):
        """Tapa la ventana entera un instante y la destapa: así el sistema obliga a repintar todo lo que
        quedó debajo. Hace falta en KDE (XWayland) tras maximizar: no solo las columnas, también botones
        e interruptores que se corrieron quedaban sin dibujar hasta pasarles el mouse encima."""
        try:
            cover = tk.Frame(self.root, bg=C["bg"])
            cover.place(x=0, y=0, relwidth=1, relheight=1)
            cover.update_idletasks()
            cover.destroy()
        except tk.TclError:
            pass

    def _repaint(self):
        """Después de maximizar o de un salto de tamaño: vuelve a pintar las columnas que se movieron."""
        for s in Scrollable.all:
            try:
                if s.winfo_ismapped() and s.moved():
                    s.refresh()
            except tk.TclError:
                pass

    def show(self, sid):
        self.screen = sid
        for k, v in self.views.items():
            v.grid_remove() if k != sid else v.grid(row=0, column=0, sticky="nsew")
        for k, b in self.nav.items():
            b.configure(style="NavOn.TButton" if k == sid else "Nav.TButton")
        if sid == "exp":
            self.exp_done.pack_forget()
        if sid in ("edit", "sec", "img"):
            if not self.switch_box.winfo_manager():
                self.switch_box.pack(side="right")
        else:
            self.switch_box.pack_forget()
        self.render()
        self.root.after(80, self._repaint)
        for sc in getattr(self, "stages", []):          # la vista previa de esta pantalla, a su tamaño
            if sc.winfo_ismapped() or sc.master is self.views.get(sid):
                self._fit_soon(sc)

    # ---------------------------------------------------------------- 1 · editar
    def _build_edit(self):
        f = tk.Frame(self.body, bg=C["panel"])
        f.columnconfigure(1, weight=1, minsize=360)
        f.rowconfigure(0, weight=1)
        # izquierda: capas
        left = Scrollable(f, C["panel"], width=290)
        left.grid(row=0, column=0, sticky="nsw")
        L_ = left.inner
        pad = dict(padx=12, sticky="ew")
        self.caps(L_, "Partir de").grid(row=0, column=0, pady=(12, 4), **pad)
        self.base_var = tk.StringVar(value=self.base_name)
        cb = ttk.Combobox(L_, textvariable=self.base_var, state="readonly", values=[t["nombre"] for t in self.themes])
        cb.grid(row=1, column=0, **pad)
        cb.bind("<<ComboboxSelected>>", lambda e: self.load_base(self.base_var.get()))
        self.auto_var = tk.BooleanVar(value=self.auto)
        ttk.Checkbutton(L_, text="Derivar tonos del acento (A)", variable=self.auto_var,
                        command=self.on_auto).grid(row=2, column=0, pady=(8, 2), **pad)
        self.rows = {}
        row = 3
        for gname, items in GROUPS:
            self.lbl(L_, gname, 0, True).grid(row=row, column=0, pady=(10, 2), **pad)
            row += 1
            for tok, label in items:
                self.rows[tok] = self._token_row(L_, tok, label)
                self.rows[tok]["frame"].grid(row=row, column=0, padx=6, sticky="ew")
                row += 1
        self.grad_box = tk.Frame(L_, bg=C["panel"])
        self.grad_box.grid(row=row, column=0, pady=(14, 0), **pad)
        self._build_grad(self.grad_box)
        self.edit_left = left
        row += 1
        wf = tk.Frame(L_, bg=C["panel"])
        wf.grid(row=row, column=0, pady=(14, 14), **pad)
        wf.columnconfigure(0, weight=1)
        top = tk.Frame(wf, bg=C["panel"])
        top.grid(row=0, column=0, sticky="ew")
        self.lbl(top, "Ventana", 0, True).pack(side="left")
        ttk.Button(top, text="Todo opaco", style="Link.TButton", command=self.all_opaque).pack(side="right")
        self.win_var = tk.IntVar(value=self.window["opacidad"])
        self.idle_var = tk.IntVar(value=self.window["sin_usar"])
        for i, (txt, var) in enumerate((("Opacidad de la ventana", self.win_var),
                                        ("Opacidad cuando no la usas", self.idle_var))):
            line = tk.Frame(wf, bg=C["panel"])
            line.grid(row=1 + i * 2, column=0, sticky="ew", pady=(8, 0))
            self.lbl(line, txt, -1).pack(side="left")
            out = self.lbl(line, "", -1, color="muted", mono=True)
            out.pack(side="right")
            setattr(self, "win_out" if i == 0 else "idle_out", out)
            self.scale(wf, var, npt.WINDOW_MIN, 100, 5, self.on_window).grid(row=2 + i * 2, column=0, sticky="ew")
        self.try_alpha = tk.BooleanVar(value=False)
        ttk.Checkbutton(wf, text="Probar la opacidad en esta ventana", variable=self.try_alpha,
                        command=self.on_window).grid(row=5, column=0, sticky="w", pady=(8, 0))
        self.lbl(wf, "Igual que el Laboratorio de Numpad Macros: la ventana deja ver el escritorio y se vuelve más "
                     "transparente cuando el mouse sale. Cada color de arriba tiene además su propia transparencia: "
                     "tócalo y aparece su barra.", -2, color="muted", wrap=260).grid(row=6, column=0, sticky="ew",
                                                                                        pady=(6, 0))
        self.lbl(wf, "Para resaltar una parte de la ventana, usa la pantalla «2 · Transparencia por sección».", -2,
                 color="muted", wrap=260).grid(row=7, column=0, sticky="ew", pady=(6, 0))
        # centro: vista previa
        mid = self._stage(f, "Vista previa · ventana principal",
                          "Toca cualquier parte de la ventana para editar su color.")
        top = mid.top
        self.hover_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Botón al pasar el mouse", variable=self.hover_var, command=self.render).pack(
            side="right")
        self.wall_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Fondo de escritorio", variable=self.wall_var, command=self.render).pack(
            side="right", padx=10)
        self.cv_edit, self.pv_edit = mid.pcv, mid.pv
        self.cv_edit.bind("<Button-1>", self.on_preview_click)
        # derecha
        right = Scrollable(f, C["panel"], width=320)
        right.grid(row=0, column=2, sticky="nse")
        R = right.inner
        R.columnconfigure(0, weight=1)
        self.caps(R, "Colores desde una imagen").grid(row=0, column=0, padx=12, pady=(12, 4), sticky="ew")
        pc = self.card(R)
        pc.grid(row=1, column=0, padx=12, sticky="ew")
        self.pal_card = pc
        top = tk.Frame(pc, bg=C["panel"])
        top.pack(fill="x")
        self.pal_thumb = tk.Label(top, bg="#0d0e11", image=self._blank(96, 60), width=96, height=60)
        self.pal_thumb.pack(side="left")
        side = tk.Frame(top, bg=C["panel"])
        side.pack(side="left", padx=10, fill="x", expand=True)
        ttk.Button(side, text="Importar…", command=self.import_palette_image).pack(anchor="w")
        self.pal_name_lbl = self.lbl(side, "", -2, color="muted")
        self.pal_name_lbl.pack(anchor="w", pady=(6, 0))
        self.pal_row = tk.Frame(pc, bg=C["panel"])
        self.pal_row.pack(fill="x", pady=(10, 2))
        self.lbl(pc, "Colores principales, del más usado al menos usado. Toca uno para elegirlo como acento.",
                 -2, color="muted", wrap=250).pack(fill="x", pady=(4, 6))
        line = tk.Frame(pc, bg=C["panel"])
        line.pack(fill="x")
        self.pal_mode = tk.StringVar(value="Tema oscuro")
        ttk.Combobox(line, textvariable=self.pal_mode, state="readonly", width=12,
                     values=("Tema oscuro", "Tema claro")).pack(side="left")
        ttk.Button(line, text="Aplicar", style="Accent.TButton", command=self.apply_palette).pack(
            side="right")
        self.pal_fix = tk.BooleanVar(value=True)
        ttk.Checkbutton(pc, text="Corregir solo lo que quede ilegible", variable=self.pal_fix).pack(anchor="w",
                                                                                                   pady=(8, 0))
        if TkinterDnD:
            try:
                pc.drop_target_register(DND_FILES)
                pc.dnd_bind("<<Drop>>", self.on_drop_palette)
                self.lbl(pc, "También puedes arrastrar una imagen aquí.", -2, color="muted").pack(anchor="w",
                                                                                                 pady=(4, 0))
            except Exception:
                pass

        self.caps(R, "Datos del tema").grid(row=2, column=0, padx=12, pady=(16, 4), sticky="ew")
        md = tk.Frame(R, bg=C["panel"])
        md.grid(row=3, column=0, padx=12, sticky="ew")
        md.columnconfigure(0, weight=1)
        md.columnconfigure(1, weight=1)
        self.name_var = tk.StringVar(value=self.meta["nombre"])
        self.ver_var = tk.StringVar(value=self.meta["version"])
        self.desc_var = tk.StringVar(value=self.meta["descripcion"])
        self.lbl(md, "Nombre", -1, color="muted").grid(row=0, column=0, columnspan=2, sticky="w")
        self.entry(md, self.name_var).grid(row=1, column=0, columnspan=2, sticky="ew", ipady=3)
        self.lbl(md, "Versión", -1, color="muted").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.lbl(md, "Tipo", -1, color="muted").grid(row=2, column=1, sticky="w", pady=(6, 0), padx=(8, 0))
        self.entry(md, self.ver_var, 6).grid(row=3, column=0, sticky="ew", ipady=3)
        self.kind_lbl = self.lbl(md, "", 0, bg="panel2", padx=8, pady=3)
        self.kind_lbl.grid(row=3, column=1, sticky="ew", padx=(8, 0))
        if self.mode == "creador":
            self.lbl(md, "Autor", -1, color="muted").grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))
            self.lbl(md, "✔ OkumaWsX · oficial", 0, bg="panel2", color="sig_text", padx=8, pady=3).grid(
                row=5, column=0, columnspan=2, sticky="ew")
        else:
            self.lbl(md, "Tu nombre de autor", -1, color="muted").grid(row=4, column=0, columnspan=2, sticky="w",
                                                                       pady=(6, 0))
            self.author_var = tk.StringVar(value=self.settings.get("nombre", ""))
            self.entry(md, self.author_var).grid(row=5, column=0, columnspan=2, sticky="ew", ipady=3)
            self.author_note = self.lbl(md, "", -2, color="muted", wrap=255)
            self.author_note.grid(row=6, column=0, columnspan=2, sticky="ew")
            self.author_var.trace_add("write", lambda *a: self.on_author())
        self.lbl(md, "Descripción", -1, color="muted").grid(row=7, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.entry(md, self.desc_var).grid(row=8, column=0, columnspan=2, sticky="ew", ipady=3)
        for v in (self.name_var, self.ver_var, self.desc_var):
            v.trace_add("write", lambda *a: self.on_meta())

        self.caps(R, "Legibilidad").grid(row=4, column=0, padx=12, pady=(16, 4), sticky="ew")
        lc = self.card(R)
        lc.grid(row=5, column=0, padx=12, pady=(0, 14), sticky="ew")
        self.leg_rows = tk.Frame(lc, bg=C["panel"])
        self.leg_rows.pack(fill="x")
        self.leg_sum = self.lbl(lc, "", -1, wrap=255)
        self.leg_sum.pack(fill="x", pady=(8, 0))
        self._paint_palette()
        self._panels(f, left, mid, right)
        return f

    def _stage(self, f, title, hint):
        """Columna central con la vista previa. No se desplaza: la vista previa se ajusta al espacio."""
        sc = tk.Frame(f, bg=C["panel"])
        sc.grid(row=0, column=1, sticky="nsew", padx=10)
        sc.pack_propagate(False)            # su tamaño lo pone la ventana, no la vista previa
        mid = sc
        top = tk.Frame(mid, bg=C["panel"])
        top.pack(fill="x", pady=(12, 4))
        self.caps(top, title).pack(side="left")
        sc.hint = self.lbl(mid, hint, -1, color="muted", wrap=V.W)
        sc.hint.pack(fill="x")
        cv = tk.Canvas(mid, width=V.W, height=V.H, highlightthickness=0, bd=0, cursor="hand2", bg="#0d0e11")
        cv.pack(expand=True)                # centrada en el espacio que queda
        sc.top, sc.pcv, sc.pv = top, cv, V.Preview(cv)
        sc.bind("<Configure>", lambda e, s=sc: self._fit_soon(s), add="+")
        self.__dict__.setdefault("stages", []).append(sc)
        return sc

    # ---------------------------------------------------------------- paneles laterales
    def _panels(self, f, left, mid, right):
        """Panel izquierdo · borde · vista previa · borde · panel derecho. Los bordes se arrastran para
        cambiar el ancho (con límites) y los interruptores de arriba muestran u ocultan cada panel."""
        for c in range(5):
            f.columnconfigure(c, weight=0, minsize=0)
        f.columnconfigure(2, weight=1, minsize=360)
        left.grid(row=0, column=0, sticky="nsw")
        mid.grid(row=0, column=2, sticky="nsew", padx=10)
        right.grid(row=0, column=4, sticky="nse")
        for side, panel, col in (("izq", left, 1), ("der", right, 3)):
            grip = tk.Frame(f, bg=C["line"], width=5, cursor="sb_h_double_arrow")
            grip.grid(row=0, column=col, sticky="ns")
            grip.bind("<Enter>", lambda e, g=grip: g.configure(bg=C["acc_dim"]))
            grip.bind("<Leave>", lambda e, g=grip: g.configure(bg=C["line"]))
            grip.bind("<ButtonPress-1>", lambda e, sd=side: self._drag_start(sd, e))
            grip.bind("<B1-Motion>", lambda e, sd=side: self._drag(sd, e))
            grip.bind("<ButtonRelease-1>", lambda e: self._save_panels())
            self.panel_sides[side].append((panel, grip))
            self._apply_panel(side)

    def _apply_panel(self, side):
        """Muestra u oculta el panel de ese lado en las tres pantallas, con su ancho."""
        st = self.panel_state[side]
        shown = False
        for panel, grip in self.panel_sides[side]:
            if st["visible"]:
                panel.cv.configure(width=st["ancho"])
                if not panel.winfo_manager():
                    panel.grid()
                    grip.grid()
                    shown = True
            elif panel.winfo_manager():
                panel.grid_remove()
                grip.grid_remove()
                shown = True
        if not shown:
            return
        # Al ocultar, Tk a veces no reparte otra vez el espacio: volver a ubicar la pantalla visible la
        # reacomoda (las otras se reacomodan solas al mostrarlas).
        f = getattr(self, "views", {}).get(self.screen)
        try:
            if f is not None and f.winfo_manager() == "grid":
                f.grid_remove()
                f.grid()
        except tk.TclError:                      # la ventana se está rearmando
            pass

    def _resize_panel(self, side):
        """Arrastrando el borde: solo cambia el ancho (sin esconder nada, para que se mueva suave)."""
        w = self.panel_state[side]["ancho"]
        for panel, _grip in self.panel_sides[side]:
            panel.cv.configure(width=w)

    def toggle_panel(self, side, visible):
        self.panel_state[side]["visible"] = bool(visible)
        self._apply_panel(side)
        self._save_panels()
        self.root.after(80, self._repaint_window)

    def _drag_start(self, side, e):
        self._drag_from = (e.x_root, self.panel_state[side]["ancho"])

    def _drag(self, side, e):
        x0, w0 = getattr(self, "_drag_from", (e.x_root, self.panel_state[side]["ancho"]))
        dx = e.x_root - x0
        lo, hi = PANEL_LIMITS[side]
        w = L.clamp(w0 + (dx if side == "izq" else -dx), lo, hi)
        if w != self.panel_state[side]["ancho"]:
            self.panel_state[side]["ancho"] = w
            if not getattr(self, "_drag_job", None):       # un solo ajuste por cuadro, aunque el mouse mande más
                self._drag_job = self.root.after_idle(lambda: self._drag_apply(side))

    def _drag_apply(self, side):
        self._drag_job = None
        self._resize_panel(side)

    def _save_panels(self):
        self.settings["paneles"] = {k: dict(v) for k, v in self.panel_state.items()}
        try:
            K.save_settings(self.settings)
        except OSError:
            pass

    def _fit_soon(self, sc):
        job = getattr(sc, "_fit_job", None)
        if job:
            self.root.after_cancel(job)
        # después del repintado de las columnas (100 ms), para que dibujar la vista previa no lo retrase
        sc._fit_job = self.root.after(160, lambda: self._fit_stage(sc))

    def _fit_stage(self, sc):
        """La vista previa crece o se achica para caber entera en su columna (hasta 2×)."""
        sc._fit_job = None
        try:
            aw = sc.winfo_width() - 8
            ah = sc.winfo_height() - (sc.hint.winfo_y() + sc.hint.winfo_height()) - 16
            sc.hint.configure(wraplength=max(200, aw))
        except tk.TclError:
            return
        if aw < 100 or ah < 100:
            return
        if sc.pv.set_scale(min(aw / V.W, ah / V.H)):
            w, h = sc.pv.size
            sc.pcv.configure(width=w, height=h)
            # solo cambió el tamaño: se reduce otra vez el último dibujo (si hay cambios pendientes, el
            # dibujo completo llega igual con render())
            if not (sc.winfo_ismapped() and sc.pv.rescale()):
                self.render()

    # ---------------------------------------------------------------- fondo de la ventana (degradado)
    def _build_grad(self, box):
        box.columnconfigure(0, weight=1)
        self.lbl(box, "Fondo de la ventana", 0, True).grid(row=0, column=0, sticky="w")
        seg = tk.Frame(box, bg=C["line"])
        seg.grid(row=1, column=0, sticky="ew", pady=(4, 6))
        self.grad_seg = {}
        for i, (key, txt) in enumerate((("solido", "Sólido"), ("degradado", "Degradado"), ("imagen", "Imagen"))):
            seg.columnconfigure(i, weight=1, uniform="g")
            b = tk.Label(seg, text=txt, font=fnt(-1), cursor="hand2", pady=5, width=7)
            b.grid(row=0, column=i, sticky="ew", padx=(0 if i else 1, 1), pady=1)
            b.bind("<Button-1>", lambda e, m=key: self.bg_mode(m))
            self.grad_seg[key] = b
        # imagen de fondo
        self.bgimg_ed = tk.Frame(box, bg=C["panel"])
        self.bgimg_ed.columnconfigure(0, weight=1)
        top = tk.Frame(self.bgimg_ed, bg=C["panel"])
        top.grid(row=0, column=0, sticky="ew")
        self.bgimg_thumb = tk.Label(top, bg="#0d0e11", image=self._blank(96, 60), width=96, height=60)
        self.bgimg_thumb.pack(side="left")
        side = tk.Frame(top, bg=C["panel"])
        side.pack(side="left", padx=(8, 0), fill="x", expand=True)
        ttk.Button(side, text="Subir imagen…", style="Small.TButton", command=self.bg_upload).pack(fill="x")
        ttk.Button(side, text="La importada", style="Small.TButton", command=self.bg_from_imported).pack(
            fill="x", pady=3)
        ttk.Button(side, text="Generar con la paleta", style="Small.TButton", command=self.bg_generate).pack(
            fill="x")
        line = tk.Frame(self.bgimg_ed, bg=C["panel"])
        line.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.lbl(line, "Oscurecer la imagen", -1).pack(side="left")
        self.bgdark_out = self.lbl(line, "", -1, color="muted", mono=True)
        self.bgdark_out.pack(side="right")
        self.bgdark_var = tk.IntVar(value=0)
        self.bgdark_scale = self.scale(self.bgimg_ed, self.bgdark_var, 0, 90, 5, self.on_bg_dark)
        self.bgdark_scale.grid(row=2, column=0, sticky="ew")
        self.bgimg_note = self.lbl(self.bgimg_ed, "", -2, color="muted", wrap=255)
        self.bgimg_note.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        # fondo de una pieza (con degradado o imagen)
        self.onep_box = tk.Frame(box, bg=C["panel"])
        self.onep_box.columnconfigure(0, weight=1)
        self.onep_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.onep_box, text="Fondo de una pieza", variable=self.onep_var,
                        command=self.on_one_piece).grid(row=0, column=0, sticky="w")
        self.lbl(self.onep_box, "El fondo pasa también por detrás del panel de teclas, las pestañas y su contenido, "
                                "como si toda la ventana fuera una sola imagen.", -2, color="muted",
                 wrap=255).grid(row=1, column=0, sticky="ew", pady=(2, 0))
        line = tk.Frame(self.onep_box, bg=C["panel"])
        line.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.tint_lbl = self.lbl(line, "Tinte de los paneles", -1)
        self.tint_lbl.pack(side="left")
        self.tint_out = self.lbl(line, "", -1, color="muted", mono=True)
        self.tint_out.pack(side="right")
        self.tint_var = tk.IntVar(value=L.TINT_DEFAULT)
        self.tint_scale = self.scale(self.onep_box, self.tint_var, 0, 90, 5, self.on_tint)
        self.tint_scale.grid(row=3, column=0, sticky="ew")
        self.lbl(self.onep_box, "Cuánto se tiñen los paneles con su color para que el texto se lea. Los campos, "
                                "botones, listas y tarjetas quedan con sus colores encima.", -2, color="muted",
                 wrap=255).grid(row=4, column=0, sticky="ew", pady=(2, 0))
        self.grad_ed = tk.Frame(box, bg=C["panel"])
        self.grad_ed.columnconfigure(0, weight=1)
        self.grad_bar = tk.Canvas(self.grad_ed, width=200, height=20, highlightthickness=1,
                                  highlightbackground="#3a3e48", bd=0)
        self.grad_bar.grid(row=0, column=0, sticky="ew")
        self.grad_bar.bind("<Configure>", lambda e: self._paint_grad_bar())
        self.grad_rows = tk.Frame(self.grad_ed, bg=C["panel"])
        self.grad_rows.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.grad_rows.columnconfigure(1, weight=1)
        btns = tk.Frame(self.grad_ed, bg=C["panel"])
        btns.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        btns.columnconfigure(0, weight=1, uniform="b")
        btns.columnconfigure(1, weight=1, uniform="b")
        self.grad_add = ttk.Button(btns, text="＋ Agregar color", style="Small.TButton", command=self.grad_add_stop)
        self.grad_add.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Button(btns, text="Colores del tema", style="Small.TButton", command=self.grad_theme).grid(
            row=1, column=0, sticky="ew", pady=(4, 0), padx=(0, 2))
        ttk.Button(btns, text="De la imagen", style="Small.TButton", command=self.grad_image).grid(
            row=1, column=1, sticky="ew", pady=(4, 0), padx=(2, 0))
        self.lbl(self.grad_ed, "Desde dónde empieza: termina en el lado opuesto. El centro hace un degradado circular.",
                 -2, color="muted", wrap=255).grid(row=3, column=0, sticky="ew", pady=(8, 4))
        dirs = tk.Frame(self.grad_ed, bg=C["panel"])
        dirs.grid(row=4, column=0, sticky="ew")
        grid = tk.Frame(dirs, bg=C["panel"])
        grid.pack(side="left")
        self.grad_dirs = {}
        for i, d in enumerate(npt.GRADIENT_FROM):
            b = tk.Label(grid, text=L.GRADIENT_DIRS[d][0], font=fnt(1), width=3, pady=3, cursor="hand2",
                         highlightthickness=1, highlightbackground=C["line"])
            b.grid(row=i // 3, column=i % 3, padx=2, pady=2)
            b.bind("<Button-1>", lambda e, dd=d: self.grad_from(dd))
            self.grad_dirs[d] = b
        self.grad_note = self.lbl(dirs, "", -2, color="muted", wrap=140)
        self.grad_note.pack(side="left", padx=10)
        self.lbl(self.grad_ed, "En Numpad Macros se ve en el borde de la ventana, el encabezado, el pie y detrás de las "
                               "teclas. Los paneles se mezclan con el color promedio del degradado.", -2, color="muted",
                 wrap=255).grid(row=5, column=0, sticky="ew", pady=(8, 0))
        self._grad_count = -1

    # ---------------------------------------------------------------- 2 · secciones
    def _build_sec(self):
        f = tk.Frame(self.body, bg=C["panel"])
        f.columnconfigure(1, weight=1, minsize=360)
        f.rowconfigure(0, weight=1)
        left = Scrollable(f, C["panel"], width=290)
        left.grid(row=0, column=0, sticky="nsw")
        LL = left.inner
        LL.columnconfigure(0, weight=1)
        self.caps(LL, "Secciones").grid(row=0, column=0, padx=12, pady=(12, 4), sticky="ew")
        self.lbl(LL, "Cada sección tiene su propia transparencia: el fondo (la plancha de la sección) y el contenido "
                     "(textos, campos y botones). Toca una sección en la lista o en la vista previa.", -2,
                 color="muted", wrap=260).grid(row=1, column=0, padx=12, sticky="ew")
        self.sec_rows = {}
        for i, (k, (name, note)) in enumerate(L.SECTIONS.items()):
            fr = tk.Frame(LL, bg=C["panel"], highlightthickness=1, highlightbackground=C["panel"], padx=8, pady=6,
                          cursor="hand2")
            fr.grid(row=2 + i, column=0, padx=6, pady=2, sticky="ew")
            fr.columnconfigure(0, weight=1)
            head = tk.Frame(fr, bg=C["panel"])
            head.grid(row=0, column=0, sticky="ew")
            nm = tk.Label(head, text=name, bg=C["panel"], fg=C["text"], font=fnt(0, True), anchor="w")
            nm.pack(side="left")
            code = tk.Label(head, text="", bg=C["panel"], fg=C["muted"], font=fnt(-3, mono=True))
            code.pack(side="right")
            nt = tk.Label(fr, text=note, bg=C["panel"], fg=C["muted"], font=fnt(-2), anchor="w", justify="left",
                          wraplength=245)
            nt.grid(row=1, column=0, sticky="ew")
            vars_ = {}
            for j, (key, txt, a) in enumerate((("fondo", "Fondo", 0), ("contenido", "Contenido",
                                                                        npt.SECTION_MIN_CONTENT))):
                line = tk.Frame(fr, bg=C["panel"])
                line.grid(row=2 + j * 2, column=0, sticky="ew", pady=(4, 0))
                tk.Label(line, text=txt, bg=C["panel"], fg=C["text"], font=fnt(-1)).pack(side="left")
                out = tk.Label(line, text="", bg=C["panel"], fg=C["muted"], font=fnt(-2, mono=True))
                out.pack(side="right")
                var = tk.IntVar(value=100)
                self.scale(fr, var, a, 100, 1, lambda kk=k: self.on_section(kk)).grid(row=3 + j * 2, column=0,
                                                                                    sticky="ew")
                vars_[key] = (var, out, line)
            rv = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(fr, text="Borde de realce", variable=rv, command=lambda kk=k: self.on_section(kk))
            cb.grid(row=6, column=0, sticky="w", pady=(4, 0))
            for w in (fr, head, nm, code, nt):
                w.bind("<Button-1>", lambda e, kk=k: self.select_section(kk))
            self.sec_rows[k] = {"frame": fr, "head": head, "name": nm, "code": code, "note": nt, "vars": vars_,
                                "realce": rv, "check": cb}
        mid = self._stage(f, "Vista previa · toca una sección",
                          "Las secciones con transparencia se mezclan con lo que tienen debajo. Prueba «Destacar» "
                          "para resaltar una sola.")
        self.cv_sec, self.pv_sec = mid.pcv, mid.pv
        self.cv_sec.bind("<Button-1>", self.on_section_click)
        right = Scrollable(f, C["panel"], width=320)
        right.grid(row=0, column=2, sticky="nse")
        R = right.inner
        R.columnconfigure(0, weight=1)
        self.caps(R, "Resaltar").grid(row=0, column=0, padx=12, pady=(12, 4), sticky="ew")
        c = self.card(R)
        c.grid(row=1, column=0, padx=12, sticky="ew")
        self.focus_btn = ttk.Button(c, text="", style="Accent.TButton", command=self.focus_section)
        self.focus_btn.pack(fill="x")
        self.lbl(c, "Deja la sección elegida a todo color, con borde de realce, y atenúa las demás.", -2,
                 color="muted", wrap=250).pack(fill="x", pady=(6, 8))
        self.caps(c, "Estilos rápidos").pack(fill="x", pady=(0, 4))
        for pid, (name, _v) in L.PRESETS.items():
            ttk.Button(c, text=name, command=lambda q=pid: self.apply_preset(q)).pack(fill="x", pady=2)
        self.caps(R, "Legibilidad de las secciones").grid(row=2, column=0, padx=12, pady=(16, 4), sticky="ew")
        c2 = self.card(R)
        c2.grid(row=3, column=0, padx=12, sticky="ew")
        self.sec_checks = tk.Frame(c2, bg=C["panel"])
        self.sec_checks.pack(fill="x")
        self.sec_sum = self.lbl(c2, "", -1, wrap=250)
        self.sec_sum.pack(fill="x", pady=(8, 0))
        self.lbl(R, "En Numpad Macros, el encabezado y las teclas dejan ver su imagen (si tienen una) a través del "
                    "fondo. Las demás secciones se mezclan con el fondo de la ventana. El escritorio se ve con la "
                    "opacidad de la ventana (pantalla 1).", -2, color="muted", wrap=260).grid(
            row=4, column=0, padx=12, pady=(12, 14), sticky="ew")
        self._panels(f, left, mid, right)
        return f

    def _token_row(self, parent, tok, label):
        fr = tk.Frame(parent, bg=C["panel"], highlightthickness=1, highlightbackground=C["panel"], cursor="hand2")
        fr.columnconfigure(1, weight=1)
        sw = tk.Canvas(fr, width=26, height=18, highlightthickness=1, highlightbackground="#3a3e48", bd=0,
                       cursor="hand2")
        sw.grid(row=0, column=0, padx=(6, 8), pady=4)
        name = tk.Label(fr, text=label, bg=C["panel"], fg=C["text"], font=fnt(-1), anchor="w")
        name.grid(row=0, column=1, sticky="ew")
        val = tk.Label(fr, text="", bg=C["panel"], fg=C["muted"], font=fnt(-3, mono=True), anchor="e", justify="right",
                       width=9)
        val.grid(row=0, column=2, padx=(4, 6))
        extra = tk.Frame(fr, bg=C["panel"])
        hexv = tk.StringVar()
        ent = self.entry(extra, hexv, 8)
        ent.grid(row=0, column=0, padx=(6, 6), ipady=2)
        ent.bind("<Return>", lambda e, t=tok: self.on_hex(t))
        ent.bind("<FocusOut>", lambda e, t=tok: self.on_hex(t))
        av = tk.IntVar(value=100)
        if tok != "bg":
            sc = self.scale(extra, av, 0, 100, 5, lambda t=tok: self.on_alpha(t))
            sc.grid(row=0, column=1, sticky="ew")
            note = f"Transparencia: se mezcla con {PARENT_NAME.get(npt.PARENT[tok], 'la capa de abajo')}."
        else:
            note = "El fondo usa la opacidad de la ventana (abajo)."
        extra.columnconfigure(1, weight=1)
        tk.Label(extra, text=note, bg=C["panel"], fg=C["muted"], font=fnt(-2), anchor="w").grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=(2, 4))
        for w in (fr, name, val):
            w.bind("<Button-1>", lambda e, t=tok: self.select(t))
        sw.bind("<Button-1>", lambda e, t=tok: self.pick_color(t))
        return {"frame": fr, "sw": sw, "name": name, "val": val, "extra": extra, "hex": hexv, "alpha": av}

    # ---------------------------------------------------------------- 3 · imágenes
    def _build_img(self):
        f = tk.Frame(self.body, bg=C["panel"])
        f.columnconfigure(1, weight=1, minsize=360)
        f.rowconfigure(0, weight=1)
        left = Scrollable(f, C["panel"], width=290)
        left.grid(row=0, column=0, sticky="nsw")
        LL = left.inner
        LL.columnconfigure(0, weight=1)
        self.caps(LL, "Plantillas").grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        self.tpl_box = tk.Frame(LL, bg=C["panel"])
        self.tpl_box.grid(row=1, column=0, padx=9, sticky="ew")
        self.caps(LL, "Espacios para imágenes").grid(row=2, column=0, padx=12, pady=(14, 2), sticky="ew")
        self.slot_box = tk.Frame(LL, bg=C["panel"])
        self.slot_box.grid(row=3, column=0, padx=6, sticky="ew")
        self.caps(LL, "Toda la ventana").grid(row=4, column=0, padx=12, pady=(10, 2), sticky="ew")
        gr = tk.Frame(LL, bg=C["panel"], padx=6, pady=4, cursor="hand2")
        gr.grid(row=5, column=0, padx=6, pady=(0, 14), sticky="ew")
        self.grad_mini = tk.Canvas(gr, width=40, height=26, highlightthickness=1, highlightbackground="#4a505c", bd=0)
        self.grad_mini.pack(side="left")
        box = tk.Frame(gr, bg=C["panel"])
        box.pack(side="left", padx=8)
        a1 = tk.Label(box, text="Fondo de toda la ventana", bg=C["panel"], fg=C["text"], font=fnt(-1), anchor="w")
        a1.pack(anchor="w")
        self.grad_mini_t = tk.Label(box, text="", bg=C["panel"], fg=C["muted"], font=fnt(-2), anchor="w",
                                    justify="left", wraplength=200)
        self.grad_mini_t.pack(anchor="w")
        for w in (gr, self.grad_mini, box, a1, self.grad_mini_t):
            w.bind("<Button-1>", lambda e: self.goto_gradient())

        mid = self._stage(f, "Vista previa · toca un espacio para editarlo",
                          "Los espacios marcados con + están libres: una imagen ahí nunca tapa botones. Admiten PNG, "
                          "JPG y GIF animado.")
        self.idle_view = tk.BooleanVar(value=False)
        ttk.Checkbutton(mid.top, text="Ver como cuando no usas la ventana", variable=self.idle_view,
                        command=self.render).pack(side="right")
        self.cv_img, self.pv_img = mid.pcv, mid.pv
        self.cv_img.bind("<Button-1>", self.on_zone_click)

        right = Scrollable(f, C["panel"], width=320)
        right.grid(row=0, column=2, sticky="nse")
        R = right.inner
        R.columnconfigure(0, weight=1)
        self.slot_title = self.caps(R, "")
        self.slot_title.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        sc = self.card(R)
        sc.grid(row=1, column=0, padx=12, sticky="ew")
        top = tk.Frame(sc, bg=C["panel"])
        top.pack(fill="x")
        self.slot_thumb = tk.Label(top, bg="#0d0e11", image=self._blank(96, 60), width=96, height=60)
        self.slot_thumb.pack(side="left")
        side = tk.Frame(top, bg=C["panel"])
        side.pack(side="left", padx=10)
        ttk.Button(side, text="Imagen o GIF…", command=self.import_slot_image).pack(anchor="w", fill="x")
        ttk.Button(side, text="La de los colores", command=self.slot_use_palette).pack(anchor="w", fill="x", pady=4)
        self.slot_size = self.lbl(sc, "", -2, color="muted", wrap=260)
        self.slot_size.pack(fill="x", pady=(8, 4))
        self.lbl(sc, "Ajuste", -1, color="muted").pack(anchor="w")
        self.fit_var = tk.StringVar()
        self.fit_cb = ttk.Combobox(sc, textvariable=self.fit_var, state="readonly", values=list(L.FITS.values()))
        self.fit_cb.pack(fill="x")
        self.fit_cb.bind("<<ComboboxSelected>>", lambda e: self.on_slot_setting())
        self.slot_vars = {}
        for key, txt, a, b_, step, unit in (("op", "Opacidad", 10, 100, 5, " %"),
                                            ("dark", "Oscurecer con el color de fondo", 0, 90, 5, " %"),
                                            ("blur", "Desenfoque", 0, 12, 1, " px")):
            line = tk.Frame(sc, bg=C["panel"])
            line.pack(fill="x", pady=(8, 0))
            self.lbl(line, txt, -1).pack(side="left")
            out = self.lbl(line, "", -1, color="muted", mono=True)
            out.pack(side="right")
            var = tk.IntVar()
            s = self.scale(sc, var, a, b_, step, self.on_slot_setting)
            s.pack(fill="x")
            self.slot_vars[key] = (var, out, unit, s)
        self.slot_del = ttk.Button(sc, text="Quitar imagen", command=self.slot_remove)
        self.slot_del.pack(anchor="w", pady=(10, 0))

        self.caps(R, "Animaciones (GIF)").grid(row=2, column=0, padx=12, pady=(16, 6), sticky="ew")
        ac = self.card(R)
        ac.grid(row=3, column=0, padx=12, sticky="ew")
        self.gif_pause_var = tk.BooleanVar(value=self.gif_pause)
        ttk.Checkbutton(ac, text="Pausar al no usar la ventana", variable=self.gif_pause_var,
                        command=self.on_gif_pause).pack(anchor="w")
        self.lbl(ac, "Ahorra procesador y batería. Se reproducen en bucle a su velocidad original. Máximo "
                     f"{npt.MAX_FRAMES} cuadros por GIF.", -2,
                 color="muted", wrap=260).pack(fill="x", pady=(6, 0))
        self.caps(R, "Peso del tema").grid(row=4, column=0, padx=12, pady=(16, 6), sticky="ew")
        self.weight_lbl = self.lbl(R, "", -1, wrap=270)
        self.weight_lbl.grid(row=5, column=0, padx=12, sticky="ew")
        self.lbl(R, "El Estudio deja cada imagen lista (recortada, oscurecida y desenfocada) antes de guardarla, "
                    "así Numpad Macros solo tiene que mostrarla.", -2, color="muted", wrap=270).grid(
            row=6, column=0, padx=12, pady=(12, 14), sticky="ew")
        self._panels(f, left, mid, right)
        return f

    # ---------------------------------------------------------------- 4 · exportar
    def _build_exp(self):
        f = tk.Frame(self.body, bg=C["panel"], padx=18, pady=16)
        f.columnconfigure(0, weight=1, uniform="c")
        f.columnconfigure(1, weight=1, uniform="c")
        a = self.card(f)
        a.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.exp_name = self.lbl(a, "", 6, True)
        self.exp_name.pack(fill="x")
        self.exp_sub = self.lbl(a, "", -1, color="muted")
        self.exp_sub.pack(fill="x", pady=(2, 8))
        self.exp_mini = tk.Canvas(a, height=110, highlightthickness=0, bd=0, bg=C["panel"])
        self.exp_mini.pack(fill="x")
        self.exp_mini.bind("<Configure>", lambda e: self._paint_mini())
        self.exp_checks = tk.Frame(a, bg=C["panel"])
        self.exp_checks.pack(fill="x", pady=(10, 6))
        self.lbl(a, "Nombre del archivo", -1, color="muted").pack(anchor="w")
        self.file_var = tk.StringVar()
        self.entry(a, self.file_var).pack(fill="x", ipady=3)
        line = tk.Frame(a, bg=C["panel"])
        line.pack(fill="x", pady=(10, 0))
        self.exp_btn = ttk.Button(line, text=self.export_label, style="Accent.TButton", command=self.export)
        self.exp_btn.pack(side="left")
        ttk.Button(line, text="Volver a editar", command=lambda: self.show("edit")).pack(side="left", padx=8)
        self.exp_done = tk.Frame(a, bg=C["ok_bg"], highlightthickness=1, highlightbackground="#2f6b4f", padx=10, pady=8)
        self.exp_done_t = self.lbl(self.exp_done, "", 0, True, bg="ok_bg")
        self.exp_done_t.pack(fill="x")
        self.exp_done_s = self.lbl(self.exp_done, "", -1, color="ok_text", bg="ok_bg", wrap=480)
        self.exp_done_s.pack(fill="x")

        b = self.card(f)
        b.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.caps(b, "Qué lleva el archivo .npt").pack(fill="x", pady=(0, 6))
        firma = ("Ed25519 con tu clave privada. Numpad Macros trae tu clave pública y así reconoce los temas oficiales."
                 if self.mode == "creador" else
                 "Ed25519 con tu firma de autor. Prueba que todos tus temas vienen de la misma persona, pero no los "
                 "vuelve oficiales.")
        for k, v in (("NPT v2", "Encabezado: identifica el archivo como tema de Numpad Macros y su versión."),
                     ("Contenido", "Nombre, autor, descripción, los 22 colores con la transparencia de cada uno y la "
                                   "opacidad de la ventana, comprimidos y cifrados (AES-256-GCM). Con un editor de "
                                   "texto solo se ven símbolos."),
                     ("Fondo", "Color sólido o degradado: sus colores, dónde va cada uno y desde dónde empieza."),
                     ("Secciones", "Fondo, contenido y borde de realce de cada una de las 6 secciones."),
                     ("Imágenes", "Las de los 9 espacios, ya preparadas, en PNG o animadas (con todos sus cuadros). "
                                  "También van cifradas."),
                     ("Firma", firma)):
            row = tk.Frame(b, bg=C["panel"], highlightthickness=0)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=k, bg=C["panel"], fg=C["acc"], font=fnt(-1, mono=True), width=10, anchor="nw").pack(
                side="left", anchor="n")
            self.lbl(row, v, -1, wrap=440).pack(side="left", fill="x", expand=True)
        self.caps(b, "Así lo verá quien lo importe en Numpad Macros").pack(fill="x", pady=(16, 6))
        imp = tk.Frame(b, bg=C["panel2"], padx=10, pady=8)
        imp.pack(fill="x")
        self.imp_sw = tk.Canvas(imp, width=64, height=40, highlightthickness=0, bd=0)
        self.imp_sw.pack(side="left")
        box = tk.Frame(imp, bg=C["panel2"])
        box.pack(side="left", padx=10)
        self.imp_name = self.lbl(box, "", 0, True, bg="panel2")
        self.imp_name.pack(anchor="w")
        self.imp_badge = self.chip(box, "", "sig" if self.mode == "creador" else "", bg="panel2")
        self.imp_badge.pack(anchor="w", pady=(4, 0))
        leg = tk.Frame(b, bg=C["panel"])
        leg.pack(fill="x", pady=(10, 0))
        self.lbl(leg, "Etiquetas posibles:", -2, color="muted").pack(side="left")
        self.chip(leg, "✔ Oficial · OkumaWsX", "sig", "panel").pack(side="left", padx=4)
        self.chip(leg, "Comunidad · @autor", "", "panel2").pack(side="left", padx=4)
        self.chip(leg, "✕ Dañado o modificado", "bad").pack(side="left", padx=4)
        self.lbl(b, "El Estudio también guarda un proyecto .nptproj sin cifrar, solo para ti, para seguir editando "
                    "el tema después.", -2, color="muted", wrap=480).pack(fill="x", pady=(12, 0))
        return f

    # ---------------------------------------------------------------- 5 · clave
    def _build_key(self):
        f = tk.Frame(self.body, bg=C["panel"], padx=18, pady=16)
        f.columnconfigure(0, weight=1, uniform="c")
        f.columnconfigure(1, weight=1, uniform="c")
        a = self.card(f)
        a.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        side = tk.Frame(f, bg=C["panel"])
        side.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        if self.mode == "creador":
            info = self.official or {}
            self.caps(a, "Clave de esta PC").pack(fill="x")
            row = tk.Frame(a, bg=C["panel"])
            row.pack(fill="x", pady=8)
            tk.Label(row, text="✔", bg=C["sig_bg"], fg=C["sig_text"], font=fnt(4, True), width=2).pack(side="left")
            box = tk.Frame(row, bg=C["panel"])
            box.pack(side="left", padx=10)
            self.lbl(box, npt.OFFICIAL_NAME, 2, True).pack(anchor="w")
            prot = "protegida con contraseña" if info.get("protegida") else "sin contraseña"
            self.lbl(box, f"Creada el {info.get('creada', '?')} · {prot}", -1, color="muted").pack(anchor="w")
            self.lbl(a, "Huella de la clave pública", -1, color="muted").pack(anchor="w")
            self.lbl(a, npt.fingerprint(info["publica"]) if info.get("publica") else "?", 0, color="sig_text",
                     mono=True).pack(anchor="w", pady=(2, 8))
            if K.official_known(info):
                self.lbl(a, "Numpad Macros ya reconoce esta clave: tus temas salen como oficiales.", -1,
                         color="ok_text", wrap=480).pack(fill="x")
            else:
                warn = tk.Frame(a, bg=C["warn_bg"], highlightthickness=1, highlightbackground="#6e5a22", padx=10,
                                pady=8)
                warn.pack(fill="x")
                self.lbl(warn, "Esta clave no es la que Numpad Macros reconoce como oficial: tus temas saldrán "
                               "como «Comunidad». Importa tu clave de firma de temas (firma-temas-OkumaWsX.key).",
                         -1, color="warn_text", bg="warn_bg", wrap=460).pack(fill="x")
            btns = tk.Frame(a, bg=C["panel"])
            btns.pack(fill="x", pady=(10, 0))
            ttk.Button(btns, text="Guardar copia de seguridad", command=lambda: self.backup_key("oficial")).pack(
                side="left")
            ttk.Button(btns, text="Copiar clave pública", command=lambda: self.copy(info.get("publica", ""))).pack(
                side="left", padx=6)
            ttk.Button(btns, text="Cambiar contraseña", command=lambda: self.change_password("oficial")).pack(
                side="left")
            box = tk.Frame(side, bg=C["warn_bg"], highlightthickness=1, highlightbackground="#6e5a22", padx=12,
                           pady=10)
            box.pack(fill="x")
            self.lbl(box, "Guarda la copia en un lugar seguro (un pendrive o tu gestor de contraseñas). Si pierdes la "
                          "clave, ya no podrás firmar temas oficiales y habría que publicar una versión nueva de "
                          "Numpad Macros con otra clave. Nunca la subas a GitHub: la clave privada no sale de esta PC.",
                     -1, color="warn_text", bg="warn_bg", wrap=460).pack(fill="x")
            c2 = self.card(side)
            c2.pack(fill="x", pady=(12, 0))
            self.caps(c2, "En otra PC").pack(fill="x", pady=(0, 6))
            self.lbl(c2, "Abre el Estudio, ve a «Mi firma de autor» e importa tu copia de seguridad o tu clave de "
                         "firma de temas (firma-temas-OkumaWsX.key): el Estudio pasa solo al modo creador.", -1,
                     wrap=460).pack(fill="x")
            ttk.Button(c2, text="Importar copia de seguridad…", command=self.import_backup).pack(anchor="w",
                                                                                                 pady=(8, 0))
        else:
            info = K.author_info() or {}
            self.caps(a, "Mi firma de autor").pack(fill="x")
            row = tk.Frame(a, bg=C["panel"])
            row.pack(fill="x", pady=8)
            tk.Label(row, text="✓", bg=C["ok_bg"], fg=C["ok_text"], font=fnt(4, True), width=2).pack(side="left")
            box = tk.Frame(row, bg=C["panel"])
            box.pack(side="left", padx=10)
            self.key_name_lbl = self.lbl(box, "", 2, True)
            self.key_name_lbl.pack(anchor="w")
            prot = " · protegida con contraseña" if info.get("protegida") else ""
            self.lbl(box, f"Creada sola el {info.get('creada', '—')}{prot}", -1, color="muted").pack(anchor="w")
            self.lbl(a, "Huella de tu firma", -1, color="muted").pack(anchor="w")
            self.lbl(a, npt.fingerprint(info["publica"]) if info.get("publica") else "Todavía no se crea.", 0,
                     mono=True).pack(anchor="w", pady=(2, 8))
            self.lbl(a, "Con esta firma nadie puede publicar un tema haciéndose pasar por ti: Numpad Macros avisa si un "
                        "tema dice ser tuyo pero la firma no coincide con la de tus temas anteriores.", -1,
                     color="muted", wrap=480).pack(fill="x")
            btns = tk.Frame(a, bg=C["panel"])
            btns.pack(fill="x", pady=(10, 0))
            ttk.Button(btns, text="Guardar copia de seguridad", command=lambda: self.backup_key("autor")).pack(
                side="left")
            ttk.Button(btns, text="Proteger con contraseña", command=lambda: self.change_password("autor")).pack(
                side="left", padx=6)
            ttk.Button(btns, text="Importar copia…", command=self.import_backup).pack(side="left")
            c1 = self.card(side)
            c1.pack(fill="x")
            self.caps(c1, "Qué puedes y qué no puedes hacer").pack(fill="x", pady=(0, 6))
            for ok, txt in ((True, "Crear y compartir todos los temas que quieras, con colores, transparencia e "
                                   "imágenes."),
                            (True, "Tus temas se instalan en cualquier Numpad Macros como «Comunidad · tu nombre»."),
                            (False, "Firmar temas oficiales: solo puede hacerlo el creador oficial de Numpad Macros, "
                                    "con una clave que no está en tu PC."),
                            (False, "Usar el nombre del creador oficial como nombre de autor: está reservado.")):
                r = tk.Frame(c1, bg=C["panel"])
                r.pack(fill="x", pady=2)
                tk.Label(r, text="✓" if ok else "✕", bg=C["ok_bg"] if ok else C["bad_bg"],
                         fg=C["ok_text"] if ok else C["bad_text"], font=fnt(-1, True), width=2).pack(side="left",
                                                                                                     anchor="n")
                self.lbl(r, txt, -1, wrap=420).pack(side="left", padx=8, fill="x")
            box = tk.Frame(side, bg=C["warn_bg"], highlightthickness=1, highlightbackground="#6e5a22", padx=12,
                           pady=10)
            box.pack(fill="x", pady=(12, 0))
            self.lbl(box, "Si cambias de PC sin la copia de seguridad, tus temas nuevos saldrán con otra firma y Numpad "
                          "Macros avisará que el autor cambió.", -1, color="warn_text", bg="warn_bg",
                     wrap=460).pack(fill="x")
        return f

    # ================================================================ pintar
    def eff(self):
        return L.effective(self.colors, self.alpha)

    def bg_image(self):
        """Imagen de fondo de la ventana (PIL), ya oscurecida, o None."""
        s = self.images.get("fondo")
        if self.grad["modo"] != "imagen" or not s:
            return None
        key = ("bgimg", hashlib.md5(s["src"]).digest(), s.get("dark", 0), self.colors["bg"])
        if key not in self._cache:
            data = L.background_png(s["src"], s.get("dark", 0), self.colors["bg"])
            self._cache[key] = (data, L.from_bytes(data).convert("RGB"))
        return self._cache[key][1]

    def bg_colors(self) -> list:
        """Colores principales del fondo (degradado o imagen), para revisar la legibilidad."""
        g = self.gradient()
        if g:
            return [c for c, _p in g["colores"]]
        img = self.bg_image()
        if img is None:
            return []
        key = ("bgcols", id(img))
        if key not in self._cache:
            self._cache[key] = L.background_colors(img)
        return self._cache[key]

    def one_piece(self) -> bool:
        return self.grad["una_pieza"] and bool(self.gradient() or self.bg_image() is not None)

    def background_meta(self) -> dict:
        """El «fondo» tal como va en el tema."""
        g = self.gradient()
        if g:
            out = {"tipo": "degradado", **g}
        elif self.bg_image() is not None:
            out = {"tipo": "imagen"}
        else:
            return {}
        if self.grad["una_pieza"]:
            out.update(una_pieza=True, tinte=int(self.grad["tinte"]))
        return out

    def gradient(self) -> dict:
        """El degradado que se usa (vacío si el fondo es de color sólido)."""
        if self.grad["modo"] == "degradado" and len(self.grad["colores"]) >= 2:
            return {"colores": [list(s) for s in self.grad["colores"]], "desde": self.grad["desde"]}
        return {}

    def render(self):
        """Pide volver a dibujar. Varios cambios seguidos (una barra que se arrastra, por ejemplo) se
        juntan en un solo dibujo cuando la ventana queda libre: así no quedan zonas a medio pintar."""
        if not hasattr(self, "rows") or getattr(self, "_render_job", None):
            return
        self._render_job = self.root.after_idle(self._render_now)

    def _render_now(self):
        self._render_job = None
        self._quiet = True
        try:
            self._render()
        finally:
            self._quiet = False

    def _render(self):
        e = self.eff()
        self._paint_tokens()
        self.win_out.configure(text=f"{self.window['opacidad']} %")
        self.idle_out.configure(text=f"{self.window['sin_usar']} %")
        self.kind_lbl.configure(text="Oscuro" if L.is_dark(self.colors) else "Claro")
        self._paint_grad()
        common = dict(gradient=self.gradient() or None, sections=self.sections, wall=self.wall_var.get(),
                      bg_image=self.bg_image(), one_piece=self.one_piece(), tint=self.grad["tinte"])
        if self.screen == "edit":
            self.pv_edit.draw(e, self.slot_frames, opacity=self.window["opacidad"], hover=self.hover_var.get(),
                              **common)
        elif self.screen == "sec":
            self.pv_sec.draw(e, self.slot_frames, opacity=self.window["opacidad"], mode="sec", sel=self.sec_sel,
                             **common)
            self._paint_secs()
        elif self.screen == "img":
            idle = self.idle_view.get()
            paused = idle and self.gif_pause
            self.pv_img.draw(e, (lambda s, z: self.slot_frames(s, z, still=True)) if paused else self.slot_frames,
                             opacity=self.window["sin_usar"] if idle else self.window["opacidad"], mode="img",
                             sel=self.slot_sel, **common)
            self._paint_slots()
        for k, pv in (("edit", self.pv_edit), ("sec", self.pv_sec), ("img", self.pv_img)):
            if k != self.screen:
                pv.stop()
        self._paint_legibility()
        self._paint_author()
        if self.screen == "exp":
            self._paint_export()

    def _paint_tokens(self):
        for tok, r in self.rows.items():
            col, a = self.colors[tok], self.alpha.get(tok, 100)
            sw = r["sw"]
            sw.delete("all")
            if a < 100:
                for y in range(0, 18, 6):
                    for x in range(0, 26, 6):
                        sw.create_rectangle(x, y, x + 6, y + 6, width=0,
                                            fill="#d6d6d6" if (x // 6 + y // 6) % 2 else "#8a8a8a")
                under = L.mix("#b0b0b0", col, a / 100)
                sw.create_rectangle(0, 0, 13, 18, fill=under, width=0)
                sw.create_rectangle(13, 0, 26, 18, fill=col, width=0)
            else:
                sw.create_rectangle(0, 0, 27, 19, fill=col, width=0)
            auto = " A" if self.auto and tok in AUTO else ""
            alpha_txt = "" if tok == "bg" else f"\n{a} %"
            r["val"].configure(text=f"{col}{auto}{alpha_txt}", fg=C["acc"] if a < 100 or auto else C["muted"])
            sel = tok == self.sel
            bg = C["acc_bg"] if sel else C["panel"]
            for w in (r["frame"], r["name"], r["val"]):
                w.configure(bg=bg)
            r["frame"].configure(highlightbackground=C["acc_dim"] if sel else C["panel"])
            if sel:
                r["extra"].grid(row=1, column=0, columnspan=3, sticky="ew")
                if r["hex"].get().lower() != col:
                    r["hex"].set(col)
                if r["alpha"].get() != a:
                    r["alpha"].set(a)
            else:
                r["extra"].grid_remove()

    def _check_rows(self, box, rows):
        """Filas «Aa · nombre · valor» reutilizando las que ya existen (no se destruyen en cada dibujo).
        rows = [(nombre, valor, (fondo, texto) o None, estado)]."""
        pool = box.__dict__.setdefault("_pool", [])
        while len(pool) < len(rows):
            fr = tk.Frame(box, bg=C["panel"])
            demo = tk.Label(fr, text="Aa", font=fnt(-2, True), padx=4)
            demo.pack(side="left")
            name = self.lbl(fr, "", -2)
            name.pack(side="left", padx=6)
            val = tk.Label(fr, font=fnt(-2, mono=True), padx=5)
            val.pack(side="right")
            pool.append((fr, demo, name, val))
        for i, (fr, demo, name, val) in enumerate(pool):
            if i >= len(rows):
                if fr.winfo_ismapped() or fr.winfo_manager():
                    fr.pack_forget()
                continue
            n, rv, colors, st = rows[i]
            if colors:
                demo.configure(text="Aa", bg=colors[0], fg=colors[1])
            else:
                demo.configure(text="  ", bg=C["panel"], fg=C["panel"])
            name.configure(text=n)
            fgc, bgc = {"ok": (C["ok_text"], C["ok_bg"]), "warn": (C["warn_text"], C["warn_bg"]),
                        "bad": (C["bad_text"], C["bad_bg"])}[st]
            val.configure(text=f"{rv:.1f}:1" if colors else f"{int(rv)} %", bg=bgc, fg=fgc)
            if not fr.winfo_manager():
                fr.pack(fill="x", pady=1)

    def _paint_legibility(self):
        e = self.eff()
        rows = self.legibility_rows()
        bad = sum(1 for r in rows if r[3] == "bad")
        warn = sum(1 for r in rows if r[3] == "warn")
        pairs = {p[0]: (e[p[2]], e[p[1]]) for p in L.PAIRS}
        self._check_rows(self.leg_rows, [(n, rv, pairs.get(n) or demo, st) for n, rv, demo, st in rows])
        if bad:
            self.leg_sum.configure(text=f"{bad} combinación{'es' if bad > 1 else ''} ilegible{'s' if bad > 1 else ''}. "
                                        "No se puede exportar hasta corregirla.", fg=C["bad_text"])
        elif warn:
            self.leg_sum.configure(text=f"Se puede exportar, pero {warn} combinación{'es' if warn > 1 else ''} "
                                        f"queda{'n' if warn > 1 else ''} justa{'s' if warn > 1 else ''}.",
                                   fg=C["warn_text"])
        else:
            self.leg_sum.configure(text="Todo legible. Mínimo 4.5:1 para texto y 3:1 para texto secundario, ya con la "
                                        "transparencia aplicada.", fg=C["ok_text"])
        self.leg_bad = bad

    def legibility_rows(self):
        """Filas de legibilidad: (nombre, valor, (fondo, texto) o None, estado). Incluye el degradado y las
        secciones que cambiaron (estas solo avisan: atenuar una sección es a propósito)."""
        rows = [(n, r, None, st) for n, r, _mn, st in L.legibility(self.colors, self.alpha, self.window)]
        e = self.eff()
        cols = self.bg_colors()
        if cols:
            r, c, st = L.colors_check(e, cols)
            what = "el degradado" if self.gradient() else "la imagen de fondo"
            rows.append((f"Texto sobre {what}", r, (c, e["text"]), st))
            if self.one_piece():
                under = L.gradient_avg(self.gradient(), e["bg"]) if self.gradient() else L.image_avg(self.bg_image())
                r, c, st = L.one_piece_check(e, cols, under, self.grad["tinte"])
                rows.append(("Texto en los paneles (de una pieza)", r, (c, e["text"]), st))
        for k, name, r, pe, te, st, changed, img in L.section_rows(self.colors, self.alpha, self.sections,
                                                                    self.gradient(), self.images):
            if changed:
                rows.append((f"Sección · {name}{' (con imagen)' if img else ''}", r, (pe, te), st))
        return rows

    def _paint_author(self):
        if self.mode == "creador":
            return
        name = self.author or "Anónimo"
        self.author_chip.configure(text=f"● Firmando como {name} · comunidad")
        if hasattr(self, "author_note"):
            if npt.is_reserved_name(self.author):
                self.author_note.configure(text="Ese nombre está reservado para el creador oficial. Elige otro para "
                                                "poder exportar.", fg=C["bad_text"])
            else:
                self.author_note.configure(text=f"Así aparecerás en Numpad Macros: «Comunidad · {name}». "
                                                "Vacío = Anónimo.", fg=C["muted"])
        if hasattr(self, "key_name_lbl"):
            self.key_name_lbl.configure(text=name)

    def _paint_palette(self):
        thumb = Image.open(io.BytesIO(self.pal_img)).convert("RGB")
        thumb = thumb.resize((96, 60))
        self._pal_photo = ImageTk.PhotoImage(thumb)
        self.pal_thumb.configure(image=self._pal_photo, width=96, height=60)
        self.pal_name_lbl.configure(text=self.pal_name if len(self.pal_name) < 26 else self.pal_name[:24] + "…")
        for w in self.pal_row.winfo_children():
            w.destroy()
        for i, (col, n) in enumerate(self.palette):
            cell = tk.Frame(self.pal_row, bg=C["panel"])
            cell.pack(side="left", padx=2, expand=True, fill="x")
            on = i == self.pal_acc
            sw = tk.Canvas(cell, width=38, height=30, bg=col, highlightthickness=2,
                           highlightbackground=C["text"] if on else C["panel"], cursor="hand2")
            sw.pack()
            sw.bind("<Button-1>", lambda e, j=i: self.set_pal_acc(j))
            tk.Label(cell, text=f"{round(n * 100)}%", bg=C["panel"], fg=C["muted"], font=fnt(-3, mono=True)).pack()

    # mini dibujo de cada plantilla (en un lienzo de 110 × 52): paneles y zonas
    _SK = {"banner": (0, 0, 110, 11), "logo": (3, 3, 6, 6), "headmid": (40, 3, 30, 6), "keys": (4, 15, 38, 22),
           "leftbot": (4, 39, 38, 6), "tabsend": (88, 13, 20, 5), "corner": (47, 31, 61, 14),
           "footband": (47, 47, 61, 5), "foot": (48, 48, 30, 3)}

    def _paint_slots(self):
        sig = (self.template, self.slot_sel,
               tuple(sorted((k, hashlib.md5(v["src"]).digest(), self.is_animated(k)) for k, v in self.images.items())))
        if sig != getattr(self, "_slots_sig", None):
            self._slots_sig = sig
            self._paint_slot_lists()
        self._paint_slot_settings()

    def _paint_slot_lists(self):
        for w in self.tpl_box.winfo_children():
            w.destroy()
        tpls = list(L.TEMPLATES) + [("custom", "Personalizada", None)]
        for i, (tid, name, slots) in enumerate(tpls):
            on = tid == self.template
            fr = tk.Frame(self.tpl_box, bg=C["acc_bg"] if on else C["panel2"], highlightthickness=1,
                          highlightbackground=C["acc"] if on else C["line"], padx=5, pady=5, cursor="hand2")
            last = tid == "custom"
            fr.grid(row=i // 2, column=0 if last else i % 2, columnspan=2 if last else 1, padx=3, pady=3, sticky="ew")
            sk = tk.Canvas(fr, width=110, height=52, bg="#0f1115", highlightthickness=0)
            sk.pack()
            for x, y, w, h in ((2, 13, 42, 34), (47, 13, 39, 5), (47, 19, 61, 26)):
                sk.create_rectangle(x, y, x + w, y + h, fill="#1d2028", width=0)
            has = (lambda s: s in slots) if slots is not None else (lambda s: s in self.images)
            for slot, (x, y, w, h) in self._SK.items():
                sk.create_rectangle(x, y, x + w, y + h, fill=C["acc"] if has(slot) else "#2a2e37", width=0)
            lab = tk.Label(fr, text=name, bg=fr["bg"], fg=C["text"], font=fnt(-2, True), anchor="w")
            lab.pack(fill="x", pady=(4, 0))
            for w in (fr, sk, lab):
                w.bind("<Button-1>", lambda e, tt=tid: self.apply_template(tt))
        self.tpl_box.columnconfigure(0, weight=1, uniform="t")
        self.tpl_box.columnconfigure(1, weight=1, uniform="t")
        for w in self.slot_box.winfo_children():
            w.destroy()
        self._slot_photos = []
        for grp, title in (("Detrás", "Detrás del contenido"), ("Libre", "En espacios libres")):
            tk.Label(self.slot_box, text=title.upper(), bg=C["panel"], fg=C["muted"], font=fnt(-3, True),
                     anchor="w").pack(fill="x", padx=6, pady=(8, 2))
            for slot, (name, g, _d) in L.SLOTS.items():
                if g != grp:
                    continue
                on = slot == self.slot_sel
                s = self.images.get(slot)
                fr = tk.Frame(self.slot_box, bg=C["acc_bg"] if on else C["panel"], highlightthickness=1,
                              highlightbackground=C["acc_dim"] if on else C["panel"], padx=6, pady=4, cursor="hand2")
                fr.pack(fill="x", pady=1)
                th = tk.Label(fr, bg="#0d0e11", image=self._blank(40, 26), width=40, height=26)
                if s:
                    im = L.from_bytes(s["src"]).convert("RGB")
                    im.thumbnail((40, 26))
                    p = ImageTk.PhotoImage(im)
                    self._slot_photos.append(p)
                    th.configure(image=p, width=40, height=26)
                th.pack(side="left")
                box = tk.Frame(fr, bg=fr["bg"])
                box.pack(side="left", padx=8, fill="x", expand=True)
                row1 = tk.Frame(box, bg=fr["bg"])
                row1.pack(anchor="w", fill="x")
                a = tk.Label(row1, text=name, bg=fr["bg"], fg=C["text"], font=fnt(-1), anchor="w", justify="left",
                             wraplength=170)
                a.pack(side="left")
                ws = [fr, th, box, row1, a]
                if s and self.is_animated(slot):
                    gl = tk.Label(row1, text="GIF", bg=C["sig_bg"], fg=C["sig_text"], font=fnt(-4, True), padx=3)
                    gl.pack(side="left", padx=4)
                    ws.append(gl)
                w_, h_ = V.export_size(slot)
                b = tk.Label(box, text=f"{'Con imagen' if s else 'Vacío'} · {w_} × {h_} px", bg=fr["bg"],
                             fg=C["muted"], font=fnt(-2), anchor="w")
                b.pack(anchor="w")
                ws.append(b)
                for wdg in ws:
                    wdg.bind("<Button-1>", lambda e, sl=slot: self.pick_slot(sl))

    def _paint_slot_settings(self):
        # degradado (fila «Toda la ventana»)
        self.grad_mini.delete("all")
        g = self.gradient()
        img = self.bg_image()
        onep = " · de una pieza" if self.one_piece() else ""
        if g:
            gi = L.gradient_image(g, (40, 26))
            self._grad_mini_photo = ImageTk.PhotoImage(gi)
            self.grad_mini.create_image(0, 0, anchor="nw", image=self._grad_mini_photo)
            self.grad_mini_t.configure(text=f"Degradado de {len(g['colores'])} colores · desde "
                                            f"{L.GRADIENT_DIRS[g['desde']][1]}{onep}")
        elif img is not None:
            self._grad_mini_photo = ImageTk.PhotoImage(L.cover(img, 40, 26))
            self.grad_mini.create_image(0, 0, anchor="nw", image=self._grad_mini_photo)
            self.grad_mini_t.configure(text=f"Imagen{onep}")
        else:
            self.grad_mini.create_rectangle(0, 0, 42, 28, fill=self.colors["bg"], width=0)
            self.grad_mini_t.configure(text="Color sólido · tócalo para usar un degradado")
        # ajustes del espacio elegido
        s = self.images.get(self.slot_sel)
        d = s or L.SLOT_DEFAULTS[self.slot_sel]
        self.slot_title.configure(text=L.SLOT_NAMES[self.slot_sel].upper())
        w, h = V.export_size(self.slot_sel)
        txt = ""
        if s and self.is_animated(self.slot_sel):
            n = L.frame_count(s["src"])
            txt = (f"GIF animado · {n} cuadros · {max(1, len(s['src']) // 1024)} KB. Se guarda con todos sus cuadros, "
                   "ya preparados. ")
            if s.get("cuadros_originales", 0) > npt.MAX_FRAMES:
                txt += f"Tenía {s['cuadros_originales']} cuadros: se recortó a {npt.MAX_FRAMES}. "
        elif s and self.is_animated(self.slot_sel, source=True):
            txt = ("Este espacio usa el primer cuadro del GIF: los GIF se mueven en los espacios libres (centro del "
                   "encabezado, final de las pestañas, debajo de las teclas y el pie). ")
        txt += f"Se guarda a {w} × {h} px."
        if self.slot_sel in npt.SLOTS_FREE:
            txt += " Se adapta al espacio libre y nunca tapa botones."
        if not s:
            txt += " Importa una imagen o un GIF, o usa la imagen de los colores."
        self.slot_size.configure(text=txt)
        if s:
            im = L.from_bytes(s["src"]).convert("RGB")
            im.thumbnail((96, 60))
            self._slot_thumb = ImageTk.PhotoImage(im)
            self.slot_thumb.configure(image=self._slot_thumb, width=96, height=60)
        else:
            self.slot_thumb.configure(image=self._blank(96, 60), width=96, height=60)
        self.fit_var.set(L.FITS[d["fit"]])
        state = "normal" if s else "disabled"
        self.fit_cb.configure(state="readonly" if s else "disabled")
        for key, (var, out, unit, sc) in self.slot_vars.items():
            if var.get() != d[key]:
                var.set(d[key])
            out.configure(text=f"{d[key]}{unit}")
            sc.configure(state=state)
        self.slot_del.configure(state=state)
        if self.gif_pause_var.get() != self.gif_pause:
            self.gif_pause_var.set(self.gif_pause)
        kb = self.theme_weight() // 1024
        n = len(self.images)
        ng = sum(1 for k in self.images if self.is_animated(k))
        self.weight_lbl.configure(text=f"{max(kb, 3)} KB aprox. · colores 3 KB + {n} imagen{'' if n == 1 else 'es'}"
                                       f"{f' ({ng} GIF)' if ng else ''}. Límite por tema: "
                                       f"{npt.MAX_FILE // 1024 // 1024} MB.",
                                  fg=C["bad_text"] if kb * 1024 > npt.MAX_FILE else C["text"])

    def _paint_grad(self):
        modo = self.grad["modo"]
        for key, b in self.grad_seg.items():
            sel = key == modo
            b.configure(bg=C["panel2"] if sel else C["bg"], fg=C["text"] if sel else C["muted"],
                        font=fnt(-1, sel))
        if modo == "solido":
            self.onep_box.grid_remove()
        else:
            self.onep_box.grid(row=4, column=0, sticky="ew", pady=(12, 0))
            if self.onep_var.get() != self.grad["una_pieza"]:
                self.onep_var.set(self.grad["una_pieza"])
            if self.tint_var.get() != self.grad["tinte"]:
                self.tint_var.set(self.grad["tinte"])
            on = self.grad["una_pieza"]
            self.tint_out.configure(text=f"{self.grad['tinte']} %")
            self.tint_scale.configure(state="normal" if on else "disabled")
            self.tint_lbl.configure(fg=C["text"] if on else C["muted"])
        if modo == "imagen":
            self.bgimg_ed.grid(row=3, column=0, sticky="ew")
            s = self.images.get("fondo")
            img = self.bg_image()
            if img is not None:
                th = img.copy()
                th.thumbnail((96, 60))
                self._bgimg_photo = ImageTk.PhotoImage(th)
                self.bgimg_thumb.configure(image=self._bgimg_photo, width=96, height=60)
                data = self._cache[("bgimg", hashlib.md5(s["src"]).digest(), s.get("dark", 0),
                                    self.colors["bg"])][0]
                self.bgimg_note.configure(text=f"Se guarda a {img.width} × {img.height} px · "
                                               f"{max(1, len(data) // 1024)} KB. Cubre toda la ventana, recortada al "
                                               "centro.")
            else:
                self.bgimg_thumb.configure(image=self._blank(96, 60), width=96, height=60)
                self.bgimg_note.configure(text="Sube una imagen (hasta 1920 × 1200 se guarda tal cual) o genera "
                                               "una con los colores de la paleta.")
            d = s.get("dark", 0) if s else 0
            if self.bgdark_var.get() != d:
                self.bgdark_var.set(d)
            self.bgdark_out.configure(text=f"{d} %")
            self.bgdark_scale.configure(state="normal" if s else "disabled")
        else:
            self.bgimg_ed.grid_remove()
        if modo != "degradado":
            self.grad_ed.grid_remove()
            return
        self.grad_ed.grid(row=2, column=0, sticky="ew")
        self._paint_grad_bar()
        stops = self.grad["colores"]
        if self._grad_count != len(stops):
            self._grad_count = len(stops)
            for w in self.grad_rows.winfo_children():
                w.destroy()
            self.grad_widgets = []
            for i in range(len(stops)):
                sw = tk.Canvas(self.grad_rows, width=26, height=18, highlightthickness=1,
                               highlightbackground="#3a3e48", bd=0, cursor="hand2")
                sw.grid(row=i, column=0, padx=(0, 6), pady=2)
                sw.bind("<Button-1>", lambda e, j=i: self.grad_pick(j))
                var = tk.IntVar(value=stops[i][1])
                sc = self.scale(self.grad_rows, var, 0, 100, 1, lambda j=i: self.grad_pos(j))
                sc.configure(length=60)
                sc.grid(row=i, column=1, sticky="ew")
                out = tk.Label(self.grad_rows, text="", bg=C["panel"], fg=C["muted"], font=fnt(-2, mono=True),
                               width=5)
                out.grid(row=i, column=2)
                x = ttk.Button(self.grad_rows, text="✕", width=2, style="Small.TButton",
                               command=lambda j=i: self.grad_remove(j))
                x.grid(row=i, column=3, padx=(4, 0))
                self.grad_widgets.append((sw, var, out, x))
        for i, (sw, var, out, x) in enumerate(self.grad_widgets):
            c, pos = stops[i]
            sw.configure(bg=c)
            if var.get() != pos:
                var.set(pos)
            out.configure(text=f"{pos} %")
            x.configure(state="normal" if len(stops) > npt.GRADIENT_STOPS[0] else "disabled")
        self.grad_add.configure(state="normal" if len(stops) < npt.GRADIENT_STOPS[1] else "disabled")
        for d, b in self.grad_dirs.items():
            sel = d == self.grad["desde"]
            b.configure(bg=C["acc"] if sel else C["panel2"], fg=C["on_acc"] if sel else C["muted"])
        _arrow, start, end = L.GRADIENT_DIRS[self.grad["desde"]]

        def prep(x):
            return "a " if x in ("la izquierda", "la derecha") else ("en " if x.startswith("el ") else "")
        if self.grad["desde"] == "c":
            self.grad_note.configure(text="Empieza en el centro y se abre en círculo hacia los bordes.")
        else:
            self.grad_note.configure(text=f"Empieza {prep(start)}{start} y termina {prep(end)}{end}.")

    def _paint_grad_bar(self):
        if self.grad["modo"] != "degradado" or len(self.grad["colores"]) < 2:
            return
        cv = self.grad_bar
        w = max(cv.winfo_width(), 40)
        gi = L.gradient_image({"colores": self.grad["colores"], "desde": "l"}, (w, 20))
        self._grad_bar_photo = ImageTk.PhotoImage(gi)
        cv.delete("all")
        cv.create_image(0, 0, anchor="nw", image=self._grad_bar_photo)

    def _paint_secs(self):
        for k, r in self.sec_rows.items():
            s = L.section(self.sections, k)
            sel = k == self.sec_sel
            bg = C["acc_bg"] if sel else C["panel"]
            for w in (r["frame"], r["head"], r["name"], r["code"], r["note"]):
                w.configure(bg=bg)
            r["frame"].configure(highlightbackground=C["acc_dim"] if sel else C["panel"])
            r["code"].configure(text=f"{s['fondo']} % · {s['contenido']} %{' · realce' if s['realce'] else ''}")
            for key, (var, out, line) in r["vars"].items():
                if var.get() != s[key]:
                    var.set(s[key])
                out.configure(text=f"{s[key]} %", bg=bg)
                line.configure(bg=bg)
                for c in line.winfo_children():
                    c.configure(bg=bg)
            if r["realce"].get() != s["realce"]:
                r["realce"].set(s["realce"])
        self.focus_btn.configure(text=f"Destacar «{L.SECTIONS[self.sec_sel][0]}»")
        rows = L.section_rows(self.colors, self.alpha, self.sections, self.gradient(), self.images)
        self._check_rows(self.sec_checks, [(name + (" (con imagen)" if img else ""), r, (pe, te), st)
                                           for k, name, r, pe, te, st, changed, img in rows])
        low = sum(1 for row in rows if row[5] != "ok")
        if low:
            self.sec_sum.configure(text=f"{low} {'secciones' if low > 1 else 'sección'} atenuada{'s' if low > 1 else ''}. Se "
                                        "puede exportar; es normal si las atenuaste a propósito para resaltar otra.",
                                   fg=C["warn_text"])
        else:
            self.sec_sum.configure(text="Todas las secciones se leen bien.", fg=C["ok_text"])

    def _paint_mini(self):
        cv = self.exp_mini
        cv.delete("all")
        w = max(cv.winfo_width(), 100)
        e = self.eff()
        cv.create_rectangle(0, 0, w, 110, fill=e["bg"], width=0)
        cv.create_rectangle(8, 8, w * .4, 102, fill=e["panel"], outline=e["line"])
        cv.create_rectangle(8, 76, w * .4, 102, fill=e["key_set"], width=0)
        cv.create_rectangle(w * .4 + 8, 8, w - 8, 102, fill=e["panel"], outline=e["line"])
        cv.create_rectangle(w * .4 + 8, 80, w - 8, 102, fill=e["acc"], width=0)

    def _paint_export(self):
        name = self.meta["nombre"] or "Sin nombre"
        self.exp_name.configure(text=name)
        who = self.author or "Anónimo"
        self.exp_sub.configure(text=f"por {who} · versión {self.meta['version']} · tema "
                                    f"{'oscuro' if L.is_dark(self.colors) else 'claro'}")
        e = self.eff()
        self._paint_mini()
        for c in self.exp_checks.winfo_children():
            c.destroy()
        rows = self.legibility_rows()
        bad = sum(1 for r in rows if r[3] == "bad")
        warn = sum(1 for r in rows if r[3] == "warn")
        reserved = self.mode != "creador" and npt.is_reserved_name(self.author)
        n = len([s for s in self.images if s in L.SLOT_NAMES])
        anim = [s for s in self.images if self.is_animated(s)]
        checks = [("ok", "Los 22 colores están completos")]
        checks.append(("bad", f"{bad} combinación ilegible: vuelve a «Editar tema»") if bad else
                      ("warn", f"Legible, con {warn} combinación justa") if warn else
                      ("ok", "Texto legible en todas las capas"))
        t = self.build_theme_meta()
        nl = sum(1 for v in self.alpha.values() if v < 100)
        checks.append(("ok", f"Admite transparencia: ventana {self.window['opacidad']} % (sin usar "
                             f"{self.window['sin_usar']} %) · {nl} {'capa' if nl == 1 else 'capas'} con nivel propio")
                      if t.transparency else ("ok", "Sin transparencia (opaco)"))
        g = self.gradient()
        onep = f" · de una pieza (tinte de los paneles {self.grad['tinte']} %)" if self.one_piece() else ""
        if g:
            checks.append(("ok", f"Fondo: degradado de {len(g['colores'])} colores, desde "
                                 f"{L.GRADIENT_DIRS[g['desde']][1]}{onep}"))
        elif self.bg_image() is not None:
            checks.append(("ok", f"Fondo: imagen de {self.bg_image().width} × {self.bg_image().height} px{onep}"))
        else:
            checks.append(("ok", "Fondo: color sólido"))
        ns = len(L.sections_clean(self.sections))
        checks.append(("ok", f"Transparencia por sección: {ns} {'sección' if ns == 1 else 'secciones'} "
                             f"ajustada{'s' if ns != 1 else ''}" if ns else "Transparencia por sección: normal"))
        gif = f" ({len(anim)} animada{'s' if len(anim) != 1 else ''})" if anim else ""
        checks.append(("ok", f"{n} imagen{'es' if n != 1 else ''}{gif}: " + ", ".join(
            L.SLOT_NAMES[s].lower() for s in self.images if s in L.SLOT_NAMES)) if n else
                      ("ok", "Sin imágenes (solo colores)"))
        kb = self.theme_weight()
        if kb > npt.MAX_FILE:
            checks.append(("bad", f"Pesa {kb // 1024} KB: el máximo es 5 MB"))
        checks.append(("ok", "Se cifrará con AES-256-GCM"))
        if self.mode == "creador":
            if K.official_known(self.official):
                checks.append(("sig", "Se firmará como OkumaWsX (tema oficial)"))
            else:
                checks.append(("warn", "Se firmará con tu clave oficial, pero Numpad Macros aún no la reconoce: "
                                       "saldrá como «Comunidad»"))
        elif reserved:
            checks.append(("bad", "Ese nombre de autor está reservado para el creador oficial"))
        else:
            checks.append(("ok", f"Se firmará con tu firma de autor como {who} (tema de la comunidad)"))
        for kind, txt in checks:
            r = tk.Frame(self.exp_checks, bg=C["panel"])
            r.pack(fill="x", pady=2)
            fg, bg = {"ok": (C["ok_text"], C["ok_bg"]), "warn": (C["warn_text"], C["warn_bg"]),
                      "bad": (C["bad_text"], C["bad_bg"]), "sig": (C["sig_text"], C["sig_bg"])}[kind]
            tk.Label(r, text={"ok": "✓", "warn": "!", "bad": "✕", "sig": "✔"}[kind], bg=bg, fg=fg,
                     font=fnt(-1, True), width=2).pack(side="left", anchor="n")
            self.lbl(r, txt, -1, wrap=480).pack(side="left", padx=8, fill="x")
        blocked = bool(bad) or reserved or kb > npt.MAX_FILE
        self.exp_btn.configure(state="disabled" if blocked else "normal")
        if not self.file_var.get() or self.file_var.get() == getattr(self, "_auto_file", ""):
            self._auto_file = L.slug(name) + npt.EXTENSION
            self.file_var.set(self._auto_file)
        self.imp_name.configure(text=name)
        self.imp_sw.delete("all")
        self.imp_sw.create_rectangle(0, 0, 36, 40, fill=e["bg"], width=0)
        self.imp_sw.create_rectangle(36, 0, 64, 40, fill=e["acc"], width=0)
        official = self.mode == "creador" and K.official_known(self.official)
        self.imp_badge.configure(text="✔ Oficial · OkumaWsX" if official else f"Comunidad · {who}",
                                 bg=C["sig_bg"] if official else C["panel"],
                                 fg=C["sig_text"] if official else C["text"])

    # ================================================================ imágenes
    def is_animated(self, slot, source=False) -> bool:
        """¿La imagen del espacio se mueve? (``source``: ¿la original es animada, aunque el espacio no lo sea?)"""
        s = self.images.get(slot)
        if not s or (not source and slot not in npt.ANIMATED_SLOTS):
            return False
        key = ("n", hashlib.md5(s["src"]).digest())
        if key not in self._cache:
            self._cache[key] = L.frame_count(s["src"]) > 1
        return self._cache[key]

    def slot_frames(self, slot, size, still=False):
        """Cuadros de un espacio preparados para la vista previa (con caché). ``still``: solo el primero."""
        s = self.images.get(slot)
        if not s:
            return None
        key = (slot, size, self.colors["bg"], s["fit"], s["op"], s["dark"], s["blur"], hashlib.md5(s["src"]).digest())
        if key not in self._cache:
            if len(self._cache) > 60:
                self._cache.clear()
            sw, _sh = npt.IMAGE_SLOTS[slot]
            self._cache[key] = L.render_slot_frames(s["src"], slot, s, self.colors["bg"], size=size,
                                                    blur_scale=size[0] / sw)
        fr = self._cache[key]
        return fr[:1] if still else fr

    def final_images(self) -> dict:
        out = {}
        for slot, s in self.images.items():
            if slot == "fondo":                    # fondo de toda la ventana: solo si el fondo es «Imagen»
                if self.bg_image() is not None:
                    out[slot] = self._cache[("bgimg", hashlib.md5(s["src"]).digest(), s.get("dark", 0),
                                             self.colors["bg"])][0]
                continue
            key = ("final", slot, self.colors["bg"], s["fit"], s["op"], s["dark"], s["blur"],
                   hashlib.md5(s["src"]).digest())
            if key not in self._cache:
                # misma forma que la zona de la vista previa: el tema guarda el mismo recorte que ves
                size = V.export_size(slot)
                self._cache[key] = L.encode(L.render_slot_frames(s["src"], slot, s, self.colors["bg"], size=size,
                                                                 blur_scale=size[0] / npt.IMAGE_SLOTS[slot][0]))
            out[slot] = self._cache[key]
        return out

    def theme_weight(self) -> int:
        return 3000 + sum(len(v) for v in self.final_images().values())

    def apply_template(self, tid):
        self.template = tid
        tpl = next((t for t in L.TEMPLATES if t[0] == tid), None)
        if tpl:
            for slot in L.SLOTS:
                if slot in tpl[2]:
                    if slot not in self.images:
                        sample = L.TEMPLATE_SAMPLES.get(slot) if tid == "stickers" or tid == "todo" else None
                        src = L.sample_anim(sample) if sample else self.pal_img
                        self.images[slot] = {"src": src, **L.SLOT_DEFAULTS[slot]}
                else:
                    self.images.pop(slot, None)
            if tpl[2]:
                self.slot_sel = tpl[2][0]
            self.mark()
        self.render()

    def pick_slot(self, slot):
        self.slot_sel = slot
        self.render()

    def on_zone_click(self, ev):
        z = self.pv_img.tag_at(ev.x, ev.y, "z:")
        if z:
            self.pick_slot(z)

    def on_slot_setting(self):
        s = self.images.get(self.slot_sel)
        if not s or self._quiet:
            return
        inv = {v: k for k, v in L.FITS.items()}
        new = {"fit": inv.get(self.fit_var.get(), "cover"),
               **{key: int(var.get()) for key, (var, _o, _u, _s) in self.slot_vars.items()}}
        if all(s.get(k) == v for k, v in new.items()):
            return
        s.update(new)
        self.template = "custom"
        self.mark()
        self.render()

    def on_gif_pause(self):
        self.gif_pause = bool(self.gif_pause_var.get())
        self.mark()
        self.render()

    def _read_image(self, path):
        """Imagen importada (también GIF animado), lista para el proyecto. Devuelve (bytes, cuadros originales)."""
        try:
            if os.path.getsize(path) > 20 * 1024 * 1024:
                raise ValueError("La imagen pesa más de 20 MB. Prueba con una más liviana.")
            with open(path, "rb") as fh:
                raw = fh.read()
            n = L.source_count(raw)
            return L.prepare_source(raw), n
        except Exception as e:
            messagebox.showerror(APP, f"No se pudo abrir la imagen:\n{e}", parent=self.root)
            return None, 0

    def import_slot_image(self):
        path = filedialog.askopenfilename(parent=self.root, title="Elige una imagen o un GIF", filetypes=IMG_TYPES)
        if not path:
            return
        data, n = self._read_image(path)
        if data:
            self.images[self.slot_sel] = {**(self.images.get(self.slot_sel) or L.SLOT_DEFAULTS[self.slot_sel]),
                                          "src": data, "cuadros_originales": n}
            self.template = "custom"
            self.mark()
            self.render()
            if n > npt.MAX_FRAMES:
                self.toast(f"El GIF tiene {n} cuadros: se usan los primeros {npt.MAX_FRAMES}.", "warn")

    def slot_use_palette(self):
        self.images[self.slot_sel] = {**(self.images.get(self.slot_sel) or L.SLOT_DEFAULTS[self.slot_sel]),
                                      "src": self.pal_img}
        self.images[self.slot_sel].pop("cuadros_originales", None)
        self.template = "custom"
        self.mark()
        self.render()

    def slot_remove(self):
        self.images.pop(self.slot_sel, None)
        self.template = "custom"
        self.mark()
        self.render()

    # ================================================================ fondo de la ventana
    def grad_mode(self, on):
        self.bg_mode("degradado" if on else "solido")

    def bg_mode(self, modo):
        if modo == "degradado" and len(self.grad["colores"]) < 2:
            self.grad["colores"] = L.gradient_from_theme(self.colors)
        self.grad["modo"] = modo
        self.grad["on"] = modo == "degradado"
        self.mark()
        self.render()

    def _set_bg_image(self, data, msg):
        old = self.images.get("fondo") or {}
        self.images["fondo"] = {"src": data, "fit": "cover", "op": 100, "dark": old.get("dark", 0), "blur": 0}
        self.bg_mode("imagen")
        self.toast(msg, "ok")

    def bg_upload(self):
        path = filedialog.askopenfilename(parent=self.root, title="Imagen para el fondo de la ventana",
                                          filetypes=IMG_TYPES)
        if not path:
            return
        data, _n = self._read_image(path)
        if data:
            self._set_bg_image(data, f"Fondo de la ventana: «{os.path.basename(path)}».")

    def bg_from_imported(self):
        self._set_bg_image(self.pal_img, f"Fondo de la ventana: la imagen importada «{self.pal_name}».")

    def bg_generate(self):
        data = L.background_from_palette(self.palette, L.is_dark(self.colors))
        self._set_bg_image(data, f"Fondo generado con los colores de «{self.pal_name}».")

    def on_bg_dark(self):
        s = self.images.get("fondo")
        if self._quiet or not s:
            return
        v = int(self.bgdark_var.get())
        if v != s.get("dark", 0):
            s["dark"] = v
            self.mark()
            self.render()

    def on_one_piece(self):
        v = bool(self.onep_var.get())
        if v != self.grad["una_pieza"]:
            self.grad["una_pieza"] = v
            self.mark()
            self.render()

    def on_tint(self):
        if self._quiet:
            return
        v = int(self.tint_var.get())
        if v != self.grad["tinte"]:
            self.grad["tinte"] = v
            self.mark()
            self.render()

    def grad_set(self, stops, msg=None):
        self.grad["colores"] = [[c, int(p)] for c, p in stops][:npt.GRADIENT_STOPS[1]]
        self.grad["on"] = True
        self.grad["modo"] = "degradado"
        self.mark()
        self.render()
        if msg:
            self.toast(msg, "ok")

    def grad_add_stop(self):
        if len(self.grad["colores"]) < npt.GRADIENT_STOPS[1]:
            self.grad_set(L.gradient_add_stop(self.grad["colores"]))

    def grad_remove(self, i):
        if len(self.grad["colores"]) > npt.GRADIENT_STOPS[0]:
            self.grad_set([s for j, s in enumerate(self.grad["colores"]) if j != i])

    def grad_theme(self):
        self.grad_set(L.gradient_from_theme(self.colors), "Degradado hecho con los colores del tema.")

    def grad_image(self):
        stops = L.gradient_from_palette(self.palette, L.is_dark(self.colors))
        if stops:
            self.grad_set(stops, f"Degradado con los colores de «{self.pal_name}», ajustados para que el texto se "
                                 "lea.")

    def grad_pick(self, i):
        c = self.grad["colores"][i][0]
        res = colorchooser.askcolor(color=c, parent=self.root, title=f"Color {i + 1} del degradado")
        if res and res[1]:
            self.grad["colores"][i][0] = res[1].lower()
            self.mark()
            self.render()

    def grad_pos(self, i):
        if self._quiet or i >= len(self.grad["colores"]):
            return
        v = int(self.grad_widgets[i][1].get())
        if v != self.grad["colores"][i][1]:
            self.grad["colores"][i][1] = v
            self.mark()
            self.render()

    def grad_from(self, d):
        self.grad["desde"] = d
        self.mark()
        self.render()

    def goto_gradient(self):
        self.show("edit")
        if self.grad["modo"] == "solido":
            self.grad_mode(True)
        self.root.update_idletasks()
        try:
            cv = self.edit_left.cv
            total = max(self.edit_left.inner.winfo_height(), 1)
            cv.yview_moveto(max(0.0, (self.grad_box.winfo_y() - 40) / total))
        except tk.TclError:
            pass

    # ================================================================ secciones
    def select_section(self, k):
        self.sec_sel = k
        self.render()

    def on_section_click(self, ev):
        k = self.pv_sec.tag_at(ev.x, ev.y, "s:")
        if k:
            self.select_section(k)

    def on_section(self, k):
        if self._quiet:
            return
        r = self.sec_rows[k]
        s = {"fondo": int(r["vars"]["fondo"][0].get()), "contenido": int(r["vars"]["contenido"][0].get()),
             "realce": bool(r["realce"].get())}
        if s == L.section(self.sections, k):
            return
        self.sections[k] = s
        self.sections = L.sections_clean(self.sections)
        self.sec_sel = k
        self.mark()
        self.render()

    def focus_section(self):
        self.sections = L.focus(self.sections, self.sec_sel)
        self.mark()
        self.render()
        self.toast(f"«{L.SECTIONS[self.sec_sel][0]}» destacada: las demás secciones quedaron atenuadas.", "ok")

    def apply_preset(self, pid):
        self.sections = L.preset(pid)
        self.mark()
        self.render()
        self.toast(f"Estilo «{L.PRESETS[pid][0]}» aplicado a las secciones.", "ok")

    # ================================================================ colores
    def select(self, tok):
        self.sel = tok
        self.render()

    def on_preview_click(self, ev):
        t = self.pv_edit.tag_at(ev.x, ev.y, "t:")
        if t:
            self.select(t)

    def pick_color(self, tok):
        self.select(tok)
        res = colorchooser.askcolor(color=self.colors[tok], parent=self.root, title=LABELS[tok])
        if res and res[1]:
            self.set_color(tok, res[1].lower())

    def set_color(self, tok, col):
        self.colors[tok] = col
        if tok in AUTO and self.auto:
            self.auto = False
            self.auto_var.set(False)
        if tok in ("acc", "bg") and self.auto:
            L.derive(self.colors)
        self.mark()
        self.render()

    def on_hex(self, tok):
        v = self.rows[tok]["hex"].get().strip()
        if not v.startswith("#"):
            v = "#" + v
        if npt._HEX.match(v) and v.lower() != self.colors[tok]:
            self.set_color(tok, v.lower())

    def on_alpha(self, tok):
        a = int(self.rows[tok]["alpha"].get())
        if self._quiet or a == self.alpha.get(tok, 100):
            return
        if a >= 100:
            self.alpha.pop(tok, None)
        else:
            self.alpha[tok] = a
        self.mark()
        self.render()

    def on_auto(self):
        self.auto = self.auto_var.get()
        if self.auto:
            L.derive(self.colors)
        self.mark()
        self.render()

    def on_window(self):
        if self._quiet:
            return
        self.window = {"opacidad": int(self.win_var.get()), "sin_usar": int(self.idle_var.get())}
        try:
            self.root.attributes("-alpha", self.window["opacidad"] / 100 if self.try_alpha.get() else 1.0)
        except tk.TclError:
            pass
        self.mark()
        self.render()

    def all_opaque(self):
        self.alpha.clear()
        self.win_var.set(100)
        self.idle_var.set(100)
        self.on_window()
        self.toast("Todas las capas quedaron opacas.")

    def load_base(self, name):
        t = next(t for t in self.themes if t["nombre"] == name)
        self.colors = dict(t["colores"])
        self.base_name = name
        if not self.meta["descripcion"] or self.meta["descripcion"] in [x["descripcion"] for x in self.themes]:
            self.desc_var.set(t["descripcion"])
        if self.auto:
            L.derive(self.colors)
        self.mark()
        self.render()

    def on_meta(self):
        if self._quiet:
            return
        self.meta = {"nombre": self.name_var.get()[:32], "version": self.ver_var.get()[:8],
                     "descripcion": self.desc_var.get()[:80]}
        self.mark()
        if self.screen == "exp":
            self._paint_export()

    def on_author(self):
        name = self.author_var.get()[:24]
        self.settings["nombre"] = name
        try:
            K.save_settings(self.settings)
        except OSError:
            pass
        self._paint_author()

    # ---------------------------------------------------------------- paleta desde imagen
    def set_pal_acc(self, i):
        self.pal_acc = i
        self._paint_palette()

    def import_palette_image(self):
        path = filedialog.askopenfilename(parent=self.root, title="Elige una imagen", filetypes=IMG_TYPES)
        if path:
            self._palette_from_path(path)

    def on_drop_palette(self, ev):
        paths = self.root.tk.splitlist(ev.data)
        if paths:
            self._palette_from_path(paths[0])
        return ev.action

    def _palette_from_path(self, path):
        data, _n = self._read_image(path)
        if data:
            self._set_palette_from_bytes(data, os.path.basename(path))

    def _set_palette_from_bytes(self, data, name, refresh=True):
        try:
            im = L.from_bytes(data)
            pal = L.extract_palette(im)
            if not pal:
                raise ValueError("La imagen es completamente transparente.")
        except Exception as e:
            messagebox.showerror(APP, f"No se pudieron sacar los colores:\n{e}", parent=self.root)
            return
        self.pal_img, self.pal_name, self.palette = data, name, pal
        self.pal_acc = L.pick_accent(pal)
        if refresh:
            self._paint_palette()
            self.toast(f"Se sacaron {len(pal)} colores de «{name}». Pulsa «Aplicar al tema» para usarlos.")

    def apply_palette(self):
        dark = self.pal_mode.get() == "Tema oscuro"
        self.colors = L.palette_to_theme(self.palette, self.pal_acc, dark, self.colors)
        self.auto = True
        self.auto_var.set(True)
        fixed = L.fix_legibility(self.colors, self.alpha) if self.pal_fix.get() else []
        self.mark()
        self.render()
        extra = f" Se corrigió: {', '.join(LABELS[t].lower() for t in fixed)}." if fixed else ""
        self.toast(f"Colores tomados de «{self.pal_name}». Puedes seguir ajustando cada uno.{extra}", "ok")

    # ================================================================ archivos
    def _load_into_widgets(self):
        if not hasattr(self, "rows"):
            return
        self._quiet = True
        self.base_var.set(self.base_name)
        self.auto_var.set(self.auto)
        self.win_var.set(self.window["opacidad"])
        self.idle_var.set(self.window["sin_usar"])
        self.name_var.set(self.meta["nombre"])
        self.ver_var.set(self.meta["version"])
        self.desc_var.set(self.meta["descripcion"])
        self.file_var.set("")
        self._quiet = False
        self._paint_palette()
        self.dirty = False
        self._title()
        self.render()

    def ask_new(self):
        if self.dirty and not messagebox.askyesno(APP, "Hay cambios sin guardar. ¿Empezar un tema nuevo igual?",
                                                  parent=self.root):
            return
        self.new_theme()
        self.toast("Tema nuevo a partir de «Original».")

    def save_project(self):
        path = self.project_path or filedialog.asksaveasfilename(
            parent=self.root, title="Guardar proyecto", defaultextension=L.PROJECT_EXT,
            initialfile=L.slug(self.meta["nombre"]) + L.PROJECT_EXT,
            filetypes=[("Proyecto del Estudio", "*" + L.PROJECT_EXT)])
        if not path:
            return False
        try:
            L.save_project(path, self.state())
        except OSError as e:
            messagebox.showerror(APP, f"No se pudo guardar el proyecto:\n{e}", parent=self.root)
            return False
        self.project_path = path
        self.dirty = False
        self._title()
        self.toast(f"Proyecto guardado: {os.path.basename(path)} (sin cifrar, solo para ti).", "ok")
        return True

    def open_any(self):
        if self.dirty and not messagebox.askyesno(APP, "Hay cambios sin guardar. ¿Abrir otro igual?",
                                                  parent=self.root):
            return
        path = filedialog.askopenfilename(parent=self.root, title="Abrir tema o proyecto", filetypes=[
            ("Temas y proyectos", "*.npt *" + L.PROJECT_EXT), ("Tema .npt", "*.npt"),
            ("Proyecto", "*" + L.PROJECT_EXT)])
        if path:
            self.open_path(path)

    def open_path(self, path):
        """Abre un proyecto .nptproj o un tema .npt (también al abrir un archivo desde el sistema)."""
        if path.lower().endswith(L.PROJECT_EXT):
            try:
                s = L.load_project(path)
            except Exception as e:
                messagebox.showerror(APP, f"No se pudo abrir el proyecto:\n{e}", parent=self.root)
                return
            backup = self.state()
            try:
                self.apply_state(s)
            except Exception as e:                # proyecto dañado: se vuelve a lo que había
                self.apply_state(backup)
                messagebox.showerror(APP, f"El proyecto tiene datos que no se pueden usar:\n{e}", parent=self.root)
                return
            self.project_path = path
            self._title()
            self.toast(f"Proyecto abierto: {os.path.basename(path)}")
            return
        self.open_npt(path)

    def my_keys(self) -> set:
        keys = set()
        for info in (K.author_info(), self.official):
            if info and info.get("publica"):
                keys.add(info["publica"])
        return keys

    def open_npt(self, path):
        try:
            with open(path, "rb") as fh:
                res = npt.read(fh.read())
        except npt.NptError as e:
            messagebox.showerror(APP, str(e), parent=self.root)
            return
        except OSError as e:
            messagebox.showerror(APP, f"No se pudo leer el archivo:\n{e}", parent=self.root)
            return
        if res.author_key not in self.my_keys():
            messagebox.showinfo(APP, f"«{res.theme.name}» es un tema de {res.label}.\n\nSolo puedes abrir para "
                                     "editar los temas que firmaste tú.", parent=self.root)
            return
        t = res.theme
        imgs = {slot: {"src": data, "fit": "cover", "op": 100, "dark": 0, "blur": 0}
                for slot, data in t.images.items()}
        self.apply_state({"nombre": t.name, "version": _next_version(t.version), "descripcion": t.description,
                          "colores": t.colors, "alfa": t.alpha, "ventana": t.window, "auto": False, "imagenes": imgs,
                          "degradado": {"modo": "degradado" if t.gradient else
                                        ("imagen" if t.background.get("tipo") == "imagen" else "solido"),
                                        **t.gradient, "una_pieza": bool(t.background.get("una_pieza")),
                                        "tinte": t.background.get("tinte", L.TINT_DEFAULT)},
                          "secciones": t.sections, "pausar_animaciones": t.gif_pause})
        self.project_path = None
        self.dirty = True
        self._title()
        self.toast(f"«{t.name}» abierto para editar. La versión subió a {self.meta['version']}.", "ok")

    def build_theme_meta(self) -> npt.Theme:
        return npt.Theme(name=self.meta["nombre"].strip() or "Sin nombre", author=self.author,
                         colors=dict(self.colors), version=self.meta["version"].strip() or "1.0",
                         description=self.meta["descripcion"].strip(),
                         kind="oscuro" if L.is_dark(self.colors) else "claro",
                         alpha={k: v for k, v in self.alpha.items() if v < 100}, window=dict(self.window),
                         background=self.background_meta(),
                         sections=L.sections_clean(self.sections),
                         gif_pause=self.gif_pause)

    def export(self):
        try:
            key = self.signing_key()
        except _Cancel:
            return
        except Exception as e:
            messagebox.showerror(APP, f"No se pudo usar la clave de firma:\n{e}", parent=self.root)
            return
        if key is None:
            return
        theme = self.build_theme_meta()
        theme.images = self.final_images()
        try:
            data = npt.write(theme, key)
        except npt.NptError as e:
            messagebox.showerror(APP, str(e), parent=self.root)
            return
        fname = self.file_var.get().strip() or L.slug(theme.name) + npt.EXTENSION
        if not fname.lower().endswith(npt.EXTENSION):
            fname += npt.EXTENSION
        path = filedialog.asksaveasfilename(parent=self.root, title="Guardar tema", initialfile=fname,
                                            defaultextension=npt.EXTENSION, filetypes=[("Tema de Numpad Macros",
                                                                                        "*.npt")])
        if not path:
            return
        try:
            with open(path, "wb") as fh:
                fh.write(data)
        except OSError as e:
            messagebox.showerror(APP, f"No se pudo guardar el tema:\n{e}", parent=self.root)
            return
        res = npt.read(data)                     # comprobación: se vuelve a leer tal como lo hará Numpad Macros
        self.exp_done_t.configure(text=f"{os.path.basename(path)} guardado")
        self.exp_done_s.configure(text=f"{max(1, len(data) // 1024)} KB · cifrado y firmado. Al importarlo, Numpad "
                                       f"Macros lo mostrará como «{res.label}».")
        self.exp_done.pack(fill="x", pady=(10, 0))
        self.toast(f"Tema exportado: {path}", "ok")

    def signing_key(self):
        kind = "oficial" if self.mode == "creador" else "autor"
        if kind == "autor" and not K.has_author_key():
            self.first_run()
            if not K.has_author_key():
                return None
        info = self.official if kind == "oficial" else K.author_info()
        pw = None
        if info and info.get("protegida"):
            pw = self.passwords.get(kind)
            if pw is None:
                pw = self.ask_password("Desbloquear la clave de firma",
                                       "Tu clave está protegida con contraseña. Se pide una vez por sesión.")
                if pw is None:
                    raise _Cancel()
        try:
            k = K.load_official_key(pw) if kind == "oficial" else K.load_author_key(pw)
        except npt.KeyFileError as e:
            self.passwords.pop(kind, None)
            messagebox.showerror(APP, str(e), parent=self.root)
            raise _Cancel()
        if pw:
            self.passwords[kind] = pw
        return k

    # ================================================================ claves
    def startup(self):
        """Primera vez: ofrece usar la clave del Publicador (creador) o pide el nombre de autor."""
        pk = K.publicador_key_path()
        if pk and not self.settings.get("no_ofrecer_clave"):
            try:
                with open(pk, "rb") as fh:
                    raw = fh.read()
                K._official_from_pem(raw)
            except (OSError, npt.KeyFileError):
                raw = None
            if raw and messagebox.askyesno(
                    APP, "Encontramos tu clave de firma de temas (la que usa el Publicador).\n\n"
                         "¿Usarla en el Estudio para firmar temas oficiales?", parent=self.root):
                try:
                    K.import_key_file(raw)
                except (OSError, npt.KeyFileError) as e:
                    messagebox.showerror(APP, f"No se pudo guardar la clave:\n{e}", parent=self.root)
                    return
                self.mode, self.official = K.mode(), K.official_info()
                self._build()
                self.render()
                self.toast("Modo creador: tus temas se firmarán como «Oficial · OkumaWsX».", "ok")
                return
            if raw:
                self.settings["no_ofrecer_clave"] = True
                K.save_settings(self.settings)
        if not K.has_author_key():
            self.first_run()

    def first_run(self):
        d = Dialog(self.root, "Bienvenido al Estudio de Temas")
        self.lbl(d.body, "¿Con qué nombre quieres firmar tus temas?", 2, True).pack(fill="x")
        self.lbl(d.body, "Aparecerá en Numpad Macros como «Comunidad · tu nombre». Puedes cambiarlo después. No hace "
                         "falta que sea tu nombre real.", -1, color="muted", wrap=380).pack(fill="x", pady=(4, 10))
        var = tk.StringVar(value=self.settings.get("nombre", ""))
        ent = self.entry(d.body, var, 30)
        ent.pack(fill="x", ipady=4)
        ent.focus_set()
        note = self.lbl(d.body, "", -2, color="bad_text", wrap=380)
        note.pack(fill="x", pady=(4, 0))

        def done(anon=False):
            name = "" if anon else var.get().strip()[:24]
            if npt.is_reserved_name(name):
                note.configure(text="Ese nombre está reservado para el creador oficial. Elige otro.")
                return
            self.settings["nombre"] = name
            K.save_settings(self.settings)
            K.create_author_key(name)
            d.close()
            self._build()
            self.render()
            self.toast(f"Listo: tu firma de autor está creada{' como ' + name if name else ' (Anónimo)'}.", "ok")

        d.button("Continuar", done, accent=True)
        d.button("Sin nombre (Anónimo)", lambda: done(True))
        ent.bind("<Return>", lambda e: done())
        d.wait()

    def ask_password(self, title, text, confirm=False):
        d = Dialog(self.root, title)
        self.lbl(d.body, text, -1, color="muted", wrap=360).pack(fill="x", pady=(0, 8))
        v1, v2 = tk.StringVar(), tk.StringVar()
        e1 = tk.Entry(d.body, textvariable=v1, show="•", bg=C["panel2"], fg=C["text"], insertbackground=C["text"],
                      relief="flat", highlightthickness=1, highlightbackground=C["line"], highlightcolor=C["acc"],
                      font=fnt())
        e1.pack(fill="x", ipady=4)
        e1.focus_set()
        e2 = None
        if confirm:
            self.lbl(d.body, "Repítela", -1, color="muted").pack(fill="x", pady=(8, 2))
            e2 = tk.Entry(d.body, textvariable=v2, show="•", bg=C["panel2"], fg=C["text"], insertbackground=C["text"],
                          relief="flat", highlightthickness=1, highlightbackground=C["line"],
                          highlightcolor=C["acc"], font=fnt())
            e2.pack(fill="x", ipady=4)
        note = self.lbl(d.body, "", -2, color="bad_text")
        note.pack(fill="x", pady=(4, 0))
        out = {"pw": None}

        def ok():
            if confirm and len(v1.get()) < 8:
                note.configure(text="Debe tener al menos 8 caracteres.")
                return
            if confirm and v1.get() != v2.get():
                note.configure(text="No coinciden.")
                return
            out["pw"] = v1.get()
            d.close()

        d.button("Aceptar", ok, accent=True)
        d.button("Cancelar", d.close)
        for e in (e1, e2):
            if e:
                e.bind("<Return>", lambda ev: ok())
        d.wait()
        return out["pw"]

    def backup_key(self, kind):
        fname = K.OFFICIAL_FILE if kind == "oficial" else K.AUTHOR_FILE
        try:
            raw = K.read_file(fname)
        except OSError:
            messagebox.showerror(APP, "Todavía no hay una clave para guardar.", parent=self.root)
            return
        base = "okumawsx-clave-oficial" if kind == "oficial" else L.slug(self.author or "anonimo") + "-firma"
        path = filedialog.asksaveasfilename(parent=self.root, title="Guardar copia de seguridad",
                                            initialfile=base + ".npkey", defaultextension=".npkey",
                                            filetypes=[("Clave del Estudio", "*.npkey")])
        if not path:
            return
        try:
            with open(path, "wb") as fh:
                fh.write(raw)
        except OSError as e:
            messagebox.showerror(APP, f"No se pudo guardar:\n{e}", parent=self.root)
            return
        self.toast(f"Copia de seguridad guardada en {path}. Guárdala en un lugar seguro.", "ok")

    def change_password(self, kind):
        info = self.official if kind == "oficial" else K.author_info()
        if not info:
            return
        old = None
        if info.get("protegida"):
            old = self.ask_password("Contraseña actual", "Escribe la contraseña actual de la clave.")
            if old is None:
                return
        try:
            k = K.load_official_key(old) if kind == "oficial" else K.load_author_key(old)
        except npt.KeyFileError as e:
            messagebox.showerror(APP, str(e), parent=self.root)
            return
        new = self.ask_password("Nueva contraseña", "Elige una contraseña de al menos 8 caracteres. Se pedirá al "
                                                    "exportar un tema.", confirm=True)
        if new is None:
            return
        K._write_private(os.path.join(K.folder(), K.OFFICIAL_FILE if kind == "oficial" else K.AUTHOR_FILE),
                         k.to_file(new))
        self.passwords[kind] = new
        self.official = K.official_info()
        self._build()
        self.toast("Contraseña guardada. Haz una copia de seguridad nueva.", "ok")

    def import_backup(self):
        path = filedialog.askopenfilename(parent=self.root, title="Importar copia de seguridad",
                                          filetypes=[("Claves", "*.npkey *.key"), ("Todos", "*")])
        if not path:
            return
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
            if raw.lstrip().startswith(b"-----BEGIN"):
                raw = K._official_from_pem(raw)
            info = npt.SigningKey.info(raw)
        except (OSError, npt.KeyFileError) as e:
            messagebox.showerror(APP, str(e), parent=self.root)
            return
        kind = "oficial" if info.get("tipo") == "oficial" else "autor"
        dest = K.OFFICIAL_FILE if kind == "oficial" else K.AUTHOR_FILE
        if os.path.exists(os.path.join(K.folder(), dest)) and not messagebox.askyesno(
                APP, "Ya hay una clave de ese tipo en esta PC. ¿Reemplazarla por la copia?", parent=self.root):
            return
        try:
            K.import_key_file(raw)
        except npt.KeyFileError as e:
            messagebox.showerror(APP, str(e), parent=self.root)
            return
        self.settings = K.load_settings()
        self.mode = K.mode()
        self.official = K.official_info()
        self._build()
        self.render()
        self.toast("Clave oficial importada: el Estudio está en modo creador." if kind == "oficial"
                   else "Firma de autor importada.", "ok")

    def copy(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.toast("Clave pública copiada (no es secreta).", "ok")

    def on_close(self):
        if self.dirty:
            r = messagebox.askyesnocancel(APP, "¿Guardar el proyecto antes de salir?", parent=self.root)
            if r is None or (r and not self.save_project()):
                return
        self.root.destroy()


class _Cancel(Exception):
    pass


def _next_version(v: str) -> str:
    parts = str(v).split(".")
    try:
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)[:8]
    except ValueError:
        return v


class Dialog:
    """Ventana modal sencilla con el estilo del Estudio."""

    def __init__(self, root, title):
        self.top = tk.Toplevel(root, bg=C["panel"])
        self.top.title(title)
        self.top.transient(root)
        self.top.resizable(False, False)
        self.body = tk.Frame(self.top, bg=C["panel"], padx=20, pady=16)
        self.body.pack(fill="both")
        self.btns = tk.Frame(self.top, bg=C["panel"], padx=20, pady=(0))
        self.btns.pack(fill="x", pady=(0, 16))
        self.top.protocol("WM_DELETE_WINDOW", self.close)

    def button(self, text, cmd, accent=False):
        ttk.Button(self.btns, text=text, command=cmd, style="Accent.TButton" if accent else "TButton").pack(
            side="right", padx=(6, 0))

    def wait(self):
        self.top.update_idletasks()
        r = self.top.master
        x = r.winfo_rootx() + (r.winfo_width() - self.top.winfo_width()) // 2
        y = r.winfo_rooty() + (r.winfo_height() - self.top.winfo_height()) // 3
        self.top.geometry(f"+{max(0, x)}+{max(0, y)}")
        try:
            self.top.wait_visibility()
            self.top.grab_set()
        except tk.TclError:
            pass
        self.top.wait_window()

    def close(self):
        self.top.destroy()


def _icon_path():
    for base in (getattr(sys, "_MEIPASS", ""), HERE, os.path.join(HERE, "..", "..", "assets")):
        path = os.path.join(base, "icon-estudio.png")
        if base and os.path.isfile(path):
            return os.path.abspath(path)
    return None


def _integrate_linux(icon):
    """Menú de aplicaciones + icono propio en la barra de tareas (solo el programa empaquetado)."""
    if not (sys.platform.startswith("linux") and getattr(sys, "frozen", False) and icon):
        return

    def job():
        try:
            from npm import desktop_linux
            env = os.environ.copy()
            for k in list(env):
                if k.startswith(("_PYI", "_MEI")):
                    env.pop(k, None)
            desktop_linux.install("estudio-temas-numpad-macros", "Estudio de Temas · Numpad Macros",
                                  "Crear temas para Numpad Macros", sys.executable, icon,
                                  "EstudioTemasNumpadMacros", categories="Graphics;Utility;", env=env)
        except Exception:
            pass
    threading.Thread(target=job, daemon=True).start()


def _make_root(cls):
    """Ventana principal. Si arrastrar y soltar (tkdnd) no carga en este sistema, se usa sin él."""
    global TkinterDnD
    if TkinterDnD:
        try:
            return TkinterDnD.Tk(className=cls)
        except Exception:
            TkinterDnD = None
    return tk.Tk(className=cls)


def _callback_error(exc, val, tb):
    """Un error dentro de la ventana: se anota y se avisa, pero el programa sigue abierto."""
    import traceback
    text = "".join(traceback.format_exception(exc, val, tb))
    try:
        sys.stderr.write(text)
        os.makedirs(os.path.dirname(_log_path()), exist_ok=True)
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception:
        pass
    if "--probar" in sys.argv:
        return
    try:
        messagebox.showerror(APP, f"Algo salió mal:\n{val}\n\nEl detalle quedó en:\n{_log_path()}")
    except Exception:
        pass


def main():
    probe = "--probar" in sys.argv          # prueba automática: abre todo y se cierra sola
    argv = [a for a in sys.argv[1:] if a != "--probar"]
    cls = "EstudioTemasNumpadMacros"
    root = _make_root(cls)
    root.report_callback_exception = _callback_error
    root.title(APP)
    icon = _icon_path()
    try:
        if icon:
            root.iconphoto(True, tk.PhotoImage(file=icon))
    except tk.TclError:
        pass
    _integrate_linux(icon)
    if probe:
        App.startup = lambda self: None
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    if probe:
        errors = []
        root.report_callback_exception = lambda *e: (_callback_error(*e), errors.append(e))
        def run(steps=("sec", "img", "exp", "key", "edit")):
            if steps:
                app.show(steps[0])
                root.after(400, lambda: run(steps[1:]))
            else:
                app.apply_palette()
                app.apply_template("todo")          # 8 espacios, con GIF animados
                app.bg_generate()                   # fondo de imagen de una pieza
                app.onep_var.set(True)
                app.on_one_piece()
                app.show("img")
                root.update()
                theme = app.build_theme_meta()
                theme.images = app.final_images()
                res = npt.read(npt.write(theme, npt.SigningKey.generate()))
                if res.theme.background.get("tipo") != "imagen" or "fondo" not in res.theme.images \
                        or not res.theme.background.get("una_pieza"):
                    errors.append("el fondo de imagen de una pieza no se exportó")
                for s in Scrollable.all:            # columnas que caben enteras: la rueda no las mueve
                    if s.winfo_ismapped() and s.inner.winfo_reqheight() <= s.cv.winfo_height():
                        s.cv.yview_scroll(-5, "units")
                        if s.cv.canvasy(0) != 0:
                            errors.append("una columna corta se desplaza hacia arriba")
                app.grad_mode(True)
                app.grad_add_stop()
                app.grad_from("c")
                app.show("sec")
                app.focus_section()
                app.show("img")
                root.update()
                theme = app.build_theme_meta()     # se exporta y se vuelve a leer, como Numpad Macros
                theme.images = app.final_images()
                res = npt.read(npt.write(theme, npt.SigningKey.generate()))
                if not (res.theme.gradient and res.theme.animated and res.theme.sections):
                    errors.append("el tema exportado no trae degradado, secciones o animaciones")
                root.update()
                root.destroy()
                if errors:
                    sys.exit(1)
                print("Estudio de Temas: prueba OK")
        root.after(800, run)
    elif argv and os.path.isfile(argv[0]):
        p = argv[0]
        root.after(300, lambda: app.open_path(p))
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        import traceback
        _fatal(traceback.format_exc())
