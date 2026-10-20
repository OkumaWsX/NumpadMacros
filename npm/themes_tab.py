# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Pestaña «Temas»: elegir, importar y exportar temas de colores (.npt)."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import npt, themes
from .theme import BASE, C, FONT

DOTS = [("bg", "Fondo"), ("panel", "Panel"), ("panel2", "Panel 2"), ("line", "Línea"), ("text", "Texto"),
        ("muted", "Suave"), ("acc", "Acento"), ("key", "Tecla"), ("key_set", "Asignada"),
        ("key_global", "Global"), ("ok", "Bien"), ("bad", "Error")]


def draw_preview(cv, c, w, h):
    """Miniatura del programa pintado con los colores de un tema."""
    cv.delete("all")
    g = lambda k, d="#000000": c.get(k, d)
    cv.create_rectangle(0, 0, w, h, fill=g("bg"), outline=g("line"))
    p = max(4, w // 25)
    cv.create_rectangle(p, p, p + w * .28, p + 5, fill=g("text"), outline="")
    cv.create_rectangle(w - p - w * .14, p, w - p, p + 7, fill=g("ok"), outline="")
    top = p + 12
    lw = w * .34
    cv.create_rectangle(p, top, p + lw, h - p, fill=g("panel"), outline="")
    cols, rows = 3, 3
    kw = (lw - 4 * 3) / cols
    kh = (h - p - top - 4 * 4) / rows
    keys = [g("key_global"), g("key"), g("key"), g("key_set"), g("key_set"), g("key"), g("key"), g("key_set"), g("key")]
    for i, col in enumerate(keys):
        x = p + 3 + (i % cols) * (kw + 3)
        y = top + 4 + (i // cols) * (kh + 4)
        cv.create_rectangle(x, y, x + kw, y + kh, fill=col, outline="")
    x0 = p + lw + p
    cv.create_rectangle(x0, top, w - p, h - p, fill=g("panel"), outline="")
    cv.create_rectangle(x0 + 6, top + 6, x0 + 6 + (w - p - x0) * .55, top + 10, fill=g("text"), outline="")
    cv.create_rectangle(x0 + 6, top + 15, x0 + 6 + (w - p - x0) * .8, top + 18, fill=g("muted"), outline="")
    cv.create_rectangle(x0 + 6, top + 24, w - p - 6, top + 32, fill=g("panel2"), outline="")
    cv.create_rectangle(w - p - 6 - (w - p - x0) * .3, h - p - 14, w - p - 6, h - p - 5, fill=g("acc"), outline="")


class ThemesTab:
    CARD_W, CARD_H = 128, 74

    def __init__(self, parent, app):
        self.app = app
        self.t = parent
        t = parent
        t.columnconfigure(0, weight=1)
        t.rowconfigure(1, weight=1)
        head = ttk.Frame(t, style="Panel.TFrame")
        head.grid(row=0, column=0, columnspan=2, sticky="ew")
        head.columnconfigure(0, weight=1)
        ttk.Label(head, text="Temas", style="H.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(head, style="Muted.TLabel", wraplength=330, justify="left", text=(
            "Cambia los colores del programa. Los temas nuevos vienen en archivos .npt (NumPad Theme), "
            "cifrados y protegidos contra daños.")).grid(row=1, column=0, sticky="w")
        ttk.Button(head, text="⬆ Importar tema (.npt)…", style="Accent.TButton",
                   command=self._import).grid(row=0, column=1, rowspan=2, padx=(10, 0))
        ttk.Button(head, text="Abrir carpeta de temas", command=self._open_folder).grid(
            row=0, column=2, rowspan=2, padx=(6, 0))

        # tarjetas con desplazamiento
        wrap = ttk.Frame(t, style="Panel.TFrame")
        wrap.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(1, weight=1)
        self.count_lbl = ttk.Label(wrap, style="Muted.TLabel")
        self.count_lbl.grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.cv = tk.Canvas(wrap, bg=C["panel"], highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=sb.set)
        self.cv.grid(row=1, column=0, sticky="nsew")
        sb.grid(row=1, column=1, sticky="ns")
        self.grid = ttk.Frame(self.cv, style="Panel.TFrame")
        self.cv.create_window(0, 0, window=self.grid, anchor="nw")
        self.grid.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self.cv.bind("<Configure>", lambda e: self._layout())
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.cv.bind(seq, self._wheel)
            self.grid.bind(seq, self._wheel)

        # detalle del tema elegido
        d = ttk.Frame(t, style="Card.TFrame", padding=14)
        d.grid(row=1, column=1, sticky="ns", padx=(14, 0), pady=(12, 0))
        self.big = tk.Canvas(d, width=260, height=150, highlightthickness=0, bd=0, bg=C["panel2"])
        self.big.pack()
        self.d_name = ttk.Label(d, style="Card.TLabel", font=(FONT, BASE + 4, "bold"))
        self.d_name.pack(anchor="w", pady=(10, 0))
        self.d_sub = ttk.Label(d, style="CardMuted.TLabel")
        self.d_sub.pack(anchor="w")
        self.d_status = tk.Label(d, font=(FONT, BASE - 1), justify="left", anchor="w", wraplength=250,
                                 padx=10, pady=8)
        self.d_status.pack(fill="x", pady=(10, 0))
        self.d_dots = tk.Canvas(d, width=260, height=96, highlightthickness=0, bd=0, bg=C["panel2"])
        self.d_dots.pack(pady=(10, 0))
        self.phone_var = tk.BooleanVar(value=app.cfg["theme"].get("phone", True))
        ttk.Checkbutton(d, text="Usar también en el celular conectado", variable=self.phone_var,
                        style="Card.TCheckbutton", command=self._on_phone).pack(anchor="w", pady=(6, 0))
        bb = ttk.Frame(d, style="Card.TFrame")
        bb.pack(fill="x", pady=(10, 0))
        self.btn_use = ttk.Button(bb, text="Usar este tema", style="Accent.TButton", command=self._use)
        self.btn_use.pack(side="left")
        ttk.Button(bb, text="Exportar .npt", command=self._export).pack(side="left", padx=6)
        self.btn_del = ttk.Button(d, text="Quitar este tema", command=self._remove)
        self.btn_del.pack(anchor="w", pady=(8, 0))

        self.items = []
        self.cards = []
        self.sel = None
        self.refresh()

    # ------------------------------------------------------------ datos
    def refresh(self):
        self.items = themes.all_themes()
        cur = themes.current(self.app.cfg)
        if self.sel is None or not any(self._same(x, self.sel) for x in self.items):
            self.sel = cur
        n_b = sum(1 for x in self.items if x.get("builtin"))
        self.count_lbl.configure(text=f"INCLUIDOS ({n_b}) · IMPORTADOS ({len(self.items) - n_b})")
        for w in self.grid.winfo_children():
            w.destroy()
        self.cards = []
        for th in self.items:
            self.cards.append(self._card(th))
        self._layout()
        self._paint()

    @staticmethod
    def _same(a, b):
        return a["name"] == b["name"] and a.get("file", "") == b.get("file", "")

    def _card(self, th):
        f = tk.Frame(self.grid, bg=C["panel2"], highlightthickness=2, cursor="hand2")
        pv = tk.Canvas(f, width=self.CARD_W, height=self.CARD_H, highlightthickness=0, bd=0, bg=C["panel2"])
        pv.pack(padx=6, pady=(6, 4))
        draw_preview(pv, th["colors"], self.CARD_W, self.CARD_H)
        row = tk.Frame(f, bg=C["panel2"])
        row.pack(fill="x", padx=6)
        tk.Label(row, text=th["name"], bg=C["panel2"], fg=C["text"], font=(FONT, BASE, "bold"),
                 anchor="w").pack(side="left")
        badge = tk.Label(row, font=(FONT, BASE - 3, "bold"), padx=4)
        badge.pack(side="right")
        tk.Label(f, text=("OkumaWsX" if th.get("official") else th.get("author", "")), bg=C["panel2"],
                 fg=C["muted"], font=(FONT, BASE - 2), anchor="w").pack(fill="x", padx=6, pady=(0, 6))
        for w in (f, pv, row) + tuple(row.winfo_children()) + tuple(f.winfo_children()):
            w.bind("<Button-1>", lambda e, th=th: self._pick(th))
            w.bind("<MouseWheel>", self._wheel)
            w.bind("<Button-4>", self._wheel)
            w.bind("<Button-5>", self._wheel)
        return f, badge, th

    def _layout(self):
        width = max(200, self.cv.winfo_width())
        cols = max(1, width // (self.CARD_W + 24))
        for i, (f, _b, _t) in enumerate(self.cards):
            f.grid(row=i // cols, column=i % cols, padx=(0, 8), pady=(0, 8), sticky="n")

    def _wheel(self, e):
        if getattr(e, "num", 0) in (4, 5):
            self.cv.yview_scroll(-2 if e.num == 4 else 2, "units")
        else:
            self.cv.yview_scroll(-1 if e.delta > 0 else 1, "units")

    def _pick(self, th):
        self.sel = th
        self._paint()

    def _paint(self):
        cur = themes.current(self.app.cfg)
        for f, badge, th in self.cards:
            on = self._same(th, self.sel)
            f.configure(highlightbackground=C["accent"] if on else C["line"],
                        highlightcolor=C["accent"] if on else C["line"])
            if self._same(th, cur):
                badge.configure(text="EN USO", bg=C["accent"], fg=C["on_accent"])
            elif not th.get("builtin"):
                badge.configure(text="IMPORTADO", bg=C["key_set"], fg=C["key_set_text"])
            else:
                badge.configure(text="", bg=C["panel2"])
        th = self.sel
        draw_preview(self.big, th["colors"], 260, 150)
        self.d_name.configure(text=th["name"])
        self.d_sub.configure(text=f"por {th.get('author', '')} · versión {th.get('version', '1.0')}")
        if th.get("builtin"):
            txt, col = "✓ Tema incluido con Numpad Macros", C["ok"]
        elif th.get("official"):
            txt, col = "✓ Tema oficial · firmado por OkumaWsX\nArchivo íntegro: no fue modificado.", C["ok"]
        else:
            txt, col = "ⓘ Tema de la comunidad\nArchivo íntegro, pero no está firmado por OkumaWsX.", C["warn"]
        if themes.supports_alpha(th):
            txt += "\nAdmite transparencia."
        self.d_status.configure(text=txt, fg=C["text"], bg=self._tint(col),
                                highlightthickness=1, highlightbackground=col)
        cv = self.d_dots
        cv.delete("all")
        for i, (k, name) in enumerate(DOTS):
            x = 22 + (i % 6) * 43
            y = 16 + (i // 6) * 48
            cv.create_oval(x - 13, y - 13, x + 13, y + 13, fill=th["colors"].get(k, "#000000"), outline=C["line"])
            cv.create_text(x, y + 22, text=name, fill=C["muted"], font=(FONT, BASE - 3))
        self.btn_use.state(["disabled"] if self._same(th, cur) else ["!disabled"])
        if th.get("builtin"):
            self.btn_del.pack_forget()
        elif not self.btn_del.winfo_ismapped():
            self.btn_del.pack(anchor="w", pady=(8, 0))

    @staticmethod
    def _tint(col):
        from .theme import mix
        return mix(col, C["panel2"], .85)

    # ------------------------------------------------------------ acciones
    def _use(self):
        th = self.sel
        if not messagebox.askyesno(
                "Usar tema", f"Para aplicar «{th['name']}», Numpad Macros se reiniciará (tarda un par de "
                "segundos). ¿Continuar?", parent=self.t):
            return
        with self.app.engine.lock:
            self.app.cfg["theme"].update(name=th["name"], file=th.get("file", ""))
        self.app._save()
        self.app._restart()

    def _on_phone(self):
        with self.app.engine.lock:
            self.app.cfg["theme"]["phone"] = self.phone_var.get()
        self.app._save()
        self.app._send_theme()

    def _import(self):
        path = filedialog.askopenfilename(parent=self.t, title="Importar tema",
                                          filetypes=[("Tema de Numpad Macros", "*.npt"), ("Todos", "*.*")])
        if path:
            self.import_file(path)

    def import_file(self, path):
        try:
            th = themes.install(path)
        except npt.NptError as e:
            messagebox.showerror("No se pudo importar el tema",
                                 f"{os.path.basename(path)}: {e}.\n\nTu tema actual no se tocó.", parent=self.t)
            return
        except OSError as e:
            messagebox.showerror("No se pudo importar el tema", str(e), parent=self.t)
            return
        who = "Tema oficial, firmado por OkumaWsX." if th["official"] else \
            "Tema de la comunidad: no está firmado por OkumaWsX."
        self.sel = th
        self.refresh()
        if messagebox.askyesno("Tema instalado",
                               f"«{th['name']}» (por {th['author']}) quedó instalado.\n"
                               f"✓ Archivo íntegro.\n{who}\n\n¿Usarlo ahora?", parent=self.t):
            self._use_now(th)

    def _use_now(self, th):
        with self.app.engine.lock:
            self.app.cfg["theme"].update(name=th["name"], file=th.get("file", ""))
        self.app._save()
        self.app._restart()

    def _export(self):
        th = self.sel
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in th["name"]).strip() or "tema"
        path = filedialog.asksaveasfilename(parent=self.t, title="Exportar tema", defaultextension=npt.EXT,
                                            initialfile=safe + npt.EXT,
                                            filetypes=[("Tema de Numpad Macros", "*.npt")])
        if not path:
            return
        try:
            themes.export(th, path)
        except (OSError, npt.NptError) as e:
            messagebox.showerror("No se pudo exportar", str(e), parent=self.t)
            return
        self.app._set_status(f"Tema guardado: {os.path.basename(path)}")

    def _remove(self):
        th = self.sel
        if th.get("builtin"):
            return
        if not messagebox.askyesno("Quitar tema", f"¿Quitar «{th['name']}» de tus temas?", parent=self.t):
            return
        themes.remove(th)
        self.sel = None
        self.refresh()

    def _open_folder(self):
        os.makedirs(themes.themes_dir(), exist_ok=True)
        self.app._open(themes.themes_dir())
