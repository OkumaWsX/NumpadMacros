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
import logica as L  # noqa: E402
import claves as K  # noqa: E402
import vista as V  # noqa: E402
from logica import npt  # noqa: E402

from PIL import Image, ImageTk  # noqa: E402

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception:          # sin la librería se elige la imagen con un botón
    TkinterDnD = None

VERSION = "1.0.0"
APP = "Estudio de Temas"
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
        self.inner.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self.cv.bind("<Configure>", lambda e: self.cv.itemconfigure(self._win, width=e.width))
        for w in (self.cv, self.inner):
            w.bind("<Enter>", self._bind)
            w.bind("<Leave>", self._unbind)

    def _bind(self, _e):
        self.cv.bind_all("<MouseWheel>", self._wheel)
        self.cv.bind_all("<Button-4>", lambda e: self.cv.yview_scroll(-3, "units"))
        self.cv.bind_all("<Button-5>", lambda e: self.cv.yview_scroll(3, "units"))

    def _unbind(self, _e):
        for s in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.cv.unbind_all(s)

    def _wheel(self, e):
        d = e.delta if sys.platform == "darwin" else e.delta // 120
        self.cv.yview_scroll(-d, "units")


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
                "imagen_colores_nombre": self.pal_name}

    def apply_state(self, s: dict):
        self.colors = {**self.themes[0]["colores"], **s.get("colores", {})}
        self.alpha = {k: int(v) for k, v in (s.get("alfa") or {}).items() if k in npt.ALPHA_TOKENS}
        w = s.get("ventana") or {}
        self.window = {"opacidad": int(w.get("opacidad", 100)), "sin_usar": int(w.get("sin_usar", 100))}
        self.meta = {"nombre": s.get("nombre", "Tema"), "version": str(s.get("version", "1.0")),
                     "descripcion": s.get("descripcion", "")}
        self.base_name = s.get("base", self.themes[0]["nombre"])
        self.auto = bool(s.get("auto", False))
        self.images = dict(s.get("imagenes") or {})
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
        r.geometry("1380x880")
        r.minsize(1300, 760)
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
        return tk.Scale(parent, variable=var, from_=a, to=b, resolution=step, orient="horizontal", showvalue=False,
                        command=lambda _v: cmd(), bg=C["acc"], troughcolor=C["panel2"], activebackground="#ffb855",
                        highlightthickness=0, bd=0, sliderrelief="flat", sliderlength=16, width=10)

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
        key_title = "4 · Clave de firma" if self.mode == "creador" else "4 · Mi firma de autor"
        for sid, text in (("edit", "1 · Editar tema"), ("img", "2 · Imágenes y plantillas"),
                          ("exp", "3 · Exportar"), ("key", key_title)):
            b = ttk.Button(nav, text=text, style="Nav.TButton", command=lambda s=sid: self.show(s))
            b.pack(side="left", padx=(0, 6))
            self.nav[sid] = b

        self.body = tk.Frame(r, bg=C["bg"], highlightthickness=1, highlightbackground=C["line"])
        self.body.grid(row=2, column=0, sticky="nsew", padx=16)
        self.body.rowconfigure(0, weight=1)
        self.body.columnconfigure(0, weight=1)
        self.views = {"edit": self._build_edit(), "img": self._build_img(), "exp": self._build_exp(),
                      "key": self._build_key()}
        self.status = tk.Label(r, text="Listo.", bg=C["bg"], fg=C["muted"], font=fnt(-1), anchor="w")
        self.status.grid(row=3, column=0, sticky="ew", padx=16, pady=(6, 10))
        self.show(self.screen)
        self._title()

    def show(self, sid):
        self.screen = sid
        for k, v in self.views.items():
            v.grid_remove() if k != sid else v.grid(row=0, column=0, sticky="nsew")
        for k, b in self.nav.items():
            b.configure(style="NavOn.TButton" if k == sid else "Nav.TButton")
        if sid == "exp":
            self.exp_done.pack_forget()
        self.render()

    # ---------------------------------------------------------------- 1 · editar
    def _build_edit(self):
        f = tk.Frame(self.body, bg=C["panel"])
        f.columnconfigure(1, weight=1, minsize=V.W + 40)
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
        # centro: vista previa
        mid = tk.Frame(f, bg=C["panel"], highlightthickness=0)
        mid.grid(row=0, column=1, sticky="nsew", padx=10)
        top = tk.Frame(mid, bg=C["panel"])
        top.pack(fill="x", pady=(12, 4))
        self.caps(top, "Vista previa · ventana principal").pack(side="left")
        self.hover_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Botón al pasar el mouse", variable=self.hover_var, command=self.render).pack(
            side="right")
        self.lbl(mid, "Toca cualquier parte de la ventana para editar su color.", -1, color="muted").pack(fill="x")
        holder = tk.Frame(mid, bg="#0d0e11", padx=10, pady=10)
        holder.pack(pady=8)
        self.cv_edit = tk.Canvas(holder, width=V.W, height=V.H, highlightthickness=0, bd=0, cursor="hand2")
        self.cv_edit.pack()
        self.pv_edit = V.Preview(self.cv_edit)
        self.cv_edit.bind("<Button-1>", self.on_preview_click)
        # derecha
        right = Scrollable(f, C["panel"], width=290)
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
        ttk.Button(side, text="Importar imagen…", command=self.import_palette_image).pack(anchor="w")
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
        ttk.Button(line, text="Aplicar al tema", style="Accent.TButton", command=self.apply_palette).pack(
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

    # ---------------------------------------------------------------- 2 · imágenes
    def _build_img(self):
        f = tk.Frame(self.body, bg=C["panel"])
        f.columnconfigure(1, weight=1, minsize=V.W + 40)
        f.rowconfigure(0, weight=1)
        left = tk.Frame(f, bg=C["panel"], width=270)
        left.grid(row=0, column=0, sticky="nsw", padx=12)
        self.caps(left, "Plantillas").pack(fill="x", pady=(12, 6))
        self.tpl_box = tk.Frame(left, bg=C["panel"])
        self.tpl_box.pack(fill="x")
        self.caps(left, "Espacios para imágenes").pack(fill="x", pady=(16, 6))
        self.slot_box = tk.Frame(left, bg=C["panel"])
        self.slot_box.pack(fill="x")
        na = tk.Frame(left, bg=C["panel"])
        na.pack(fill="x", pady=(8, 0))
        self.lbl(na, "Fondo de toda la ventana", -1, color="muted").pack(anchor="w")
        self.lbl(na, "No disponible: los paneles y campos de Numpad Macros se pintan con color sólido. Las imágenes "
                     "van en las zonas que el programa ya dibuja a mano.", -2, color="muted", wrap=260).pack(anchor="w")
        mid = tk.Frame(f, bg=C["panel"])
        mid.grid(row=0, column=1, sticky="nsew", padx=10)
        self.caps(mid, "Vista previa · toca un espacio para editarlo").pack(fill="x", pady=(12, 4))
        self.lbl(mid, "Las imágenes van dentro del .npt, cifradas y firmadas junto con los colores.", -1,
                 color="muted").pack(fill="x")
        holder = tk.Frame(mid, bg="#0d0e11", padx=10, pady=10)
        holder.pack(pady=8)
        self.cv_img = tk.Canvas(holder, width=V.W, height=V.H, highlightthickness=0, bd=0, cursor="hand2")
        self.cv_img.pack()
        self.pv_img = V.Preview(self.cv_img)
        self.cv_img.bind("<Button-1>", self.on_zone_click)
        right = tk.Frame(f, bg=C["panel"], width=300)
        right.grid(row=0, column=2, sticky="nse", padx=12)
        self.slot_title = self.caps(right, "")
        self.slot_title.pack(fill="x", pady=(12, 6))
        sc = self.card(right)
        sc.pack(fill="x")
        top = tk.Frame(sc, bg=C["panel"])
        top.pack(fill="x")
        self.slot_thumb = tk.Label(top, bg="#0d0e11", image=self._blank(96, 60), width=96, height=60)
        self.slot_thumb.pack(side="left")
        side = tk.Frame(top, bg=C["panel"])
        side.pack(side="left", padx=10)
        ttk.Button(side, text="Importar imagen…", command=self.import_slot_image).pack(anchor="w", fill="x")
        ttk.Button(side, text="Usar la imagen de los colores", command=self.slot_use_palette).pack(anchor="w",
                                                                                                    fill="x", pady=4)
        self.slot_size = self.lbl(sc, "", -2, color="muted", wrap=260)
        self.slot_size.pack(fill="x", pady=(8, 4))
        self.lbl(sc, "Ajuste", -1, color="muted").pack(anchor="w")
        self.fit_var = tk.StringVar()
        self.fit_cb = ttk.Combobox(sc, textvariable=self.fit_var, state="readonly", values=list(L.FITS.values()))
        self.fit_cb.pack(fill="x")
        self.fit_cb.bind("<<ComboboxSelected>>", lambda e: self.on_slot_setting())
        self.slot_vars = {}
        for key, txt, a, b, step, unit in (("op", "Opacidad", 10, 100, 5, " %"),
                                           ("dark", "Oscurecer con el color de fondo", 0, 90, 5, " %"),
                                           ("blur", "Desenfoque", 0, 12, 1, " px")):
            line = tk.Frame(sc, bg=C["panel"])
            line.pack(fill="x", pady=(8, 0))
            self.lbl(line, txt, -1).pack(side="left")
            out = self.lbl(line, "", -1, color="muted", mono=True)
            out.pack(side="right")
            var = tk.IntVar()
            s = self.scale(sc, var, a, b, step, self.on_slot_setting)
            s.pack(fill="x")
            self.slot_vars[key] = (var, out, unit, s)
        self.slot_del = ttk.Button(sc, text="Quitar imagen", command=self.slot_remove)
        self.slot_del.pack(anchor="w", pady=(10, 0))
        self.caps(right, "Peso del tema").pack(fill="x", pady=(16, 6))
        self.weight_lbl = self.lbl(right, "", -1, wrap=280)
        self.weight_lbl.pack(fill="x")
        self.lbl(right, "El Estudio deja cada imagen lista (recortada, oscurecida y desenfocada) antes de guardarla, "
                        "así Numpad Macros solo tiene que mostrarla.", -2, color="muted", wrap=280).pack(fill="x",
                                                                                                 pady=(12, 0))
        return f

    # ---------------------------------------------------------------- 3 · exportar
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
        for k, v in (("NPT v1", "Encabezado: identifica el archivo como tema de Numpad Macros y su versión."),
                     ("Contenido", "Nombre, autor, descripción, los 22 colores con la transparencia de cada uno y la "
                                   "opacidad de la ventana, comprimidos y cifrados (AES-256-GCM). Con un editor de "
                                   "texto solo se ven símbolos."),
                     ("Imágenes", "Las de cada espacio, ya preparadas, en PNG. También van cifradas."),
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

    # ---------------------------------------------------------------- 4 · clave
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

    def render(self):
        if not hasattr(self, "rows"):
            return
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
        if self.screen == "edit":
            self.pv_edit.draw(e, self.slot_image, hover=self.hover_var.get())
        elif self.screen == "img":
            self.pv_img.draw(e, self.slot_image, zones=True, sel_zone=self.slot_sel)
            self._paint_slots()
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

    def _paint_legibility(self):
        for w in self.leg_rows.winfo_children():
            w.destroy()
        e = self.eff()
        rows = L.legibility(self.colors, self.alpha, self.window)
        bad = sum(1 for r in rows if r[3] == "bad")
        warn = sum(1 for r in rows if r[3] == "warn")
        pairs = {p[0]: (p[1], p[2]) for p in L.PAIRS}
        for name, rv, _mn, st in rows:
            fr = tk.Frame(self.leg_rows, bg=C["panel"])
            fr.pack(fill="x", pady=1)
            if name in pairs:
                fg, bgk = pairs[name]
                tk.Label(fr, text="Aa", bg=e[bgk], fg=e[fg], font=fnt(-2, True), padx=4).pack(side="left")
                val = f"{rv:.1f}:1"
            else:
                val = f"{int(rv)} %"
            self.lbl(fr, name, -2).pack(side="left", padx=6)
            fgc, bgc = {"ok": (C["ok_text"], C["ok_bg"]), "warn": (C["warn_text"], C["warn_bg"]),
                        "bad": (C["bad_text"], C["bad_bg"])}[st]
            tk.Label(fr, text=val, bg=bgc, fg=fgc, font=fnt(-2, mono=True), padx=5).pack(side="right")
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

    def _paint_slots(self):
        for w in self.tpl_box.winfo_children():
            w.destroy()
        tpls = list(L.TEMPLATES) + [("custom", "Personalizada", None)]
        for i, (tid, name, slots) in enumerate(tpls):
            on = tid == self.template
            fr = tk.Frame(self.tpl_box, bg=C["acc_bg"] if on else C["panel2"], highlightthickness=1,
                          highlightbackground=C["acc"] if on else C["line"], padx=6, pady=6, cursor="hand2")
            fr.grid(row=i // 2, column=i % 2, padx=3, pady=3, sticky="ew")
            sk = tk.Canvas(fr, width=110, height=40, bg="#0f1115", highlightthickness=0)
            sk.pack()
            has = (lambda s: s in slots) if slots is not None else (lambda s: s in self.images)
            sk.create_rectangle(4, 4, 106, 12, fill=C["acc"] if has("banner") else "#2a2e37", width=0)
            sk.create_rectangle(4, 15, 44, 36, fill=C["acc"] if has("keys") else "#2a2e37", width=0)
            sk.create_rectangle(48, 15, 106, 36, fill="#2a2e37", width=0)
            lab = tk.Label(fr, text=name, bg=fr["bg"], fg=C["text"], font=fnt(-1, True), anchor="w")
            lab.pack(fill="x", pady=(4, 0))
            for w in (fr, sk, lab):
                w.bind("<Button-1>", lambda e, t=tid: self.apply_template(t))
        for w in self.slot_box.winfo_children():
            w.destroy()
        self._slot_photos = []
        for slot, name in L.SLOT_NAMES.items():
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
            box.pack(side="left", padx=8)
            w, h = npt.IMAGE_SLOTS[slot]
            a = tk.Label(box, text=name, bg=fr["bg"], fg=C["text"], font=fnt(-1), anchor="w")
            a.pack(anchor="w")
            b = tk.Label(box, text=f"{'Con imagen' if s else 'Vacío'} · {w} × {h} px", bg=fr["bg"], fg=C["muted"],
                         font=fnt(-2), anchor="w")
            b.pack(anchor="w")
            for wdg in (fr, th, box, a, b):
                wdg.bind("<Button-1>", lambda e, sl=slot: self.pick_slot(sl))
        # ajustes del espacio elegido
        s = self.images.get(self.slot_sel)
        d = s or L.SLOT_DEFAULTS[self.slot_sel]
        self.slot_title.configure(text=L.SLOT_NAMES[self.slot_sel].upper())
        w, h = npt.IMAGE_SLOTS[self.slot_sel]
        self.slot_size.configure(text=f"Se guarda a {w} × {h} px." + ("" if s else
                                 " Importa una imagen o usa la de los colores."))
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
        kb = self.theme_weight() // 1024
        n = len(self.images)
        self.weight_lbl.configure(text=f"{max(kb, 3)} KB aprox. · {n} imagen{'' if n == 1 else 'es'}. "
                                       f"Límite por tema: {npt.MAX_FILE // 1024 // 1024} MB.",
                                  fg=C["bad_text"] if kb * 1024 > npt.MAX_FILE else C["text"])

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
        rows = L.legibility(self.colors, self.alpha, self.window)
        bad = sum(1 for r in rows if r[3] == "bad")
        warn = sum(1 for r in rows if r[3] == "warn")
        reserved = self.mode != "creador" and npt.is_reserved_name(self.author)
        n = len(self.images)
        checks = [("ok", "Los 22 colores están completos")]
        checks.append(("bad", f"{bad} combinación ilegible: vuelve a «Editar tema»") if bad else
                      ("warn", f"Legible, con {warn} combinación justa") if warn else
                      ("ok", "Texto legible en todas las capas"))
        t = self.build_theme_meta()
        checks.append(("ok", f"Admite transparencia: ventana {self.window['opacidad']} % (sin usar "
                             f"{self.window['sin_usar']} %) · {sum(1 for v in self.alpha.values() if v < 100)} capas "
                             "con nivel propio") if t.transparency else ("ok", "Sin transparencia (opaco)"))
        checks.append(("ok", f"{n} imagen{'es' if n != 1 else ''}: " + ", ".join(
            L.SLOT_NAMES[s].lower() for s in self.images)) if n else ("ok", "Sin imágenes (solo colores)"))
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
    def slot_image(self, slot, size, under):
        """Imagen de un espacio preparada para la vista previa (con caché)."""
        s = self.images.get(slot)
        if not s:
            return None
        key = (slot, size, self.colors["bg"], s["fit"], s["op"], s["dark"], s["blur"], hashlib.md5(s["src"]).digest())
        if key not in self._cache:
            if len(self._cache) > 40:
                self._cache.clear()
            src = L.from_bytes(s["src"])
            sw, sh = npt.IMAGE_SLOTS[slot]
            blur = s["blur"] * size[0] / sw          # desenfoque proporcional al tamaño de la vista
            self._cache[key] = L.render_slot(src, slot, s["fit"], s["op"], s["dark"], round(blur), self.colors["bg"],
                                             size=size)
        return self._cache[key]

    def final_images(self) -> dict:
        out = {}
        for slot, s in self.images.items():
            key = ("final", slot, self.colors["bg"], s["fit"], s["op"], s["dark"], s["blur"],
                   hashlib.md5(s["src"]).digest())
            if key not in self._cache:
                im = L.render_slot(L.from_bytes(s["src"]), slot, s["fit"], s["op"], s["dark"], s["blur"],
                                   self.colors["bg"])
                self._cache[key] = L.to_png(im)
            out[slot] = self._cache[key]
        return out

    def theme_weight(self) -> int:
        return 3000 + sum(len(v) for v in self.final_images().values())

    def apply_template(self, tid):
        self.template = tid
        tpl = next((t for t in L.TEMPLATES if t[0] == tid), None)
        if tpl:
            for slot in L.SLOT_NAMES:
                if slot in tpl[2]:
                    self.images.setdefault(slot, {"src": self.pal_img, **L.SLOT_DEFAULTS[slot]})
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
        s["fit"] = inv.get(self.fit_var.get(), "cover")
        for key, (var, _o, _u, _s) in self.slot_vars.items():
            s[key] = int(var.get())
        self.template = "custom"
        self.mark()
        self.render()

    def _read_image(self, path):
        try:
            if os.path.getsize(path) > 20 * 1024 * 1024:
                raise ValueError("La imagen pesa más de 20 MB. Prueba con una más liviana.")
            im = Image.open(path)
            im.load()
            # se guarda una copia razonable (no hace falta más para 1200 px de ancho)
            im = im.convert("RGBA")
            im.thumbnail((1600, 1600))
            return L.to_png(im)
        except Exception as e:
            messagebox.showerror(APP, f"No se pudo abrir la imagen:\n{e}", parent=self.root)
            return None

    def import_slot_image(self):
        path = filedialog.askopenfilename(parent=self.root, title="Elige una imagen", filetypes=IMG_TYPES)
        if not path:
            return
        data = self._read_image(path)
        if data:
            self.images[self.slot_sel] = {**(self.images.get(self.slot_sel) or L.SLOT_DEFAULTS[self.slot_sel]),
                                          "src": data}
            self.template = "custom"
            self.mark()
            self.render()

    def slot_use_palette(self):
        self.images[self.slot_sel] = {**(self.images.get(self.slot_sel) or L.SLOT_DEFAULTS[self.slot_sel]),
                                      "src": self.pal_img}
        self.template = "custom"
        self.mark()
        self.render()

    def slot_remove(self):
        self.images.pop(self.slot_sel, None)
        self.template = "custom"
        self.mark()
        self.render()

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
        data = self._read_image(path)
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
        if not path:
            return
        if path.lower().endswith(L.PROJECT_EXT):
            try:
                s = L.load_project(path)
            except Exception as e:
                messagebox.showerror(APP, f"No se pudo abrir el proyecto:\n{e}", parent=self.root)
                return
            self.apply_state(s)
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
                          "colores": t.colors, "alfa": t.alpha, "ventana": t.window, "auto": False, "imagenes": imgs})
        self.project_path = None
        self.dirty = True
        self._title()
        self.toast(f"«{t.name}» abierto para editar. La versión subió a {self.meta['version']}.", "ok")

    def build_theme_meta(self) -> npt.Theme:
        return npt.Theme(name=self.meta["nombre"].strip() or "Sin nombre", author=self.author,
                         colors=dict(self.colors), version=self.meta["version"].strip() or "1.0",
                         description=self.meta["descripcion"].strip(),
                         kind="oscuro" if L.is_dark(self.colors) else "claro",
                         alpha={k: v for k, v in self.alpha.items() if v < 100}, window=dict(self.window))

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
                K.import_key_file(raw)
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
        path = os.path.join(base, "icon.png")
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


def main():
    cls = "EstudioTemasNumpadMacros"
    root = TkinterDnD.Tk(className=cls) if TkinterDnD else tk.Tk(className=cls)
    root.title(APP)
    icon = _icon_path()
    try:
        if icon:
            root.iconphoto(True, tk.PhotoImage(file=icon))
    except tk.TclError:
        pass
    _integrate_linux(icon)
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        p = sys.argv[1]
        root.after(300, lambda: app.open_npt(p) if p.lower().endswith(".npt") else None)
    root.mainloop()


if __name__ == "__main__":
    main()
