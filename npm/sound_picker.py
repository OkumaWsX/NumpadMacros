# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Selector de sonidos del editor de teclas: vista de lista o de cuadrícula con portadas.

- Lista: nombre (con miniatura de la portada), tipo, duración, volumen medido y cuántas
  teclas lo usan.
- Cuadrícula: portadas (o una onda si el archivo no trae imagen), tamaño ajustable de
  3 a 10 por fila (deslizador o Ctrl + rueda) y botón ▶ para escuchar por los audífonos.
La vista y el tamaño se recuerdan en la configuración (cfg["ui"]["picker"]).
"""
from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from . import aa, covers, library
from .soundboard import title_of
from .theme import BASE, C, FONT

MIN_COLS, MAX_COLS = 3, 10


class SoundPicker:
    def __init__(self, parent, app, on_pick, on_add, label_width=10):
        self.app = app
        self.on_pick = on_pick
        self.on_add = on_add
        self.d = getattr(app, "dpi", 1.0)
        ui = app.cfg.setdefault("ui", {})
        st = ui.setdefault("picker", {})
        self.view = st.get("view", "grid") if st.get("view") in ("grid", "list") else "grid"
        self.cols = max(MIN_COLS, min(MAX_COLS, int(st.get("cols", 6) or 6)))
        self.items: list[dict] = []
        self.current = None                 # ruta normalizada del sonido de la tecla
        self.thumbs: dict = {}              # ruta normalizada → imagen PIL o None
        self.durs: dict = {}
        self._pending: set = set()
        self._jobs: queue.Queue = queue.Queue()
        self._done: queue.Queue = queue.Queue()
        self._worker = None
        self._poll_job = None
        self._redraw_job = None
        self._play_job = None
        self._quiet = False
        self.height = int(260 * self.d)

        f = self.frame = ttk.Frame(parent, style="Panel.TFrame")
        f.columnconfigure(0, weight=1)

        # ---- barra: buscar · lista/cuadrícula · agregar
        bar = ttk.Frame(f, style="Panel.TFrame")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Label(bar, text="Buscar", style="Panel.TLabel", width=label_width).pack(side="left")
        self.q = tk.StringVar()
        ttk.Entry(bar, textvariable=self.q, width=18).pack(side="left")
        self.q.trace_add("write", lambda *_: self.refresh())
        seg = ttk.Frame(bar, style="Panel.TFrame")
        seg.pack(side="left", padx=(10, 0))
        ic = int(round(14 * self.d))
        self.btn_list = ttk.Button(seg, text=" Lista", compound="left", width=-1,
                                   command=lambda: self.set_view("list"))
        self.btn_grid = ttk.Button(seg, text=" Cuadrícula", compound="left", width=-1,
                                   command=lambda: self.set_view("grid"))
        self.btn_list.pack(side="left")
        self.btn_grid.pack(side="left")
        self._icons = {"list_on": aa.list_icon(app.root, ic, C["accent"]), "list_off": aa.list_icon(app.root, ic, C["muted"]),
                       "grid_on": aa.grid_icon(app.root, ic, 2, C["accent"]),
                       "grid_off": aa.grid_icon(app.root, ic, 2, C["muted"])}
        ttk.Button(bar, text="＋ Agregar…", width=-1, command=on_add).pack(side="left", padx=(10, 0))

        # ---- cuerpo: lista (Treeview) o cuadrícula (Canvas)
        self.body = tk.Frame(f, bg=C["panel2"], highlightthickness=1, highlightbackground=C["line"],
                             highlightcolor=C["line"], height=self.height)
        self.body.grid(row=1, column=0, sticky="ew")
        self.body.grid_propagate(False)
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(0, weight=1)
        self.sb = ttk.Scrollbar(self.body, orient="vertical")
        self.sb.grid(row=0, column=1, sticky="ns", padx=(0, 3), pady=4)

        self.cv = tk.Canvas(self.body, bg=C["panel2"], highlightthickness=0, bd=0,
                            yscrollcommand=self.sb.set)
        self.cv.bind("<Configure>", lambda e: self._schedule_redraw())
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.cv.bind(seq, self._on_wheel)
        self.cv.bind("<Button-1>", self._on_click)
        self.cv.bind("<Double-Button-1>", self._on_double)
        self._layout = None

        rh = int(round(38 * self.d))
        s = ttk.Style(app.root)
        s.configure("Pick.Treeview", background=C["panel2"], fieldbackground=C["panel2"], foreground=C["text"],
                    rowheight=rh, borderwidth=0, relief="flat", font=(FONT, BASE),
                    lightcolor=C["panel2"], darkcolor=C["panel2"], bordercolor=C["panel2"])
        s.map("Pick.Treeview", background=[("selected", C["accent_bg"])],
              foreground=[("selected", C["accent"])])
        s.configure("Pick.Treeview.Heading", background=C["panel2"], foreground=C["muted"], relief="flat",
                    borderwidth=0, font=(FONT, BASE - 2, "bold"), padding=(6, 4),
                    lightcolor=C["panel2"], darkcolor=C["panel2"], bordercolor=C["line"])
        s.map("Pick.Treeview.Heading", background=[("active", C["panel2"])])
        s.layout("Pick.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        self.tree = ttk.Treeview(self.body, style="Pick.Treeview", columns=("tipo", "dur", "vol", "teclas"),
                                 show="tree headings", selectmode="browse", yscrollcommand=self.sb.set)
        self.tree.heading("#0", text="NOMBRE", anchor="w")
        for col, txt, w in (("tipo", "TIPO", 60), ("dur", "DURA", 56), ("vol", "VOLUMEN", 92), ("teclas", "TECLAS", 70)):
            self.tree.heading(col, text=txt, anchor="w")
            self.tree.column(col, width=int(w * self.d), stretch=False, anchor="w")
        self.tree.column("#0", width=int(260 * self.d), stretch=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-Button-1>", lambda e: app._test_action())
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.tree.bind(seq, self._tree_wheel)

        # ---- pie: cuántos hay · tamaño de la cuadrícula
        foot = ttk.Frame(f, style="Panel.TFrame")
        foot.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        self.count_lbl = ttk.Label(foot, style="Muted.TLabel")
        self.count_lbl.pack(side="left")
        self.size_box = ttk.Frame(foot, style="Panel.TFrame")
        ttk.Label(self.size_box, text="Tamaño", style="Muted.TLabel").pack(side="left", padx=(0, 6))
        si = int(round(13 * self.d))
        self._icons["more"] = aa.grid_icon(app.root, si, 3, C["muted"])
        self._icons["less"] = aa.grid_icon(app.root, si, 2, C["muted"])
        b1 = ttk.Button(self.size_box, image=self._icons["more"], width=2,
                        command=lambda: self.set_cols(self.cols + 1))
        b1.pack(side="left")
        self.size_var = tk.DoubleVar(value=MIN_COLS + MAX_COLS - self.cols)
        ttk.Scale(self.size_box, from_=MIN_COLS, to=MAX_COLS, variable=self.size_var, length=int(120 * self.d),
                  command=self._on_scale).pack(side="left", padx=6)
        b2 = ttk.Button(self.size_box, image=self._icons["less"], width=2,
                        command=lambda: self.set_cols(self.cols - 1))
        b2.pack(side="left")
        self.size_lbl = ttk.Label(self.size_box, style="Panel.TLabel", width=10)
        self.size_lbl.pack(side="left", padx=(8, 0))

        self.frame.bind("<Destroy>", self._on_destroy, add="+")
        self._apply_view()

    # ------------------------------------------------------------------ público
    def grid(self, **kw):
        self.frame.grid(**kw)

    def set_height(self, px):
        px = int(px)
        if px != self.height:
            self.height = px
            self.body.configure(height=px)

    def set_view(self, view):
        if view == self.view:
            return
        self.view = view
        self._remember()
        self._apply_view()
        self.refresh()

    def set_cols(self, n):
        n = max(MIN_COLS, min(MAX_COLS, int(n)))
        if n == self.cols:
            return
        self.cols = n
        self._quiet = True
        self.size_var.set(MIN_COLS + MAX_COLS - n)
        self._quiet = False
        self.size_lbl.configure(text=f"{n} por fila")
        self._remember()
        self._schedule_redraw()

    def refresh(self, current=None):
        """Vuelve a llenar con la biblioteca (respetando lo buscado)."""
        if current is not None:
            if current != self.current:
                self._reveal = True               # mostrar el elegido al dibujar
            self.current = current
        self.items = library.search(self.app.cfg, self.q.get())
        self.usage = library.usage(self.app.cfg)
        n = len(self.items)
        total = len(self.app.cfg.get("library", []))
        self.count_lbl.configure(text=("Biblioteca vacía: usa «＋ Agregar archivos…»" if not total else
                                       f"{n} sonido" + ("" if n == 1 else "s") +
                                       (f" de {total}" if n != total else "")))
        for it in self.items:
            self._want(it["path"])
        if self.view == "list":
            self._fill_tree()
        else:
            self._schedule_redraw(0)

    # ------------------------------------------------------------------ vista
    def _remember(self):
        with self.app.engine.lock:
            self.app.cfg.setdefault("ui", {})["picker"] = {"view": self.view, "cols": self.cols}
        self.app._save_later()

    def _apply_view(self):
        on = {"background": C["accent_bg"], "foreground": C["accent"]}
        s = ttk.Style(self.app.root)
        s.configure("SegOn.TButton", background=on["background"], foreground=on["foreground"],
                    lightcolor=on["background"], darkcolor=on["background"], bordercolor=C["line"],
                    font=(FONT, BASE - 1, "bold"), padding=(10, 5))
        s.map("SegOn.TButton", background=[("active", on["background"])])
        s.configure("Seg.TButton", foreground=C["muted"], font=(FONT, BASE - 1), padding=(10, 5))
        grid = self.view == "grid"
        self.btn_grid.configure(style="SegOn.TButton" if grid else "Seg.TButton",
                                image=self._icons["grid_on" if grid else "grid_off"])
        self.btn_list.configure(style="Seg.TButton" if grid else "SegOn.TButton",
                                image=self._icons["list_off" if grid else "list_on"])
        if grid:
            self.tree.grid_remove()
            self.cv.grid(row=0, column=0, sticky="nsew")
            self.sb.configure(command=self.cv.yview)
            self.cv.configure(yscrollcommand=self.sb.set)
            self.size_box.pack(side="right")
            self.size_lbl.configure(text=f"{self.cols} por fila")
        else:
            self.cv.grid_remove()
            self.tree.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=4)
            self.sb.configure(command=self.tree.yview)
            self.size_box.pack_forget()

    def _on_scale(self, _v):
        if self._quiet:
            return
        self.set_cols(round(MIN_COLS + MAX_COLS - self.size_var.get()))

    # ------------------------------------------------------------------ portadas (en otro hilo)
    def _want(self, path):
        key = library.norm(path)
        if key in self.thumbs or key in self._pending:
            return
        self._pending.add(key)
        self._jobs.put((key, path))
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._work, name="portadas", daemon=True)
            self._worker.start()
        if self._poll_job is None:
            self._poll_job = self.frame.after(120, self._poll)

    def _work(self):
        cache = SoundPicker._shared
        while True:
            try:
                key, path = self._jobs.get(timeout=1.0)
            except queue.Empty:
                return
            try:
                st = os.stat(path)
                stamp = (st.st_mtime, st.st_size)
            except OSError:
                stamp = None
            hit = cache.get(key)
            if hit and hit[0] == stamp:
                img, dur = hit[1], hit[2]
            else:
                img = covers.cover_image(path, 256) if stamp else None
                dur = covers.duration(path) if stamp else None
                cache[key] = (stamp, img, dur)
            self._done.put((key, img, dur))

    _shared: dict = {}                     # caché entre selectores (mismo proceso)

    def _poll(self):
        self._poll_job = None
        got = False
        try:
            while True:
                key, img, dur = self._done.get_nowait()
                self.thumbs[key] = img
                self.durs[key] = dur
                self._pending.discard(key)
                got = True
        except queue.Empty:
            pass
        if got:
            if self.view == "list":
                self._fill_tree(keep=True)
            else:
                self._schedule_redraw(60)
        if self._pending:
            try:
                self._poll_job = self.frame.after(150, self._poll)
            except tk.TclError:
                pass

    def _on_destroy(self, e):
        if e.widget is not self.frame:
            return
        for job in (self._poll_job, self._redraw_job, self._play_job):
            if job:
                try:
                    self.frame.after_cancel(job)
                except tk.TclError:
                    pass

    # ------------------------------------------------------------------ lista
    def _meta(self, it):
        key = library.norm(it["path"])
        ext = os.path.splitext(it["path"])[1].lstrip(".").upper() or "?"
        dur = covers.fmt_duration(self.durs.get(key)) if key in self.durs else "…"
        lufs = it.get("lufs")
        vol = f"{lufs:.1f} LUFS".replace(".", ",") if isinstance(lufs, (int, float)) else "—"
        n = self.usage.get(key, 0)
        keys = "—" if not n else f"{n} tecla" + ("" if n == 1 else "s")
        return key, ext, dur, vol, keys

    def _fill_tree(self, keep=False):
        t = self.tree
        top = t.yview()[0] if keep else None
        t.delete(*t.get_children())
        ts = int(round(30 * self.d))
        ph = aa.wave_icon(self.app.root, int(ts * .7), int(ts * .42), C["muted"])
        self._tree_imgs = []
        sel = None
        for i, it in enumerate(self.items):
            key, ext, dur, vol, keys = self._meta(it)
            pil = self.thumbs.get(key)
            img = aa.rounded_image(self.app.root, ("t", key), pil, ts, max(3, ts // 6)) if pil else ph
            if img is not None:
                self._tree_imgs.append(img)
            warn = "⚠ " if not os.path.isfile(it["path"]) else ""
            iid = str(i)
            t.insert("", "end", iid=iid, text="  " + warn + it["title"], image=img or "",
                     values=(ext, dur, vol, keys))
            if key == self.current:
                sel = iid
        self._quiet = True
        if sel is not None:
            t.selection_set(sel)
            if not keep:
                t.see(sel)
        else:
            t.selection_remove(t.selection())
        self._quiet = False
        if top is not None:
            t.yview_moveto(top)

    def _on_tree_select(self, _e=None):
        if self._quiet:
            return
        sel = self.tree.selection()
        if not sel:
            return
        i = int(sel[0])
        if i < len(self.items):
            self._choose(self.items[i])

    def _tree_wheel(self, e):
        n = -1 if (getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0) else 1
        self.tree.yview_scroll(n * 2, "units")
        return "break"

    # ------------------------------------------------------------------ cuadrícula
    def _schedule_redraw(self, delay=30):
        if self._redraw_job:
            try:
                self.frame.after_cancel(self._redraw_job)
            except tk.TclError:
                pass
        try:
            self._redraw_job = self.frame.after(delay, self._draw_grid)
        except tk.TclError:
            pass

    def _fonts(self):
        px = {3: 15, 4: 14, 5: 14, 6: 13, 7: 13, 8: 12, 9: 12, 10: 12}[self.cols]
        cache = self.__dict__.setdefault("_fcache", {})
        if px not in cache:
            cache[px] = (tkfont.Font(root=self.app.root, family=FONT, size=-px, weight="bold"),
                         tkfont.Font(root=self.app.root, family=FONT, size=-11))
        return cache[px]

    def _draw_grid(self):
        self._redraw_job = None
        if self.view != "grid":
            return
        cv = self.cv
        try:
            W = cv.winfo_width()
        except tk.TclError:
            return
        if W < 50:
            self._schedule_redraw(80)
            return
        top = cv.yview()[0]
        cv.delete("all")
        self._badges = {}
        d = self.d
        pad = int(12 * d)
        gap = int((9 if self.cols >= 8 else 12) * d)
        cell = int((W - 2 * pad - gap * (self.cols - 1)) / self.cols)
        r = max(4, int(cell * .07))
        tf, mf = self._fonts()
        lh = tf.metrics("linespace")
        show_meta = self.cols <= 8
        extra = int(8 * d) + 2 * lh + (mf.metrics("linespace") + 2 if show_meta else 0)
        # con pocas por fila, cada tarjeta entera (portada + nombre) debe caber en lo visible
        cell = max(24, min(cell, int(self.height - 2 * pad - extra - 2), int(220 * d)))
        card_h = cell + extra
        root = self.app.root
        y = pad
        for i, it in enumerate(self.items):
            col = i % self.cols
            if col == 0 and i:
                y += card_h + gap
            x = pad + col * (cell + gap)
            key, ext, dur, _vol, _keys = self._meta(it)
            selected = key == self.current
            tag = f"c{i}"
            if selected:
                ring = aa.key_shape(root, cell + 8, cell + 8, r + 4, C["accent"], C["accent"], 0)
                inner = aa.key_shape(root, cell + 4, cell + 4, r + 2, C["panel2"], C["panel2"], 0)
                if ring is not None:
                    cv.create_image(x - 4, y - 4, image=ring, anchor="nw", tags=(tag,))
                    cv.create_image(x - 2, y - 2, image=inner, anchor="nw", tags=(tag,))
            pil = self.thumbs.get(key)
            img = aa.rounded_image(root, ("g", key), pil, cell, r) if pil else None
            if img is not None:
                cv.create_image(x, y, image=img, anchor="nw", tags=(tag,))
            else:
                bg = aa.key_shape(root, cell, cell, r, C["key"], C["line"], 1)
                if bg is not None:
                    cv.create_image(x, y, image=bg, anchor="nw", tags=(tag,))
                else:
                    cv.create_rectangle(x, y, x + cell, y + cell, fill=C["key"], outline=C["line"], tags=(tag,))
                wv = aa.wave_icon(root, int(cell * .36), int(cell * .2), C["muted"])
                if wv is not None:
                    cv.create_image(x + cell / 2, y + cell * .44, image=wv, tags=(tag,))
                if self.cols <= 8:
                    cv.create_text(x + cell / 2, y + cell * .7, text=ext, fill=C["muted"],
                                   font=(FONT, max(7, BASE - 3), "bold"), tags=(tag,))
                if not os.path.isfile(it["path"]):
                    cv.create_text(x + 8, y + 6, text="⚠", anchor="nw", fill=C["warn"], tags=(tag,))
            if selected:
                bs = max(16, int(cell * .17))
                chk = aa.check_badge(root, bs, C["accent"], C["on_accent"])
                if chk is not None:
                    cv.create_image(x + cell - bs - 5, y + 5, image=chk, anchor="nw", tags=(tag,))
            title = self.app._wrap(it["title"], tf, cell, 2)
            ty = y + cell + int(8 * d)
            cv.create_text(x, ty, text=title, anchor="nw", fill=C["accent"] if selected else C["text"],
                           font=tf, tags=(tag,))
            if show_meta:
                cv.create_text(x, ty + 2 * lh + 2, text=f"{dur} · {ext}", anchor="nw", fill=C["muted"],
                               font=mf, tags=(tag,))
            # botón de escuchar
            ps = max(22, min(34, int(cell * .24)))
            ptag = f"p{i}"
            px, py = x + cell - ps - 6, y + cell - ps - 6
            bid = cv.create_image(px, py, anchor="nw", tags=(ptag,))
            self._badges[i] = (bid, ps, it["path"], (px, py))
        self._layout = (pad, cell, gap, card_h)
        total = (y + card_h + pad) if self.items else pad
        if not self.items:
            cv.create_text(W / 2, 40, text=("Ningún sonido coincide con «" + self.q.get() + "»." if self.q.get()
                                            else "Biblioteca vacía: usa «＋ Agregar archivos…»."),
                           fill=C["muted"], font=(FONT, BASE))
        cv.configure(scrollregion=(0, 0, W, max(total, self.height - 2)))
        cv.yview_moveto(top)
        if getattr(self, "_reveal", False):
            self._reveal = False
            idx = next((i for i, it in enumerate(self.items) if library.norm(it["path"]) == self.current), None)
            if idx is not None and total > 0:
                ry = pad + (idx // self.cols) * (card_h + gap)
                y0, y1 = cv.yview()[0] * total, cv.yview()[1] * total
                if ry < y0 or ry + card_h > y1:
                    cv.yview_moveto(max(0, ry - pad) / total)
        self._paint_badges()

    def _preview_tag(self, path):
        return f"vista-previa|{path}"

    def _paint_badges(self):
        board = self.app.board
        any_playing = False
        for i, (bid, ps, path, _pos) in getattr(self, "_badges", {}).items():
            try:
                playing = board.playing(self._preview_tag(path))
            except Exception:
                playing = False
            any_playing |= playing
            img = aa.play_badge(self.app.root, ps, C["accent"] if playing else C["bg"],
                                C["on_accent"] if playing else C["text"], playing)
            if img is not None:
                try:
                    self.cv.itemconfigure(bid, image=img)
                except tk.TclError:
                    return
        if self._play_job:
            try:
                self.frame.after_cancel(self._play_job)
            except tk.TclError:
                pass
            self._play_job = None
        if any_playing:
            self._play_job = self.frame.after(200, self._paint_badges)

    def _preview(self, path):
        board = self.app.board
        tag = self._preview_tag(path)
        if board.playing(tag):
            board.stop_tag(tag)
        else:
            self.app.engine.preview(path)
            self.app._set_status(f"▶ Escuchando «{title_of(path)}» en tus audífonos")
        self.frame.after(120, self._paint_badges)
        self.frame.after(400, self._paint_badges)
        return "break"

    def _hit(self, e):
        """(índice, ¿botón de escuchar?) bajo el puntero, o (None, False)."""
        if not self._layout:
            return None, False
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        pad, cell, gap, card_h = self._layout
        col = int((x - pad) // (cell + gap))
        row = int((y - pad) // (card_h + gap))
        if col < 0 or col >= self.cols or row < 0:
            return None, False
        cx, cy = pad + col * (cell + gap), pad + row * (card_h + gap)
        if x > cx + cell or y > cy + card_h:
            return None, False
        i = row * self.cols + col
        if i >= len(self.items):
            return None, False
        bid, ps, _p, (px, py) = self._badges.get(i, (None, 0, None, (0, 0)))
        on_play = px <= x <= px + ps and py <= y <= py + ps
        return i, on_play

    def _on_click(self, e):
        i, on_play = self._hit(e)
        if i is None:
            return
        if on_play:
            self._preview(self.items[i]["path"])
        else:
            self._choose(self.items[i])

    def _on_double(self, e):
        i, on_play = self._hit(e)
        if i is not None and not on_play:
            self.app._test_action()

    def _choose(self, item):
        self.current = library.norm(item["path"])
        self.on_pick(item)
        if self.view == "grid":
            self._schedule_redraw(0)

    def _on_wheel(self, e):
        up = getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0
        if e.state & 0x4:                                   # Ctrl + rueda: tamaño
            self.set_cols(self.cols - 1 if up else self.cols + 1)
            return "break"
        self.cv.yview_scroll(-2 if up else 2, "units")
        return "break"
