# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Ventana principal de Numpad Macros (tkinter, Windows / Linux / macOS)."""
import os
import queue
import sys
import threading
import traceback
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import aa, __version__, about, capture, config, library, sysutil, updater, xbg
from . import loudness as ld
from .capture import PLATFORM, BackendError, describe_device
from .engine import Engine
from .dialogs import NewsDialog, UpdateDialog
from . import themes
from .devices_tab import DevicesTab
from .sound_picker import SoundPicker
from .theme_art import CanvasPill, CanvasText, ThemeArt
from .themes_tab import ThemesTab
from .remote import RemoteServer
from .keys import (PHONE_IDS, VIRTUAL_COLS, VIRTUAL_COUNT, VIRTUAL_ROWS, phone_layout, KEY_CHOICES, MODIFIER_KEYSYMS, MODIFIERS, NUMPAD_IDS, NUMPAD_LAYOUT, ROW_IDS,
                   ROW_LAYOUT, TOGGLE_CHOICES, busy_reason, combo_text, join_combo, key_label,
                   keysym_to_key, parse_combo, parse_toggle)
from .senders import make_sender
from .soundboard import AUDIO_EXT, PLAY_MODES, clean_env, make_soundboard, title_of
from .widgets import CompCurve, Meter

from .theme import BASE, BUTTON_COLORS, C, apply_theme, FONT, IS_LINUX, IS_MAC, IS_WIN, MOD_LABEL, OS_NAME, button_color, mix

ACTION_TYPES = [
    ("none", "— Sin acción —"),
    ("file", "🔊  Reproducir sonido"),
    ("sound_stop", "■  Detener todos los sonidos"),
    ("keys", "⌨  Atajo de teclado"),
    ("bank_next", "▶  Banco siguiente"),
    ("bank_prev", "◀  Banco anterior"),
    ("bank_go", "→  Ir a un banco"),
]
TYPE_LABEL = dict(ACTION_TYPES)
LABEL_TYPE = {v: k for k, v in ACTION_TYPES}
MODE_LABEL = dict(PLAY_MODES)
LABEL_MODE = {v: k for k, v in PLAY_MODES}
MODE_ICON = {"overlap": "", "restart": "↺ ", "toggle": "⏯ ", "hold": "⏵ "}


def short_action(act, narrow=False) -> str:
    """Texto corto para dibujar en la tecla. `narrow`: tecla de una columna (2 líneas cortas)."""
    if not act:
        return ""
    t = act.get("type")
    if t == "file":
        title = act.get("title") or title_of(act.get("path", "")) or "?"
        icon = "🔊 " + MODE_ICON.get(act.get("mode", "overlap"), "")
        if narrow:                       # el icono se dibuja aparte, arriba a la derecha
            return title if len(title) <= 8 else title[:7] + "…"
        return icon + (title if len(title) <= 15 else title[:14] + "…")
    if t == "keys" and narrow:
        txt = combo_text(act.get("combo", ""))
        return txt.replace("+", "+\n") if len(txt) > 8 else txt
    return {
        "sound_stop": "■ Detener",
        "keys": combo_text(act.get("combo", "")),
        "bank_next": "Banco ▶",
        "bank_prev": "◀ Banco",
        "bank_go": f"→ Banco {act.get('bank', 1)}",
    }.get(t, "")



# Medir texto le cuesta a Tk unos 4 ms en Linux (cada vez). Al cambiar el tamaño de la ventana la
# cabecera y el pie se reacomodan en cada cuadro: se recuerda lo ya medido (la letra no cambia sin
# volver a armar la ventana).
_FONT_CACHE = {}


def font_measure(w, font, text) -> int:
    key = ("m", str(font), text)
    v = _FONT_CACHE.get(key)
    if v is None:
        v = _FONT_CACHE[key] = int(w.tk.call("font", "measure", font, text))
    return v


def font_linespace(w, font) -> int:
    key = ("l", str(font))
    v = _FONT_CACHE.get(key)
    if v is None:
        v = _FONT_CACHE[key] = int(w.tk.call("font", "metrics", font, "-linespace"))
    return v


class _HeadSlot(tk.Frame):
    """Aviso de versión nueva dentro del encabezado dibujado: grid() lo muestra y grid_remove() lo oculta."""

    def __init__(self, master, app, **kw):
        super().__init__(master, **kw)
        self.app = app
        self.shown = False

    def grid(self, **_kw):
        self.shown = True
        self.app._schedule_head()

    def grid_remove(self):
        self.shown = False
        self.app._schedule_head()


class FlatButton(tk.Label):
    """Botón de color plano. tk.Button ignora el color de fondo en macOS."""

    def __init__(self, master, command=None, **kw):
        kw.setdefault("cursor", "hand2")
        super().__init__(master, **kw)
        self._cmd = command
        self.bind("<Button-1>", lambda e: self._cmd and self._cmd())


def make_listbox(parent, height, width=20):
    box = tk.Frame(parent, bg=C["panel2"], highlightthickness=1, highlightbackground=C["line"],
                   highlightcolor=C["line"])
    box.columnconfigure(0, weight=1)
    box.rowconfigure(0, weight=1)
    lb = tk.Listbox(box, bg=C["panel2"], fg=C["text"], selectbackground=C["accent_bg"],
                    selectforeground=C["accent"], highlightthickness=0, bd=0, activestyle="none",
                    font=(FONT, BASE), height=height, exportselection=False, width=width)
    lb.grid(row=0, column=0, sticky="nsew", padx=(8, 2), pady=6)
    sb = ttk.Scrollbar(box, orient="vertical", command=lb.yview)
    sb.grid(row=0, column=1, sticky="ns", padx=(0, 3), pady=4)
    lb.configure(yscrollcommand=sb.set)
    return box, lb


SCROLL_HOOKS: list = []          # se llaman al desplazar (fondo de una pieza)


def scroll_frame(parent):
    """Marco con barra de desplazamiento vertical (para pestañas con muchas opciones)."""
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(0, weight=1)
    cv = tk.Canvas(parent, bg=C["panel"], highlightthickness=0, bd=0)
    sb = ttk.Scrollbar(parent, orient="vertical", command=cv.yview)
    inner = ttk.Frame(cv, style="Panel.TFrame")
    win = cv.create_window(0, 0, window=inner, anchor="nw")

    def on_scroll(a, b):
        sb.set(a, b)
        for hook in list(SCROLL_HOOKS):
            try:
                hook()
            except Exception:
                pass
    cv.configure(yscrollcommand=on_scroll)
    cv.grid(row=0, column=0, sticky="nsew")

    def resize(_e=None):
        cv.configure(scrollregion=(0, 0, inner.winfo_reqwidth(), inner.winfo_reqheight()))
        cv.itemconfigure(win, width=cv.winfo_width())
        if inner.winfo_reqheight() > cv.winfo_height() > 1:
            sb.grid(row=0, column=1, sticky="ns")
        else:
            sb.grid_remove()
            cv.yview_moveto(0)

    inner.bind("<Configure>", resize)
    cv.bind("<Configure>", resize)

    def wheel(e):
        if not sb.winfo_ismapped():
            return
        if getattr(e, "num", 0) in (4, 5):
            cv.yview_scroll(-3 if e.num == 4 else 3, "units")
        else:
            cv.yview_scroll(int(-e.delta / (120 if IS_WIN else 1)) or (-1 if e.delta > 0 else 1), "units")

    def bind_all(_e):
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            cv.bind_all(seq, wheel)

    def unbind_all(_e):
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            cv.unbind_all(seq)

    cv.bind("<Enter>", bind_all)
    cv.bind("<Leave>", unbind_all)
    return inner


LBL_W = 10           # ancho (en letras) de la columna de nombres en el editor


class App:
    UNIT, GAP = 60, 7
    RUNIT, RGAP = 40, 6         # teclas de la fila de números
    VUNIT, VGAP = 58, 8         # teclas virtuales (se recalculan con la ventana)
    VMARGIN = VPAD = (0, 0, 0, 0)   # en px de pantalla (se recalculan con la escala)
    VBORDER = 0
    # Recuadro de las teclas virtuales como una caja de CSS, en px a escala 1
    # (tools/ajustar_panel.py los edita a la vista). Lados: (arriba, derecha, abajo, izquierda).
    V_MARGIN = (8, 0, 16, 0)        # margin: espacio fuera del recuadro
    V_BORDER = 0                    # border: grosor del borde del recuadro (0 = sin borde)
    V_PADDING = (14, 14, 14, 14)    # padding: espacio entre el borde y las teclas
    V_MAX = 88                      # content: lado máximo de una tecla
    V_MIN = 28                      # content: lado mínimo (si no cabe, antes se achica que cortarse)
    V_GAP_DIV = 8                   # content: separación entre teclas = lado / V_GAP_DIV (mín. 6 px)
    V_ALIGN = "center"              # position: el recuadro a la izquierda ("left"), "center" o "right"
    NMARGIN = NPAD = (0, 0, 0, 0)   # numpad: en px de pantalla (se recalculan con la escala)
    NBORDER = 0
    # Recuadro de las teclas del numpad, la misma caja de CSS que el de las virtuales
    N_MARGIN = (4, 0, 8, 0)         # margin: espacio fuera del recuadro
    N_BORDER = 0                    # border: grosor del borde del recuadro (0 = sin borde)
    N_PADDING = (14, 14, 14, 14)    # padding: espacio entre el borde y las teclas
    N_MAX = 92                      # content: lado máximo de una tecla
    N_MIN = 28                      # content: lado mínimo (si no cabe, antes se achica que cortarse)
    N_GAP_DIV = 9                   # content: separación entre teclas = lado / N_GAP_DIV (mín. 6 px)
    N_ALIGN = "center"              # position: el recuadro a la izquierda ("left"), "center" o "right"
    N_SAFE = 10                     # margen de seguridad que siempre queda libre al final del panel
    # padding de cada pestaña de la derecha (arriba, derecha, abajo, izquierda), como en CSS
    TAB_PADDING = (14, 18, 10, 18)

    def __init__(self, root: tk.Tk, start_minimized=False):
        self.root = root
        self.first_run = not os.path.exists(config.config_path())
        self.cfg = config.load()
        self.theme = themes.current(self.cfg)
        apply_theme(self.theme["colors"])           # antes de crear cualquier ventana
        self.art = ThemeArt(self, self.theme)       # imágenes, degradado y secciones del tema
        self.art.tweak_colors()
        self.uiq: queue.Queue = queue.Queue()     # mensajes de otros hilos -> GUI
        self.sender, self.sender_err = make_sender()
        self.board = make_soundboard(self.cfg["audio"])
        self.engine = Engine(self.cfg, self.sender, on_save=self._write_cfg, soundboard=self.board)
        if self.cfg.get("start_paused", True):
            # Empieza en pausa: el numpad escribe normal hasta pulsar ACTIVO (se fija antes de
            # abrir la captura, así nunca se toma el numpad al iniciar)
            self.engine.active = False
        # app del celular: los avisos llegan desde otros hilos y se atienden en _poll
        self.remote = RemoteServer(self.cfg, self.engine, self.board,
                                   notify=lambda *w: self.uiq.put(("remote",) + w),
                                   save=lambda: self.uiq.put(("remote_save",)))
        self._dev_refresh_job = None
        self.backend = None
        self.fallback = ""                            # por qué se usa el modo sin driver
        self.layer = self.cfg["active_bank"]          # capa que se edita: int o "global"
        self.selected = "47"
        self.flash = {}
        self.tray = None
        self.toast = None
        self._editor_lock = False
        self._save_job = None
        self.relaunch = None                          # ruta del programa nuevo (Linux)
        self._rec = None                              # grabando una combinación: "keys"/"toggle"
        self._rec_mods = set()
        self.update_rel = None                        # versión nueva encontrada
        self._upd_dialog = None
        self.estudio_upd = None                       # (Release, versión) del Estudio de Temas
        self._estudio_busy = False
        try:
            choice = updater.take_installer_choice()        # lo elegido en el instalador de Windows
            if choice is not None:
                self.cfg["updates"]["estudio"] = choice
                config.save(self.cfg)                       # el valor del registro ya se borró
            elif self.cfg["updates"].get("estudio") is None:   # sin decidir: activa si ya está instalado
                self.cfg["updates"]["estudio"] = updater.estudio_installed() is not None
        except Exception:
            if self.cfg["updates"].get("estudio") is None:
                self.cfg["updates"]["estudio"] = False
        self._lufs_q: queue.Queue = queue.Queue()
        self._lufs_busy = False
        for item in self.cfg.get("library", []):      # mediciones guardadas
            if item.get("lufs_mtime"):
                self.board.set_known_loudness(item["path"], item["lufs_mtime"], item.get("lufs"))

        self._style()
        self._set_icon()
        self._build()
        self._apply_phone_only()
        self._start_backend()
        try:
            self.remote.start()
        except Exception as e:
            self.remote.errors["wifi"] = str(e)
        self.devtab.refresh()
        if IS_LINUX and self._needs_perms():
            self._set_status("Falta un paso: ve a «Numpad y opciones» → «Dar permisos…» "
                             "(se pide tu contraseña una sola vez).", bad=True)
        elif self.sender_err:
            self._set_status(f"Los atajos no funcionarán: {self.sender_err}", bad=True)
        elif not self.engine.active:
            self._set_status("En pausa: el numpad funciona normal. Pulsa PAUSADO (arriba a la derecha) "
                             "para activar tus acciones.")
        self._apply_audio_async(initial=True)
        self._redraw()
        self._load_editor()
        self._update_bank_label()
        self.root.after(30, self._poll)
        self.root.after(200, self._tick_meters)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._setup_tray()
        if start_minimized and self.tray:
            self.root.withdraw()
        self._queue_loudness()
        self._setup_alpha()
        self._setup_responsive()
        self.root.after_idle(lambda: xbg.paint(self.root))       # fondo nativo de los widgets ttk
        self.root.after(1200, self._startup_news)
        self.root.after(3000, lambda: self._check_updates(manual=False))

    # ================================================================ estilo
    def _style(self, first=True):
        r = self.root
        r.configure(bg=C["bg"])
        if first:
            r.title("Numpad Macros")
            # tamaño inicial según la pantalla (laptops de 768 px de alto incluidas)
            sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
            w, h = min(1200, int(sw * .94)), min(820, int(sh * .88))
            r.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 3)}")
            r.minsize(min(980, sw - 40), min(640, sh - 80))
        s = ttk.Style(r)
        s.theme_use("clam")
        flat = dict(lightcolor=C["panel2"], darkcolor=C["panel2"], bordercolor=C["line"])
        s.configure(".", background=C["bg"], foreground=C["text"], fieldbackground=C["panel2"],
                    bordercolor=C["line"], lightcolor=C["line"], darkcolor=C["line"],
                    troughcolor=C["panel2"], focuscolor=C["panel"], selectbackground=C["accent_bg"],
                    selectforeground=C["text"], insertcolor=C["text"], font=(FONT, BASE))
        s.configure("TFrame", background=C["bg"])
        s.configure("Panel.TFrame", background=C["panel"])
        s.configure("Realce.Panel.TFrame", background=C["panel"], borderwidth=2, relief="solid",
                    bordercolor=C["accent"], lightcolor=C["accent"], darkcolor=C["accent"])
        s.configure("TLabel", background=C["bg"])
        s.configure("Panel.TLabel", background=C["panel"])
        s.configure("Field.TLabel", background=C["panel"], foreground=C["muted"])
        s.configure("Muted.TLabel", background=C["panel"], foreground=C["muted"], font=(FONT, BASE - 1))
        s.configure("Warn.TLabel", background=C["panel"], foreground=C["warn"], font=(FONT, BASE - 1))
        s.configure("H.TLabel", background=C["panel"], font=(FONT, BASE + 4, "bold"))
        s.configure("Title.TLabel", background=C["bg"], font=(FONT, BASE + 7, "bold"))

        # botones planos
        s.configure("TButton", background=C["panel2"], foreground=C["text"], padding=(12, 6),
                    borderwidth=1, relief="flat", focusthickness=0, **flat)
        s.map("TButton", background=[("pressed", C["line"]), ("active", mix(C["panel2"], C["text"], .08)),
                                     ("disabled", C["panel"])],
              lightcolor=[("active", mix(C["panel2"], C["text"], .08))],
              darkcolor=[("active", mix(C["panel2"], C["text"], .08))],
              bordercolor=[("focus", C["muted"])],
              foreground=[("disabled", C["muted"])])
        s.configure("Accent.TButton", background=C["accent"], foreground=C["on_accent"],
                    lightcolor=C["accent"], darkcolor=C["accent"], bordercolor=C["accent"],
                    font=(FONT, BASE, "bold"))
        s.map("Accent.TButton", background=[("active", C["accent_hover"]), ("disabled", C["panel2"])],
              lightcolor=[("active", C["accent_hover"])], darkcolor=[("active", C["accent_hover"])],
              bordercolor=[("active", C["accent_hover"])], foreground=[("disabled", C["muted"])])

        # campos: combobox, entry y spinbox planos (borde de color al tener el foco)
        for w in ("TCombobox", "TEntry", "TSpinbox"):
            s.configure(w, foreground=C["text"], fieldbackground=C["panel2"], background=C["panel2"],
                        arrowcolor=C["muted"], arrowsize=13, padding=(8, 5), insertcolor=C["text"],
                        selectbackground=C["panel2"], selectforeground=C["text"], **flat)
            s.map(w, bordercolor=[("focus", C["accent"]), ("hover", C["muted"])],
                  lightcolor=[("focus", C["panel2"])], darkcolor=[("focus", C["panel2"])],
                  fieldbackground=[("readonly", C["panel2"]), ("disabled", C["panel"])],
                  background=[("active", C["panel2"]), ("pressed", C["panel2"])],
                  arrowcolor=[("active", C["text"])],
                  foreground=[("readonly", C["text"]), ("disabled", C["muted"])])
        s.configure("TEntry", selectbackground=C["accent_bg"])
        r.option_add("*TCombobox*Listbox.background", C["panel2"])
        r.option_add("*TCombobox*Listbox.foreground", C["text"])
        r.option_add("*TCombobox*Listbox.selectBackground", C["accent_bg"])
        r.option_add("*TCombobox*Listbox.selectForeground", C["text"])
        r.option_add("*TCombobox*Listbox.font", (FONT, BASE))
        r.option_add("*TCombobox*Listbox.borderWidth", 0)
        r.option_add("*TCombobox*Listbox.highlightThickness", 0)

        # pestañas
        s.configure("TNotebook", background=C["bg"], borderwidth=1, bordercolor=C["line"],
                    lightcolor=C["panel"], darkcolor=C["panel"], tabmargins=(0, 0, 0, 0))
        tab_bg = C.get("tab_bg", mix(C["bg"], C["panel"], .5))
        tab_on = C.get("tab_on", C["panel"])
        art = getattr(self, "art", None)
        tab_line = C["accent"] if art is not None and art.realce("tabs") else C["line"]
        if art is not None and art.realce("body"):
            s.configure("TNotebook", bordercolor=C["accent"])
        s.configure("TNotebook.Tab", background=tab_bg, foreground=C["muted"],
                    padding=(14, 7), borderwidth=1, bordercolor=tab_line,
                    lightcolor=tab_bg, darkcolor=tab_bg,
                    font=(FONT, BASE, "bold"))
        s.map("TNotebook.Tab", background=[("selected", tab_on), ("active", tab_on)],
              lightcolor=[("selected", tab_on)], darkcolor=[("selected", tab_on)],
              foreground=[("selected", C["text"]), ("active", C["text"])],
              expand=[("selected", (0, 0, 0, 1))], padding=[("selected", (14, 7))])

        s.configure("Horizontal.TProgressbar", background=C["accent"], troughcolor=C["panel2"],
                    bordercolor=C["panel2"], lightcolor=C["accent"], darkcolor=C["accent"])
        s.configure("Banner.TFrame", background=C["accent_bg"])
        s.configure("Card.TFrame", background=C["panel2"])
        s.configure("Card.TLabel", background=C["panel2"])
        s.configure("CardMuted.TLabel", background=C["panel2"], foreground=C["muted"], font=(FONT, BASE - 1))

        # casillas, opciones, deslizador y barra de desplazamiento con imágenes propias
        self._make_control_images(s)
        for w in ("TCheckbutton", "TRadiobutton"):
            s.configure(w, background=C["panel"], foreground=C["text"], padding=(0, 2), focuscolor=C["panel"])
            s.map(w, background=[("active", C["panel"])], foreground=[("disabled", C["muted"])])
        for w in ("Card.TCheckbutton", "Card.TRadiobutton"):
            s.configure(w, background=C["panel2"], foreground=C["text"], focuscolor=C["panel2"])
            s.map(w, background=[("active", C["panel2"])])
        s.configure("Horizontal.TScale", background=C["panel"])
        s.configure("Card.Horizontal.TScale", background=C["panel2"])
        s.configure("Vertical.TScrollbar", troughcolor=C["panel"], background=C["panel"],
                    bordercolor=C["panel"], lightcolor=C["panel"], darkcolor=C["panel"])

    def _make_control_images(self, s):
        """Casillas y opciones redondeadas, deslizador con perilla y barras delgadas."""
        from . import ui_images as ui
        d = max(1.0, self.root.winfo_fpixels("1i") / 96)
        n = int(round(16 * d))
        old = getattr(self, "_ctl_img", None)
        img = old if old else {}

        def mk(name, data):
            if name in img:                   # cambio de tema: misma imagen, colores nuevos
                img[name].configure(data=data)
            else:
                img[name] = tk.PhotoImage(master=self.root, data=data)
            return img[name]
        if old:                               # los elementos ttk ya existen y usan estas imágenes
            for kind, fn in (("check", ui.checkbox), ("radio", ui.radio)):
                mk(kind + "0", fn(n, False, C))
                mk(kind + "1", fn(n, True, C))
                mk(kind + "0h", fn(n, False, C, hover=True))
                mk(kind + "1h", fn(n, True, C, hover=True))
                mk(kind + "0d", fn(n, False, C, disabled=True))
                mk(kind + "1d", fn(n, True, C, disabled=True))
            k = int(round(18 * d))
            mk("knob", ui.knob(k, C))
            mk("knobh", ui.knob(k, C, hover=True))
            mk("track", ui.track(int(20 * d), k, max(3, int(4 * d)), C))
            bw = int(round(10 * d))
            mk("thumb", ui.pill(bw, int(28 * d), C["line"]))
            mk("thumbh", ui.pill(bw, int(28 * d), C["muted"]))
            return
        try:
            for kind, fn in (("check", ui.checkbox), ("radio", ui.radio)):
                off, on = mk(kind + "0", fn(n, False, C)), mk(kind + "1", fn(n, True, C))
                hoff, hon = mk(kind + "0h", fn(n, False, C, hover=True)), mk(kind + "1h", fn(n, True, C, hover=True))
                doff, don = (mk(kind + "0d", fn(n, False, C, disabled=True)),
                             mk(kind + "1d", fn(n, True, C, disabled=True)))
                el = f"NM.{kind}.indicator"
                s.element_create(el, "image", off,
                                 ("disabled", "selected", don), ("disabled", doff),
                                 ("active", "selected", hon), ("selected", on), ("active", hoff),
                                 width=n + int(7 * d), sticky="w")
                base = "Checkbutton" if kind == "check" else "Radiobutton"
                s.layout("T" + base, [(base + ".padding", {"sticky": "nswe", "children": [
                    (el, {"side": "left", "sticky": ""}),
                    (base + ".label", {"side": "left", "sticky": "nswe"})]})])
            k = int(round(18 * d))
            knob, knob_h = mk("knob", ui.knob(k, C)), mk("knobh", ui.knob(k, C, hover=True))
            trough = mk("track", ui.track(int(20 * d), k, max(3, int(4 * d)), C))
            s.element_create("NM.Horizontal.Scale.trough", "image", trough,
                             border=(int(6 * d), 0), sticky="ew")
            s.element_create("NM.Horizontal.Scale.slider", "image", knob, ("active", knob_h),
                             ("pressed", knob_h), sticky="")
            s.layout("Horizontal.TScale", [("NM.Horizontal.Scale.trough", {"sticky": "nswe", "children": [
                ("NM.Horizontal.Scale.slider", {"side": "left", "sticky": ""})]})])
            bw = int(round(10 * d))
            thumb = mk("thumb", ui.pill(bw, int(28 * d), C["line"]))
            thumb_h = mk("thumbh", ui.pill(bw, int(28 * d), C["muted"]))
            s.element_create("NM.Vertical.Scrollbar.thumb", "image", thumb, ("active", thumb_h),
                             ("pressed", thumb_h), border=(0, int(8 * d)), sticky="ns")
            s.layout("Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
                ("NM.Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        except tk.TclError:
            pass                   # tema ya creado (otra ventana) o Tk sin PNG: quedan los de clam
        self._ctl_img = img

    def _set_icon(self):
        path = sysutil.resource("assets", "icon.png")
        if os.path.isfile(path):
            try:
                self._icon = tk.PhotoImage(file=path)
                self.root.iconphoto(True, self._icon)
            except tk.TclError:
                pass

    # ================================================================ estructura
    def _build(self):
        r = self.root
        self._u_orig, self._u_lbl = {}, {}          # fondo de una pieza (se rehace con la ventana)
        SCROLL_HOOKS.clear()
        r.columnconfigure(0, weight=0)
        r.columnconfigure(1, weight=1)
        r.rowconfigure(1, weight=1)

        # ---------- fondo de toda la ventana (degradado del tema)
        self.win_bg = None
        if self.art.has_window_bg:
            self.win_bg = tk.Label(r, bd=0, highlightthickness=0, bg=C["bg"])
            self.win_bg.place(x=0, y=0, relwidth=1, relheight=1)
            self.win_bg.lower()

        # ---------- cabecera (un lienzo: el banner o el degradado del tema se ve detrás)
        self._build_head(r)

        # ---------- izquierda: numpad
        left = ttk.Frame(r, style="Panel.TFrame", padding=16)
        left.grid(row=1, column=0, sticky="ns", padx=(18, 8), pady=(0, 8))
        self.left_panel = left

        # dos pestañas: el numpad (y la fila 1–0) o las teclas virtuales del celular
        self.left_view = "virt" if self._phone_only() else "numpad"
        lt = tk.Frame(left, bg=C["panel"])
        lt.pack(fill="x", pady=(0, 10))
        self.lt_tabs = {}
        for vid, text in (("numpad", "⌨  Numpad y fila 1–0"), ("virt", "▦  Teclas virtuales")):
            box = tk.Frame(lt, bg=C["panel"])
            box.pack(side="left", fill="x", expand=True, padx=(0, 4))
            b = FlatButton(box, text=text, command=lambda v=vid: self._set_view(v),
                           font=(FONT, BASE, "bold"), padx=8, pady=6)
            b.pack(fill="x")
            bar = tk.Frame(box, height=3, bg=C["line"])
            bar.pack(fill="x")
            self.lt_tabs[vid] = (box, b, bar)

        ttk.Label(left, text="Capa que estás editando", style="Muted.TLabel").pack(anchor="w")
        lrow = ttk.Frame(left, style="Panel.TFrame")
        lrow.pack(fill="x", pady=(2, 10))
        self.layer_cb = ttk.Combobox(lrow, state="readonly", width=24)
        self.layer_cb.pack(side="left")
        self.layer_cb.bind("<<ComboboxSelected>>", self._on_layer_pick)
        ttk.Button(lrow, text="＋", width=3, command=self._add_bank).pack(side="left", padx=(6, 0))
        ttk.Button(lrow, text="✎", width=3, command=self._rename_bank).pack(side="left", padx=(4, 0))
        ttk.Button(lrow, text="✕", width=3, command=self._delete_bank).pack(side="left", padx=(4, 0))

        # ---- vista numpad
        vn = ttk.Frame(left, style="Panel.TFrame")
        self.view_numpad = vn
        self.canvas = tk.Canvas(vn, bg=C["panel"], highlightthickness=0)
        w, h = self._numpad_box_size()
        self.canvas.configure(width=w, height=h)
        self._pack_numpad_box()
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.row_title = ttk.Label(vn, style="Muted.TLabel", wraplength=280)
        self.row_title.pack(anchor="w", pady=(4, 0))
        rw = 6 * self.RUNIT + 5 * self.RGAP
        rh = 2 * self.RUNIT + self.RGAP
        self.row_canvas = tk.Canvas(vn, width=rw, height=rh, bg=C["panel"], highlightthickness=0)
        self.row_canvas.pack(pady=(4, 8))
        self.row_canvas.bind("<Button-1>", self._on_row_click)
        self.extra_frame = ttk.Frame(vn, style="Panel.TFrame")
        self.extra_frame.pack(fill="x")
        self.btn_capture = ttk.Button(vn, text="Capturar tecla física", command=self._capture_key)
        self.btn_capture.pack(fill="x", pady=(6, 0))

        # ---- vista teclas virtuales (5 × 6)
        vv = ttk.Frame(left, style="Panel.TFrame")
        self.view_virt = vv
        top = ttk.Frame(vv, style="Panel.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text=f"Teclas virtuales · {VIRTUAL_COUNT}", style="Panel.TLabel",
                  font=(FONT, BASE, "bold")).pack(side="left")
        ttk.Label(top, text=f"{VIRTUAL_COLS} columnas × {VIRTUAL_ROWS} filas · G = Global",
                  style="Muted.TLabel").pack(side="right")
        vw, vh = self._virt_box_size()
        self.virt_canvas = tk.Canvas(vv, width=vw, height=vh, bg=C["panel"], highlightthickness=0)
        self._pack_virt_box()
        self.virt_canvas.bind("<Button-1>", self._on_virt_click)
        ttk.Label(vv, style="Muted.TLabel", wraplength=300, justify="left", text=(
            "Solo se tocan en la app del celular: nunca interfieren con los teclados del equipo.")
        ).pack(anchor="w")

        # ---------- derecha: pestañas
        nb = ttk.Notebook(r)
        nb.grid(row=1, column=1, sticky="nsew", padx=(8, 18), pady=(0, 8))
        self.nb = nb
        pt, pr, pb, pl = self.TAB_PADDING          # CSS (arriba, derecha, abajo, izquierda) -> ttk
        pad = (pl, pt, pr, pb)
        self.tab_key = ttk.Frame(nb, style="Panel.TFrame", padding=pad)
        self.tab_lib = ttk.Frame(nb, style="Panel.TFrame", padding=pad)
        self.tab_cap = ttk.Frame(nb, style="Panel.TFrame", padding=pad)
        self.tab_audio = ttk.Frame(nb, style="Panel.TFrame", padding=pad)
        self.tab_dev = ttk.Frame(nb, style="Panel.TFrame", padding=pad)
        self.tab_themes = ttk.Frame(nb, style="Panel.TFrame", padding=pad)
        nb.add(self.tab_key, text="Tecla")
        nb.add(self.tab_lib, text="Sonidos")
        nb.add(self.tab_cap, text="Numpad y opciones")
        nb.add(self.tab_audio, text="Audio")
        nb.add(self.tab_dev, text="Celular")
        nb.add(self.tab_themes, text="Temas")
        nb.bind("<<NotebookTabChanged>>", lambda e: self._on_tab())
        self._build_editor()
        self._build_library_tab()
        self._build_capture_tab()
        self._build_audio_tab()
        self.devtab = DevicesTab(self.tab_dev, self)
        self.themestab = ThemesTab(self.tab_themes, self)

        # ---------- pie (también un lienzo, por la banda y el espacio libre del tema)
        self._build_foot(r)
        # ---------- espacios libres del tema: final de las pestañas y abajo del panel de teclas
        self._place_free_slots(left)
        if self.art.one_piece:
            SCROLL_HOOKS.append(lambda: self._unify_soon(90))
            if not getattr(self, "_map_bound", False):
                r.bind_all("<Map>", lambda e: self._unify_soon(120), add="+")
                self._map_bound = True
            nb.bind("<<NotebookTabChanged>>", lambda e: self._unify_soon(30), add="+")
            self._unify_soon(200)
        self._refresh_layer_combo()

    # ---------------------------------------------------------------- cabecera y pie dibujados
    def _build_head(self, r):
        art = self.art
        cv = tk.Canvas(r, bg=C["bg"], highlightthickness=0, bd=0, height=70)
        cv.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.head_cv = cv
        self._head_bg = cv.create_image(0, 0, anchor="nw", tags=("bg",))
        relayout = self._schedule_head
        self.title_txt = CanvasText(cv, (FONT, BASE + 7, "bold"), C["text"], "head", art, text="Numpad Macros")
        self.logo_item = cv.create_image(0, 0, anchor="nw")
        self.headmid_item = cv.create_image(0, 0, anchor="center")
        small = (FONT, BASE - 1)
        self.chip_dev = CanvasText(cv, small, C["muted"], "head", art, relayout)
        self.chip_board = CanvasText(cv, small, C["muted"], "head", art, relayout)
        self.chip_row = CanvasPill(cv, (FONT, BASE - 1, "bold"), self._toggle_row, art, relayout, "head")
        self.meter_flag = CanvasText(cv, (FONT, BASE - 1, "bold"), C["muted"], "head", art, relayout)

        self.bank_prev = ttk.Button(cv, text="◀", width=3, command=lambda: self.engine.set_bank(self.engine.bank - 1))
        self.bank_next = ttk.Button(cv, text="▶", width=3, command=lambda: self.engine.set_bank(self.engine.bank + 1))
        self.bank_lbl = CanvasText(cv, (FONT, BASE + 1, "bold"), C["text"], "head", art, anchor="center")
        self.btn_active = FlatButton(cv, command=self._toggle_active, font=(FONT, BASE, "bold"), padx=16, pady=6)
        self._head_win = {w: cv.create_window(0, 0, window=w, anchor="nw")
                          for w in (self.bank_prev, self.bank_next, self.btn_active)}
        self._paint_active()
        self._paint_row()

        # medidores de volumen en tiempo real
        self.meters = {}
        self._meter_rows = []
        for key, name in (("spk", "Audífonos"), ("mic", "Micrófono virtual")):
            lbl = CanvasText(cv, (FONT, BASE - 2), C["muted"], "head", art, anchor="ne", text=name)
            m = Meter(cv, width=190, height=9)
            mw = cv.create_window(0, 0, window=m, anchor="nw")
            val = CanvasText(cv, (FONT, BASE - 2), C["muted"], "head", art, text="—")
            self.meters[key] = (m, val)
            self._meter_rows.append((lbl, m, mw, val))

        # aviso de versión nueva (oculto hasta que haya una)
        self.banner = _HeadSlot(cv, self, bg=C["accent_bg"], highlightbackground=C["accent_dim"], highlightthickness=1)
        self.banner.columnconfigure(1, weight=1)
        self.banner_icon = tk.Label(self.banner, text="⬇", bg=C["accent_bg"], fg=C["accent"], font=(FONT, BASE + 3, "bold"))
        self.banner_icon.grid(row=0, column=0, padx=(12, 8), pady=6)
        self.banner_lbl = tk.Label(self.banner, bg=C["accent_bg"], fg=C["text"], font=(FONT, BASE, "bold"), anchor="w")
        self.banner_lbl.grid(row=0, column=1, sticky="ew")
        self.banner_btn = FlatButton(self.banner, text="Actualizar", command=self._open_update,
                                     bg=C["accent"], fg=C["on_accent"], font=(FONT, BASE - 1, "bold"), padx=14, pady=4)
        self.banner_btn.grid(row=0, column=2, padx=6, pady=6)
        self.banner_later = FlatButton(self.banner, text="Más tarde", command=self._hide_banner,
                                       bg=C["accent_bg"], fg=C["text"], font=(FONT, BASE - 1), padx=10, pady=4)
        self.banner_later.grid(row=0, column=3, padx=(0, 10))
        self._banner_win = cv.create_window(0, 0, window=self.banner, anchor="nw", state="hidden")
        self._head_job = None
        self._head_size = None
        cv.bind("<Configure>", lambda e: self._schedule_head())
        self._schedule_head()

    def _schedule_head(self):
        if getattr(self, "_head_job", None) is None and hasattr(self, "head_cv"):
            try:
                self._head_job = self.root.after_idle(self._layout_head)
            except tk.TclError:
                pass

    def _layout_head(self):
        self._head_job = None
        cv, art = self.head_cv, self.art
        try:
            W = cv.winfo_width()
        except tk.TclError:
            return
        if W < 50:
            W = max(self.root.winfo_width(), 900)
        d = getattr(self, "dpi", 1.0)
        pad, top = 18, 14
        title_h = font_linespace(cv, cv.itemcget(self.title_txt.item, "font"))
        chip_h = font_linespace(cv, (FONT, BASE - 1))
        block_h = title_h + 4 + chip_h
        x = pad
        if art.has("logo"):
            size = int(block_h)
            got = art.show("logo", lambda ph: cv.itemconfigure(self.logo_item, image=ph), size, size, key="logo")
            cv.coords(self.logo_item, pad, top)
            if got:
                x = pad + got[0] + 10
        self.title_txt.move_to(x, top)
        cy = top + title_h + 4
        cx = x
        for t in (self.chip_dev, self.chip_board):
            t.move_to(cx, cy)
            w = t.width()
            cx += (w + 14) if w else 0
        self.chip_row.move_to(cx + 8, cy)
        cx += (self.chip_row.width() + 14) if self.chip_row.width() else 0
        self.meter_flag.move_to(cx, cy)
        chips_right = cx + self.meter_flag.width()
        title_right = x + self.title_txt.width()

        # derecha: ACTIVO · banco · medidores
        ah = self.btn_active.winfo_reqheight()
        aw = self.btn_active.winfo_reqwidth()
        rx = W - pad
        cv.coords(self._head_win[self.btn_active], rx - aw, top)
        rx -= aw + 14
        bw, bh = self.bank_next.winfo_reqwidth(), self.bank_next.winfo_reqheight()
        by = top + (ah - bh) / 2
        cv.coords(self._head_win[self.bank_next], rx - bw, by)
        rx -= bw + 6
        lw = int(150 * d)
        self.bank_lbl.move_to(rx - lw / 2, top + ah / 2)
        rx -= lw + 6
        cv.coords(self._head_win[self.bank_prev], rx - bw, by)
        rx -= bw + 22
        mfont = (FONT, BASE - 2)
        val_w = font_measure(cv, mfont, "−60.0 dB") + 4
        label_w = max(font_measure(cv, mfont, r[0].cget("text")) for r in self._meter_rows)
        row_h = max(13, font_linespace(cv, mfont))
        meters_left = rx - val_w - 6 - 190 - 6 - label_w
        my = top + max(0, (ah - 2 * row_h) / 2)
        for i, (lbl, m, mw, val) in enumerate(self._meter_rows):
            y = my + i * (row_h + 1)
            lbl.move_to(meters_left + label_w, y)
            cv.coords(mw, meters_left + label_w + 6, y + (row_h - 9) / 2)
            val.move_to(meters_left + label_w + 6 + 190 + 6, y)
        base_h = top + max(block_h, ah) + 8

        # espacio central del encabezado (sticker o GIF)
        gap_l = max(title_right, chips_right) + 20
        gap_r = meters_left - 20
        if art.has("headmid") and gap_r - gap_l > 40:
            got = art.show("headmid", lambda ph: cv.itemconfigure(self.headmid_item, image=ph),
                           int(min(360 * d, gap_r - gap_l)), int(min(48 * d, base_h - 6)), key="headmid")
            cv.coords(self.headmid_item, (gap_l + gap_r) / 2, (base_h + 2) / 2)
        else:
            art.stop("headmid")
            cv.itemconfigure(self.headmid_item, image="")

        H = base_h
        if self.banner.shown:
            cv.itemconfigure(self._banner_win, state="normal", width=W - 2 * pad)
            cv.coords(self._banner_win, pad, base_h)
            H = base_h + self.banner.winfo_reqheight() + 10
        else:
            cv.itemconfigure(self._banner_win, state="hidden")
        H = int(H)
        if int(cv.cget("height")) != H:
            cv.configure(height=H)
        # fondo: degradado + plancha de la sección + banner del tema
        if (W, H) != self._head_size or getattr(self, "_head_dirty", True):
            self._head_size = (W, H)
            self._head_dirty = False
            img = art.compose(W, H, box=(0, 0), slot="banner", section="head") if art.active else None
            if img is not None:
                if art.realce("head"):
                    from PIL import ImageDraw
                    ImageDraw.Draw(img).rectangle((1, 1, W - 2, H - 2), outline=C["accent"], width=2)
                cv.itemconfigure(self._head_bg, image=art.photo("head", img))
                for lbl, m, mw, val in self._meter_rows:
                    x0, y0 = cv.coords(mw)
                    m.configure(bg=art.average(img, (int(x0), int(y0), int(x0) + 190, int(y0) + 9)))
            else:
                cv.itemconfigure(self._head_bg, image="")
        cv.tag_lower("bg")

    def _build_foot(self, r):
        art = self.art
        cv = tk.Canvas(r, bg=C["bg"], highlightthickness=0, bd=0, height=34)
        cv.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.foot_cv = cv
        self._foot_bg = cv.create_image(0, 0, anchor="nw", tags=("bg",))
        self.status = CanvasText(cv, (FONT, BASE - 1), C["muted"], "foot", art, self._schedule_foot, anchor="w")
        self.status.winfo_height = lambda: cv.winfo_height()
        self.foot_item = cv.create_image(0, 0, anchor="e")
        btns = [
            FlatButton(cv, text=f"v{__version__} · Novedades", command=self._show_news,
                       bg=C["bg"], fg=C["muted"], font=(FONT, BASE - 1), padx=10, pady=4,
                       highlightbackground=C["line"], highlightthickness=1),
            FlatButton(cv, text=f"Creado por {about.CREATOR} · Soporte", command=self._show_about,
                       bg=C["panel2"], fg=C["text"], font=(FONT, BASE - 1), padx=12, pady=4),
            FlatButton(cv, text="♥ Donar", command=lambda: self._open(about.DONATE),
                       bg=C["accent"], fg=C["on_accent"], font=(FONT, BASE - 1, "bold"), padx=12, pady=4),
        ]
        self._foot_btns = [(b, cv.create_window(0, 0, window=b, anchor="e")) for b in btns]
        self._foot_job = None
        self._foot_size = None
        cv.bind("<Configure>", lambda e: self._schedule_foot())
        self._schedule_foot()

    def _schedule_foot(self):
        if getattr(self, "_foot_job", None) is None and hasattr(self, "foot_cv"):
            try:
                self._foot_job = self.root.after_idle(self._layout_foot)
            except tk.TclError:
                pass

    def _layout_foot(self):
        self._foot_job = None
        cv, art = self.foot_cv, self.art
        try:
            W = cv.winfo_width()
        except tk.TclError:
            return
        if W < 50:
            W = max(self.root.winfo_width(), 900)
        d = getattr(self, "dpi", 1.0)
        pad = 18
        bh = max(b.winfo_reqheight() for b, _ in self._foot_btns)
        line_h = max(1, font_linespace(cv, (FONT, BASE - 1)))
        x = W - pad
        for b, item in reversed(self._foot_btns):
            x -= b.winfo_reqwidth()
            x -= 6
        btn_left = x + 6
        free_r = btn_left - 10
        status_w = max(100, free_r - pad)
        if art.has("foot"):
            got = art.show("foot", lambda ph: cv.itemconfigure(self.foot_item, image=ph),
                           int(min(420 * d, (free_r - pad) / 2)), int(28 * d), key="foot")
            if got:
                status_w = max(100, free_r - got[0] - 12 - pad)
        cv.itemconfigure(self.status.item, width=status_w)
        lines = max(1, self.status.height() // line_h)
        H = int(max(bh, lines * line_h) + 10 + 4)
        cy = (H - 10) / 2 + 2
        xb = W - pad
        for b, item in reversed(self._foot_btns):
            cv.coords(item, xb, cy)
            xb -= b.winfo_reqwidth() + 6
        self.status.move_to(pad, cy)
        cv.coords(self.foot_item, free_r, cy)
        if int(cv.cget("height")) != H:
            cv.configure(height=H)
        if (W, H) != self._foot_size or getattr(self, "_foot_dirty", True):
            self._foot_size = (W, H)
            self._foot_dirty = False
            img = None
            if art.active:
                y = max(0, self.root.winfo_height() - H)
                img = art.compose(W, H, box=(0, y), slot="footband", section="foot")
                if img is not None and art.realce("foot"):
                    from PIL import ImageDraw
                    ImageDraw.Draw(img).rectangle((1, 1, W - 2, H - 2), outline=C["accent"], width=2)
            cv.itemconfigure(self._foot_bg, image=art.photo("foot", img) if img is not None else "")
        cv.tag_lower("bg")

    def _place_free_slots(self, left):
        """Espacios libres del tema: abajo del panel de teclas y al final de las pestañas."""
        art = self.art
        d = getattr(self, "dpi", 1.0)
        self.leftbot_lbl = None
        if art.has("leftbot"):
            # Una franja de todo el ancho del panel, como en la vista previa del Estudio: la imagen se ve
            # completa (sin recortes) y se ajusta cuando el panel cambia de ancho.
            lb = tk.Label(left, bg=C["panel"], bd=0, highlightthickness=0)
            lb.pack(side="bottom", fill="x", pady=(8, 0))
            last = {"w": 0}

            def fit(_e=None):
                try:
                    # el ancho lo deciden los demás elementos del panel (si no, la imagen no lo dejaría
                    # achicarse al reducir la ventana)
                    w = max([c.winfo_reqwidth() for c in left.winfo_children() if c is not lb] + [0])
                except tk.TclError:
                    return
                if w < 40 or abs(w - last["w"]) < 2:
                    return
                last["w"] = w
                art.show("leftbot", lambda ph: lb.configure(image=ph), w, int(160 * d), key="leftbot")
            left.bind("<Configure>", fit, add="+")

            def first(ph):                   # su alto cambia el espacio de las teclas
                lb.configure(image=ph)
                self._refit_soon()
            art.show("leftbot", first, int(300 * d), int(160 * d), key="leftbot")
            self.leftbot_lbl = lb
        self.tabsend_lbl = None
        if art.has("tabsend"):
            self.tabsend_lbl = tk.Label(self.root, bg=C["bg"], bd=0, highlightthickness=0)
            self.nb.bind("<Configure>", lambda e: self._place_tabsend(), add="+")
        if self.art.realce("left"):
            left.configure(style="Realce.Panel.TFrame")

    def _paint_tab_corner(self, cv):
        """«Pestaña · parte de abajo»: la imagen del tema al fondo de la pestaña Tecla."""
        art = self.art
        if not art.has("corner"):
            return
        d = getattr(self, "dpi", 1.0)

        def place(_e=None):
            try:
                w, h = cv.winfo_width(), cv.winfo_height()
            except tk.TclError:
                return
            if w < 50:
                return
            s = art.slots["corner"]
            iw, ih = s.size
            ch = int(min(200 * d, w * ih / max(1, iw)))
            got = art.show("corner", lambda ph: cv.itemconfigure("corner", image=ph), w, ch, mode="cover", key="corner")
            if not cv.find_withtag("corner"):
                cv.create_image(0, h, anchor="sw", tags=("corner",))
                got = art.show("corner", lambda ph: cv.itemconfigure("corner", image=ph), w, ch, mode="cover",
                               key="corner")
            cv.coords("corner", 0, h)
            cv.tag_lower("corner")
            del got
        cv.bind("<Configure>", lambda e: (place(), None)[1], add="+")
        place()

    def _paint_window_bg(self):
        """Degradado de toda la ventana (se ve en los bordes y entre los paneles)."""
        if self.win_bg is None:
            return
        if self.art.one_piece:
            self._unify_soon(0)
            return
        W, H = self.root.winfo_width(), self.root.winfo_height()
        img = self.art.window_gradient(W, H)
        if img is not None:
            self.win_bg.configure(image=self.art.photo("window", img))
            self.win_bg.lower()
        self._head_dirty = self._foot_dirty = True
        self._schedule_head()
        self._schedule_foot()
        self._place_tabsend()

    def _place_tabsend(self):
        """«Pestañas · espacio al final»: a la derecha de la última pestaña, con el fondo de detrás."""
        tl = getattr(self, "tabsend_lbl", None)
        if tl is None:
            return
        art = self.art
        d = getattr(self, "dpi", 1.0)
        if getattr(self, "_tabsend_busy", False):
            return
        self._tabsend_busy = True
        try:
            nx = self.nb.winfo_rootx() - self.root.winfo_rootx()
            ny = self.nb.winfo_rooty() - self.root.winfo_rooty()
            nw = self.nb.winfo_width()
            tab_h = 4
            while tab_h < 80 and self.nb.identify(12, tab_h):
                tab_h += 2
            right = 0
            for x in range(0, nw, 3):
                if self.nb.identify(x, max(2, tab_h // 2)):
                    right = x
            tabs_right = nx + right
        except tk.TclError:
            return
        finally:
            self._tabsend_busy = False
        if tab_h < 12:
            tab_h = int(34 * d)
        free = nx + nw - tabs_right - 12
        w, h = art.fit_size("tabsend", min(240 * d, free), min(28 * d, tab_h - 4))
        if free < 30 or w < 8:
            tl.place_forget()
            art.stop("tabsend")
            return
        x, y = nx + nw - w - 4, ny + max(0, (tab_h - h) // 2)
        from PIL import Image                      # la barra de pestañas es de color sólido
        back = Image.new("RGB", (w, h), tuple(int(C["bg"][i:i + 2], 16) for i in (1, 3, 5)))
        art.show("tabsend", lambda ph: tl.configure(image=ph), w, h, key="tabsend", backdrop=back)
        tl.place(x=x, y=y)
        tl.lift()

    # ---------------------------------------------------------------- fondo de una pieza
    def _unify_soon(self, delay=60):
        art = getattr(self, "art", None)
        if art is None or not art.one_piece:
            return
        job = getattr(self, "_unify_job", None)
        if job:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        try:
            self._unify_job = self.root.after(delay, self._unify)
        except tk.TclError:
            pass

    def _rect(self, w):
        rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
        return w.winfo_rootx() - rx, w.winfo_rooty() - ry, w.winfo_width(), w.winfo_height()

    def _unify(self):
        """«Fondo de una pieza»: el fondo del tema pasa por detrás de todos los paneles.
        Los contenedores muestran su recorte del fondo y los textos y casillas toman el color
        del fondo justo donde están; campos, botones, listas y tarjetas quedan como siempre."""
        self._unify_job = None
        art = self.art
        if not art.one_piece:
            return
        r = self.root
        try:
            W, H = r.winfo_width(), r.winfo_height()
        except tk.TclError:
            return
        if W < 50 or H < 50:
            return
        plates = []
        for w in (self.left_panel, self.nb):
            try:
                x, y, ww, hh = self._rect(w)
            except tk.TclError:
                continue
            plates.append((x, y, x + ww, y + hh))
        m = art.window_map(W, H, plates)
        if m is None:
            return
        if self.win_bg is not None:
            ph = art.map_photo("u:win", 0, 0, W, H)
            self.win_bg.configure(image=ph)
            self.win_bg.lower()
        self._head_dirty = self._foot_dirty = True
        self._schedule_head()
        self._schedule_foot()
        s = ttk.Style(r)
        surface = {C["bg"], C["panel"]}
        orig = self.__dict__.setdefault("_u_orig", {})
        labels = self.__dict__.setdefault("_u_lbl", {})
        skip = {self.head_cv, self.foot_cv, self.win_bg, getattr(self, "tabsend_lbl", None)}
        stack = list(r.winfo_children())
        while stack:
            w = stack.pop()
            if w in skip or isinstance(w, tk.Toplevel) or getattr(w, "_u_bg", False):
                continue
            try:
                if not w.winfo_ismapped():
                    continue
                x, y, ww, hh = self._rect(w)
            except tk.TclError:
                continue
            stack.extend(w.winfo_children())
            key = str(w)
            cls = w.winfo_class()
            if isinstance(w, ttk.Widget):
                if cls not in ("TFrame", "TLabel", "TCheckbutton", "TRadiobutton", "TLabelframe"):
                    continue
                base = orig.get(key)
                if base is None:
                    base = w.cget("style") or cls
                    if str(s.lookup(base, "background")) not in surface:
                        orig[key] = ""
                        continue
                    orig[key] = base
                if not base:
                    continue
                if cls == "TFrame" and ww * hh >= 2500:
                    lbl = labels.get(key)
                    if lbl is None or not lbl.winfo_exists():
                        lbl = tk.Label(w, bd=0, highlightthickness=0)
                        lbl._u_bg = True
                        lbl.place(x=0, y=0, relwidth=1, relheight=1, bordermode="outside")
                        labels[key] = lbl
                    lbl.configure(image=art.map_photo("u:" + key, x, y, ww, hh))
                    lbl.lower()
                    col = art.sample(x, y, ww, hh)
                else:
                    col = art.sample(x, y, ww, hh)
                name = f"U{abs(hash(key)) % 10 ** 9}.{base}"
                s.configure(name, background=col)
                if cls in ("TCheckbutton", "TRadiobutton"):
                    s.map(name, background=[("active", col)])
                if w.cget("style") != name:
                    w.configure(style=name)
            else:
                if cls not in ("Frame", "Label", "Canvas"):
                    continue
                base = orig.get(key)
                if base is None:
                    try:
                        bg = str(w.cget("bg"))
                    except tk.TclError:
                        orig[key] = ""
                        continue
                    orig[key] = bg if bg in surface else ""
                    base = orig[key]
                if not base:
                    continue
                if cls == "Canvas" and w in (self.canvas, self.virt_canvas):
                    w.configure(bg=art.sample(x, y, ww, hh))
                    continue
                if cls == "Frame" and ww * hh >= 2500:
                    lbl = labels.get(key)
                    if lbl is None or not lbl.winfo_exists():
                        lbl = tk.Label(w, bd=0, highlightthickness=0)
                        lbl._u_bg = True
                        lbl.place(x=0, y=0, relwidth=1, relheight=1, bordermode="outside")
                        labels[key] = lbl
                    lbl.configure(image=art.map_photo("u:" + key, x, y, ww, hh))
                    lbl.lower()
                col = art.sample(x, y, ww, hh)
                try:
                    w.configure(bg=col)
                except tk.TclError:
                    pass
        try:
            s.configure("TNotebook", background=art.sample(*self._rect(self.nb)[:2], self._rect(self.nb)[2], 30))
        except tk.TclError:
            pass
        self.__dict__.pop("_keysbg_ok", None)
        self._redraw()

    # ---------------------------------------------------------------- editor
    def _build_editor(self):
        t = scroll_frame(self.tab_key)          # en pantallas bajas se desplaza en vez de cortarse
        self._key_inner = t
        self._pick_job = None
        # el selector de sonidos toma el alto que sobra: se recalcula si cambia la ventana o el contenido
        t.bind("<Configure>", lambda e: self._fit_pick_soon(), add="+")
        t.master.bind("<Configure>", lambda e: self._fit_pick_soon(), add="+")
        self._paint_tab_corner(t.master)
        t.columnconfigure(0, weight=1)
        self.ed_title = ttk.Label(t, style="H.TLabel")
        self.ed_title.grid(row=0, column=0, sticky="w")
        self.ed_note = ttk.Label(t, style="Muted.TLabel", wraplength=500, justify="left")
        self.ed_note.grid(row=1, column=0, sticky="w", pady=(2, 10))

        row = ttk.Frame(t, style="Panel.TFrame")
        row.grid(row=2, column=0, sticky="w")
        ttk.Label(row, text="Acción", style="Panel.TLabel", width=LBL_W).pack(side="left")
        self.type_cb = ttk.Combobox(row, state="readonly", width=34,
                                    values=[lbl for _, lbl in ACTION_TYPES])
        self.type_cb.pack(side="left")
        self.type_cb.bind("<<ComboboxSelected>>", self._on_type_pick)

        self.sub = ttk.Frame(t, style="Panel.TFrame")
        self.sub.grid(row=3, column=0, sticky="nsew", pady=(12, 0))

        # color del botón (se ve igual en el PC y en el celular)
        cc = ttk.Frame(t, style="Card.TFrame", padding=(16, 12))
        cc.grid(row=4, column=0, sticky="w", pady=(16, 0))
        t.rowconfigure(5, weight=1)                  # el espacio que sobra queda abajo
        self.color_card = cc
        head = ttk.Frame(cc, style="Card.TFrame")
        head.pack(fill="x")
        ttk.Label(head, text="Color del botón", style="Card.TLabel", font=(FONT, BASE, "bold")).pack(side="left")
        self.color_name = ttk.Label(head, style="CardMuted.TLabel")
        self.color_name.pack(side="left", padx=(10, 0))
        ttk.Label(head, text="·  se ve igual en el PC y en el celular", style="CardMuted.TLabel").pack(
            side="left", padx=(8, 0))
        sw = ttk.Frame(cc, style="Card.TFrame")
        sw.pack(anchor="w", pady=(8, 0))
        self.swatches = []
        for i in range(-1, len(BUTTON_COLORS)):
            cv = tk.Canvas(sw, width=30, height=30, bg=C["panel2"], highlightthickness=0, cursor="hand2")
            cv.pack(side="left", padx=(0, 7))
            cv.bind("<Button-1>", lambda e, i=i: self._set_color(i))
            self.swatches.append((i, cv))

    def _clear_sub(self):
        for wdg in self.sub.winfo_children():
            wdg.destroy()
        self.picker = None
        self.btn_test = None

    def _build_file_sub(self, act):
        f = self.sub
        f.columnconfigure(0, weight=1)
        top = ttk.Frame(f, style="Panel.TFrame")
        top.grid(row=0, column=0, sticky="ew")
        self.file_lbl = ttk.Label(top, style="Panel.TLabel", font=(FONT, BASE + 1, "bold"))
        self.file_lbl.pack(side="left")
        self.file_warn = ttk.Label(top, style="Warn.TLabel")
        self.file_warn.pack(side="left", padx=10)

        # elegir sonido: lista o cuadrícula con portadas (sound_picker.py)
        self.picker = SoundPicker(f, self, on_pick=lambda item: self._assign_file(item, rebuild=False),
                                  on_add=self._add_files_for_key, label_width=LBL_W)
        self.picker.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self._fit_pick_soon()

        opts = ttk.Frame(f, style="Panel.TFrame")
        opts.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(opts, text="Al pulsar", style="Panel.TLabel", width=LBL_W).grid(row=0, column=0, sticky="w")
        self.mode_cb = ttk.Combobox(opts, state="readonly", width=44, values=[m for _, m in PLAY_MODES])
        self.mode_cb.set(MODE_LABEL.get(act.get("mode", "overlap")))
        self.mode_cb.grid(row=0, column=1, sticky="w")
        self.mode_cb.bind("<<ComboboxSelected>>", lambda e: self._on_file_opt())
        ttk.Label(opts, text="Volumen", style="Panel.TLabel").grid(row=1, column=0, sticky="nw", pady=(10, 0))
        vrow = ttk.Frame(opts, style="Panel.TFrame")
        vrow.grid(row=1, column=1, sticky="w", pady=(8, 0))
        self.vol_var = tk.DoubleVar(value=round(float(act.get("volume", 1.0)) * 100))
        ttk.Scale(vrow, from_=0, to=150, variable=self.vol_var, length=300,
                  command=lambda _v: self._on_volume()).grid(row=0, column=0, sticky="w")
        self.vol_lbl = tk.Label(vrow, bg=C["panel"], fg=C["accent"], font=(FONT, BASE, "bold"),
                                width=15, padx=6, pady=2, anchor="w")
        self.vol_lbl.grid(row=0, column=1, sticky="w", padx=(10, 0))
        marks = tk.Canvas(vrow, width=300, height=14, bg=C["panel"], highlightthickness=0)
        marks.grid(row=1, column=0, sticky="w")
        for v, txt in ((0, "0"), (50, "50"), (100, "100 · original"), (150, "150")):
            x = 8 + (300 - 16) * v / 150
            marks.create_text(x, 7, text=txt, fill=C["muted"], font=(FONT, BASE - 3),
                              anchor="w" if v == 0 else ("e" if v == 150 else "center"))
        self.norm_lbl = ttk.Label(vrow, style="Muted.TLabel", wraplength=430, justify="left")
        self.norm_lbl.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))

        lines = ttk.Frame(f, style="Panel.TFrame")
        lines.grid(row=4, column=0, sticky="w", pady=(12, 0))
        self.spk_var = tk.BooleanVar(value=act.get("speakers", True))
        self.mic_var = tk.BooleanVar(value=act.get("mic", True))
        ttk.Checkbutton(lines, text="Por mis audífonos", variable=self.spk_var,
                        command=self._on_file_opt).pack(side="left")
        ttk.Checkbutton(lines, text="Por el micrófono", variable=self.mic_var,
                        command=self._on_file_opt).pack(side="left", padx=16)
        self.btn_test = ttk.Button(lines, text="▶ Probar", style="Accent.TButton", width=11,
                                   command=self._test_action)
        self.btn_test.pack(side="left", padx=(24, 0))
        self._refresh_file_header(act)
        self._fill_pick()

    def _build_keys_sub(self, act):
        f = self.sub
        try:
            mods, key = parse_combo(act.get("combo", "f13"))
        except ValueError:
            mods, key = [], "f13"
        ttk.Label(f, text="Combinación que se enviará", style="Panel.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w")
        mrow = ttk.Frame(f, style="Panel.TFrame")
        mrow.grid(row=1, column=0, sticky="w", pady=8)
        self.mod_vars = {}
        for m in MODIFIERS:
            v = tk.BooleanVar(value=m in mods)
            self.mod_vars[m] = v
            ttk.Checkbutton(mrow, text=MOD_LABEL[m], variable=v,
                            command=self._on_combo_change).pack(side="left", padx=(0, 12))
        ttk.Label(mrow, text="+", style="Panel.TLabel").pack(side="left", padx=(0, 10))
        unsupported = getattr(self.sender, "unsupported", frozenset())
        choices = [k for k in KEY_CHOICES if k not in unsupported]
        self.key_cb = ttk.Combobox(mrow, state="readonly", width=12, values=[k.upper() for k in choices])
        self.key_cb.set(key.upper())
        self.key_cb.pack(side="left")
        self.key_cb.bind("<<ComboboxSelected>>", lambda e: self._on_combo_change())
        prow = ttk.Frame(f, style="Panel.TFrame")
        prow.grid(row=2, column=0, sticky="w", pady=(4, 12))
        self.combo_preview = tk.Label(prow, bg=C["panel2"], fg=C["accent"], font=(FONT, BASE + 8, "bold"),
                                      padx=16, pady=8)
        self.combo_preview.pack(side="left")
        self.combo_preview.configure(text=self._combo_text(act.get("combo", "f13")))
        self.btn_rec_keys = ttk.Button(prow, text="⏺ Grabar pulsando las teclas",
                                       command=lambda: self._start_rec("keys"))
        self.btn_rec_keys.pack(side="left", padx=(12, 0))
        self.keys_warn = ttk.Label(f, style="Warn.TLabel", wraplength=500, justify="left")
        self.keys_warn.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self._paint_keys_warn(act.get("combo", "f13"))
        hint = {
            "win": "F13–F24 son teclas que Windows reconoce pero ningún teclado trae, así que no "
                   "chocan con nada.",
            "linux": "F13–F24 no chocan con nada. Ojo: en Wayland, OBS solo tiene atajos globales "
                     "con algunos escritorios; en X11 funcionan siempre.",
            "mac": "En macOS existen F13–F20 (F21–F24 no). No chocan con nada.",
        }[PLATFORM]
        ttk.Label(f, style="Muted.TLabel", wraplength=500, justify="left", text=(
            hint + " Para asignarlas en OBS u otro programa: abre su ventana de atajos, haz clic en "
            "el campo y pulsa esta tecla (en el numpad o en la app del celular). La combinación se "
            "mantiene apretada mientras mantengas la tecla (sirve para push-to-talk).")).grid(row=3, column=0, sticky="w")
        ttk.Button(f, text="Probar en 3 s", command=self._test_keys_delayed).grid(
            row=4, column=0, sticky="w", pady=(14, 0))

    @staticmethod
    def _combo_text(combo):
        try:
            mods, key = parse_combo(combo)
        except ValueError:
            return combo
        return "+".join([MOD_LABEL[m] for m in mods] + [key.upper()])

    def _build_bank_go_sub(self, act):
        f = self.sub
        ttk.Label(f, text="Ir al banco número", style="Panel.TLabel").grid(row=0, column=0, sticky="w")
        self.bank_go_var = tk.IntVar(value=int(act.get("bank", 1)))
        sp = ttk.Spinbox(f, from_=1, to=max(1, len(self.cfg["banks"])), width=6,
                         textvariable=self.bank_go_var, command=self._on_bank_go)
        sp.grid(row=0, column=1, sticky="w", padx=10)
        sp.bind("<KeyRelease>", lambda e: self._on_bank_go())

    def _build_info_sub(self, text):
        ttk.Label(self.sub, text=text, style="Muted.TLabel", wraplength=500,
                  justify="left").grid(row=0, column=0, sticky="w")

    # ---------------------------------------------------------------- pestaña sonidos
    def _build_library_tab(self):
        t = self.tab_lib
        t.columnconfigure(0, weight=1)
        t.rowconfigure(3, weight=1)
        head = ttk.Frame(t, style="Panel.TFrame")
        head.grid(row=0, column=0, sticky="ew")
        ttk.Label(head, text="Tu biblioteca de sonidos", style="H.TLabel").pack(side="left")
        self.lib_count = ttk.Label(head, style="Muted.TLabel")
        self.lib_count.pack(side="left", padx=12)

        btns = ttk.Frame(t, style="Panel.TFrame")
        btns.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(btns, text="＋ Archivos…", command=self._lib_add_files).pack(side="left")
        ttk.Button(btns, text="＋ Carpeta…", command=self._lib_add_folder).pack(side="left", padx=6)
        ttk.Button(btns, text="Importar lista de Soundpad…", command=self._lib_import_spl).pack(side="left")
        ttk.Button(btns, text="Quitar", command=self._lib_remove).pack(side="right")

        srow = ttk.Frame(t, style="Panel.TFrame")
        srow.grid(row=2, column=0, sticky="ew", pady=(10, 6))
        ttk.Label(srow, text="Buscar", style="Panel.TLabel").pack(side="left", padx=(0, 8))
        self.lib_q = tk.StringVar()
        ttk.Entry(srow, textvariable=self.lib_q, width=34).pack(side="left")
        self.lib_q.trace_add("write", lambda *_: self._fill_library())

        box, self.lib_lb = make_listbox(t, 14)
        self.lib_lb.configure(selectmode="extended")
        box.grid(row=3, column=0, sticky="nsew")
        self.lib_lb.bind("<Double-Button-1>", lambda e: self._lib_preview())
        self.lib_lb.bind("<<ListboxSelect>>", lambda e: self._lib_sel_changed())

        bottom = ttk.Frame(t, style="Panel.TFrame")
        bottom.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(bottom, text="▶ Escuchar", command=self._lib_preview).pack(side="left")
        ttk.Button(bottom, text="■ Detener", command=lambda: self.board.stop_all()).pack(side="left", padx=6)
        self.btn_assign = ttk.Button(bottom, style="Accent.TButton", command=self._lib_assign)
        self.btn_assign.pack(side="right")
        ttk.Label(t, style="Muted.TLabel", wraplength=520, justify="left", text=(
            "Doble clic para escuchar (solo por tus audífonos). Los archivos no se copian: se usan "
            "desde donde están. «Importar lista de Soundpad» lee un archivo .spl exportado desde "
            "Soundpad (Archivo → Guardar lista) para traer tus sonidos.")).grid(
            row=5, column=0, sticky="w", pady=(12, 0))
        self._lib_view = []
        self._fill_library()

    # ---------------------------------------------------------------- pestaña creador
    def _build_about_tab(self, t):
        t.columnconfigure(0, weight=1)
        t.rowconfigure(5, weight=1)
        head = ttk.Frame(t, style="Panel.TFrame")
        head.grid(row=0, column=0, sticky="w")
        if getattr(self, "_icon", None) is not None:
            self._icon_small = self._icon.subsample(max(1, self._icon.width() // 64))
            logo = tk.Label(head, image=self._icon_small, bg=C["panel"], highlightthickness=3,
                            highlightbackground=C["panel"], highlightcolor=C["panel"])
            logo.pack(side="left", padx=(0, 16))
            logo.bind("<Button-1>", lambda e, w=logo: self._mark(w))
        txt = ttk.Frame(head, style="Panel.TFrame")
        txt.pack(side="left")
        ttk.Label(txt, text=f"Numpad Macros {__version__}", style="H.TLabel",
                  font=(FONT, BASE + 7, "bold")).pack(anchor="w")
        ttk.Label(txt, text=f"Creado por {about.CREATOR}", style="Panel.TLabel",
                  font=(FONT, BASE + 2)).pack(anchor="w", pady=(2, 0))

        ttk.Label(t, style="Muted.TLabel", wraplength=520, justify="left", text=(
            "¿Dudas, ideas o algo no funciona? Escríbeme o entra al servidor de Discord: ahí "
            "respondo preguntas, recibo sugerencias y aviso de las nuevas versiones.")).grid(
            row=1, column=0, sticky="w", pady=(14, 10))

        for i, (name, sub, url) in enumerate((about.INSTAGRAM, about.DISCORD, about.GITHUB)):
            self._link_card(t, name, sub, url).grid(row=2 + i, column=0, sticky="ew", pady=(0, 6))
        ttk.Label(t, style="Muted.TLabel", text=f"Software libre bajo licencia {about.LICENSE}.").grid(
            row=5, column=0, sticky="nw", pady=(4, 0))

        up = ttk.Frame(t, style="Card.TFrame", padding=(16, 12))
        up.grid(row=6, column=0, sticky="ew", pady=(6, 0))
        up.columnconfigure(1, weight=1)
        ttk.Label(up, text="Actualizaciones", style="Card.TLabel", font=(FONT, BASE + 1, "bold")).grid(
            row=0, column=0, sticky="w")
        ttk.Label(up, text=f"Versión instalada: {__version__}", style="Card.TLabel").grid(
            row=0, column=1, sticky="w", padx=14)
        self.upd_lbl = ttk.Label(up, style="CardMuted.TLabel", text="")
        self.upd_lbl.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 6))
        upd = self.cfg["updates"]
        self.upd_auto = tk.BooleanVar(value=upd.get("auto", True))
        self.upd_beta = tk.BooleanVar(value=upd.get("beta", False))
        ttk.Checkbutton(up, text="Buscar actualizaciones al iniciar (una vez al día)", variable=self.upd_auto,
                        style="Card.TCheckbutton", command=self._on_upd_opts).grid(row=2, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(up, text="Recibir también versiones de prueba (beta)", variable=self.upd_beta,
                        style="Card.TCheckbutton", command=self._on_upd_opts).grid(row=3, column=0, columnspan=3, sticky="w")
        self.upd_estudio = tk.BooleanVar(value=bool(upd.get("estudio")))
        ttk.Checkbutton(up, text="Estudio de Temas (editor de temas): instalarlo y buscar también sus versiones",
                        variable=self.upd_estudio, style="Card.TCheckbutton",
                        command=self._on_estudio_opt).grid(row=4, column=0, columnspan=3, sticky="w")
        ub = ttk.Frame(up, style="Card.TFrame")
        ub.grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.btn_check = ttk.Button(ub, text="Buscar ahora", command=lambda: self._check_updates(manual=True))
        self.btn_check.pack(side="left")
        ttk.Button(ub, text="Novedades de esta versión", command=self._show_news).pack(side="left", padx=8)

        don = tk.Frame(t, bg=C["panel2"], highlightbackground=C["accent"], highlightthickness=1)
        don.grid(row=8, column=0, sticky="ew", pady=(10, 0))
        don.columnconfigure(0, weight=1)
        tk.Label(don, text="¿Te sirve la app?", bg=C["panel2"], fg=C["text"],
                 font=(FONT, BASE + 1, "bold"), anchor="w").grid(row=0, column=0, sticky="w", padx=16, pady=(12, 0))
        tk.Label(don, text="Es gratis. Si quieres apoyar su desarrollo, puedes donar.",
                 bg=C["panel2"], fg=C["muted"], font=(FONT, BASE - 1), anchor="w",
                 wraplength=340, justify="left").grid(
            row=1, column=0, sticky="w", padx=16, pady=(2, 12))
        FlatButton(don, text="♥  Donar", command=lambda: self._open(about.DONATE), bg=C["accent"],
                   fg=C["on_accent"], font=(FONT, BASE + 1, "bold"), padx=22, pady=8).grid(
            row=0, column=1, rowspan=2, padx=16, pady=12)

    def _link_card(self, parent, name, sub, url):
        card = tk.Frame(parent, bg=C["panel2"], cursor="hand2")
        card.columnconfigure(1, weight=1)
        badge = {"Instagram": ("IG", "#c13584"), "Discord": ("DC", "#5865f2"),
                 "GitHub": ("GH", "#30363d")}.get(name, ("↗", C["line"]))
        tk.Label(card, text=badge[0], bg=badge[1], fg="#ffffff", font=(FONT, BASE + 1, "bold"),
                 width=3, pady=8).grid(row=0, column=0, rowspan=2, padx=(12, 14), pady=12)
        tk.Label(card, text=name, bg=C["panel2"], fg=C["text"], font=(FONT, BASE + 1, "bold"),
                 anchor="w").grid(row=0, column=1, sticky="sw", pady=(12, 0))
        tk.Label(card, text=sub, bg=C["panel2"], fg=C["muted"], font=(FONT, BASE - 1),
                 anchor="w").grid(row=1, column=1, sticky="nw", pady=(0, 12))
        tk.Label(card, text="Abrir ↗", bg=C["panel2"], fg=C["accent"], font=(FONT, BASE, "bold")).grid(
            row=0, column=2, rowspan=2, padx=16)
        for w in [card] + card.winfo_children():
            w.bind("<Button-1>", lambda e, u=url: self._open(u))
            w.configure(cursor="hand2")
        return card

    def _show_about(self):
        """Ventana «Creador y soporte» (botón de abajo)."""
        self.root.deiconify()
        w = getattr(self, "about_win", None)
        if w is not None and w.winfo_exists():
            w.deiconify()
            w.lift()
            w.focus_force()
            return
        w = tk.Toplevel(self.root)
        self.about_win = w
        w.title("Creador y soporte · Numpad Macros")
        w.configure(bg=C["panel"])
        w.transient(self.root)
        w.resizable(False, False)
        body = ttk.Frame(w, style="Panel.TFrame", padding=24)
        body.pack(fill="both", expand=True)
        self._build_about_tab(body)
        self.about_body = body
        self._paint_extra()
        w.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - w.winfo_width()) // 2
        y = self.root.winfo_rooty() + 40
        w.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _mark(self, logo):
        ui = self.cfg.setdefault("ui", {})
        if ui.get("extra"):
            return
        now = time.monotonic()
        if now - getattr(self, "_mark_t0", 0) > 4:
            self._mark_t0, self._mark_n = now, 0
        self._mark_n = getattr(self, "_mark_n", 0) + 1
        n = self._mark_n
        if n >= 4:
            logo.configure(highlightbackground=C["accent"], highlightcolor=C["accent"])
        if 4 <= n < 7:
            self._show_toast(f"Te faltan {7 - n} clics…")
        if n >= 7:
            with self.engine.lock:
                ui["extra"] = True
            self._save()
            logo.configure(highlightbackground=C["panel"], highlightcolor=C["panel"])
            self._show_toast("✦ Funciones ocultas desbloqueadas")
            self._paint_extra()

    def _paint_extra(self):
        body = getattr(self, "about_body", None)
        if body is None or not body.winfo_exists():
            return
        old = getattr(self, "extra_card", None)
        if old is not None and old.winfo_exists():
            old.destroy()
        if not self.cfg.get("ui", {}).get("extra"):
            return
        lab = C["key_global_line"]
        card = tk.Frame(body, bg=C["key_global"], highlightbackground=lab, highlightthickness=1)
        card.grid(row=7, column=0, sticky="ew", pady=(10, 0))
        card.columnconfigure(0, weight=1)
        tk.Label(card, text="Laboratorio · funciones ocultas", bg=C["key_global"], fg=C["text"],
                 font=(FONT, BASE + 1, "bold"), anchor="w").grid(row=0, column=0, sticky="w", padx=14, pady=(10, 0))
        tk.Label(card, text="Opciones experimentales, como la transparencia de los temas.",
                 bg=C["key_global"], fg=C["key_global_text"], font=(FONT, BASE - 1), anchor="w").grid(
            row=1, column=0, sticky="w", padx=14, pady=(0, 10))
        FlatButton(card, text="Abrir laboratorio", command=self._show_lab, bg=lab, fg="#ffffff",
                   font=(FONT, BASE, "bold"), padx=14, pady=6).grid(row=0, column=1, rowspan=2, padx=(0, 6))
        FlatButton(card, text="Ocultar", command=self._hide_extra, bg=C["key_global"], fg=C["key_global_text"],
                   font=(FONT, BASE - 1), padx=10, pady=6).grid(row=0, column=2, rowspan=2, padx=(0, 12))
        self.extra_card = card

    def _hide_extra(self):
        with self.engine.lock:
            self.cfg.setdefault("ui", {})["extra"] = False
        self._save()
        self._mark_n = 0
        self._paint_extra()

    # ---------------------------------------------------------------- laboratorio
    def _alpha_cfg(self):
        a = self.cfg.setdefault("ui", {}).setdefault("alpha", {})
        base = self.theme.get("alpha") or {}
        a.setdefault("on", False)
        a.setdefault("window", float(base.get("window", 0.92)))
        a.setdefault("idle", float(base.get("idle", 0.6)))
        a.setdefault("top", False)
        return a

    def _apply_alpha(self, idle=False):
        """Transparencia de la ventana (solo con temas que la permiten)."""
        a = self._alpha_cfg()
        on = a["on"] and themes.supports_alpha(self.theme)
        value = 1.0 if not on else (a["idle"] if idle else a["window"])
        if getattr(self, "art", None) is not None:
            self.art.set_idle(idle)
        try:
            self.root.attributes("-alpha", value)
            self.root.attributes("-topmost", bool(on and a["top"]))
        except tk.TclError:
            pass

    def _setup_alpha(self):
        self.root.bind("<Enter>", lambda e: self._apply_alpha(False), add="+")
        self.root.bind("<Leave>", lambda e: self.root.after(120, self._alpha_check), add="+")
        self._apply_alpha()

    def _alpha_check(self):
        try:
            x, y = self.root.winfo_pointerxy()
            rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
            inside = rx <= x < rx + self.root.winfo_width() and ry <= y < ry + self.root.winfo_height()
        except tk.TclError:
            return
        self._apply_alpha(idle=not inside)

    def _show_lab(self):
        w = getattr(self, "lab_win", None)
        if w is not None and w.winfo_exists():
            w.lift()
            return
        w = tk.Toplevel(self.root)
        self.lab_win = w
        w.title("Laboratorio · Numpad Macros")
        w.configure(bg=C["panel"])
        w.transient(self.root)
        w.resizable(False, False)
        lab = C["key_global_line"]
        top = tk.Frame(w, bg=C["key_global"])
        top.pack(fill="x")
        tk.Label(top, text="Funciones ocultas", bg=C["key_global"], fg=C["key_global_text"],
                 font=(FONT, BASE - 1)).pack(anchor="w", padx=18, pady=(12, 0))
        hl = tk.Frame(top, bg=C["key_global"])
        hl.pack(fill="x", padx=18, pady=(0, 12))
        tk.Label(hl, text="Laboratorio", bg=C["key_global"], fg=C["text"], font=(FONT, BASE + 7, "bold")).pack(side="left")
        tk.Label(hl, text="EXPERIMENTAL", bg=lab, fg="#ffffff", font=(FONT, BASE - 2, "bold"), padx=6).pack(side="right")
        body = ttk.Frame(w, style="Panel.TFrame", padding=18)
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body, style="Panel.TFrame")
        left.grid(row=0, column=0, sticky="nw")
        right = ttk.Frame(body, style="Panel.TFrame")
        right.grid(row=0, column=1, sticky="nw", padx=(24, 0))
        ok = themes.supports_alpha(self.theme)
        a = self._alpha_cfg()
        ttk.Label(left, text="Transparencia de los temas", style="H.TLabel").pack(anchor="w")
        if ok:
            msg = f"«{self.theme['name']}» admite transparencia."
        else:
            msg = (f"«{self.theme['name']}» no admite transparencia. Solo los temas creados con esta "
                   "opción (en su archivo .npt) la activan.")
        tk.Label(left, text=msg, bg=C["panel2"], fg=C["text"], wraplength=360, justify="left",
                 font=(FONT, BASE - 1), padx=10, pady=8, anchor="w").pack(fill="x", pady=(8, 10))
        st = ["!disabled"] if ok else ["disabled"]
        self.al_on = tk.BooleanVar(value=a["on"])
        self.al_win = tk.DoubleVar(value=round(a["window"] * 100))
        self.al_idle = tk.DoubleVar(value=round(a["idle"] * 100))
        self.al_top = tk.BooleanVar(value=a["top"])
        cb = ttk.Checkbutton(left, text="Activar transparencia", variable=self.al_on, command=self._on_alpha)
        cb.pack(anchor="w")
        cb.state(st)
        rows = []
        for text, var, lo, sub in (("Opacidad de la ventana", self.al_win, 50, "Toda la ventana deja ver lo que hay detrás."),
                                   ("Opacidad cuando no la usas", self.al_idle, 30, "Más transparente cuando el mouse sale de la ventana.")):
            f = ttk.Frame(left, style="Panel.TFrame")
            f.pack(fill="x", pady=(10, 0))
            lbl = ttk.Label(f, style="Panel.TLabel")
            lbl.pack(anchor="w")
            sc = ttk.Scale(f, from_=lo, to=100, variable=var, length=340,
                           command=lambda _v, lbl=lbl, t=text, var=var: (
                               lbl.configure(text=f"{t}: {round(var.get())} %"), self._on_alpha()))
            sc.pack(anchor="w")
            sc.state(st)
            lbl.configure(text=f"{text}: {round(var.get())} %")
            ttk.Label(f, text=sub, style="Muted.TLabel").pack(anchor="w")
            rows.append(sc)
        tc = ttk.Checkbutton(left, text="Mantener la ventana siempre encima", variable=self.al_top,
                             command=self._on_alpha)
        tc.pack(anchor="w", pady=(10, 0))
        tc.state(st)
        ttk.Label(right, text="TEMAS COMPATIBLES", style="Muted.TLabel", font=(FONT, BASE - 1, "bold")).pack(anchor="w")
        for th in themes.all_themes():
            r = ttk.Frame(right, style="Panel.TFrame")
            r.pack(fill="x", pady=(4, 0))
            ttk.Label(r, text=th["name"], style="Panel.TLabel", width=18).pack(side="left")
            yes = themes.supports_alpha(th)
            tk.Label(r, text="Admite" if yes else "No admite", bg=C["panel"], fg=C["ok"] if yes else C["muted"],
                     font=(FONT, BASE - 1, "bold" if yes else "normal")).pack(side="right")
        ttk.Label(right, text="Más funciones experimentales\naparecerán aquí en futuras versiones.",
                  style="Muted.TLabel", justify="left").pack(anchor="w", pady=(12, 0))
        foot = ttk.Frame(w, style="Panel.TFrame", padding=(18, 0, 18, 16))
        foot.pack(fill="x")
        ttk.Label(foot, text="Para esconder el laboratorio otra vez: «Ocultar» en Creador y soporte.",
                  style="Muted.TLabel").pack(side="left")
        ttk.Button(foot, text="Cerrar", style="Accent.TButton", command=w.destroy).pack(side="right")
        w.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - w.winfo_width()) // 2
        y = self.root.winfo_rooty() + 60
        w.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _on_alpha(self):
        a = self._alpha_cfg()
        a.update(on=self.al_on.get(), window=round(self.al_win.get()) / 100,
                 idle=round(self.al_idle.get()) / 100, top=self.al_top.get())
        self._save_later()
        self._apply_alpha()

    def _open(self, url):
        if not sysutil.open_url(url):
            self._set_status(f"No pude abrir el navegador. Enlace: {url}", bad=True)

    # ---------------------------------------------------------------- pestaña numpad
    def _build_capture_tab(self):
        t = scroll_frame(self.tab_cap)
        t.columnconfigure(0, weight=1)
        r = 0
        ttk.Label(t, text="Cómo se captura el numpad", style="H.TLabel").grid(row=r, column=0, sticky="w")
        self.mode_var = tk.StringVar(value=self.cfg["mode"])
        for mode_id, title, desc in capture.modes():
            r += 1
            ttk.Radiobutton(t, text=title, value=mode_id, variable=self.mode_var,
                            command=self._on_mode).grid(row=r, column=0, sticky="w", pady=(8, 0))
            r += 1
            ttk.Label(t, style="Muted.TLabel", text="   " + desc, wraplength=520,
                      justify="left").grid(row=r, column=0, sticky="w")
        r += 1
        dev = ttk.Frame(t, style="Panel.TFrame")
        dev.grid(row=r, column=0, sticky="w", pady=(14, 0))
        self.dev_lbl = ttk.Label(dev, style="Panel.TLabel")
        self.dev_lbl.pack(side="left")
        self.btn_learn = ttk.Button(dev, text="Detectar numpad", command=self._learn_device)
        self.btn_learn.pack(side="left", padx=12)
        r += 1
        self.perm_row = ttk.Frame(t, style="Panel.TFrame")
        self.perm_row.grid(row=r, column=0, sticky="w", pady=(10, 0))
        if IS_LINUX:
            self.perm_lbl = ttk.Label(self.perm_row, style="Warn.TLabel", wraplength=360, justify="left")
            self.perm_lbl.pack(side="left")
            self.btn_perm = ttk.Button(self.perm_row, text="Dar permisos…", style="Accent.TButton",
                                       command=self._grant_linux)
            self.btn_perm.pack(side="left", padx=12)

        r += 1
        ttk.Label(t, text="Fila de números (sin numpad)", style="H.TLabel").grid(
            row=r, column=0, sticky="w", pady=(20, 0))
        rm = self.cfg["row_mode"]
        r += 1
        self.row_on_var = tk.BooleanVar(value=rm.get("enabled", True))
        ttk.Checkbutton(t, text="Usar 1–0, - y = del teclado principal en «modo macros»",
                        variable=self.row_on_var, command=self._on_row_opts).grid(
            row=r, column=0, sticky="w", pady=(8, 0))
        r += 1
        tg = ttk.Frame(t, style="Panel.TFrame")
        tg.grid(row=r, column=0, sticky="w", pady=(6, 0))
        ttk.Label(tg, text="Activar / desactivar con", style="Panel.TLabel").pack(side="left", padx=(0, 10))
        try:
            tmods, _tkid, tkey = parse_toggle(rm.get("toggle", ""))
        except ValueError:
            tmods, tkey = {"ctrl", "alt"}, "m"
        self.tog_vars = {}
        for m in MODIFIERS:
            v = tk.BooleanVar(value=m in tmods)
            self.tog_vars[m] = v
            ttk.Checkbutton(tg, text=MOD_LABEL[m], variable=v, command=self._on_row_opts).pack(
                side="left", padx=(0, 8))
        ttk.Label(tg, text="+", style="Panel.TLabel").pack(side="left", padx=(0, 8))
        self.tog_key = ttk.Combobox(tg, state="readonly", width=10,
                                    values=[k.upper() for k in TOGGLE_CHOICES])
        self.tog_key.set(tkey.upper())
        self.tog_key.pack(side="left")
        self.tog_key.bind("<<ComboboxSelected>>", lambda e: self._on_row_opts())
        r += 1
        self.btn_rec_tog = ttk.Button(t, text="⏺ Grabar pulsando las teclas",
                                      command=lambda: self._start_rec("toggle"))
        self.btn_rec_tog.grid(row=r, column=0, sticky="w", pady=(6, 0))
        r += 1
        self.tog_warn = ttk.Label(t, style="Warn.TLabel", wraplength=520, justify="left")
        self.tog_warn.grid(row=r, column=0, sticky="w")
        self._paint_tog_warn(rm.get("toggle", ""))
        r += 1
        ttk.Label(t, style="Muted.TLabel", wraplength=520, justify="left", text=(
            "Con el modo macros apagado la fila de números escribe normal. Al activarlo, 1–0, - y = "
            "lanzan lo que asignes en la fila de números del dibujo (cada banco tiene las suyas); "
            "todas las demás teclas siguen escribiendo.")).grid(row=r, column=0, sticky="w", pady=(4, 0))

        r += 1
        ttk.Label(t, text="Teclas virtuales (app del celular)", style="H.TLabel").grid(
            row=r, column=0, sticky="w", pady=(20, 0))
        r += 1
        ph = ttk.Frame(t, style="Panel.TFrame")
        ph.grid(row=r, column=0, sticky="w", pady=(8, 0))
        self.only_var = tk.BooleanVar(value=self._phone_only())
        ttk.Checkbutton(ph, text="Usar solo la app del celular (no buscar numpad ni teclados)",
                        variable=self.only_var, command=self._on_phone_opts).pack(side="left")
        r += 1
        ttk.Label(t, style="Muted.TLabel", wraplength=520, justify="left", text=(
            f"Cada banco tiene {VIRTUAL_COUNT} teclas virtuales ({VIRTUAL_COLS} × {VIRTUAL_ROWS}). No son teclas "
            "físicas: solo se tocan en la app del celular, así que nunca interfieren con los teclados del "
            "equipo. Con «solo celular» el programa no necesita ningún teclado conectado y solo muestra "
            "la pestaña «Teclas virtuales».")
        ).grid(row=r, column=0, sticky="w", pady=(4, 0))

        r += 1
        ttk.Label(t, text="Comportamiento", style="H.TLabel").grid(row=r, column=0, sticky="w", pady=(20, 0))
        self.block_var = tk.BooleanVar(value=self.cfg.get("block_unassigned", True))
        self.toast_var = tk.BooleanVar(value=self.cfg.get("bank_toast", True))
        self.paused_var = tk.BooleanVar(value=self.cfg.get("start_paused", True))
        self.auto_var = tk.BooleanVar(value=sysutil.autostart_enabled())
        r += 1
        ttk.Checkbutton(t, text="Bloquear las teclas sin acción (si no, escriben números)",
                        variable=self.block_var, command=self._on_opts).grid(row=r, column=0, sticky="w", pady=(8, 0))
        r += 1
        ttk.Checkbutton(t, text="Mostrar aviso en pantalla al cambiar de banco",
                        variable=self.toast_var, command=self._on_opts).grid(row=r, column=0, sticky="w", pady=(6, 0))
        r += 1
        ttk.Checkbutton(t, text="Empezar en pausa al abrir (el numpad funciona normal hasta pulsar ACTIVO)",
                        variable=self.paused_var, command=self._on_opts).grid(row=r, column=0, sticky="w", pady=(6, 0))
        r += 1
        ttk.Checkbutton(t, text=f"Iniciar con {OS_NAME}", variable=self.auto_var,
                        command=self._on_autostart).grid(row=r, column=0, sticky="w", pady=(6, 0))
        r += 1
        cl = ttk.Frame(t)
        cl.grid(row=r, column=0, sticky="w", pady=(12, 0))
        ttk.Label(cl, text="Al cerrar la ventana:").pack(side="left")
        self.close_var = tk.StringVar(value=self.cfg.get("ui", {}).get("close", "ask"))
        for val, txt in (("ask", "Preguntar"), ("tray", "Dejar en la bandeja"), ("quit", "Salir del programa")):
            ttk.Radiobutton(cl, text=txt, value=val, variable=self.close_var,
                            command=self._on_close_opt).pack(side="left", padx=(10, 0))
        r += 1
        ttk.Label(t, style="Muted.TLabel", wraplength=520, justify="left", text=(
            "Al pausar o cerrar el programa todo vuelve a funcionar normal. Si por error elegiste "
            "tu teclado principal como numpad, pulsa PAUSADO con el mouse y vuelve a detectarlo.")
        ).grid(row=r, column=0, sticky="w", pady=(16, 0))

    # ---------------------------------------------------------------- pestaña audio
    def _build_audio_tab(self):
        t = self.tab_audio
        t.columnconfigure(1, weight=1)
        a = self.cfg["audio"]
        r = 0
        ttk.Label(t, text="Salida de los sonidos", style="H.TLabel").grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1
        self.board_lbl = ttk.Label(t, style="Muted.TLabel", wraplength=580, justify="left")
        self.board_lbl.grid(row=r, column=0, columnspan=2, sticky="w", pady=(2, 6))

        # falta el micrófono virtual (Windows: VB-Cable, macOS: BlackHole)
        r += 1
        self.vmic_card = tk.Frame(t, bg=C["accent_bg"], highlightbackground=C["accent_dim"], highlightthickness=1)
        self.vmic_card.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.vmic_card.columnconfigure(0, weight=1)
        need = "VB-Cable" if IS_WIN else "BlackHole 2ch"
        tk.Label(self.vmic_card, text=f"No se encontró el micrófono virtual ({need})", bg=C["accent_bg"],
                 fg=C["text"], font=(FONT, BASE, "bold"), anchor="w").grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 0))
        self.vmic_lbl = tk.Label(self.vmic_card, bg=C["accent_bg"], fg=C["muted"], font=(FONT, BASE - 1), anchor="w",
                                 justify="left", wraplength=470, text=(
                                     "Sin él los sonidos solo se escuchan en tus audífonos: nadie te oye en "
                                     "Discord, OBS o el juego. Es gratis y se instala una sola vez."))
        self.vmic_lbl.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        self.vmic_btn = FlatButton(self.vmic_card, text="Instalar VB-Cable" if IS_WIN else "Descargar BlackHole ↗",
                                   command=self._install_vmic, bg=C["accent"], fg=C["on_accent"],
                                   font=(FONT, BASE - 1, "bold"), padx=14, pady=5)
        self.vmic_btn.grid(row=0, column=1, rowspan=2, padx=12)
        self.vmic_card.grid_remove()

        ok, _msg = self.board.available()
        self.audio_widgets = []
        # dónde escuchas tú (todos los sistemas)
        r += 1
        ttk.Label(t, text="Tus audífonos", style="Panel.TLabel").grid(row=r, column=0, sticky="w", pady=3)
        orow = ttk.Frame(t, style="Panel.TFrame")
        orow.grid(row=r, column=1, sticky="w", padx=10)
        self.mon_cb = ttk.Combobox(orow, state="readonly", width=28)
        self.mon_cb.pack(side="left")
        self.mon_cb.bind("<<ComboboxSelected>>", lambda e: self._on_audio())
        ttk.Button(orow, text="↻", width=3, command=self._fill_outputs).pack(side="left", padx=(6, 0))
        ttk.Button(orow, text="▶ Probar", width=9, command=self._test_output).pack(side="left", padx=(6, 0))
        self._fill_outputs()
        self.audio_widgets += [self.mon_cb]
        if self.board.kind == "mixer":
            r += 1
            ttk.Label(t, text="Micrófono virtual", style="Panel.TLabel").grid(row=r, column=0, sticky="w", pady=3)
            mics = ["(ninguno)"] + self.board.outputs()
            if not a["mic_device"] and self.board.suggested_mic():
                a["mic_device"] = self.board.suggested_mic()
            self.micdev_cb = ttk.Combobox(t, state="readonly", width=44, values=mics)
            self.micdev_cb.set(a["mic_device"] or mics[0])
            self.micdev_cb.grid(row=r, column=1, sticky="w", padx=10)
            self.micdev_cb.bind("<<ComboboxSelected>>", lambda e: self._on_audio())
            self.audio_widgets += [self.micdev_cb]
        r += 1
        self.mix_var = tk.BooleanVar(value=a["mix_mic"])
        mix = ttk.Checkbutton(t, text="Mezclar mi micrófono real (hablo y suenan los efectos por el mismo mic)",
                              variable=self.mix_var, command=self._on_audio)
        mix.grid(row=r, column=0, columnspan=2, sticky="w", pady=(8, 2))
        r += 1
        ttk.Label(t, text="Mi micrófono", style="Panel.TLabel").grid(row=r, column=0, sticky="w", pady=3)
        ins = ["(predeterminado)"] + self.board.inputs()
        self.micin_cb = ttk.Combobox(t, state="readonly", width=44, values=ins)
        self.micin_cb.set(a["mic_input"] if a["mic_input"] in ins else ins[0])
        self.micin_cb.grid(row=r, column=1, sticky="w", padx=10)
        self.micin_cb.bind("<<ComboboxSelected>>", lambda e: self._on_audio())
        r += 1
        ttk.Label(t, text="Volumen general", style="Panel.TLabel").grid(row=r, column=0, sticky="w", pady=(8, 2))
        mrow = ttk.Frame(t, style="Panel.TFrame")
        mrow.grid(row=r, column=1, sticky="w", padx=10, pady=(8, 2))
        self.master_var = tk.DoubleVar(value=round(float(a.get("volume", 1.0)) * 100))
        ttk.Scale(mrow, from_=0, to=150, variable=self.master_var, length=260,
                  command=lambda _v: self._on_master()).pack(side="left")
        self.master_lbl = tk.Label(mrow, bg=C["panel2"], fg=C["accent"], font=(FONT, BASE, "bold"),
                                   width=15, padx=6, pady=2)
        self.master_lbl.pack(side="left", padx=10)
        self.master_lbl.configure(text=self._vol_text(round(self.master_var.get())))
        self.audio_widgets += [mix, self.micin_cb]

        # ---- procesamiento: igualar volumen + compresor
        r += 1
        proc = ttk.Frame(t, style="Panel.TFrame")
        proc.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        proc.columnconfigure(0, weight=1, uniform="p")
        proc.columnconfigure(1, weight=1, uniform="p")

        nf = ttk.Frame(proc, style="Card.TFrame", padding=12)
        nf.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.norm_var = tk.BooleanVar(value=a.get("normalize", True))
        ttk.Checkbutton(nf, text="Igualar volumen de los sonidos", variable=self.norm_var,
                        style="Card.TCheckbutton", command=self._on_processing).pack(anchor="w")
        ttk.Label(nf, style="CardMuted.TLabel", wraplength=255, justify="left", text=(
            "Mide cuánto «suena» cada archivo (LUFS) y los ajusta para que todos se escuchen "
            "parecido: ni uno muy despacio ni otro que te reviente los oídos.")).pack(anchor="w", pady=(4, 8))
        ttk.Label(nf, text="Volumen objetivo", style="Card.TLabel").pack(anchor="w")
        trow = ttk.Frame(nf, style="Card.TFrame")
        trow.pack(anchor="w", pady=(2, 0))
        self.target_var = tk.DoubleVar(value=float(a.get("target_lufs", -16)))
        ttk.Scale(trow, from_=-24, to=-10, variable=self.target_var, length=170, style="Card.Horizontal.TScale",
                  command=lambda _v: self._on_processing(save_later=True)).pack(side="left")
        self.target_lbl = ttk.Label(trow, style="Card.TLabel", width=9)
        self.target_lbl.pack(side="left", padx=8)
        ttk.Label(nf, style="CardMuted.TLabel", wraplength=255, justify="left",
                  text="−16 LUFS es lo recomendado para Discord y streams.").pack(anchor="w", pady=(4, 0))

        cf = ttk.Frame(proc, style="Card.TFrame", padding=12)
        cf.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        cf.columnconfigure(0, weight=1)
        comp = a["compressor"]
        self.comp_on = tk.BooleanVar(value=comp.get("on", True))
        ttk.Checkbutton(cf, text="Compresor / limitador", variable=self.comp_on, style="Card.TCheckbutton",
                        command=self._on_processing).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(cf, style="CardMuted.TLabel", wraplength=255, justify="left", text=(
            "Baja los picos fuertes para que no sature ni se corte en Discord.")).grid(
            row=1, column=0, columnspan=2, sticky="nw", pady=(4, 6))
        self.curve = CompCurve(cf, size=104)
        self.curve.grid(row=2, column=1, rowspan=2, sticky="ne", padx=(8, 0))
        prow = ttk.Frame(cf, style="Card.TFrame")
        prow.grid(row=2, column=0, sticky="nw")
        self.preset_var = tk.StringVar(value=comp.get("preset", "media"))
        for i, (pid, name) in enumerate(ld.PRESET_NAMES):
            ttk.Radiobutton(prow, text=name, value=pid, variable=self.preset_var, style="Card.TRadiobutton",
                            command=self._on_processing).grid(row=i, column=0, sticky="w")
        self.custom = ttk.Frame(cf, style="Card.TFrame")
        self.custom.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.comp_vars = {}
        for i, (key, name, lo, hi) in enumerate((("thr", "Umbral", -40, 0), ("ratio", "Relación", 1, 10),
                                                 ("ceil", "Techo", -6, 0))):
            ttk.Label(self.custom, text=name, style="Card.TLabel").grid(row=i, column=0, sticky="w")
            v = tk.DoubleVar(value=float(comp.get(key, {"thr": -18, "ratio": 3, "ceil": -1}[key])))
            ttk.Scale(self.custom, from_=lo, to=hi, variable=v, length=120, style="Card.Horizontal.TScale",
                      command=lambda _v: self._on_processing(save_later=True)).grid(row=i, column=1, padx=6)
            lbl = ttk.Label(self.custom, style="Card.TLabel", width=8)
            lbl.grid(row=i, column=2, sticky="w")
            self.comp_vars[key] = (v, lbl)
        self.comp_live = ttk.Label(cf, style="CardMuted.TLabel")
        self.comp_live.grid(row=3, column=0, sticky="w", pady=(6, 0))
        self._paint_processing()

        r += 1
        ttk.Button(t, text="Aplicar / reconectar audio", command=self._apply_audio_async).grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(12, 0))
        r += 1
        help_txt = {
            "win": "En Discord, OBS o el juego elige «CABLE Output» como micrófono; aquí, «CABLE Input» "
                   "como micrófono virtual.",
            "mac": "Elige BlackHole aquí como micrófono virtual y también como micrófono en Discord, OBS o "
                   "el juego.",
            "linux": "El micrófono virtual «NumpadMacros-Mic» se crea al iniciar (PipeWire o PulseAudio) y "
                     "se quita al cerrar. Elígelo como micrófono en Discord, OBS o el juego.",
        }[PLATFORM]
        ttk.Label(t, style="Muted.TLabel", wraplength=580, justify="left", text=help_txt).grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(8, 0))
        if not ok:
            for wdg in self.audio_widgets:
                wdg.state(["disabled"])
        self._paint_vmic()

    def _fill_outputs(self):
        """Lista de salidas (audífonos, parlantes, HDMI…); se puede refrescar al conectar algo."""
        a = self.cfg["audio"]
        try:
            outs = self.board.outputs()
        except Exception:
            outs = []
        values = ["(predeterminada del sistema)"] + outs
        cur = a.get("monitor_device", "")
        if cur and cur not in values:
            values.append(cur)                     # elegida antes, ahora desconectada
        self.mon_cb.configure(values=values)
        self.mon_cb.set(cur or values[0])

    def _test_output(self):
        try:
            self.board.test_tone()
            self._set_status("Sonó un pitido corto en tus audífonos (no sale por el micrófono).")
        except Exception as e:
            self._set_status(f"No pude probar la salida: {e}", bad=True)

    def _paint_processing(self):
        a = self.cfg["audio"]
        self.target_lbl.configure(text=f"{a.get('target_lufs', -16):.0f} LUFS")
        comp = a["compressor"]
        custom = comp.get("preset") == "custom"
        if custom:
            self.custom.grid()
        else:
            self.custom.grid_remove()
        for key, (v, lbl) in self.comp_vars.items():
            val = comp.get(key)
            lbl.configure(text=f"{val:.1f}:1" if key == "ratio" else f"{val:.0f} dB")
        thr, ratio, ceil = ld.comp_params(a)
        self.curve.draw(thr, ratio, ceil, on=comp.get("on", True))

    def _on_processing(self, save_later=False):
        a = self.cfg["audio"]
        with self.engine.lock:
            a["normalize"] = self.norm_var.get()
            a["target_lufs"] = float(round(self.target_var.get()))
            comp = a["compressor"]
            comp["on"] = self.comp_on.get()
            comp["preset"] = self.preset_var.get()
            for key, (v, _l) in self.comp_vars.items():
                comp[key] = round(v.get(), 1 if key == "ratio" else 0)
        self._paint_processing()
        self._paint_volume()
        self._fill_library()
        if save_later:
            self._save_later()
        else:
            self._save()

    def _paint_vmic(self):
        missing = getattr(self.board, "virtual_mic_missing", lambda: False)()
        if missing and not IS_LINUX:
            self.vmic_card.grid()
        else:
            self.vmic_card.grid_remove()

    def _install_vmic(self):
        if IS_MAC:
            self._open("https://existential.audio/blackhole/")
            return
        self.vmic_btn.configure(text="Descargando…")
        self._set_status("Descargando VB-Cable desde vb-audio.com…")

        def job():
            try:
                updater.install_vbcable()
                self.uiq.put(("vbcable", True, ""))
            except Exception as e:
                self.uiq.put(("vbcable", False, str(e)))
        threading.Thread(target=job, daemon=True).start()

    def _after_vbcable(self, ok, msg):
        self.vmic_btn.configure(text="Instalar VB-Cable")
        if ok:
            self.vmic_lbl.configure(text="En la ventana de VB-Cable pulsa «Install Driver». Después reinicia "
                                         "el PC y elige «CABLE Input» como micrófono virtual aquí.")
            self._set_status("Se abrió el instalador de VB-Cable: pulsa «Install Driver».")
        else:
            self._set_status(msg, bad=True)

    # ================================================================ captura
    def _start_backend(self):
        if self.backend:
            self.backend.stop()
            self.backend = None
        self.fallback = ""
        if self._phone_only():
            self._set_status("Modo solo celular: conecta la app en la pestaña «Celular».")
            self._update_device_ui()
            return
        try:
            self.backend = capture.create(self.cfg["mode"], self.engine, self.cfg.get("device", ""))
            self.backend.start()
        except BackendError as e:
            self.backend = None
            if IS_WIN and self.cfg["mode"] == "interception":
                # Sin el driver, la app igual funciona: captura las teclas numéricas de todos los teclados
                try:
                    self.backend = capture.create("hook", self.engine, "")
                    self.backend.start()
                    self.fallback = str(e)
                except BackendError as e2:
                    self.backend = None
                    e = e2
            if self.backend is None:
                self._set_status(f"No se pudo iniciar la captura: {e}", bad=True)
        except Exception as e:
            self.backend = None
            self._set_status(f"Error al iniciar la captura: {e}", bad=True)
        if self.backend:
            if self.fallback:
                self._set_status("Interception no está instalado: se usa el modo sin driver "
                                 "(captura el numpad de todos los teclados).")
            elif self.backend.learns_device and not self.cfg.get("device"):
                self._set_status("Ve a «Numpad y opciones» → «Detectar numpad» para elegir tu numpad.")
            else:
                self._set_status("Listo.")
        self._update_device_ui()

    def _update_device_ui(self):
        b = self.backend
        dev = self.cfg.get("device", "")
        if self._phone_only():
            txt, col = "● Solo celular (sin teclado)", C["ok"]
        elif b is None:
            txt, col = "● Captura detenida", C["bad"]
        elif not b.learns_device:
            txt = "● Sin driver (Interception no instalado)" if self.fallback else \
                "● Sin driver: teclas numéricas de cualquier teclado"
            col = C["warn"] if self.fallback else C["ok"]
        elif not dev:
            txt, col = "● Numpad sin elegir", C["warn"]
        elif b.connected():
            txt, col = f"● Numpad conectado: {describe_device(dev)}", C["ok"]
        else:
            txt, col = f"● Numpad desconectado: {describe_device(dev)}", C["bad"]
        self.chip_dev.configure(text=txt, fg=col)
        self.dev_lbl.configure(text=f"Numpad elegido: {describe_device(dev)}")
        self.btn_learn.state(["!disabled"] if b is not None and b.learns_device else ["disabled"])
        self.btn_capture.state(["!disabled"] if b else ["disabled"])
        if IS_LINUX:
            if not self._needs_perms():
                self.perm_row.grid_remove()
            else:
                self.perm_lbl.configure(text="Falta dar permiso para leer el numpad y enviar atajos "
                                             "(se pide tu contraseña una sola vez).")
                self.perm_row.grid()

    @staticmethod
    def _needs_perms() -> bool:
        from .linux_perms import has_access
        return not has_access()

    def _grant_linux(self):
        from .linux_perms import grant
        self._set_status("Esperando tu contraseña…")
        self.btn_perm.state(["disabled"])

        def job():
            ok, msg = grant(env=clean_env())
            self.uiq.put(("perm", ok, msg))
        threading.Thread(target=job, daemon=True).start()

    def _after_perms(self, ok, msg):
        self.btn_perm.state(["!disabled"])
        if not ok:
            self._set_status(msg, bad=True)
            return
        self.root.after(700, self._reload_after_perms)   # udev aplica los permisos en un instante

    def _reload_after_perms(self):
        self.sender, self.sender_err = make_sender()
        self.engine.sender = self.sender
        self._start_backend()
        if self.sender_err:
            self._set_status("Permisos aplicados. Si algo no funciona, cierra sesión y vuelve a entrar.")
        else:
            self._set_status("Permisos listos ✓")

    # ================================================================ audio
    def _apply_audio_async(self, initial=False):
        a = self.cfg["audio"]
        if initial and self.board.kind == "mixer" and not a.get("mic_device"):
            self._update_board_ui()
            return

        def job():
            try:
                self.board.apply()
                self.uiq.put(("board_ok",))
            except Exception as e:
                self.uiq.put(("board_error", str(e)))
        threading.Thread(target=job, daemon=True).start()
        self._update_board_ui()

    def _update_board_ui(self, err=None):
        ok, msg = self.board.available()
        text = err or (self.board.status() if ok else msg)
        good = ok and not err
        self.board_lbl.configure(text=text)
        has_mic = self.board.kind == "pipewire" or bool(self.cfg["audio"].get("mic_device"))
        chip = ("● Audio listo" + (" · micrófono virtual" if has_mic else " · solo audífonos")) if good \
            else "● Audio con problemas"
        self.chip_board.configure(text=chip, fg=C["ok"] if good and has_mic else (C["warn"] if good else C["bad"]))
        if hasattr(self, "vmic_card"):
            self._paint_vmic()

    def _on_audio(self):
        a = self.cfg["audio"]
        with self.engine.lock:
            mon = self.mon_cb.get()
            a["monitor_device"] = "" if mon.startswith("(") else mon
            if self.board.kind == "mixer":
                mic = self.micdev_cb.get()
                a["mic_device"] = "" if mic.startswith("(") else mic
            a["mix_mic"] = self.mix_var.get()
            mi = self.micin_cb.get()
            a["mic_input"] = "" if mi.startswith("(") else mi
        self._save()
        self._apply_audio_async()

    def _on_master(self):
        with self.engine.lock:
            self.cfg["audio"]["volume"] = round(self.master_var.get()) / 100
        self.master_lbl.configure(text=self._vol_text(round(self.master_var.get())))
        self._save_later()

    def _save_later(self):
        if self._save_job:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(400, self._save)

    # ================================================================ biblioteca
    def _ask_files(self):
        exts = " ".join(f"*{e}" for e in AUDIO_EXT)
        paths = filedialog.askopenfilenames(
            parent=self.root, title="Elige sonidos",
            initialdir=self.cfg.get("last_dir") or os.path.expanduser("~"),
            filetypes=[("Audio", exts), ("Todos los archivos", "*")])
        paths = list(paths or [])
        if paths:
            with self.engine.lock:
                self.cfg["last_dir"] = os.path.dirname(paths[0])
        return paths

    def _lib_changed(self, msg=None):
        self._save()
        if getattr(self, "remote", None):
            self.remote.library_changed()
        self._fill_library()
        self._queue_loudness()
        self._fill_pick()
        if msg:
            self._set_status(msg)

    def _lib_add_files(self):
        paths = self._ask_files()
        if paths:
            with self.engine.lock:
                n = library.add(self.cfg, paths)
            self._lib_changed(f"Agregados {n} sonidos." if n else "Esos sonidos ya estaban en la biblioteca.")

    def _lib_add_folder(self):
        folder = filedialog.askdirectory(parent=self.root, title="Elige una carpeta con sonidos",
                                         initialdir=self.cfg.get("last_dir") or os.path.expanduser("~"))
        if not folder:
            return
        found = library.scan_folder(folder)
        with self.engine.lock:
            self.cfg["last_dir"] = folder
            n = library.add(self.cfg, found)
        self._lib_changed(f"Agregados {n} sonidos de «{os.path.basename(folder)}»." if found
                          else "No encontré audios en esa carpeta.")

    def _lib_import_spl(self):
        path = filedialog.askopenfilename(parent=self.root, title="Lista de Soundpad (.spl)",
                                          filetypes=[("Lista de Soundpad", "*.spl"), ("Todos", "*")])
        if not path:
            return
        try:
            with self.engine.lock:
                n, total = library.import_spl(self.cfg, path)
        except ValueError as e:
            self._set_status(str(e), bad=True)
            return
        self._lib_changed(f"Importados {n} de {total} sonidos de la lista de Soundpad.")

    def _lib_selected(self):
        return [self._lib_view[i] for i in self.lib_lb.curselection() if i < len(self._lib_view)]

    def _lib_remove(self):
        items = self._lib_selected()
        if not items:
            return
        used = library.usage(self.cfg)
        n_used = sum(1 for x in items if used.get(library.norm(x["path"])))
        extra = f"\n\n{n_used} de ellos están asignados a teclas; esas teclas seguirán funcionando." if n_used else ""
        if not messagebox.askyesno("Quitar sonidos",
                                   f"¿Quitar {len(items)} sonido(s) de la biblioteca?{extra}\n\n"
                                   "(Los archivos no se borran del disco)", parent=self.root):
            return
        with self.engine.lock:
            library.remove(self.cfg, [x["path"] for x in items])
        self._lib_changed()

    def _lib_preview(self):
        items = self._lib_selected()
        if items:
            self.engine.preview(items[0]["path"])

    def _lib_assign(self):
        items = self._lib_selected()
        if not items:
            self._set_status("Elige un sonido de la lista primero.", bad=True)
            return
        self._assign_file(items[0])
        self.nb.select(0)

    def _lib_sel_changed(self):
        self.btn_assign.state(["!disabled"] if self.lib_lb.curselection() else ["disabled"])

    def _fill_library(self):
        lb = self.lib_lb
        keep = {library.norm(x["path"]) for x in self._lib_selected()} if self._lib_view else set()
        lb.delete(0, "end")
        self._lib_view = library.search(self.cfg, self.lib_q.get())
        used = library.usage(self.cfg)
        for x in self._lib_view:
            n = used.get(library.norm(x["path"]), 0)
            mark = "⚠ " if not os.path.isfile(x["path"]) else "   "
            tail = f"   · {n} tecla{'s' if n != 1 else ''}" if n else ""
            tail += self._lufs_text(x)
            lb.insert("end", f" {mark}{x['title']}{tail}")
            if library.norm(x["path"]) in keep:
                lb.selection_set("end")
        total = len(self.cfg.get("library", []))
        self.lib_count.configure(text=f"{total} sonido{'s' if total != 1 else ''}")
        if not total:
            lb.insert("end", "  Agrega tus sonidos con «＋ Archivos…» o «＋ Carpeta…».")
        self._update_assign_label()
        self._lib_sel_changed()

    def _lufs_text(self, item):
        if "lufs" not in item:
            return ""
        if item["lufs"] is None:
            return "   · silencio"
        txt = f"   · {item['lufs']:.0f} LUFS"
        if self.cfg["audio"].get("normalize", True):
            adj = ld.norm_gain_db(item["lufs"], self.cfg["audio"].get("target_lufs", -16))
            txt += f" ({adj:+.0f} dB)"
        return txt

    def _queue_loudness(self):
        """Mide en segundo plano los sonidos que aún no tienen su volumen (LUFS)."""
        for item in self.cfg.get("library", []):
            path = item.get("path", "")
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            if item.get("lufs_mtime") != mtime:
                self._lufs_q.put(path)
        if self._lufs_busy or self._lufs_q.empty() or not self.board.available()[0]:
            return
        self._lufs_busy = True

        def job():
            while True:
                try:
                    path = self._lufs_q.get_nowait()
                except queue.Empty:
                    break
                try:
                    mtime = os.path.getmtime(path)
                    value = self.board.loudness(path)
                    self.uiq.put(("lufs", path, mtime, value))
                except Exception:
                    pass
                time.sleep(0.02)             # sin acaparar el procesador
            self.uiq.put(("lufs_done",))
        threading.Thread(target=job, daemon=True).start()

    def _on_lufs(self, path, mtime, value):
        key = library.norm(path)
        with self.engine.lock:
            for item in self.cfg.get("library", []):
                if library.norm(item["path"]) == key:
                    item["lufs"], item["lufs_mtime"] = value, mtime
        self._lufs_dirty = True

    def _update_assign_label(self):
        where = "Global" if self.layer == "global" else self.cfg["banks"][self.layer]["name"]
        self.btn_assign.configure(text=f"Asignar a {key_label(self.selected)} · {where}")

    # ---- elegir sonido para la tecla
    def _fill_pick(self):
        pk = getattr(self, "picker", None)
        if pk is None:
            return
        try:
            if not pk.frame.winfo_exists():
                return
        except tk.TclError:
            return
        act = self._current_action() or {}
        cur = library.norm(act["path"]) if act.get("type") == "file" and act.get("path") else ""
        pk.refresh(current=cur)

    def _add_files_for_key(self):
        paths = self._ask_files()
        if not paths:
            return
        with self.engine.lock:
            library.add(self.cfg, paths)
        self._fill_library()
        self._queue_loudness()
        self._assign_file({"path": os.path.abspath(paths[0]), "title": title_of(paths[0])})
        if len(paths) > 1:
            self._set_status(f"Asignado «{title_of(paths[0])}»; los otros {len(paths) - 1} quedaron en la biblioteca.")

    def _assign_file(self, item, rebuild=True):
        old = self._current_action() or {}
        keep = old if old.get("type") == "file" else {}
        act = {"type": "file", "path": item["path"], "title": item["title"],
               "volume": keep.get("volume", 1.0), "mode": keep.get("mode", "overlap"),
               "speakers": keep.get("speakers", True), "mic": keep.get("mic", True)}
        self._store(act)
        self._fill_library()
        if rebuild:
            self._load_editor()
        else:
            self._refresh_file_header(act)
        self._set_status(f"{key_label(self.selected)} → {item['title']}")

    def _refresh_file_header(self, act):
        if not hasattr(self, "file_lbl") or not self.file_lbl.winfo_exists():
            return
        path = act.get("path", "")
        self.file_lbl.configure(text=("🔊 " + (act.get("title") or title_of(path))) if path
                                else "Elige un sonido de la lista")
        self.file_warn.configure(text="⚠ No se encuentra el archivo" if path and not os.path.isfile(path) else "")
        self._paint_volume(act)

    def _vol_text(self, pct):
        if pct <= 0:
            return "0 % · silencio"
        db = ld.lin_to_db(pct / 100)
        return f"{pct:.0f} % · {db:+.1f} dB".replace("+0.0", "0.0").replace("-0.0", "0.0")

    def _paint_volume(self, act=None):
        if not hasattr(self, "vol_lbl") or not self.vol_lbl.winfo_exists():
            return
        self.vol_lbl.configure(text=self._vol_text(round(self.vol_var.get())))
        act = act or self._current_action() or {}
        path = act.get("path", "")
        a = self.cfg["audio"]
        txt = ""
        if path and a.get("normalize", True):
            item = next((x for x in self.cfg.get("library", [])
                         if library.norm(x["path"]) == library.norm(path)), None)
            if item and "lufs" in item and item.get("lufs") is not None:
                adj = ld.norm_gain_db(item["lufs"], a.get("target_lufs", -16))
                txt = (f"Igualar volumen: este sonido mide {item['lufs']:.1f} LUFS → se ajusta "
                       f"{adj:+.1f} dB para quedar en {a.get('target_lufs', -16):.0f} LUFS. "
                       "El volumen de la tecla se aplica después.")
            elif path:
                txt = "Igualar volumen: midiendo este sonido…"
        elif path:
            txt = "Igualar volumen está apagado (pestaña Audio)."
        self.norm_lbl.configure(text=txt)

    def _on_volume(self):
        self._paint_volume()
        act = self._current_action()
        if act and act.get("type") == "file":
            with self.engine.lock:
                self._layer_dict()[self.selected] = dict(act, volume=round(self.vol_var.get()) / 100)
            self._save_later()

    def _on_file_opt(self):
        if not self.spk_var.get() and not self.mic_var.get():
            self.spk_var.set(True)
        act = self._current_action()
        if act and act.get("type") == "file":
            mode = LABEL_MODE.get(self.mode_cb.get(), "overlap")
            self._store(dict(act, speakers=self.spk_var.get(), mic=self.mic_var.get(), mode=mode))

    def _test_tag(self, act=None):
        """Etiqueta del sonido de la tecla elegida (la misma que usa el motor)."""
        act = act if act is not None else self._current_action()
        if not act or act.get("type") != "file":
            return None
        return self.engine._tag(act, self.selected)

    def _test_action(self):
        """▶ Probar / ■ Detener: si el sonido de esta tecla ya está sonando, lo detiene."""
        act = self._current_action()
        if not act:
            return
        tag = self._test_tag(act)
        if tag and self.board.playing(tag):
            self.board.stop_tag(tag)
            self._test_pending = 0
            self._set_test_btn(False)
            return
        self.engine.run_action(act, self.selected)
        if tag:
            self._test_pending = time.monotonic()        # el motor lo lanza en un instante
            self._set_test_btn(True)

    def _set_test_btn(self, playing):
        btn = getattr(self, "btn_test", None)
        try:
            if btn is not None and btn.winfo_exists():
                want = "■ Detener" if playing else "▶ Probar"
                if btn.cget("text") != want:
                    btn.configure(text=want)
        except tk.TclError:
            pass

    def _paint_test_btn(self):
        """Muestra «■ Detener» mientras suena el sonido de la tecla elegida (llamado ~20 veces/s)."""
        if getattr(self, "btn_test", None) is None:
            return
        tag = self._test_tag()
        try:
            playing = bool(tag) and self.board.playing(tag)
        except Exception:
            playing = False
        if not playing and time.monotonic() - getattr(self, "_test_pending", 0) < 0.6:
            return                                      # todavía no empieza: no parpadear
        self._set_test_btn(playing)

    # ================================================================ dibujo
    def _layer_dict(self, layer=None):
        layer = self.layer if layer is None else layer
        return self.cfg["global"] if layer == "global" else self.cfg["banks"][layer]["keys"]

    # ---------------------------------------------------------------- tamaño adaptable
    def _setup_responsive(self):
        """Las teclas crecen o se achican con la ventana (y con la escala de la pantalla)."""
        try:
            self.dpi = max(1.0, self.root.winfo_fpixels("1i") / 96)
        except tk.TclError:
            self.dpi = 1.0
        self._fit_job = None
        self._fit_size = None
        self.root.bind("<Configure>", self._on_configure, add="+")
        self.root.after(60, self._fit_keys)

    def _on_configure(self, ev):
        if ev.widget is not self.root:
            return
        if self._fit_job:
            self.root.after_cancel(self._fit_job)
        self._fit_job = self.root.after(90, self._fit_keys)
        if getattr(self, "_settle_job", None):
            self.root.after_cancel(self._settle_job)
        self._settle_job = self.root.after(150, self._after_resize)
        # mientras se arrastra el borde, también en cada cuadro (no solo al soltar); cuesta unos 2 ms
        if getattr(self, "_repaint_job", None) is None:
            self._repaint_job = self.root.after(16, self._repaint_moved)

    def _after_resize(self):
        """Cuando la ventana deja de cambiar de tamaño: lo que se movió de sitio se vuelve a mostrar
        entero. En algunos sistemas (XWayland) lo movido no recibe aviso de repintado y queda vacío."""
        self._settle_job = None
        self._repaint_moved()
        xbg.paint(self.root, only_mapped=True)                    # widgets que aparecieron desde entonces

    def _repaint_moved(self):
        """Pide a cada widget visible que se dibuje entero otra vez (sin ocultarlo: no parpadea).
        Volver a poner una opción con el mismo valor obliga a Tk a redibujar todo el widget.
        Solo los que cambiaron de sitio o de tamaño desde la vez anterior: redibujar un widget le
        cuesta a Tk ~1 ms en XWayland y la ventana entera (~60 ms) no alcanzaba a seguir el arrastre."""
        self._repaint_job = None
        geo = self.__dict__.setdefault("_repaint_geo", {})        # widget -> (geometría, vuelta)
        n = self._repaint_pass = getattr(self, "_repaint_pass", 0) + 1

        def walk(w):
            try:
                if not w.winfo_ismapped():
                    return
                g = (w.winfo_rootx(), w.winfo_rooty(), w.winfo_width(), w.winfo_height())
                key = str(w)
                old = geo.get(key)
                geo[key] = (g, n)
                # también si la vuelta anterior no estaba a la vista (se volvió a mostrar)
                if old is None or old[0] != g or old[1] != n - 1:
                    if isinstance(w, ttk.Widget):
                        w.configure(style=w.cget("style"))
                    elif "background" in w.keys():
                        w.configure(background=w.cget("background"))
            except tk.TclError:
                return
            for c in w.winfo_children():
                walk(c)
        walk(self.root)

    def _repaint_all(self, later=(120, 600, 1500)):
        """Pide a cada elemento que se vuelva a dibujar. En algunos escritorios Linux con efectos
        (KWin, Mutter…) quedaban rectángulos negros después de cambiar el tema o de pasar a pantalla
        completa: partes de la ventana que el sistema no mandó a redibujar."""
        def run():
            stack = [self.root]
            while stack:
                w = stack.pop()
                try:
                    if w.winfo_ismapped():
                        w.event_generate("<Expose>", x=0, y=0, width=max(1, w.winfo_width()),
                                         height=max(1, w.winfo_height()), count=0)
                    stack.extend(w.winfo_children())
                except tk.TclError:
                    pass
        for ms in later:
            try:
                self.root.after(ms, run)
            except tk.TclError:
                pass

    def _fit_keys(self):
        self._fit_job = None
        W, H = self.root.winfo_width(), self.root.winfo_height()
        if W < 50 or H < 50 or (W, H) == self._fit_size:
            return
        # (al cambiar de tamaño, lo que se movió se repinta con _repaint_moved/_after_resize: no hace falta
        # pedirle a toda la ventana que se redibuje, que en XWayland frenaba el redimensionado)
        self._fit_size = (W, H)
        self._paint_window_bg()
        if self.themes_wide():
            # panel de teclas oculto (pestaña Temas): medirlo obliga a dibujar toda la ventana a medio
            # cambiar de tamaño (~0,4 s) y la pestaña se ve a medio cargar. Se ajusta al volver a verse
            # (_apply_wide pone _fit_size en None y lo vuelve a llamar).
            return
        d = self.dpi
        # alto libre para el dibujo (cabecera, pestañas y pie fuera)
        free = H - self.left_top_h()
        width_cap = W * .36 - 40 * d
        lb = getattr(self, "leftbot_lbl", None)
        if lb is not None:
            # la imagen de abajo del panel ocupa su alto: las teclas se achican para que todas quepan.
            # Si así quedarían demasiado chicas (ventana baja, p. ej. 1280×720), la imagen se esconde:
            # las teclas importan más.
            lbh = self.art.fit_size("leftbot", max(1, width_cap), 160 * d)[1] + 8 * d
            if self.left_view == "virt":
                room = (free - lbh - 90 * d) / 6.15
            else:
                room = (free - lbh - 135 * d) / 6.5
            try:
                if room >= 52 * d:
                    free -= lbh
                    if not lb.winfo_manager():
                        lb.pack(side="bottom", fill="x", pady=(8, 0))
                elif lb.winfo_manager():
                    lb.pack_forget()
            except tk.TclError:
                pass
        # numpad: 5 filas + fila de números (2/3 del tamaño) + títulos y botón
        u = self._numpad_room(free, d)
        mt, mr, mb, ml = self.NMARGIN
        pt, pr, pb, pl = self.NPAD
        u = min(u, (width_cap - 3 * 7 - ml - mr - pl - pr - 2 * self.NBORDER) / 4, self.N_MAX * d)
        self.UNIT = int(max(self.N_MIN * d, u))
        self.GAP = max(6, int(self.UNIT / self.N_GAP_DIV))
        self.RUNIT = int(self.UNIT * .66)
        self.RGAP = max(5, int(self.GAP * .8))
        v = self._virt_room(free, d)
        mt, mr, mb, ml = self.VMARGIN
        pt, pr, pb, pl = self.VPAD
        v = min(v, (width_cap - 4 * 8 - ml - mr - pl - pr - 2 * self.VBORDER) / 5, self.V_MAX * d)
        self.VUNIT = int(max(self.V_MIN * d, v))
        self.VGAP = max(6, int(self.VUNIT / self.V_GAP_DIV))
        if getattr(self, "picker", None) is not None:
            self._fit_pick_rows()
        nw, nh = self._numpad_box_size()
        self.canvas.configure(width=nw, height=nh)
        self.row_canvas.configure(width=6 * self.RUNIT + 5 * self.RGAP, height=2 * self.RUNIT + self.RGAP)
        vw, vh = self._virt_box_size()
        self.virt_canvas.configure(width=vw, height=vh)
        self._redraw()

    def _panel_room(self, canvases, view):
        """Alto libre en el panel izquierdo para los lienzos dados (todo lo demás, medido), o None."""
        try:
            lp = self.left_panel
            avail = lp.winfo_height()
            if avail <= 100:
                return None
            rest = lp.winfo_reqheight() - sum(c.winfo_reqheight() for c in canvases)
            if self.left_view != view:               # medido con la otra vista puesta
                shown, other = ((self.view_numpad, self.view_virt) if view == "virt"
                                else (self.view_virt, self.view_numpad))
                rest += other.winfo_reqheight() - shown.winfo_reqheight()
            return avail - rest - 2 * getattr(self, "dpi", 1.0)
        except (tk.TclError, AttributeError):
            return None

    def _numpad_room(self, free, d):
        """Lado máximo de una tecla del numpad para que el numpad y la fila 1–0 quepan enteros."""
        self._pack_numpad_box()                      # el margin cuenta en lo que se mide
        try:
            self.root.update_idletasks()
        except tk.TclError:
            pass
        h = self._panel_room((self.canvas, self.row_canvas), "numpad")
        if h is None:                                # aún sin dibujar: estimación
            h = free - 135 * d - self.NMARGIN[0] - self.NMARGIN[2]
        h -= self.NPAD[0] + self.NPAD[2] + 2 * self.NBORDER     # padding y border de arriba y abajo
        h -= self.N_SAFE * d                                     # margen de seguridad
        k = self.N_GAP_DIV
        # numpad: 5 lados + 4 separaciones (lado / k, mín. 6); fila 1–0: 2 × 0,66 lado + 1 separación
        return min(h / (5 + 4 / k + 1.32 + .8 / k), (h - 4 * 6 - 5) / (5 + 1.32))

    def _virt_room(self, free, d):
        """Lado máximo de una tecla virtual para que las 6 filas quepan enteras en el panel.
        Se mide lo que ocupa todo lo demás (pestañas, capa, títulos, texto de ayuda y la imagen
        del tema abajo) en vez de estimarlo."""
        self._pack_virt_box()                        # el margin cuenta en lo que se mide
        try:
            self.root.update_idletasks()             # medir con el margin nuevo, no con el anterior
        except tk.TclError:
            pass
        h = self._panel_room((self.virt_canvas,), "virt")
        if h is None:                                # aún sin dibujar: estimación
            h = free - 90 * d - self.VMARGIN[0] - self.VMARGIN[2]
        h -= self.VPAD[0] + self.VPAD[2] + 2 * self.VBORDER     # padding y border de arriba y abajo
        rows, gaps = VIRTUAL_ROWS, VIRTUAL_ROWS - 1
        # separación = lado / V_GAP_DIV (mínimo 6 px)
        return min(h / (rows + gaps / self.V_GAP_DIV), (h - gaps * 6) / rows)

    def _pack_virt_box(self):
        """Aplica margin y position del recuadro de teclas virtuales (como en CSS)."""
        d = getattr(self, "dpi", 1.0)
        self.VMARGIN = tuple(int(v * d) for v in self.V_MARGIN)
        self.VPAD = tuple(int(v * d) for v in self.V_PADDING)
        self.VBORDER = int(self.V_BORDER * d)
        mt, mr, mb, ml = self.VMARGIN
        anchor = {"left": "w", "right": "e"}.get(self.V_ALIGN, "center")
        self.virt_canvas.pack_configure(pady=(mt, mb), padx=(ml, mr), anchor=anchor)

    def _pack_numpad_box(self):
        """Aplica margin y position del recuadro del numpad (como en CSS)."""
        d = getattr(self, "dpi", 1.0)
        self.NMARGIN = tuple(int(v * d) for v in self.N_MARGIN)
        self.NPAD = tuple(int(v * d) for v in self.N_PADDING)
        self.NBORDER = int(self.N_BORDER * d)
        mt, mr, mb, ml = self.NMARGIN
        anchor = {"left": "w", "right": "e"}.get(self.N_ALIGN, "center")
        self.canvas.pack_configure(pady=(mt, mb), padx=(ml, mr), anchor=anchor)

    def _numpad_box_size(self):
        """Ancho y alto del recuadro del numpad: content + padding + border."""
        pt, pr, pb, pl = self.NPAD
        b = 2 * self.NBORDER
        return (4 * self.UNIT + 3 * self.GAP + pl + pr + b, 5 * self.UNIT + 4 * self.GAP + pt + pb + b)

    def _virt_box_size(self):
        """Ancho y alto del recuadro: content + padding + border (el margin va por fuera)."""
        pt, pr, pb, pl = self.VPAD
        b = 2 * self.VBORDER
        return (VIRTUAL_COLS * self.VUNIT + (VIRTUAL_COLS - 1) * self.VGAP + pl + pr + b,
                VIRTUAL_ROWS * self.VUNIT + (VIRTUAL_ROWS - 1) * self.VGAP + pt + pb + b)

    def _refit_soon(self):
        """Vuelve a calcular el tamaño de las teclas (p. ej. cuando carga una imagen del tema)."""
        self._fit_size = None
        if getattr(self, "_fit_job", None):
            self.root.after_cancel(self._fit_job)
        self._fit_job = self.root.after(90, self._fit_keys)

    PICK_MIN, PICK_MAX = 96, 560    # alto del selector de sonidos (px a escala 1)
    TAB_SAFE = 12                   # margen de seguridad al final de una pestaña (px a escala 1)

    def _fit_pick_soon(self):
        if getattr(self, "_pick_job", None) is None:
            try:
                self._pick_job = self.root.after_idle(self._fit_pick_rows)
            except tk.TclError:
                pass

    def _fit_pick_rows(self):
        """Alto del selector de sonidos: todo lo que sobra en la pestaña «Tecla», medido (como las
        teclas del panel). Solo si ni con el mínimo cabe, la pestaña se desplaza."""
        self._pick_job = None
        pk = getattr(self, "picker", None)
        if pk is None:
            return
        d = getattr(self, "dpi", 1.0)
        try:
            inner = self._key_inner
            have = inner.master.winfo_height()          # alto visible de la pestaña
            if have < 50:
                return
            rest = inner.winfo_reqheight() - pk.body.winfo_reqheight()
            border = pk.body.winfo_reqheight() - pk.height
            target = have - rest - border - self.TAB_SAFE * d
            target = max(self.PICK_MIN * d, min(self.PICK_MAX * d, target))
            if abs(target - pk.height) >= 2:
                pk.set_height(target)
        except (tk.TclError, AttributeError):
            pass

    def left_top_h(self):
        """Alto que ocupan la cabecera, las pestañas del panel y el pie de la ventana."""
        try:
            self.root.update_idletasks()
            top = self.layer_cb.winfo_rooty() + self.layer_cb.winfo_height() - self.root.winfo_rooty()
            foot = self.status.winfo_height() if hasattr(self, "status") else 30
        except (tk.TclError, AttributeError):
            top, foot = 200, 30
        return top + foot + 50

    def _key_rect(self, kid):
        _, c, r, w, h = NUMPAD_LAYOUT[kid]
        u, g, b = self.UNIT, self.GAP, self.NBORDER
        x0, y0 = b + self.NPAD[3] + c * (u + g), b + self.NPAD[0] + r * (u + g)
        return x0, y0, x0 + w * u + (w - 1) * g, y0 + h * u + (h - 1) * g

    def _row_rect(self, kid):
        _, c, r = ROW_LAYOUT[kid]
        u, g = self.RUNIT, self.RGAP
        x0, y0 = c * (u + g), r * (u + g)
        return x0, y0, x0 + u, y0 + u

    def _virt_rect(self, kid):
        _, c, r = phone_layout()[kid]
        u, g, b = self.VUNIT, self.VGAP, self.VBORDER
        x0, y0 = b + self.VPAD[3] + c * (u + g), b + self.VPAD[0] + r * (u + g)
        return x0, y0, x0 + u, y0 + u

    def _key_font(self, px, bold=False):
        """Fuente en píxeles (cacheada) para dibujar dentro de las teclas."""
        cache = self.__dict__.setdefault("_kfonts", {})
        key = (px, bold)
        if key not in cache:
            cache[key] = tkfont.Font(root=self.root, family=FONT, size=-px,
                                     weight="bold" if bold else "normal")
        return cache[key]

    @staticmethod
    def _wrap(text, font, width, lines=2):
        """Parte el texto en hasta `lines` líneas que quepan en `width` (con «…» si sobra)."""
        words, out, cur = text.split(), [], ""
        for w in words:
            test = f"{cur} {w}".strip()
            if font.measure(test) <= width or not cur:
                cur = test
            else:
                out.append(cur)
                cur = w
        if cur:
            out.append(cur)
        out = out or [""]
        if len(out) > lines:
            out = out[:lines]
            out[-1] += "…"
        fixed = []
        for ln in out:                                 # una palabra muy larga: cortarla
            if font.measure(ln) > width:
                while len(ln) > 1 and font.measure(ln + "…") > width:
                    ln = ln[:-1]
                ln = ln.rstrip("…") + "…"
            fixed.append(ln)
        return "\n".join(fixed)

    def _draw_key(self, cv, rect, kid, label, act, gact, size="big"):
        """Dibuja una tecla: vacía, con acción, de la capa Global (marca «G») o con su color."""
        x0, y0, x1, y1 = rect
        kw, kh = x1 - x0, y1 - y0
        u = min(kw, kh)
        shown = gact or act
        is_global = bool(gact) or (self.layer == "global" and bool(act))
        col = button_color(shown)
        fill, line, lw, sub = C["key"], C["key"], 1, C["muted"]
        if shown:
            if col:
                fill, line, lw, sub = mix(col, C["panel"], .80), col, 2, C["text"]
            elif is_global:
                fill, line, sub = C["key_global"], C["key_global_line"], C["key_global_text"]
            else:
                fill, line, sub = C["key_set"], C["key_set_line"], C["key_set_text"]
        if kid in self.flash:
            fill = C["accent"]
        if kid == self.selected:
            line, lw = C["accent"], 3
            if col and mix(col, C["accent"], .5) == col:
                line = C["text"]
        small = size == "small"
        r = max(5, int(u * (.14 if small else .12)))
        # fondo suavizado (Pillow); sin Pillow, dos formas llenas del lienzo
        art = getattr(self, "art", None)
        ka = 1.0
        if art is not None and art.has("keys") and kid not in self.flash:
            ka = art.section("keys").get("contenido", 100) / 100 if art.section("keys") else 1.0
            # transparencia propia de la capa de la tecla (vacía, con acción o Global)
            tok = "key" if not shown else ("key_global" if is_global else "key_set")
            ka *= art.layer(tok) if not col else 1.0
            ka = ka if shown else min(ka, .82)            # las vacías dejan ver un poco la imagen
        img = aa.key_shape(self.root, int(x1 - x0) - 1, int(y1 - y0) - 1, r, fill, line, lw, ka)
        if img is not None:
            cv.create_image(int(x0) + 1, int(y0) + 1, image=img, anchor="nw")
        else:
            self._round_rect(x0 + 1, y0 + 1, x1 - 1, y1 - 1, r, canvas=cv, fill=line, outline="")
            self._round_rect(x0 + 1 + lw, y0 + 1 + lw, x1 - 1 - lw, y1 - 1 - lw, max(3, r - lw), canvas=cv,
                             fill=fill, outline="")
        pad = max(5, int(u * .13))
        num_px = max(11, min(15, int(u * .30))) if small else max(13, min(22, int(u * .24)))
        if len(label) > 2:
            num_px = max(10, int(num_px * (.72 if small else .66)))
            room = kw - 2 * pad - (max(11, int(u * .19)) + 3 if is_global else 0)
            while num_px > 8 and self._key_font(num_px, True).measure(label) > room:
                num_px -= 1
        cv.create_text(x0 + pad, y0 + pad - 1, text=label, anchor="nw", fill=C["text"],
                       font=self._key_font(num_px, True))
        ico_px = max(9, min(13, int(u * .15)))
        if is_global:                       # marca «G» de la capa Global
            gs = max(11, int(u * .19))
            gx, gy = x1 - pad - gs + 2, y0 + pad - 1
            gline = C["key_global_line"] if not col else col
            bimg = aa.badge(self.root, gs, gline)
            if bimg is not None:
                cv.create_image(gx, gy, image=bimg, anchor="nw")
            else:
                cv.create_rectangle(gx, gy, gx + gs, gy + gs, fill=gline, outline="")
            cv.create_text(gx + gs / 2, gy + gs / 2, text="G", fill=C["bg"],
                           font=self._key_font(max(8, int(gs * .72)), True))
        if not shown:
            return
        t = shown.get("type")
        if small:
            icon = {"file": "🔊", "keys": "⌨", "sound_stop": "■"}.get(t, "→")
            cv.create_text(x1 - pad + 2, y1 - pad + 2, text=icon, anchor="se", fill=sub,
                           font=self._key_font(ico_px))
            return
        if not is_global:                   # icono del tipo, arriba a la derecha
            icon = {"file": "🔊", "keys": "⌨", "sound_stop": "■"}.get(t, "›")
            if t == "file":
                icon = (MODE_ICON.get(shown.get("mode", "overlap"), "").strip() + " 🔊").strip()
            cv.create_text(x1 - pad + 2, y0 + pad, text=icon, anchor="ne", fill=sub,
                           font=self._key_font(ico_px))
        if t == "file":
            txt = shown.get("title") or title_of(shown.get("path", "")) or "?"
        else:
            txt = short_action(shown, False).replace("\n", " ").replace("+ ", "+")
        lab_px = max(9, min(13, int(u * .155)))
        font = self._key_font(lab_px, True)
        lines = 2 if kh >= 52 else 1
        txt = self._wrap(txt, font, kw - 2 * max(4, pad - 3), lines)
        cv.create_text((x0 + x1) / 2, y1 - pad + 3, text=txt, anchor="s", fill=sub,
                       font=font, justify="center")

    def _redraw(self):
        layer = self._layer_dict()
        glob = (lambda k: self.cfg["global"].get(k)) if self.layer != "global" else (lambda k: None)
        self._paint_view_tabs()
        if self.left_view == "virt":
            cv = self.virt_canvas
            cv.delete("all")
            self._draw_keys_bg(cv)
            self._draw_box_border(cv, self.VBORDER)
            for kid, (label, _c, _r) in phone_layout().items():
                self._draw_key(cv, self._virt_rect(kid), kid, label, layer.get(kid), glob(kid))
            return
        cv = self.canvas
        cv.delete("all")
        self._draw_keys_bg(cv)
        self._draw_box_border(cv, self.NBORDER)
        for kid, (label, *_rest) in NUMPAD_LAYOUT.items():
            self._draw_key(cv, self._key_rect(kid), kid, label, layer.get(kid), glob(kid))
        self._draw_row()
        self._draw_extras()

    @staticmethod
    def _draw_box_border(cv, b):
        """border del recuadro de teclas (CSS), con el color de línea del tema."""
        if b:
            w, h = int(cv.cget("width")), int(cv.cget("height"))
            cv.create_rectangle(b / 2, b / 2, w - b / 2, h - b / 2, outline=C["line"], width=b)

    def _draw_keys_bg(self, cv):
        """Imagen del tema detrás de la tabla de teclas (y la plancha de la sección «keys»)."""
        art = getattr(self, "art", None)
        if art is None or not (art.has("keys") or art.section("keys") or art.one_piece):
            return
        try:
            w, h = int(cv.cget("width")), int(cv.cget("height"))
        except (tk.TclError, ValueError):
            return
        if art.one_piece:
            try:
                x, y, _ww, _hh = self._rect(cv)
            except tk.TclError:
                x = y = 0
            img = art.photo(("keysbg", id(cv)), art.compose(w, h, box=(x, y), slot="keys", section="keys",
                                                            base_color=C["panel"]))
            key = None
        else:
            key = ("keysbg", id(cv), w, h)
            img = art._photos.get(key)
        if img is None and key is not None:
            img = art.photo(key, art.compose(w, h, slot="keys", section="keys", base_color=C["panel"]))
        if img is not None:
            cv.create_image(0, 0, image=img, anchor="nw")
            if art.realce("keys"):
                cv.create_rectangle(1, 1, w - 2, h - 2, outline=C["accent"], width=2)

    def _round_rect(self, x0, y0, x1, y1, r, canvas=None, **kw):
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
               x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return (canvas or self.canvas).create_polygon(pts, smooth=True, **kw)

    def _phone_only(self):
        return bool(self.cfg.get("phone", {}).get("only"))

    def _set_view(self, view):
        if self._phone_only():
            view = "virt"
        self.left_view = view
        self._apply_view()
        if getattr(self, "leftbot_lbl", None) is not None:
            self._fit_size = None              # cada vista necesita otro alto: volver a medir
            self._fit_keys()
        if view == "virt" and self.selected not in PHONE_IDS:
            self._select("m1")
        elif view == "numpad" and self.selected in PHONE_IDS:
            self._select("47")
        else:
            self._redraw()

    def _apply_view(self):
        """Muestra el numpad o las teclas virtuales (en «solo celular», solo las virtuales)."""
        only = self._phone_only()
        box = self.lt_tabs["numpad"][0]
        if only:
            box.pack_forget()
        elif not box.winfo_ismapped():
            box.pack(side="left", fill="x", expand=True, padx=(0, 4), before=self.lt_tabs["virt"][0])
        if self.left_view == "virt":
            self.view_numpad.pack_forget()
            self.view_virt.pack(fill="x")
        else:
            self.view_virt.pack_forget()
            self.view_numpad.pack(fill="x")
        self._paint_view_tabs()

    def _paint_view_tabs(self):
        for vid, (_box, b, bar) in self.lt_tabs.items():
            on = vid == self.left_view
            b.configure(bg=C["panel2"] if on else C["panel"], fg=C["text"] if on else C["muted"])
            bar.configure(bg=C["accent"] if on else C["line"])

    def _draw_row(self):
        cv = self.row_canvas
        cv.delete("all")
        enabled = self.cfg["row_mode"].get("enabled", True)
        try:
            toggle = self._combo_text(self.cfg["row_mode"]["toggle"])
        except Exception:
            toggle = "?"
        self.row_title.configure(
            text=(f"Fila de números · modo macros ({toggle})" if enabled
                  else "Fila de números · desactivada (ver «Numpad y opciones»)"))
        layer = self._layer_dict()
        for kid, (label, *_r) in ROW_LAYOUT.items():
            gact = self.cfg["global"].get(kid) if self.layer != "global" else None
            self._draw_key(cv, self._row_rect(kid), kid, label, layer.get(kid), gact, size="small")

    def _on_row_click(self, ev):
        for kid in ROW_LAYOUT:
            x0, y0, x1, y1 = self._row_rect(kid)
            if x0 <= ev.x <= x1 and y0 <= ev.y <= y1:
                self._select(kid)
                return

    def _on_virt_click(self, ev):
        for kid in phone_layout():
            x0, y0, x1, y1 = self._virt_rect(kid)
            if x0 <= ev.x <= x1 and y0 <= ev.y <= y1:
                self._select(kid)
                return

    def _draw_extras(self):
        for wdg in self.extra_frame.winfo_children():
            wdg.destroy()
        extras = [k for k in self.cfg.get("extra_keys", [])
                  if k not in NUMPAD_IDS and k not in ROW_IDS and k not in PHONE_IDS]
        if not extras:
            return
        ttk.Label(self.extra_frame, text="Teclas extra de tu numpad",
                  style="Muted.TLabel").pack(anchor="w")
        row = ttk.Frame(self.extra_frame, style="Panel.TFrame")
        row.pack(fill="x", pady=(4, 0))
        layer = self._layer_dict()
        for kid in extras:
            act = layer.get(kid) or (self.cfg["global"].get(kid) if self.layer != "global" else None)
            txt = key_label(kid) + (f"\n{short_action(act)}" if act else "")
            col = button_color(act)
            bg = C["accent"] if kid in self.flash else (mix(col, C["panel"], .78) if col else
                                                        (C["key_set"] if act else C["key"]))
            b = FlatButton(row, text=txt, bg=bg, fg=C["text"], font=(FONT, BASE - 2), padx=8, pady=4,
                           highlightthickness=2, highlightbackground=C["accent"] if kid == self.selected else bg,
                           command=lambda k=kid: self._select(k))
            b.pack(side="left", padx=(0, 6))

    def _on_canvas_click(self, ev):
        for kid in NUMPAD_LAYOUT:
            x0, y0, x1, y1 = self._key_rect(kid)
            if x0 <= ev.x <= x1 and y0 <= ev.y <= y1:
                self._select(kid)
                return

    def _select(self, kid):
        self.selected = kid
        want = "virt" if kid in PHONE_IDS else "numpad"
        if want != self.left_view and not (self._phone_only() and want == "numpad"):
            self.left_view = want
            self._apply_view()
        self._redraw()
        self._load_editor()
        self._update_assign_label()

    def _on_tab(self):
        if self.nb.index("current") == 1:
            self._fill_library()
        self._apply_wide()

    def themes_wide(self) -> bool:
        """En «Temas» el panel de teclas se oculta (salvo que el usuario pida verlo)."""
        try:
            on_themes = self.nb.select() == str(self.tab_themes)
        except tk.TclError:
            return False
        return on_themes and not self.cfg.get("ui", {}).get("temas_teclas", False)

    def _apply_wide(self):
        """Oculta o muestra el panel de teclas y vuelve a pintar lo que se movió."""
        wide = self.themes_wide()
        lp = self.left_panel
        if wide == (not lp.winfo_manager()):
            return
        if wide:
            lp.grid_remove()
            self.nb.grid_configure(column=0, columnspan=2, padx=(18, 18))
        else:
            lp.grid()
            self.nb.grid_configure(column=1, columnspan=1, padx=(8, 18))
        if hasattr(self, "themestab"):
            self.themestab.paint_header()
            self.root.after(80, self.themestab.repaint_after_move)
        if self.art.one_piece:
            self._unify_soon(120)
        self._fit_size = None
        self.root.after(100, self._fit_keys)

    def toggle_theme_keys(self):
        """Botón de la pestaña Temas: mostrar u ocultar el panel de teclas (se recuerda)."""
        ui = self.cfg.setdefault("ui", {})
        with self.engine.lock:
            ui["temas_teclas"] = not ui.get("temas_teclas", False)
        self._save()
        self._apply_wide()

    # ================================================================ capas / bancos
    def _refresh_layer_combo(self):
        vals = ["🌐 Global (todos los bancos)"] + [
            f"{i + 1}. {b['name']}" for i, b in enumerate(self.cfg["banks"])]
        self.layer_cb.configure(values=vals)
        if self.layer != "global" and self.layer >= len(self.cfg["banks"]):
            self.layer = len(self.cfg["banks"]) - 1
        self.layer_cb.current(0 if self.layer == "global" else self.layer + 1)

    def _on_layer_pick(self, _e=None):
        i = self.layer_cb.current()
        self.layer = "global" if i == 0 else i - 1
        if self.layer != "global":
            self.engine.set_bank(self.layer, notify=False)
            self._update_bank_label()
        self._redraw()
        self._load_editor()
        self._update_assign_label()

    def _add_bank(self):
        name = simpledialog.askstring("Nuevo banco", "Nombre del banco:",
                                      initialvalue=f"Banco {len(self.cfg['banks']) + 1}",
                                      parent=self.root)
        if not name:
            return
        with self.engine.lock:
            self.cfg["banks"].append({"name": name.strip()[:30], "keys": {}})
        self.layer = len(self.cfg["banks"]) - 1
        self._save()
        self._refresh_layer_combo()
        self._on_layer_pick()

    def _rename_bank(self):
        if self.layer == "global":
            return
        b = self.cfg["banks"][self.layer]
        name = simpledialog.askstring("Renombrar banco", "Nuevo nombre:",
                                      initialvalue=b["name"], parent=self.root)
        if name:
            with self.engine.lock:
                b["name"] = name.strip()[:30]
            self._save()
            self._refresh_layer_combo()
            self._update_bank_label()
            self._load_editor()

    def _delete_bank(self):
        if self.layer == "global":
            return
        if len(self.cfg["banks"]) <= 1:
            messagebox.showinfo("Numpad Macros", "Debe quedar al menos un banco.", parent=self.root)
            return
        b = self.cfg["banks"][self.layer]
        if not messagebox.askyesno("Eliminar banco",
                                   f"¿Eliminar «{b['name']}» y todas sus asignaciones?",
                                   parent=self.root):
            return
        with self.engine.lock:
            del self.cfg["banks"][self.layer]
            self.cfg["active_bank"] = min(self.cfg["active_bank"], len(self.cfg["banks"]) - 1)
        self.layer = min(self.layer, len(self.cfg["banks"]) - 1)
        self._save()
        self._refresh_layer_combo()
        self._update_bank_label()
        self._on_layer_pick()

    def _update_bank_label(self):
        i = self.engine.bank
        text = f"{i + 1}. {self.cfg['banks'][i]['name']}"
        f = tkfont.Font(font=(FONT, BASE + 1, "bold"))
        room = int(146 * getattr(self, "dpi", 1.0))          # cabe entre las flechas ◀ ▶
        if f.measure(text) > room:
            while text and f.measure(text + "…") > room:
                text = text[:-1]
            text = text.rstrip() + "…"
        self.bank_lbl.configure(text=text)

    # ================================================================ editor: carga
    def _load_editor(self):
        self.root.after_idle(lambda: self._unify_soon(80))
        kid = self.selected
        act = self._layer_dict().get(kid) or {"type": "none"}
        where = "Global" if self.layer == "global" else self.cfg["banks"][self.layer]["name"]
        self.ed_title.configure(text=f"{key_label(kid)}   ·   {where}")
        note = ""
        if self.layer != "global" and self.cfg["global"].get(kid):
            note = ("Esta tecla tiene una acción en la capa Global, que tiene prioridad sobre "
                    "cualquier banco. Edítala en «Global» o quítala de ahí para usarla en este banco.")
        elif self.layer == "global":
            note = "Lo que asignes aquí funciona en todos los bancos (ideal para cambiar de banco o detener sonidos)."
        if kid in ROW_IDS:
            row_note = (f"Tecla {ROW_LAYOUT[kid][0]} de la fila de números: funciona solo con el modo "
                        f"macros activo ({self._combo_text(self.cfg['row_mode'].get('toggle', ''))}).")
            if not self.cfg["row_mode"].get("enabled", True):
                row_note = "La fila de números está desactivada: actívala en «Numpad y opciones»."
            note = (row_note + " " + note).strip()
        elif kid in PHONE_IDS:
            note = (f"Tecla {key_label(kid).lower()}: no es una tecla física, solo se toca en la app del "
                    "celular (pestaña «Celular» para conectarlo). " + note).strip()
        self.ed_note.configure(text=note)
        self._editor_lock = True
        self.type_cb.set(TYPE_LABEL.get(act.get("type", "none"), TYPE_LABEL["none"]))
        self._editor_lock = False
        self._build_sub(act)

    def _build_sub(self, act):
        self._clear_sub()
        self.sub.columnconfigure(0, weight=0)
        self.sub.rowconfigure(2, weight=0)
        t = act.get("type", "none")
        if t == "file":
            self._build_file_sub(act)
        elif t == "keys":
            self._build_keys_sub(act)
        elif t == "bank_go":
            self._build_bank_go_sub(act)
        elif t == "sound_stop":
            self._build_info_sub("Detiene todos los sonidos que estén sonando.")
        elif t == "bank_next":
            self._build_info_sub("Pasa al banco siguiente (después del último vuelve al primero).")
        elif t == "bank_prev":
            self._build_info_sub("Vuelve al banco anterior.")
        else:
            self._build_info_sub("Elige qué hará esta tecla.")
        self._paint_color()

    def _paint_color(self):
        act = self._current_action()
        if not act or act.get("type", "none") == "none":
            self.color_card.grid_remove()
            return
        self.color_card.grid()
        cur = act.get("color", -1) if isinstance(act.get("color"), int) else -1
        n = int(round(30 * getattr(self, "dpi", 1.0)))
        for i, cv in self.swatches:
            cv.delete("all")
            on = i == cur
            img = aa.swatch(self.root, n, None if i < 0 else BUTTON_COLORS[i][1], on,
                            C["text"], "#14161b", C["muted"])
            if img is not None:
                cv.configure(width=n, height=n)
                cv.create_image(0, 0, image=img, anchor="nw")
                continue
            if on:
                cv.create_oval(1, 1, 29, 29, outline=C["text"], width=2)
            if i < 0:
                cv.create_oval(5, 5, 25, 25, outline=C["muted"], dash=(3, 2), width=2)
                cv.create_text(15, 15, text="✕", fill=C["muted"], font=(FONT, BASE - 2))
            else:
                cv.create_oval(5, 5, 25, 25, fill=BUTTON_COLORS[i][1], outline="")
                if on:
                    cv.create_text(15, 15, text="✓", fill="#14161b", font=(FONT, BASE - 1, "bold"))
        self.color_name.configure(text=("Sin color" if cur < 0 else BUTTON_COLORS[cur][0]))

    def _set_color(self, i):
        act = self._current_action()
        if not act:
            return
        new = dict(act)
        if i < 0:
            new.pop("color", None)
        else:
            new["color"] = i
        with self.engine.lock:
            self._layer_dict()[self.selected] = new
        self._save()
        self._redraw()
        self._paint_color()

    # ================================================================ editor: cambios
    def _current_action(self):
        return self._layer_dict().get(self.selected)

    def _store(self, act, redraw=True):
        with self.engine.lock:
            d = self._layer_dict()
            if not act or act.get("type") == "none":
                d.pop(self.selected, None)
            else:
                old = d.get(self.selected) or {}
                if "color" in old and "color" not in act:      # cambiar la acción no borra el color
                    act = dict(act, color=old["color"])
                d[self.selected] = act
        self._save()
        if redraw:
            self._redraw()

    def _kick_backend(self):
        if self.backend and hasattr(self.backend, "_force_scan"):
            self.backend._force_scan = True
        if self.backend and hasattr(self.backend, "_next_scan"):
            self.backend._next_scan = 0

    def _free_fkey(self):
        used = set()
        for layer in [self.cfg["global"]] + [b["keys"] for b in self.cfg["banks"]]:
            for a in layer.values():
                if a.get("type") == "keys":
                    used.add(a.get("combo", "").lower())
        top = 20 if IS_MAC else 24
        for i in range(13, top + 1):
            if f"f{i}" not in used:
                return f"f{i}"
        return "f13"

    def _on_type_pick(self, _e=None):
        if self._editor_lock:
            return
        t = LABEL_TYPE.get(self.type_cb.get(), "none")
        old = self._current_action() or {}
        if old.get("type") == t:
            return
        act = {"type": t}
        if t == "keys":
            act["combo"] = self._free_fkey()
        elif t == "bank_go":
            act["bank"] = 1
        if t == "file":
            # se guarda cuando se elige un sonido de la lista
            self._store(None)
            self._build_sub({"type": "file", "speakers": True, "mic": True, "mode": "overlap"})
            return
        self._store(act)
        self._build_sub(act)

    # ---- atajo
    def _on_combo_change(self):
        mods = [m for m, v in self.mod_vars.items() if v.get()]
        key = self.key_cb.get().lower()
        combo = "+".join(mods + [key])
        self.combo_preview.configure(text=self._combo_text(combo))
        self._paint_keys_warn(combo)
        self._store({"type": "keys", "combo": combo})

    def _paint_keys_warn(self, combo):
        if not hasattr(self, "keys_warn") or not self.keys_warn.winfo_exists():
            return
        why = busy_reason(combo)
        self.keys_warn.configure(text=f"Ojo: {self._combo_text(combo)} ya se usa para {why} en muchos "
                                      "programas. Mejor usa F13–F24." if why else "")

    # ---- grabar una combinación pulsándola
    def _start_rec(self, target):
        if self._rec == target:
            self._stop_rec("Grabación cancelada.")
            return
        self._rec = target
        self._rec_mods = set()
        self.root.bind_all("<KeyPress>", self._rec_key, add="+")
        self.root.bind_all("<KeyRelease>", self._rec_release, add="+")
        self.root.focus_force()
        btn = self.btn_rec_keys if target == "keys" else self.btn_rec_tog
        btn.configure(text="● Pulsa la combinación… (Esc cancela)")
        self._set_status("Pulsa en tu teclado la combinación que quieres (con Ctrl/Shift/Alt si quieres). "
                         "Esc para cancelar.")

    def _stop_rec(self, msg=None):
        self._rec = None
        self.root.unbind_all("<KeyPress>")
        self.root.unbind_all("<KeyRelease>")
        for name in ("btn_rec_keys", "btn_rec_tog"):
            b = getattr(self, name, None)
            if b is not None and b.winfo_exists():
                b.configure(text="⏺ Grabar pulsando las teclas")
        if msg:
            self._set_status(msg)

    def _rec_release(self, ev):
        m = MODIFIER_KEYSYMS.get((ev.keysym or "").lower())
        if m:
            self._rec_mods.discard(m)

    def _rec_key(self, ev):
        if not self._rec:
            return
        sym = (ev.keysym or "").lower()
        if sym in MODIFIER_KEYSYMS:
            self._rec_mods.add(MODIFIER_KEYSYMS[sym])
            return "break"
        if sym == "escape" and not self._rec_mods:
            self._stop_rec("Grabación cancelada.")
            return "break"
        key = keysym_to_key(ev.keysym)
        target = self._rec
        if target == "toggle":
            if key not in TOGGLE_CHOICES:
                self._set_status(f"«{ev.keysym}» no sirve para el modo macros: usa una letra, F1–F12 u otra "
                                 "de la lista.", bad=True)
                return "break"
            if not self._rec_mods:
                self._set_status("Agrega Ctrl, Alt, Shift o Win: una tecla sola dejaría de escribir.", bad=True)
                return "break"
        else:
            unsupported = getattr(self.sender, "unsupported", frozenset())
            if key is None or key not in KEY_CHOICES or key in unsupported:
                self._set_status(f"«{ev.keysym}» no se puede enviar: elige la tecla en la lista.", bad=True)
                return "break"
        combo = join_combo(self._rec_mods, key)
        self._stop_rec()
        if target == "toggle":
            for m, v in self.tog_vars.items():
                v.set(m in self._rec_mods)
            self.tog_key.set(key.upper())
            self._on_row_opts()
            self._set_status(f"Modo macros: {self._combo_text(combo)}")
        else:
            for m, v in self.mod_vars.items():
                v.set(m in self._rec_mods)
            self.key_cb.set(key.upper())
            self._on_combo_change()
            self._set_status(f"Combinación grabada: {self._combo_text(combo)}")
        return "break"

    def _test_keys_delayed(self):
        act = self._current_action()
        if not act:
            return
        self._set_status("Enviaré la combinación en 3 segundos: cambia a la ventana de destino…")
        self.root.after(3000, lambda: (self.engine.run_action(act),
                                       self._set_status(f"Enviado: {self._combo_text(act['combo'])}")))

    # ---- ir a banco
    def _on_bank_go(self):
        try:
            n = int(self.bank_go_var.get())
        except (tk.TclError, ValueError):
            return
        self._store({"type": "bank_go", "bank": max(1, n)})

    # ================================================================ opciones
    def _on_mode(self):
        with self.engine.lock:
            self.cfg["mode"] = self.mode_var.get()
        self._save()
        self._start_backend()

    def _on_opts(self):
        with self.engine.lock:
            self.cfg["block_unassigned"] = self.block_var.get()
            self.cfg["bank_toast"] = self.toast_var.get()
            self.cfg["start_paused"] = self.paused_var.get()
        self._save()

    def _on_autostart(self):
        try:
            sysutil.set_autostart(self.auto_var.get())
        except OSError as e:
            self._set_status(f"No pude cambiar el inicio automático: {e}", bad=True)

    def _learn_device(self):
        if self.backend and self.backend.learns_device:
            self.backend.learn_device(15)
            self._set_status("Presiona cualquier tecla en el NUMPAD que quieres usar (tienes 15 s)…")

    def _capture_key(self):
        self.engine.capture_next = True
        self._set_status("Presiona la tecla del numpad que quieres configurar…")

    # ================================================================ fila de números
    def _toggle_row(self):
        if not self.cfg["row_mode"].get("enabled", True):
            self.nb.select(2)
            self._set_status("La fila de números está desactivada: actívala aquí.")
            return
        self.engine.set_row_mode(not self.engine.row_mode)

    def _paint_row(self):
        rm = self.cfg["row_mode"]
        if not rm.get("enabled", True):
            self.chip_row.configure(text="", bg=C["bg"])
            return
        tog = self._combo_text(rm.get("toggle", ""))
        if self.engine.row_mode:
            self.chip_row.configure(text=f"⌨ Modo macros ACTIVO ({tog})", bg=C["accent"], fg=C["on_accent"])
        else:
            self.chip_row.configure(text=f"⌨ Modo macros apagado ({tog})", bg=C["panel2"], fg=C["muted"])

    def _on_row_opts(self):
        mods = [m for m, v in self.tog_vars.items() if v.get()]
        combo = "+".join(mods + [self.tog_key.get().lower()])
        try:
            parse_toggle(combo)
        except ValueError as e:
            self._set_status(str(e), bad=True)
            return
        self._paint_tog_warn(combo)
        with self.engine.lock:
            self.cfg["row_mode"]["enabled"] = self.row_on_var.get()
            self.cfg["row_mode"]["toggle"] = combo
            if not self.row_on_var.get():
                self.engine.row_mode = False
        self._save()
        self._paint_row()
        self._redraw()
        self._load_editor()
        if self.backend and hasattr(self.backend, "_force_scan"):
            self.backend._force_scan = True
        if self.backend and hasattr(self.backend, "_next_scan"):
            self.backend._next_scan = 0

    def _on_phone_opts(self):
        only = self.only_var.get()
        with self.engine.lock:
            ph = self.cfg.setdefault("phone", {})
            changed = bool(ph.get("only")) != only
            ph["only"] = only
        self._save()
        if changed:
            self._apply_phone_only()
            self._start_backend()
        self._redraw()
        self._load_editor()

    def _apply_phone_only(self):
        """En «solo celular» solo se muestran las teclas virtuales."""
        if self._phone_only():
            self.left_view = "virt"
            if self.selected not in PHONE_IDS:
                self.selected = "m1"
        self._apply_view()

    # ================================================================ activo / pausa
    def _paint_tog_warn(self, combo):
        try:
            mods, _key = parse_combo(combo)
        except ValueError:
            mods = ["?"]
        why = busy_reason(combo)
        if not mods:
            txt = "Ojo: sin Ctrl/Alt/Shift/Win, esa tecla sola activará el modo macros y dejará de escribir."
        elif why:
            txt = f"Ojo: {self._combo_text(combo)} ya se usa para {why} en muchos programas."
        else:
            txt = ""
        self.tog_warn.configure(text=txt)

    def _toggle_active(self):
        new = not self.engine.active
        if not new:
            self.engine.release_all()
        self.engine.set_active(new)

    def _paint_active(self):
        self._schedule_head()
        if self.engine.active:
            self.btn_active.configure(text="●  ACTIVO", bg=C["ok"], fg=C["on_ok"])
        else:
            self.btn_active.configure(text="❚❚  PAUSADO", bg=C["panel2"], fg=C["muted"])
        if self.tray:
            try:
                self.tray.update_menu()
            except Exception:
                pass

    # ================================================================ eventos
    def _poll(self):
        for q in (self.engine.events, self.uiq):
            try:
                while True:
                    ev = q.get_nowait()
                    try:
                        self._handle(ev)
                    except Exception:            # un error no debe congelar la ventana
                        traceback.print_exc()
            except queue.Empty:
                pass
        self.root.after(30, self._poll)

    def _handle(self, ev):
        kind = ev[0]
        if kind == "key":
            _, kid, down = ev
            if down:
                self.flash[kid] = time.monotonic()
                self.root.after(160, lambda k=kid: (self.flash.pop(k, None), self._redraw()))
                self._redraw()
        elif kind == "captured":
            kid = ev[1]
            if kid not in NUMPAD_IDS and kid not in ROW_IDS and kid not in PHONE_IDS \
                    and kid not in self.cfg["extra_keys"]:
                with self.engine.lock:
                    self.cfg["extra_keys"].append(kid)
                self._save()
            self._set_status(f"Seleccionada: {key_label(kid)}")
            self.nb.select(0)
            self._select(kid)
        elif kind == "bank":
            _, idx, name = ev
            self._update_bank_label()
            self._remote_state()
            if self.layer != "global":
                self.layer = idx
                self._refresh_layer_combo()
                self._redraw()
                self._load_editor()
                self._update_assign_label()
            if self.cfg.get("bank_toast", True):
                label = name if name.lower().startswith("banco") else f"Banco {idx + 1} · {name}"
                self._show_toast(label)
        elif kind == "row_mode":
            self._paint_row()
            self._show_toast("Modo macros: ACTIVADO" if ev[1] else "Modo macros: desactivado")
        elif kind == "active":
            self._paint_active()
            self._set_status("Activo: el numpad lanza tus acciones." if ev[1]
                             else "Pausado: el numpad funciona normal.")
        elif kind == "device":
            with self.engine.lock:
                self.cfg["device"] = ev[1]
            self._save()
            self._set_status(f"Numpad elegido: {describe_device(ev[1])}")
            self._update_device_ui()
        elif kind == "device_timeout":
            self._set_status("No se presionó ninguna tecla. Vuelve a intentarlo.", bad=True)
        elif kind == "device_state":
            self._update_device_ui()
        elif kind == "played":
            self._set_status(f"▶ {ev[1]}")
        elif kind == "stopped":
            self._set_status(f"■ {ev[1]}")
        elif kind == "error":
            self._set_status(ev[1], bad=True)
        elif kind == "board_ok":
            self._update_board_ui()
        elif kind == "board_error":
            self._update_board_ui(err=ev[1])
            self._set_status(f"Audio: {ev[1]}", bad=True)
        elif kind == "perm":
            self._after_perms(ev[1], ev[2])
        elif kind == "lufs":
            self._on_lufs(ev[1], ev[2], ev[3])
        elif kind == "lufs_done":
            self._lufs_busy = False
            if getattr(self, "_lufs_dirty", False):
                self._lufs_dirty = False
                self._save()
                self._fill_library()
                self._paint_volume()
            if not self._lufs_q.empty():
                self._queue_loudness()
        elif kind == "vbcable":
            self._after_vbcable(ev[1], ev[2])
        elif kind == "update":
            self._on_update_result(*ev[1:])
        elif kind == "estudio":
            self._after_estudio(*ev[1:])
        elif kind == "remote":
            self._on_remote(ev[1:])
        elif kind == "remote_save":
            self._save()
        elif kind == "tray":
            cmd = ev[1]
            if cmd == "show":
                self._show_window()
            elif cmd == "show_toggle":          # clic en el icono: mostrar u ocultar
                if self.root.state() in ("withdrawn", "iconic") or not self.root.winfo_viewable():
                    self._show_window()
                else:
                    self._to_tray()
            elif cmd == "popup":
                self._tray_popup()
            elif cmd == "help":
                self._show_window()
                self._show_about()
            elif cmd == "toggle":
                self._toggle_active()
            elif cmd == "quit":
                self._quit()

    # ================================================================ celular
    def _on_remote(self, what):
        kind = what[0] if what else ""
        if kind == "keys":                       # se editó una tecla desde el celular
            self._redraw()
            self._load_editor()
            self._update_assign_label()
        elif kind == "library":
            self._fill_library()
            self._queue_loudness()
            self._fill_pick()
        elif kind == "volume" and hasattr(self, "master_var"):
            self.master_var.set(round(float(what[1]) * 100))
            self.master_lbl.configure(text=self._vol_text(round(self.master_var.get())))
            self._save_later()
        if self._dev_refresh_job is None:        # agrupar varios avisos seguidos
            self._dev_refresh_job = self.root.after(150, self._refresh_devices)

    def _refresh_devices(self):
        self._dev_refresh_job = None
        try:
            self.devtab.refresh()
        except Exception:
            pass

    def _send_theme(self):
        if getattr(self, "remote", None):
            self.remote.theme_changed()

    def apply_theme_live(self, theme):
        """Cambia el tema al instante: vuelve a armar la ventana con los colores nuevos sin
        reiniciar el programa (el numpad, el audio y los celulares siguen conectados)."""
        r = self.root
        keep = dict(selected=self.selected, layer=self.layer, view=self.left_view,
                    tab=self.nb.index("current"), status=getattr(self, "_status_last", None),
                    banner=bool(self.update_rel or self.estudio_upd) and self.banner.shown,
                    theme_sel=getattr(self.themestab, "sel", None))
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            r.unbind_all(seq)                    # ruedas de listas que se van a borrar
        for job in ("_fit_job", "_dev_refresh_job"):
            j = getattr(self, job, None)
            if j:
                try:
                    r.after_cancel(j)
                except tk.TclError:
                    pass
                setattr(self, job, None)
        for w in list(r.winfo_children()):
            try:
                w.destroy()
            except tk.TclError:
                pass
        self.toast = None
        self.picker = None
        self._upd_dialog = None
        self.__dict__.pop("_kfonts", None)

        self.theme = theme
        if getattr(self, "art", None) is not None:
            self.art.stop()
        apply_theme(theme["colors"])
        self.art = ThemeArt(self, theme)
        self.art.tweak_colors()
        self._style(first=False)
        xbg.forget()
        self._build()
        self.root.after_idle(lambda: xbg.paint(self.root))       # los widgets nuevos, con el color nuevo
        self.layer = keep["layer"]
        self._refresh_layer_combo()
        self.left_view, self.selected = keep["view"], keep["selected"]
        self._apply_phone_only()
        self._apply_view()
        self._update_device_ui()
        self._update_board_ui()
        self._paint_active()
        self._paint_row()
        try:
            self.devtab.refresh()
        except Exception:
            pass
        self._redraw()
        self._load_editor()
        self._update_bank_label()
        if keep["banner"]:
            self._repaint_banner()
        if keep["status"]:
            self._set_status(*keep["status"])
        try:
            self.nb.select(keep["tab"])
        except tk.TclError:
            pass
        if keep["theme_sel"] is not None:
            self.themestab.sel = keep["theme_sel"]
            self.themestab.refresh()
        self._apply_alpha()
        self._fit_size = None
        self._fit_keys()
        self._send_theme()
        self._repaint_all((120, 600, 1500))

    def _remote_state(self):
        if getattr(self, "remote", None):
            self.remote.state_changed()

    # ================================================================ medidores
    def _tick_meters(self):
        self._paint_test_btn()
        try:
            lv = self.board.levels() if self.board.available()[0] else {}
        except Exception:
            lv = {}
        flag, color = "", C["muted"]
        for key, (meter, val) in self.meters.items():
            data = lv.get(key)
            if data is None:
                meter.clear()
                val.configure(text="—" if key == "mic" and not self._has_vmic() else "")
                continue
            rms, peak, gr, sat = data
            shown = meter.set(peak)
            val.configure(text=f"{shown:.0f} dB" if shown > -59 else "")
            if sat:
                flag, color = "● SATURA: baja el volumen", C["bad"]
            elif gr >= 1.0 and not flag:
                flag, color = f"● Compresor bajando {gr:.0f} dB", C["warn"]
        self.meter_flag.configure(text=flag, fg=color)
        if hasattr(self, "comp_live"):
            gr = max((d[2] for d in lv.values() if d), default=0.0)
            self.comp_live.configure(text=f"Bajando ahora: {gr:.1f} dB" if gr >= 0.5 else "")
        self.root.after(50, self._tick_meters)

    def _has_vmic(self):
        return self.board.kind == "pipewire" or bool(self.cfg["audio"].get("mic_device"))

    # ================================================================ novedades
    def _show_news(self):
        versions = updater.read_changelog(sysutil.resource("CHANGELOG.md"))
        self._news_show = tk.BooleanVar(value=self.cfg["updates"].get("show_news", True))

        def changed():
            with self.engine.lock:
                self.cfg["updates"]["show_news"] = self._news_show.get()
            self._save()
        self.root.deiconify()
        NewsDialog(self.root, versions, __version__, self._news_show, changed)

    def _startup_news(self):
        """La primera vez que se abre una versión nueva, muestra sus novedades."""
        upd = self.cfg["updates"]
        seen = upd.get("last_seen", "")
        if seen == __version__:
            return
        if self.root.state() == "withdrawn" and not self.first_run:
            self.root.after(5000, self._startup_news)    # minimizada: mostrarlas al abrir la ventana
            return
        with self.engine.lock:
            upd["last_seen"] = __version__
        self._save()
        if self.first_run or not upd.get("show_news", True):
            return
        if seen and not updater.newer(__version__, seen):
            return
        self._show_news()

    # ================================================================ actualizaciones
    def _on_upd_opts(self):
        with self.engine.lock:
            self.cfg["updates"]["auto"] = self.upd_auto.get()
            self.cfg["updates"]["beta"] = self.upd_beta.get()
        self._save()

    def _upd_text(self, text):
        """Texto de actualizaciones en «Creador y soporte» (si esa ventana está abierta)."""
        lbl = getattr(self, "upd_lbl", None)
        try:
            if lbl is not None and lbl.winfo_exists():
                lbl.configure(text=text)
        except tk.TclError:
            pass

    def _upd_btn(self, enabled):
        btn = getattr(self, "btn_check", None)
        try:
            if btn is not None and btn.winfo_exists():
                btn.state(["!disabled"] if enabled else ["disabled"])
        except tk.TclError:
            pass

    def _check_updates(self, manual=False):
        upd = self.cfg["updates"]
        if not manual and not updater.due(upd):
            return
        if manual:
            self._upd_text("Buscando…")
            self._upd_btn(False)
        snapshot = dict(upd)

        def job():
            try:
                rel, est_rel, est_ver = updater.check_all(snapshot, __version__, manual=manual)
                self.uiq.put(("update", manual, rel, None, snapshot.get("last_check", 0), est_rel, est_ver))
            except Exception as e:
                self.uiq.put(("update", manual, None, str(e), 0))
        threading.Thread(target=job, daemon=True).start()

    def _on_update_result(self, manual, rel, err, checked_at, est_rel=None, est_ver=None):
        self._upd_btn(True)
        if checked_at:
            with self.engine.lock:
                self.cfg["updates"]["last_check"] = checked_at
            self._save()
        if err:
            self._upd_text("No se pudo comprobar (sin conexión con GitHub). Se volverá a intentar.")
            if manual:
                self._set_status("No pude consultar si hay versiones nuevas (¿hay internet?).", bad=True)
            return
        stamp = time.strftime("%H:%M")
        self.estudio_upd = (est_rel, est_ver) if est_ver else None
        est_txt = f" · Estudio de Temas: versión nueva {est_ver}" if est_ver else ""
        if not rel:
            if self.estudio_upd:
                self._upd_text(f"Numpad Macros está al día{est_txt}")
                self._repaint_banner()
                if manual:
                    self._open_update()
                return
            self._upd_text(f"Estás al día · comprobado a las {stamp}")
            if manual:
                self._set_status("Tienes la última versión.")
            return
        self.update_rel = rel
        self._upd_text(f"Hay una versión nueva: {rel.version}{est_txt}")
        self._paint_banner(rel)
        if manual:
            self._open_update()

    def _repaint_banner(self):
        """Vuelve a mostrar el aviso de la cabecera (Numpad Macros primero; si no, el Estudio)."""
        if self.update_rel:
            self._paint_banner(self.update_rel)
        elif self.estudio_upd:
            self.banner_lbl.configure(text=f"Hay una nueva versión del Estudio de Temas: {self.estudio_upd[1]}")
            self.banner_later.grid()
            self.banner.grid()

    def _paint_banner(self, rel):
        extra = " · importante" if rel.important else (" · beta" if rel.prerelease else "")
        self.banner_lbl.configure(text=f"Hay una nueva versión: {rel.version}{extra}   (tienes {__version__})")
        self.banner.grid()
        if rel.important:
            self.banner_later.grid_remove()

    def _hide_banner(self):
        self.banner.grid_remove()
        self._set_status("Te lo recordaré la próxima vez que abras la app.")

    def _open_update(self):
        rel = self.update_rel
        if not rel:
            if self.estudio_upd:
                est_rel, ver = self.estudio_upd
                have = updater.estudio_installed()
                if messagebox.askyesno("Estudio de Temas",
                                       f"Hay una versión nueva del Estudio de Temas: {ver}"
                                       + (f" (tienes {have[1]})" if have and have[1] else "")
                                       + ".\n\n¿Instalarla ahora? Si el Estudio está abierto, se cerrará.",
                                       parent=self.root):
                    self._install_estudio(est_rel, ver)
            return
        if self._upd_dialog is not None and self._upd_dialog.winfo_exists():
            self._upd_dialog.lift()
            return
        self.root.deiconify()
        self._upd_dialog = UpdateDialog(self.root, rel, updater.install_kind(), self._skip_version,
                                        self._install_update)

    # ---------------------------------------------------------------- Estudio de Temas
    def _on_estudio_opt(self):
        on = self.upd_estudio.get()
        with self.engine.lock:
            self.cfg["updates"]["estudio"] = on
        self._save()
        if not on:
            self.estudio_upd = None
            if not self.update_rel:
                self.banner.grid_remove()
            return
        if updater.estudio_installed() is None:
            if messagebox.askyesno("Estudio de Temas",
                                   "El Estudio de Temas (el editor para crear tus propios temas) no está "
                                   "instalado.\n\n¿Instalarlo ahora?", parent=self.root):
                self._install_estudio()
        else:
            self._check_updates(manual=True)

    def open_estudio(self):
        """Abre el Estudio de Temas. Si no está instalado, sugiere instalarlo (lo usan las
        funciones de la app que necesitan el editor de temas)."""
        have = updater.estudio_installed()
        if have is None:
            if messagebox.askyesno("Estudio de Temas",
                                   "Para crear o editar temas se usa el Estudio de Temas, un programa "
                                   "aparte que no está instalado en este equipo.\n\n"
                                   "¿Instalarlo ahora? (también se buscarán sus actualizaciones)",
                                   parent=self.root):
                self.upd_estudio.set(True)
                with self.engine.lock:
                    self.cfg["updates"]["estudio"] = True
                self._save()
                self._install_estudio(open_after=True)
            return
        exe = have[0]
        try:
            if IS_WIN:
                os.startfile(exe)
            elif IS_MAC:
                import subprocess
                subprocess.Popen(["open", exe])
            else:
                import subprocess
                subprocess.Popen([exe], env=updater.relaunch_env(), start_new_session=True, close_fds=True)
            self._set_status("Abriendo el Estudio de Temas…")
        except Exception as e:
            self._set_status(f"No pude abrir el Estudio de Temas: {e}", bad=True)

    def _install_estudio(self, rel=None, version=None, open_after=False):
        """Descarga e instala (o actualiza) el Estudio desde la Release de GitHub, en un hilo."""
        if not updater.estudio_can_install():
            self._set_status("Descarga el Estudio de Temas desde la página de versiones.")
            self._open(updater.RELEASES_URL)
            return
        if self._estudio_busy:
            return
        self._estudio_busy = True
        self._set_status("Descargando el Estudio de Temas…")
        beta = bool(self.cfg["updates"].get("beta"))

        def progress(done, total):
            if total:
                self.uiq.put(("estudio", None, f"Descargando el Estudio de Temas… {done * 100 // total} %", False))

        def job():
            try:
                r, v = rel, version
                if r is None:
                    r = updater.fetch_latest_estudio(beta)
                    v = updater.estudio_version(r)
                    if not r:
                        raise updater.UpdateError("No encontré ninguna versión publicada del Estudio de Temas.")
                    if updater.ESTUDIO_ASSET[updater.platform_key()] not in r.assets:
                        raise updater.UpdateError("La última versión del Estudio de Temas no trae archivo para tu sistema.")
                updater.install_estudio(r, v, progress)
                self.uiq.put(("estudio", True, f"Estudio de Temas {v} instalado.".replace("  ", " "), open_after))
            except Exception as e:
                self.uiq.put(("estudio", False, f"No se pudo instalar el Estudio de Temas: {e}", False))
        threading.Thread(target=job, daemon=True).start()

    def _after_estudio(self, ok, msg, open_after):
        if ok is None:                       # progreso de la descarga
            self._set_status(msg)
            return
        self._estudio_busy = False
        self._set_status(msg, bad=not ok)
        if not ok:
            return
        self.estudio_upd = None
        if not self.update_rel:
            self.banner.grid_remove()
        self._upd_text(msg)
        if open_after and updater.estudio_installed() is not None:
            self.open_estudio()

    def _skip_version(self, version):
        with self.engine.lock:
            self.cfg["updates"]["skip"] = version
        self._save()
        self.banner.grid_remove()
        self._upd_text(f"Omitiste la versión {version}")
        self._set_status(f"No volveré a avisar de la versión {version}.")

    def _install_update(self, path, dialog):
        kind = updater.install_kind()
        try:
            if kind == "installer":
                updater.install_windows(path)
                self._quit()                 # el instalador vuelve a abrir la app
            elif kind == "binary":
                self.relaunch = updater.install_linux(path)
                self._quit()
        except Exception as e:
            dialog.fail(str(e))

    def _set_status(self, msg, bad=False):
        self._status_last = (msg, bad)
        self.status.configure(text=msg, fg=C["bad"] if bad else C["muted"])

    def _show_toast(self, text):
        if self.toast is not None:
            try:
                self.toast.destroy()
            except tk.TclError:
                pass
        t = tk.Toplevel(self.root)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        try:
            t.attributes("-alpha", 0.93)
        except tk.TclError:
            pass
        f = tk.Frame(t, bg=C["panel"], highlightbackground=C["accent"], highlightthickness=2)
        f.pack()
        tk.Label(f, text=text, bg=C["panel"], fg=C["text"], font=(FONT, BASE + 6, "bold"),
                 padx=26, pady=12).pack()
        t.update_idletasks()
        sw, sh = t.winfo_screenwidth(), t.winfo_screenheight()
        w, h = t.winfo_width(), t.winfo_height()
        t.geometry(f"+{(sw - w) // 2}+{sh - h - 110}")
        self.toast = t
        self.root.after(1400, lambda: t.destroy() if t.winfo_exists() else None)

    # ================================================================ guardar / salir
    def _write_cfg(self):
        config.save(self.cfg)

    def _save(self):
        self._save_job = None
        try:
            with self.engine.lock:
                config.save(self.cfg)
        except OSError as e:
            self._set_status(f"No pude guardar la configuración: {e}", bad=True)
        self._remote_state()          # los celulares ven el cambio al instante

    def _tray_menu(self):
        """Opciones del icono de la bandeja: [(texto, comando)] o None = separador."""
        return [
            ("Mostrar ventana", "show"),
            ("Pausar" if self.engine.active else "Reanudar", "toggle"),
            None,
            ("Ayuda y soporte", "help"),
            None,
            ("Salir de Numpad Macros", "quit"),
        ]

    def _setup_tray(self):
        if IS_MAC:          # en macOS el icono de bandeja necesita el hilo principal (lo usa tkinter)
            return
        try:
            from PIL import Image, ImageDraw
        except Exception:
            return
        path = sysutil.resource("assets", "icon.png")
        if os.path.isfile(path):
            img = Image.open(path).convert("RGBA").resize((64, 64))
        else:
            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            ImageDraw.Draw(img).rounded_rectangle((4, 4, 60, 60), 12, fill=(242, 163, 58, 255))
        put = self.uiq.put

        # Linux: menú nativo del escritorio (KDE, GNOME con AppIndicator, XFCE, Cinnamon…)
        if sys.platform.startswith("linux"):
            try:
                from . import tray_sni
                tray = tray_sni.SniTray(
                    "NumpadMacros", "Numpad Macros", img,
                    lambda: [None if e is None else (e[0], lambda c=e[1]: put(("tray", c)))
                             for e in self._tray_menu()],
                    on_activate=lambda: put(("tray", "show_toggle")),
                    on_secondary=lambda: put(("tray", "toggle")))
                if tray.start():
                    self.tray = tray
                    return
            except Exception:
                pass
        try:
            import pystray
        except Exception:
            return

        def item(text, cmd, **kw):
            return pystray.MenuItem(text, lambda: put(("tray", cmd)), **kw)
        menu = pystray.Menu(
            item("Mostrar ventana", "show", default=True),
            pystray.MenuItem(lambda _i: "Pausar" if self.engine.active else "Reanudar",
                             lambda: put(("tray", "toggle"))),
            pystray.Menu.SEPARATOR,
            item("Ayuda y soporte", "help"),
            pystray.Menu.SEPARATOR,
            item("Salir de Numpad Macros", "quit"),
        )
        try:
            tray = pystray.Icon("NumpadMacros", img, "Numpad Macros", menu)
            if not getattr(tray, "HAS_MENU", True):
                # bandeja sin menú (pystray en modo xorg): el clic abre nuestro propio menú
                tray = pystray.Icon("NumpadMacros", img, "Numpad Macros", pystray.Menu(
                    item("Opciones", "popup", default=True)))
            tray.run_detached()
            self.tray = tray
        except Exception:
            self.tray = None

    def _tray_popup(self):
        """Menú de la bandeja dibujado por la app (cuando el escritorio no muestra uno)."""
        m = tk.Menu(self.root, tearoff=0, bg=C["panel"], fg=C["text"],
                    activebackground=C["accent"], activeforeground=C["on_accent"])
        for e in self._tray_menu():
            if e is None:
                m.add_separator()
            else:
                m.add_command(label=e[0], command=lambda c=e[1]: self.uiq.put(("tray", c)))
        x, y = self.root.winfo_pointerxy()
        try:
            m.tk_popup(x, y)
        finally:
            m.grab_release()

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _on_close(self):
        if not self.tray:
            return self._quit()
        ui = self.cfg.setdefault("ui", {})
        how = ui.get("close", "ask")
        if how == "quit":
            return self._quit()
        if how == "tray":
            return self._to_tray()
        self._ask_close()

    def _to_tray(self):
        self.root.withdraw()
        self._set_status("Sigue funcionando en la bandeja del sistema.")

    def _ask_close(self):
        """Primera vez que se cierra la ventana: ¿salir o dejarla en la bandeja?"""
        w = getattr(self, "close_win", None)
        if w is not None and w.winfo_exists():
            w.lift()
            return
        w = tk.Toplevel(self.root)
        self.close_win = w
        w.title("Cerrar Numpad Macros")
        w.configure(bg=C["panel"])
        w.transient(self.root)
        w.resizable(False, False)
        body = ttk.Frame(w, style="Panel.TFrame", padding=22)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="¿Qué hago al cerrar la ventana?", style="H.TLabel").pack(anchor="w")
        ttk.Label(body, style="Muted.TLabel", wraplength=400, justify="left", text=(
            "En la bandeja, tus teclas siguen funcionando y la ventana vuelve con el icono de "
            "Numpad Macros (junto al reloj). Al salir, el programa se cierra por completo.")
        ).pack(anchor="w", pady=(6, 12))
        remember = tk.BooleanVar(value=False)
        ttk.Checkbutton(body, text="Recordar mi elección", variable=remember).pack(anchor="w")
        ttk.Label(body, style="Muted.TLabel", text="Puedes cambiarlo en «Numpad y opciones».").pack(
            anchor="w", pady=(2, 14))
        row = ttk.Frame(body, style="Panel.TFrame")
        row.pack(fill="x")

        def choose(how):
            if remember.get():
                self.cfg.setdefault("ui", {})["close"] = how
                if hasattr(self, "close_var"):
                    self.close_var.set(how)
                self._save()
            w.destroy()
            if how == "quit":
                self._quit()
            else:
                self._to_tray()
        ttk.Button(row, text="Salir del programa", command=lambda: choose("quit")).pack(side="right")
        ttk.Button(row, text="Dejar en la bandeja", style="Accent.TButton",
                   command=lambda: choose("tray")).pack(side="right", padx=(0, 8))
        w.protocol("WM_DELETE_WINDOW", w.destroy)          # cerrar este aviso = no hacer nada
        w.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - w.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - w.winfo_height()) // 3
        w.geometry(f"+{max(0, x)}+{max(0, y)}")
        w.grab_set()

    def _on_close_opt(self):
        self.cfg.setdefault("ui", {})["close"] = self.close_var.get()
        self._save()

    def _quit(self):
        try:
            try:
                self.remote.stop()
            except Exception:
                pass
            if self.backend:
                self.backend.stop()
            self.engine.stop()
            self.board.close()
            self._save()
        finally:
            if self.tray:
                try:
                    self.tray.stop()
                except Exception:
                    pass
            self.root.destroy()


def main():
    minimized = "--minimizado" in sys.argv
    ok = sysutil.single_instance()
    if not ok and "--tras-actualizar" in sys.argv:
        for _ in range(40):                 # la versión anterior se está cerrando
            time.sleep(0.25)
            if sysutil.single_instance():
                ok = True
                break
    if not ok:
        r = tk.Tk()
        r.withdraw()
        messagebox.showinfo("Numpad Macros", "Numpad Macros ya está abierto.")
        return
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)   # texto nítido en pantallas HiDPI
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("NumpadMacros")
        except Exception:
            pass
    if IS_LINUX and getattr(sys, "frozen", False):
        # menú de aplicaciones + icono propio en la barra de tareas (en segundo plano)
        def integrate():
            try:
                from . import desktop_linux
                desktop_linux.install("numpad-macros", "Numpad Macros",
                                      "Numpad como botonera de sonidos y atajos", sys.executable,
                                      sysutil.resource("assets", "icon.png"), "NumpadMacros", env=clean_env())
            except Exception:
                pass
        threading.Thread(target=integrate, daemon=True).start()
    root = tk.Tk(className="NumpadMacros")
    app = App(root, start_minimized=minimized)
    root.mainloop()
    if app.relaunch:                        # versión recién instalada (Linux)
        import subprocess
        sysutil.release_instance()
        cmd = app.relaunch if isinstance(app.relaunch, list) else [app.relaunch]
        subprocess.Popen(cmd + ["--tras-actualizar"], env=updater.relaunch_env(),
                         start_new_session=True, close_fds=True)
