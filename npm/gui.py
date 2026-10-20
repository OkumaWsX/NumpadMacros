# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Ventana principal de Numpad Macros (tkinter, Windows / Linux / macOS)."""
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import __version__, about, capture, config, library, sysutil, updater
from . import loudness as ld
from .capture import PLATFORM, BackendError, describe_device
from .engine import Engine
from .dialogs import NewsDialog, UpdateDialog
from .devices_tab import DevicesTab
from .remote import RemoteServer
from .keys import (PHONE_COUNTS, PHONE_IDS, phone_count, phone_layout, KEY_CHOICES, MODIFIER_KEYSYMS, MODIFIERS, NUMPAD_IDS, NUMPAD_LAYOUT, ROW_IDS,
                   ROW_LAYOUT, TOGGLE_CHOICES, busy_reason, combo_text, join_combo, key_label,
                   keysym_to_key, parse_combo, parse_toggle)
from .senders import make_sender
from .soundboard import AUDIO_EXT, PLAY_MODES, clean_env, make_soundboard, title_of
from .widgets import CompCurve, Meter

from .theme import BASE, C, FONT, IS_LINUX, IS_MAC, IS_WIN, MOD_LABEL, OS_NAME

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


class FlatButton(tk.Label):
    """Botón de color plano. tk.Button ignora el color de fondo en macOS."""

    def __init__(self, master, command=None, **kw):
        kw.setdefault("cursor", "hand2")
        super().__init__(master, **kw)
        self._cmd = command
        self.bind("<Button-1>", lambda e: self._cmd and self._cmd())


def make_listbox(parent, height):
    box = ttk.Frame(parent, style="Panel.TFrame")
    box.columnconfigure(0, weight=1)
    box.rowconfigure(0, weight=1)
    lb = tk.Listbox(box, bg=C["panel2"], fg=C["text"], selectbackground=C["accent_dim"],
                    selectforeground="#fff", highlightthickness=0, bd=0, activestyle="none",
                    font=(FONT, BASE), height=height, exportselection=False)
    lb.grid(row=0, column=0, sticky="nsew")
    sb = ttk.Scrollbar(box, orient="vertical", command=lb.yview)
    sb.grid(row=0, column=1, sticky="ns")
    lb.configure(yscrollcommand=sb.set)
    return box, lb


def scroll_frame(parent):
    """Marco con barra de desplazamiento vertical (para pestañas con muchas opciones)."""
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(0, weight=1)
    cv = tk.Canvas(parent, bg=C["panel"], highlightthickness=0, bd=0)
    sb = ttk.Scrollbar(parent, orient="vertical", command=cv.yview)
    inner = ttk.Frame(cv, style="Panel.TFrame")
    win = cv.create_window(0, 0, window=inner, anchor="nw")
    cv.configure(yscrollcommand=sb.set)
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


class App:
    UNIT, GAP = 60, 7
    RUNIT, RGAP = 40, 6         # teclas de la fila de números

    def __init__(self, root: tk.Tk, start_minimized=False):
        self.root = root
        self.first_run = not os.path.exists(config.config_path())
        self.cfg = config.load()
        self.uiq: queue.Queue = queue.Queue()     # mensajes de otros hilos -> GUI
        self.sender, self.sender_err = make_sender()
        self.board = make_soundboard(self.cfg["audio"])
        self.engine = Engine(self.cfg, self.sender, on_save=self._write_cfg, soundboard=self.board)
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
        self.root.after(1200, self._startup_news)
        self.root.after(3000, lambda: self._check_updates(manual=False))

    # ================================================================ estilo
    def _style(self):
        r = self.root
        r.title("Numpad Macros")
        r.configure(bg=C["bg"])
        r.geometry("1120x820")
        r.minsize(1020, 760)
        s = ttk.Style(r)
        s.theme_use("clam")
        s.configure(".", background=C["bg"], foreground=C["text"], fieldbackground=C["panel2"],
                    bordercolor=C["line"], lightcolor=C["line"], darkcolor=C["line"],
                    font=(FONT, BASE))
        s.configure("Panel.TFrame", background=C["panel"])
        s.configure("TLabel", background=C["bg"])
        s.configure("Panel.TLabel", background=C["panel"])
        s.configure("Muted.TLabel", background=C["panel"], foreground=C["muted"], font=(FONT, BASE - 1))
        s.configure("Warn.TLabel", background=C["panel"], foreground=C["warn"], font=(FONT, BASE - 1))
        s.configure("H.TLabel", background=C["panel"], font=(FONT, BASE + 3, "bold"))
        s.configure("Title.TLabel", background=C["bg"], font=(FONT, BASE + 6, "bold"))
        s.configure("TButton", background=C["panel2"], foreground=C["text"], padding=(10, 5),
                    borderwidth=1, focusthickness=0)
        s.map("TButton", background=[("active", C["line"]), ("disabled", C["panel"])],
              foreground=[("disabled", C["muted"])])
        s.configure("Accent.TButton", background=C["accent"], foreground="#1a1306",
                    font=(FONT, BASE, "bold"))
        s.map("Accent.TButton", background=[("active", "#ffb855"), ("disabled", C["panel2"])],
              foreground=[("disabled", C["muted"])])
        for w in ("TCheckbutton", "TRadiobutton"):
            s.configure(w, background=C["panel"], foreground=C["text"])
            s.map(w, background=[("active", C["panel"])],
                  indicatorcolor=[("selected", C["accent"]), ("!selected", C["panel2"])])
        s.configure("TCombobox", arrowcolor=C["text"], foreground=C["text"],
                    selectbackground=C["panel2"], selectforeground=C["text"])
        s.map("TCombobox", fieldbackground=[("readonly", C["panel2"])],
              foreground=[("readonly", C["text"])])
        r.option_add("*TCombobox*Listbox.background", C["panel2"])
        r.option_add("*TCombobox*Listbox.foreground", C["text"])
        r.option_add("*TCombobox*Listbox.selectBackground", C["accent_dim"])
        s.configure("TNotebook", background=C["bg"], borderwidth=0)
        s.configure("TNotebook.Tab", background=C["bg"], foreground=C["muted"],
                    padding=(16, 7), borderwidth=0, font=(FONT, BASE, "bold"))
        s.map("TNotebook.Tab", background=[("selected", C["panel"])],
              foreground=[("selected", C["text"])])
        s.configure("TEntry", foreground=C["text"], insertcolor=C["text"])
        s.configure("TSpinbox", foreground=C["text"], arrowcolor=C["text"])
        s.configure("Horizontal.TScale", background=C["panel"], troughcolor=C["panel2"])
        s.configure("Horizontal.TProgressbar", background=C["accent"], troughcolor=C["panel2"],
                    bordercolor=C["panel2"], lightcolor=C["accent"], darkcolor=C["accent"])
        s.configure("Banner.TFrame", background="#3a2c14")
        s.configure("Card.TFrame", background=C["panel2"])
        s.configure("Card.TLabel", background=C["panel2"])
        s.configure("CardMuted.TLabel", background=C["panel2"], foreground=C["muted"], font=(FONT, BASE - 1))
        s.configure("Card.TCheckbutton", background=C["panel2"], foreground=C["text"])
        s.map("Card.TCheckbutton", background=[("active", C["panel2"])],
              indicatorcolor=[("selected", C["accent"]), ("!selected", C["panel"])])
        s.configure("Card.TRadiobutton", background=C["panel2"], foreground=C["text"])
        s.map("Card.TRadiobutton", background=[("active", C["panel2"])],
              indicatorcolor=[("selected", C["accent"]), ("!selected", C["panel"])])
        s.configure("Vertical.TScrollbar", background=C["line"], troughcolor=C["panel2"],
                    arrowcolor=C["muted"], bordercolor=C["panel2"])
        s.map("Vertical.TScrollbar", background=[("active", C["muted"])])

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
        r.columnconfigure(0, weight=0)
        r.columnconfigure(1, weight=1)
        r.rowconfigure(1, weight=1)

        # ---------- cabecera
        head = ttk.Frame(r)
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(14, 8))
        head.columnconfigure(1, weight=1)
        ttk.Label(head, text="Numpad Macros", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        chips = ttk.Frame(head)
        chips.grid(row=1, column=0, columnspan=4, sticky="w", pady=(4, 0))
        self.chip_dev = tk.Label(chips, bg=C["bg"], fg=C["muted"], font=(FONT, BASE - 1))
        self.chip_dev.pack(side="left", padx=(0, 14))
        self.chip_board = tk.Label(chips, bg=C["bg"], fg=C["muted"], font=(FONT, BASE - 1))
        self.chip_board.pack(side="left", padx=(0, 14))
        self.chip_row = FlatButton(chips, command=self._toggle_row, bg=C["bg"],
                                   font=(FONT, BASE - 1, "bold"), padx=8, pady=1)
        self.chip_row.pack(side="left")
        # aviso del compresor o de saturación (junto a los demás indicadores)
        self.meter_flag = tk.Label(chips, bg=C["bg"], font=(FONT, BASE - 1, "bold"))
        self.meter_flag.pack(side="left", padx=(14, 0))

        bank_box = ttk.Frame(head)
        bank_box.grid(row=0, column=2, sticky="e", padx=(0, 14))
        ttk.Button(bank_box, text="◀", width=3,
                   command=lambda: self.engine.set_bank(self.engine.bank - 1)).pack(side="left")
        self.bank_lbl = tk.Label(bank_box, bg=C["bg"], fg=C["text"], font=(FONT, BASE + 1, "bold"),
                                 width=18)
        self.bank_lbl.pack(side="left", padx=6)
        ttk.Button(bank_box, text="▶", width=3,
                   command=lambda: self.engine.set_bank(self.engine.bank + 1)).pack(side="left")

        self.btn_active = FlatButton(head, command=self._toggle_active,
                                     font=(FONT, BASE, "bold"), padx=16, pady=6)
        self.btn_active.grid(row=0, column=3, sticky="e")
        self._paint_active()
        self._paint_row()

        # medidores de volumen en tiempo real
        mt = ttk.Frame(head)
        mt.grid(row=0, column=1, sticky="e", padx=(10, 22))
        self.meters = {}
        for i, (key, name) in enumerate((("spk", "Audífonos"), ("mic", "Micrófono virtual"))):
            tk.Label(mt, text=name, bg=C["bg"], fg=C["muted"], font=(FONT, BASE - 2), anchor="e").grid(
                row=i, column=0, sticky="e", padx=(0, 6))
            m = Meter(mt, width=190, height=9)
            m.grid(row=i, column=1, pady=1)
            val = tk.Label(mt, text="—", bg=C["bg"], fg=C["muted"], font=(FONT, BASE - 2), width=7, anchor="w")
            val.grid(row=i, column=2, sticky="w", padx=(6, 0))
            self.meters[key] = (m, val)

        # aviso de versión nueva (oculto hasta que haya una)
        self.banner = tk.Frame(head, bg="#3a2c14", highlightbackground=C["accent_dim"], highlightthickness=1)
        self.banner.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        self.banner.columnconfigure(1, weight=1)
        self.banner_icon = tk.Label(self.banner, text="⬇", bg="#3a2c14", fg=C["accent"], font=(FONT, BASE + 3, "bold"))
        self.banner_icon.grid(row=0, column=0, padx=(12, 8), pady=6)
        self.banner_lbl = tk.Label(self.banner, bg="#3a2c14", fg=C["text"], font=(FONT, BASE, "bold"), anchor="w")
        self.banner_lbl.grid(row=0, column=1, sticky="ew")
        self.banner_btn = FlatButton(self.banner, text="Actualizar", command=self._open_update,
                                     bg=C["accent"], fg="#1a1306", font=(FONT, BASE - 1, "bold"), padx=14, pady=4)
        self.banner_btn.grid(row=0, column=2, padx=6, pady=6)
        self.banner_later = FlatButton(self.banner, text="Más tarde", command=self._hide_banner,
                                       bg="#3a2c14", fg=C["text"], font=(FONT, BASE - 1), padx=10, pady=4)
        self.banner_later.grid(row=0, column=3, padx=(0, 10))
        self.banner.grid_remove()

        # ---------- izquierda: numpad
        left = ttk.Frame(r, style="Panel.TFrame", padding=16)
        left.grid(row=1, column=0, sticky="ns", padx=(18, 8), pady=(0, 8))

        ttk.Label(left, text="Capa que estás editando", style="Muted.TLabel").pack(anchor="w")
        lrow = ttk.Frame(left, style="Panel.TFrame")
        lrow.pack(fill="x", pady=(2, 10))
        self.layer_cb = ttk.Combobox(lrow, state="readonly", width=24)
        self.layer_cb.pack(side="left")
        self.layer_cb.bind("<<ComboboxSelected>>", self._on_layer_pick)
        ttk.Button(lrow, text="＋", width=3, command=self._add_bank).pack(side="left", padx=(6, 0))
        ttk.Button(lrow, text="✎", width=3, command=self._rename_bank).pack(side="left", padx=(4, 0))
        ttk.Button(lrow, text="✕", width=3, command=self._delete_bank).pack(side="left", padx=(4, 0))

        w = 4 * self.UNIT + 3 * self.GAP
        h = 5 * self.UNIT + 4 * self.GAP
        self.canvas = tk.Canvas(left, width=w, height=h, bg=C["panel"], highlightthickness=0)
        self.canvas.pack(pady=(4, 8))
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        # teclas virtuales y fila de números comparten el mismo espacio (se elige con los botones)
        self.small_group = "cel"
        self.cel_page = 0
        sg = ttk.Frame(left, style="Panel.TFrame")
        sg.pack(fill="x")
        self.sg_frame = sg
        self.sg_btns = {}
        for gid, text in (("cel", "Virtuales"), ("row", "Fila 1–0")):
            b = FlatButton(sg, text=text, command=lambda g=gid: self._set_group(g),
                           font=(FONT, BASE - 1, "bold"), padx=8, pady=2)
            b.pack(side="left", padx=(0, 5))
            self.sg_btns[gid] = b
        self.pg_next = FlatButton(sg, text="▶", command=lambda: self._cel_page_step(1), bg=C["panel2"],
                                  fg=C["text"], font=(FONT, BASE - 1, "bold"), padx=6, pady=2)
        self.pg_lbl = tk.Label(sg, bg=C["panel"], fg=C["muted"], font=(FONT, BASE - 2))
        self.pg_prev = FlatButton(sg, text="◀", command=lambda: self._cel_page_step(-1), bg=C["panel2"],
                                  fg=C["text"], font=(FONT, BASE - 1, "bold"), padx=6, pady=2)
        self.row_title = ttk.Label(left, style="Muted.TLabel", wraplength=4 * self.UNIT + 3 * self.GAP)
        self.row_title.pack(anchor="w", pady=(4, 0))
        rw = 6 * self.RUNIT + 5 * self.RGAP
        rh = 2 * self.RUNIT + self.RGAP
        self.row_canvas = tk.Canvas(left, width=rw, height=rh, bg=C["panel"], highlightthickness=0)
        self.row_canvas.pack(pady=(4, 8))
        self.row_canvas.bind("<Button-1>", self._on_row_click)

        self.extra_frame = ttk.Frame(left, style="Panel.TFrame")
        self.extra_frame.pack(fill="x")
        self.btn_capture = ttk.Button(left, text="Capturar tecla física", command=self._capture_key)
        self.btn_capture.pack(fill="x", pady=(6, 0))

        # ---------- derecha: pestañas
        nb = ttk.Notebook(r)
        nb.grid(row=1, column=1, sticky="nsew", padx=(8, 18), pady=(0, 8))
        self.nb = nb
        self.tab_key = ttk.Frame(nb, style="Panel.TFrame", padding=18)
        self.tab_lib = ttk.Frame(nb, style="Panel.TFrame", padding=18)
        self.tab_cap = ttk.Frame(nb, style="Panel.TFrame", padding=18)
        self.tab_audio = ttk.Frame(nb, style="Panel.TFrame", padding=18)
        self.tab_about = ttk.Frame(nb, style="Panel.TFrame", padding=24)
        self.tab_dev = ttk.Frame(nb, style="Panel.TFrame", padding=18)
        nb.add(self.tab_key, text="Tecla")
        nb.add(self.tab_lib, text="Sonidos")
        nb.add(self.tab_cap, text="Numpad y opciones")
        nb.add(self.tab_audio, text="Audio")
        nb.add(self.tab_dev, text="Celular")
        nb.add(self.tab_about, text="Creador")
        nb.bind("<<NotebookTabChanged>>", lambda e: self._on_tab())
        self._build_editor()
        self._build_library_tab()
        self._build_capture_tab()
        self._build_audio_tab()
        self.devtab = DevicesTab(self.tab_dev, self)
        self._build_about_tab()

        # ---------- barra de estado
        foot = ttk.Frame(r)
        foot.grid(row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 10))
        foot.columnconfigure(0, weight=1)
        self.status = tk.Label(foot, anchor="w", bg=C["bg"], fg=C["muted"], font=(FONT, BASE - 1))
        self.status.grid(row=0, column=0, sticky="ew")
        FlatButton(foot, text=f"v{__version__} · Novedades", command=self._show_news,
                   bg=C["bg"], fg=C["muted"], font=(FONT, BASE - 1), padx=10, pady=4,
                   highlightbackground=C["line"], highlightthickness=1).grid(row=0, column=1, padx=(10, 0))
        FlatButton(foot, text=f"Creado por {about.CREATOR} · Soporte", command=self._show_about,
                   bg=C["panel2"], fg=C["text"], font=(FONT, BASE - 1), padx=12, pady=4).grid(
            row=0, column=2, padx=(6, 6))
        FlatButton(foot, text="♥ Donar", command=lambda: self._open(about.DONATE),
                   bg=C["accent"], fg="#1a1306", font=(FONT, BASE - 1, "bold"), padx=12, pady=4).grid(
            row=0, column=3)
        self._refresh_layer_combo()

    # ---------------------------------------------------------------- editor
    def _build_editor(self):
        t = self.tab_key
        t.columnconfigure(0, weight=1)
        self.ed_title = ttk.Label(t, style="H.TLabel")
        self.ed_title.grid(row=0, column=0, sticky="w")
        self.ed_note = ttk.Label(t, style="Muted.TLabel", wraplength=500, justify="left")
        self.ed_note.grid(row=1, column=0, sticky="w", pady=(2, 10))

        row = ttk.Frame(t, style="Panel.TFrame")
        row.grid(row=2, column=0, sticky="w")
        ttk.Label(row, text="Acción", style="Panel.TLabel").pack(side="left", padx=(0, 10))
        self.type_cb = ttk.Combobox(row, state="readonly", width=34,
                                    values=[lbl for _, lbl in ACTION_TYPES])
        self.type_cb.pack(side="left")
        self.type_cb.bind("<<ComboboxSelected>>", self._on_type_pick)

        self.sub = ttk.Frame(t, style="Panel.TFrame")
        self.sub.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
        t.rowconfigure(3, weight=1)

    def _clear_sub(self):
        for wdg in self.sub.winfo_children():
            wdg.destroy()
        self.pick_lb = None

    def _build_file_sub(self, act):
        f = self.sub
        f.columnconfigure(0, weight=1)
        f.rowconfigure(2, weight=1)
        top = ttk.Frame(f, style="Panel.TFrame")
        top.grid(row=0, column=0, sticky="ew")
        self.file_lbl = ttk.Label(top, style="Panel.TLabel", font=(FONT, BASE + 1, "bold"))
        self.file_lbl.pack(side="left")
        self.file_warn = ttk.Label(top, style="Warn.TLabel")
        self.file_warn.pack(side="left", padx=10)

        srow = ttk.Frame(f, style="Panel.TFrame")
        srow.grid(row=1, column=0, sticky="ew", pady=(8, 6))
        ttk.Label(srow, text="Buscar", style="Panel.TLabel").pack(side="left", padx=(0, 8))
        self.pick_q = tk.StringVar()
        ttk.Entry(srow, textvariable=self.pick_q, width=26).pack(side="left")
        self.pick_q.trace_add("write", lambda *_: self._fill_pick())
        ttk.Button(srow, text="＋ Agregar archivos…", command=self._add_files_for_key).pack(side="left", padx=8)

        box, self.pick_lb = make_listbox(f, 7)
        box.grid(row=2, column=0, sticky="nsew")
        self.pick_lb.bind("<<ListboxSelect>>", self._on_pick)
        self.pick_lb.bind("<Double-Button-1>", lambda e: self._test_action())

        opts = ttk.Frame(f, style="Panel.TFrame")
        opts.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(opts, text="Al pulsar", style="Panel.TLabel").grid(row=0, column=0, sticky="w")
        self.mode_cb = ttk.Combobox(opts, state="readonly", width=48, values=[m for _, m in PLAY_MODES])
        self.mode_cb.set(MODE_LABEL.get(act.get("mode", "overlap")))
        self.mode_cb.grid(row=0, column=1, sticky="w", padx=10)
        self.mode_cb.bind("<<ComboboxSelected>>", lambda e: self._on_file_opt())
        ttk.Label(opts, text="Volumen", style="Panel.TLabel").grid(row=1, column=0, sticky="nw", pady=(10, 0))
        vrow = ttk.Frame(opts, style="Panel.TFrame")
        vrow.grid(row=1, column=1, sticky="w", padx=10, pady=(8, 0))
        self.vol_var = tk.DoubleVar(value=round(float(act.get("volume", 1.0)) * 100))
        ttk.Scale(vrow, from_=0, to=150, variable=self.vol_var, length=300,
                  command=lambda _v: self._on_volume()).grid(row=0, column=0, sticky="w")
        self.vol_lbl = tk.Label(vrow, bg=C["panel2"], fg=C["accent"], font=(FONT, BASE, "bold"),
                                width=15, padx=6, pady=2)
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
        lines.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.spk_var = tk.BooleanVar(value=act.get("speakers", True))
        self.mic_var = tk.BooleanVar(value=act.get("mic", True))
        ttk.Checkbutton(lines, text="Por mis audífonos", variable=self.spk_var,
                        command=self._on_file_opt).pack(side="left")
        ttk.Checkbutton(lines, text="Por el micrófono", variable=self.mic_var,
                        command=self._on_file_opt).pack(side="left", padx=16)
        ttk.Button(lines, text="▶ Probar", style="Accent.TButton",
                   command=self._test_action).pack(side="right")
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
    def _build_about_tab(self):
        t = self.tab_about
        t.columnconfigure(0, weight=1)
        t.rowconfigure(5, weight=1)
        head = ttk.Frame(t, style="Panel.TFrame")
        head.grid(row=0, column=0, sticky="w")
        if getattr(self, "_icon", None) is not None:
            self._icon_small = self._icon.subsample(max(1, self._icon.width() // 64))
            tk.Label(head, image=self._icon_small, bg=C["panel"]).pack(side="left", padx=(0, 16))
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
        ub = ttk.Frame(up, style="Card.TFrame")
        ub.grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))
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
                   fg="#1a1306", font=(FONT, BASE + 1, "bold"), padx=22, pady=8).grid(
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
        self.root.deiconify()
        self.nb.select(self.tab_about)

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
        pc = ttk.Frame(t, style="Panel.TFrame")
        pc.grid(row=r, column=0, sticky="w", pady=(6, 0))
        ttk.Label(pc, text="Teclas virtuales por banco", style="Panel.TLabel").pack(side="left", padx=(0, 10))
        self.phone_count_cb = ttk.Combobox(pc, state="readonly", width=5, values=[str(n) for n in PHONE_COUNTS])
        self.phone_count_cb.set(str(phone_count(self.cfg)))
        self.phone_count_cb.pack(side="left")
        self.phone_count_cb.bind("<<ComboboxSelected>>", lambda e: self._on_phone_opts())
        r += 1
        ttk.Label(t, style="Muted.TLabel", wraplength=520, justify="left", text=(
            "Las teclas virtuales no son teclas físicas: solo se tocan en la app del celular, así que "
            "nunca interfieren con los teclados del equipo. Con «solo celular» el programa no necesita "
            "ningún teclado conectado y en vez del numpad dibuja las teclas virtuales para editarlas aquí.")
        ).grid(row=r, column=0, sticky="w", pady=(4, 0))

        r += 1
        ttk.Label(t, text="Comportamiento", style="H.TLabel").grid(row=r, column=0, sticky="w", pady=(20, 0))
        self.block_var = tk.BooleanVar(value=self.cfg.get("block_unassigned", True))
        self.toast_var = tk.BooleanVar(value=self.cfg.get("bank_toast", True))
        self.auto_var = tk.BooleanVar(value=sysutil.autostart_enabled())
        r += 1
        ttk.Checkbutton(t, text="Bloquear las teclas sin acción (si no, escriben números)",
                        variable=self.block_var, command=self._on_opts).grid(row=r, column=0, sticky="w", pady=(8, 0))
        r += 1
        ttk.Checkbutton(t, text="Mostrar aviso en pantalla al cambiar de banco",
                        variable=self.toast_var, command=self._on_opts).grid(row=r, column=0, sticky="w", pady=(6, 0))
        r += 1
        ttk.Checkbutton(t, text=f"Iniciar con {OS_NAME}", variable=self.auto_var,
                        command=self._on_autostart).grid(row=r, column=0, sticky="w", pady=(6, 0))
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
        self.vmic_card = tk.Frame(t, bg="#3a2c14", highlightbackground=C["accent_dim"], highlightthickness=1)
        self.vmic_card.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.vmic_card.columnconfigure(0, weight=1)
        need = "VB-Cable" if IS_WIN else "BlackHole 2ch"
        tk.Label(self.vmic_card, text=f"No se encontró el micrófono virtual ({need})", bg="#3a2c14",
                 fg=C["text"], font=(FONT, BASE, "bold"), anchor="w").grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 0))
        self.vmic_lbl = tk.Label(self.vmic_card, bg="#3a2c14", fg="#c9b48f", font=(FONT, BASE - 1), anchor="w",
                                 justify="left", wraplength=470, text=(
                                     "Sin él los sonidos solo se escuchan en tus audífonos: nadie te oye en "
                                     "Discord, OBS o el juego. Es gratis y se instala una sola vez."))
        self.vmic_lbl.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        self.vmic_btn = FlatButton(self.vmic_card, text="Instalar VB-Cable" if IS_WIN else "Descargar BlackHole ↗",
                                   command=self._install_vmic, bg=C["accent"], fg="#1a1306",
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
        ttk.Scale(trow, from_=-24, to=-10, variable=self.target_var, length=170,
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
            ttk.Scale(self.custom, from_=lo, to=hi, variable=v, length=120,
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
        lb = getattr(self, "pick_lb", None)
        if lb is None or not lb.winfo_exists():
            return
        lb.delete(0, "end")
        self._pick_view = library.search(self.cfg, self.pick_q.get())
        act = self._current_action() or {}
        cur = library.norm(act["path"]) if act.get("type") == "file" and act.get("path") else None
        sel = None
        for i, x in enumerate(self._pick_view):
            mark = "⚠ " if not os.path.isfile(x["path"]) else ""
            lb.insert("end", f"  {mark}{x['title']}")
            if cur and library.norm(x["path"]) == cur:
                sel = i
        if not self.cfg.get("library"):
            lb.insert("end", "  Biblioteca vacía: usa «＋ Agregar archivos…».")
        if sel is not None:
            lb.selection_set(sel)
            lb.see(sel)

    def _on_pick(self, _e=None):
        sel = self.pick_lb.curselection()
        if not sel or sel[0] >= len(self._pick_view):
            return
        self._assign_file(self._pick_view[sel[0]], rebuild=False)

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

    def _test_action(self):
        act = self._current_action()
        if act:
            self.engine.run_action(act, self.selected)

    # ================================================================ dibujo
    def _layer_dict(self, layer=None):
        layer = self.layer if layer is None else layer
        return self.cfg["global"] if layer == "global" else self.cfg["banks"][layer]["keys"]

    def _key_rect(self, kid):
        _, c, r, w, h = NUMPAD_LAYOUT[kid]
        u, g = self.UNIT, self.GAP
        x0, y0 = c * (u + g), r * (u + g)
        return x0, y0, x0 + w * u + (w - 1) * g, y0 + h * u + (h - 1) * g

    def _redraw(self):
        cv = self.canvas
        cv.delete("all")
        layer = self._layer_dict()
        for kid, (label, _c, _r, kw, _kh) in NUMPAD_LAYOUT.items():
            x0, y0, x1, y1 = self._key_rect(kid)
            narrow = kw == 1
            act = layer.get(kid)
            gact = self.cfg["global"].get(kid) if self.layer != "global" else None
            fill, line, txt, sub_col = C["key"], C["line"], "", C["muted"]
            if act:
                fill, line, txt, sub_col = C["key_set"], C["key_set_line"], short_action(act, narrow), "#bfe0ff"
            if gact:
                fill, line = C["key_global"], C["key_global_line"]
                txt, sub_col = ("🌐 " if not narrow else "") + short_action(gact, narrow), "#d9c9ff"
            if kid in self.flash:
                fill = C["accent"]
            width = 1
            if kid == self.selected:
                line, width = C["accent"], 3
            self._round_rect(x0 + 1, y0 + 1, x1 - 1, y1 - 1, 10, fill=fill, outline=line, width=width)
            big = BASE + 5 if len(label) <= 2 else BASE
            cv.create_text(x0 + 10, y0 + 8, text=label, anchor="nw", fill=C["text"],
                           font=(FONT, big, "bold"))
            if txt:
                cv.create_text((x0 + x1) / 2, y1 - 6, text=txt, anchor="s", fill=sub_col,
                               font=(FONT, BASE - 2), width=(x1 - x0) - 6, justify="center")
            shown = gact or act
            if narrow and shown and shown.get("type") == "file":
                icon = "🔊" + MODE_ICON.get(shown.get("mode", "overlap"), "").strip()
                cv.create_text(x1 - 5, y0 + 6, text=icon, anchor="ne", fill=sub_col, font=(FONT, BASE - 3))
        self._draw_row()
        self._draw_extras()

    def _round_rect(self, x0, y0, x1, y1, r, canvas=None, **kw):
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
               x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return (canvas or self.canvas).create_polygon(pts, smooth=True, **kw)

    def _phone_only(self):
        return bool(self.cfg.get("phone", {}).get("only"))

    def _cel_rows(self):
        """Filas visibles de botones del celular (más si no se dibuja el numpad)."""
        return 8 if self._phone_only() else 2

    def _cel_pages(self):
        per = 6 * self._cel_rows()
        return max(1, -(-phone_count(self.cfg) // per))

    def _cel_page_step(self, d):
        self.cel_page = (self.cel_page + d) % self._cel_pages()
        self._redraw()

    def _small_layout(self):
        if self.small_group == "cel":
            per = 6 * self._cel_rows()
            self.cel_page = min(self.cel_page, self._cel_pages() - 1)
            first = self.cel_page * per
            out = {}
            for kid, (label, c, r) in phone_layout(phone_count(self.cfg), 6).items():
                i = int(kid[1:]) - 1
                if first <= i < first + per:
                    out[kid] = (label, c, r - first // 6)
            return out
        return ROW_LAYOUT

    def _set_group(self, gid):
        self.small_group = gid
        self._redraw()

    def _row_rect(self, kid):
        _, c, r = self._small_layout()[kid]
        u, g = self.RUNIT, self.RGAP
        x0, y0 = c * (u + g), r * (u + g)
        return x0, y0, x0 + u, y0 + u

    def _draw_row(self):
        cv = self.row_canvas
        cv.delete("all")
        for gid, b in self.sg_btns.items():
            on = gid == self.small_group
            b.configure(bg=C["accent"] if on else C["panel2"], fg="#1a1306" if on else C["muted"])
        lay = self._small_layout()
        rows = max((v[2] for v in lay.values()), default=0) + 1
        cv.configure(height=rows * (self.RUNIT + self.RGAP) - self.RGAP)
        multi = self.small_group == "cel" and self._cel_pages() > 1
        for w in (self.pg_next, self.pg_lbl, self.pg_prev):
            if multi:
                w.pack(side="right", padx=(2, 0))
            else:
                w.pack_forget()
        if multi:
            self.pg_lbl.configure(text=f"{self.cel_page + 1}/{self._cel_pages()}")
        if self.small_group == "cel":
            enabled = True
            self.row_title.configure(text=(
                f"Teclas virtuales ({phone_count(self.cfg)}) · se tocan en la app del celular "
                "y nunca interfieren con tus teclados"))
        else:
            enabled = self.cfg["row_mode"].get("enabled", True)
            try:
                toggle = self._combo_text(self.cfg["row_mode"]["toggle"])
            except Exception:
                toggle = "?"
            self.row_title.configure(
                text=(f"Fila de números · modo macros ({toggle})" if enabled
                      else "Fila de números · desactivada (ver «Numpad y opciones»)"))
        layer = self._layer_dict()
        for kid, (label, *_r) in lay.items():
            x0, y0, x1, y1 = self._row_rect(kid)
            act = layer.get(kid)
            gact = self.cfg["global"].get(kid) if self.layer != "global" else None
            fill, line = C["key"], C["line"]
            if act:
                fill, line = C["key_set"], C["key_set_line"]
            if gact:
                fill, line = C["key_global"], C["key_global_line"]
            if kid in self.flash:
                fill = C["accent"]
            width = 3 if kid == self.selected else 1
            if kid == self.selected:
                line = C["accent"]
            self._round_rect(x0 + 1, y0 + 1, x1 - 1, y1 - 1, 7, canvas=cv, fill=fill,
                             outline=line, width=width)
            fg = C["text"] if enabled else C["muted"]
            cv.create_text(x0 + 7, y0 + 4, text=label, anchor="nw", fill=fg,
                           font=(FONT, BASE + 1 if len(label) < 3 else BASE - 1, "bold"))
            a = gact or act
            if a:
                icon = {"file": "🔊", "keys": "⌨", "sound_stop": "■"}.get(a.get("type"), "→")
                cv.create_text(x1 - 5, y1 - 4, text=icon, anchor="se", fill="#bfe0ff",
                               font=(FONT, BASE - 2))

    def _on_row_click(self, ev):
        for kid in self._small_layout():
            x0, y0, x1, y1 = self._row_rect(kid)
            if x0 <= ev.x <= x1 and y0 <= ev.y <= y1:
                self._select(kid)
                return

    def _draw_extras(self):
        for wdg in self.extra_frame.winfo_children():
            wdg.destroy()
        extras = [k for k in self.cfg.get("extra_keys", [])
                  if k not in NUMPAD_IDS and k not in ROW_IDS and k not in PHONE_IDS]
        if self._phone_only():
            extras = []
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
            bg = C["accent"] if kid in self.flash else (C["key_set"] if act else C["key"])
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
        if kid in ROW_IDS:
            self.small_group = "row"
        elif kid in PHONE_IDS:
            self.small_group = "cel"
            self.cel_page = (int(kid[1:]) - 1) // (6 * self._cel_rows())
        self._redraw()
        self._load_editor()
        self._update_assign_label()

    def _on_tab(self):
        if self.nb.index("current") == 1:
            self._fill_library()

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
        self.bank_lbl.configure(text=f"{i + 1}. {self.cfg['banks'][i]['name']}")

    # ================================================================ editor: carga
    def _load_editor(self):
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

    # ================================================================ editor: cambios
    def _current_action(self):
        return self._layer_dict().get(self.selected)

    def _store(self, act, redraw=True):
        with self.engine.lock:
            d = self._layer_dict()
            if not act or act.get("type") == "none":
                d.pop(self.selected, None)
            else:
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
            self.chip_row.configure(text=f"⌨ Modo macros ACTIVO ({tog})", bg=C["accent"], fg="#1a1306")
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
            ph["count"] = int(self.phone_count_cb.get())
        self._save()
        if changed:
            self.small_group = "cel"
            self._apply_phone_only()
            self._start_backend()
        self.cel_page = 0
        self._redraw()
        self._load_editor()

    def _apply_phone_only(self):
        """En «solo celular» no se dibuja el numpad (los botones del celular ocupan su lugar)."""
        if self._phone_only():
            self.canvas.pack_forget()
            self.btn_capture.pack_forget()
        else:
            if not self.canvas.winfo_ismapped():
                self.canvas.pack(pady=(4, 8), before=self.sg_frame)
            if not self.btn_capture.winfo_ismapped():
                self.btn_capture.pack(fill="x", pady=(6, 0))
        if self._phone_only() and self.selected not in PHONE_IDS:
            self.selected = "m1"

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
        if self.engine.active:
            self.btn_active.configure(text="●  ACTIVO", bg=C["ok"], fg="#06210f")
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
                    self._handle(q.get_nowait())
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
        elif kind == "remote":
            self._on_remote(ev[1:])
        elif kind == "remote_save":
            self._save()
        elif kind == "tray":
            cmd = ev[1]
            if cmd == "show":
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
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

    def _remote_state(self):
        if getattr(self, "remote", None):
            self.remote.state_changed()

    # ================================================================ medidores
    def _tick_meters(self):
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

    def _check_updates(self, manual=False):
        upd = self.cfg["updates"]
        if not manual and not updater.due(upd):
            return
        if manual:
            self.upd_lbl.configure(text="Buscando…")
            self.btn_check.state(["disabled"])
        snapshot = dict(upd)

        def job():
            try:
                rel = updater.check(snapshot, __version__, manual=manual)
                self.uiq.put(("update", manual, rel, None, snapshot.get("last_check", 0)))
            except Exception as e:
                self.uiq.put(("update", manual, None, str(e), 0))
        threading.Thread(target=job, daemon=True).start()

    def _on_update_result(self, manual, rel, err, checked_at):
        self.btn_check.state(["!disabled"])
        if checked_at:
            with self.engine.lock:
                self.cfg["updates"]["last_check"] = checked_at
            self._save()
        if err:
            self.upd_lbl.configure(text="No se pudo comprobar (sin conexión con GitHub). Se volverá a intentar.")
            if manual:
                self._set_status("No pude consultar si hay versiones nuevas (¿hay internet?).", bad=True)
            return
        stamp = time.strftime("%H:%M")
        if not rel:
            self.upd_lbl.configure(text=f"Estás al día · comprobado a las {stamp}")
            if manual:
                self._set_status("Tienes la última versión.")
            return
        self.update_rel = rel
        self.upd_lbl.configure(text=f"Hay una versión nueva: {rel.version}")
        extra = " · importante" if rel.important else (" · beta" if rel.prerelease else "")
        self.banner_lbl.configure(text=f"Hay una nueva versión: {rel.version}{extra}   (tienes {__version__})")
        self.banner.grid()
        if rel.important:
            self.banner_later.grid_remove()
        if manual:
            self._open_update()

    def _hide_banner(self):
        self.banner.grid_remove()
        self._set_status("Te lo recordaré la próxima vez que abras la app.")

    def _open_update(self):
        rel = self.update_rel
        if not rel:
            return
        if self._upd_dialog is not None and self._upd_dialog.winfo_exists():
            self._upd_dialog.lift()
            return
        self.root.deiconify()
        self._upd_dialog = UpdateDialog(self.root, rel, updater.install_kind(), self._skip_version,
                                        self._install_update)

    def _skip_version(self, version):
        with self.engine.lock:
            self.cfg["updates"]["skip"] = version
        self._save()
        self.banner.grid_remove()
        self.upd_lbl.configure(text=f"Omitiste la versión {version}")
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

    def _setup_tray(self):
        if IS_MAC:          # en macOS el icono de bandeja necesita el hilo principal (lo usa tkinter)
            return
        try:
            import pystray
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
        menu = pystray.Menu(
            pystray.MenuItem("Mostrar", lambda: put(("tray", "show")), default=True),
            pystray.MenuItem(lambda item: "Pausar" if self.engine.active else "Reanudar",
                             lambda: put(("tray", "toggle"))),
            pystray.MenuItem("Salir", lambda: put(("tray", "quit"))),
        )
        try:
            self.tray = pystray.Icon("NumpadMacros", img, "Numpad Macros", menu)
            self.tray.run_detached()
        except Exception:
            self.tray = None

    def _on_close(self):
        if self.tray:
            self.root.withdraw()
            self._set_status("Sigue funcionando en la bandeja del sistema.")
        else:
            self._quit()

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
    if app.relaunch:                        # Linux: abrir la versión recién instalada
        import subprocess
        sysutil.release_instance()
        subprocess.Popen([app.relaunch, "--tras-actualizar"], env=updater.relaunch_env(),
                         start_new_session=True, close_fds=True)
