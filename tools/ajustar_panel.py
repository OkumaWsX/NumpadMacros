# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Editor visual de los recuadros de teclas (herramienta de desarrollo, no es parte de la app).

Edita dos recuadros: las teclas virtuales (5 × 6) y el numpad (4 × 5). Los dos funcionan como el
modelo de caja de CSS (y el panel «Box model» del inspector del navegador):

    position  dónde va el recuadro en el panel: izquierda, centro o derecha
    margin    espacio FUERA del recuadro (arriba, derecha, abajo, izquierda)
    border    grosor del borde del recuadro
    padding   espacio entre el borde y las teclas (arriba, derecha, abajo, izquierda)
    content   la rejilla de teclas: lado máximo/mínimo y separación

Abre Numpad Macros con una COPIA de tu configuración (no toca la original ni el numpad, el
celular, el audio o la bandeja) y resalta las cuatro capas sobre el panel, con los colores del
inspector. Se edita:
  - en el diagrama de cajas: arrastra un número a izquierda/derecha, usa la rueda del mouse o
    haz doble clic para escribirlo;
  - sobre el panel: arrastra las manijas de padding (verdes), la de tamaño de tecla (azul), la de
    separación (celeste) y las franjas de margin (naranjas).
«Guardar en el código» escribe los valores de los dos recuadros en npm/gui.py
(V_MARGIN, V_BORDER, … para las virtuales; N_MARGIN, N_BORDER, … para el numpad).

    .venv-build/bin/python tools/ajustar_panel.py
"""
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUI_PY = os.path.join(ROOT, "npm", "gui.py")


def _copy_config():
    """Copia la configuración real a una carpeta temporal y la usa en vez de la original."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    src = os.path.join(base, "NumpadMacros")
    tmp = tempfile.mkdtemp(prefix="ajustar-panel-")
    if os.path.isdir(src):
        shutil.copytree(src, os.path.join(tmp, "NumpadMacros"),
                        ignore=shutil.ignore_patterns("instancia.lock", "*.log"))
    os.environ["XDG_CONFIG_HOME"] = tmp
    return tmp


TMP = _copy_config()
sys.path.insert(0, ROOT)

import tkinter as tk  # noqa: E402
from tkinter import messagebox, simpledialog, ttk  # noqa: E402

from npm import gui  # noqa: E402
from npm.remote import RemoteServer  # noqa: E402

# Sin numpad, celular, audio, bandeja ni actualizaciones: solo la ventana
for _name in ("_start_backend", "_setup_tray", "_apply_audio_async", "_check_updates",
              "_startup_news", "_queue_loudness"):
    setattr(gui.App, _name, lambda self, *a, **k: None)
RemoteServer.start = lambda self, *a, **k: None

# Las mismas propiedades para los dos recuadros; en gui.py llevan el prefijo del recuadro
NAMES = ("MARGIN", "BORDER", "PADDING", "MAX", "MIN", "GAP_DIV", "ALIGN")
LIMITS = {"MARGIN": (0, 120), "BORDER": (0, 20), "PADDING": (0, 80),
          "MAX": (24, 200), "MIN": (12, 120), "GAP_DIV": (2, 30)}
# Cada recuadro: prefijo en gui.py, vista del panel, lienzo, columnas × filas y sus medidas actuales
TARGETS = {
    "virt": dict(prefix="V_", title="Teclas virtuales", css=".teclas-virtuales", view="virt",
                 canvas="virt_canvas", cols=5, rows=6, unit="VUNIT", gap="VGAP",
                 pad="VPAD", border="VBORDER", margin="VMARGIN"),
    "numpad": dict(prefix="N_", title="Numpad", css=".numpad", view="numpad",
                   canvas="canvas", cols=4, rows=5, unit="UNIT", gap="GAP",
                   pad="NPAD", border="NBORDER", margin="NMARGIN"),
}
SIDES = ("arriba", "derecha", "abajo", "izquierda")
# colores del inspector del navegador
COL = {"margin": "#f9cc9d", "border": "#fbe39b", "padding": "#c3d08b", "content": "#8cb6c0"}
INK = "#222"
HANDLE = 6

TAMANOS = [("Tu ventana", 1550, 950), ("1189×826", 1189, 826), ("1000×660", 1000, 660),
           ("1366×768", 1366, 768), ("1920×1040", 1920, 1040)]


# ---------------------------------------------------------------- leer y guardar npm/gui.py
def _fmt(v):
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, tuple):
        return "(" + ", ".join(str(int(x)) for x in v) + ")"
    return str(int(v))


def leer_todo():
    """Los valores de los dos recuadros, con su nombre real de gui.py."""
    return {t["prefix"] + n: getattr(gui.App, t["prefix"] + n) for t in TARGETS.values() for n in NAMES}


def guardar_codigo(values):
    with open(GUI_PY, encoding="utf-8") as f:
        text = f.read()
    for attr, v in values.items():
        new = _fmt(v)
        pat = re.compile(rf"^(    {attr} = )(.+?)(\s+#.*)?$", re.M)
        m = pat.search(text)
        if not m:
            raise RuntimeError(f"No encontré {attr} en npm/gui.py")
        old_len = len(m.group(2))
        comment = m.group(3) or ""
        if comment:                       # mantener el comentario alineado
            spaces = len(comment) - len(comment.lstrip())
            comment = " " * max(2, spaces + old_len - len(new)) + comment.lstrip()
        text = text[:m.start()] + m.group(1) + new + comment + text[m.end():]
    with open(GUI_PY, "w", encoding="utf-8") as f:
        f.write(text)


def css(selector, v, cols, rows):
    """Los valores escritos como una regla de CSS (para leerlos de un vistazo)."""
    def sides(t):
        t = list(t)
        if len(set(t)) == 1:
            return f"{t[0]}px"
        if t[0] == t[2] and t[1] == t[3]:
            return f"{t[0]}px {t[1]}px"
        return " ".join(f"{x}px" for x in t)
    just = {"left": "start", "right": "end"}.get(v["ALIGN"], "center")
    return (f"{selector} {{\n"
            f"  justify-self: {just};   /* position */\n"
            f"  margin: {sides(v['MARGIN'])};\n"
            f"  border: {v['BORDER']}px solid;\n"
            f"  padding: {sides(v['PADDING'])};\n"
            f"  /* content: {cols} × {rows} teclas */\n"
            f"  --tecla: clamp({v['MIN']}px, auto, {v['MAX']}px);\n"
            f"  gap: calc(var(--tecla) / {v['GAP_DIV']});\n"
            "}")


class Editor:
    def __init__(self, root, app):
        self.root, self.app = root, app
        self.saved = leer_todo()
        self.drag = None
        self.tgt = "virt"
        self.linked = {"MARGIN": tk.BooleanVar(value=False), "PADDING": tk.BooleanVar(value=True)}
        w = tk.Toplevel(root)
        self.w = w
        w.title("Ajustar panel · modelo de caja")
        w.attributes("-topmost", True)
        w.protocol("WM_DELETE_WINDOW", self.salir)
        f = ttk.Frame(w, padding=12)
        f.pack(fill="both", expand=True)

        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Label(top, text="Recuadro:", font=("TkDefaultFont", 12, "bold")).pack(side="left")
        self.tgt_var = tk.StringVar(value=self.tgt)
        for key, t in TARGETS.items():
            ttk.Radiobutton(top, text=t["title"], value=key, variable=self.tgt_var,
                            command=lambda: self.elegir(self.tgt_var.get())).pack(side="left", padx=6)
        ttk.Label(f, foreground="gray", text="Arrastra un número, usa la rueda o haz doble clic para escribirlo.").pack(
            anchor="w", pady=(4, 0))
        self.box = tk.Canvas(f, width=520, height=360, bg="#2b2b2b", highlightthickness=0)
        self.box.pack(pady=(8, 4))
        self.box.bind("<ButtonPress-1>", self._box_press)
        self.box.bind("<B1-Motion>", self._box_drag)
        self.box.bind("<ButtonRelease-1>", lambda e: setattr(self, "drag", None))
        self.box.bind("<Double-Button-1>", self._box_type)
        self.box.bind("<MouseWheel>", self._box_wheel)
        self.box.bind("<Button-4>", lambda e: self._box_wheel(e, 1))
        self.box.bind("<Button-5>", lambda e: self._box_wheel(e, -1))

        opt = ttk.Frame(f)
        opt.pack(fill="x", pady=(4, 0))
        ttk.Checkbutton(opt, text="margin: los 4 lados iguales", variable=self.linked["MARGIN"]).pack(side="left")
        ttk.Checkbutton(opt, text="padding: los 4 lados iguales", variable=self.linked["PADDING"]).pack(
            side="left", padx=10)
        pos = ttk.Frame(f)
        pos.pack(fill="x", pady=(6, 0))
        ttk.Label(pos, text="position:").pack(side="left")
        self.align = tk.StringVar(value=self.get("ALIGN"))
        for val, txt in (("left", "izquierda"), ("center", "centro"), ("right", "derecha")):
            ttk.Radiobutton(pos, text=txt, value=val, variable=self.align,
                            command=lambda: self._set("ALIGN", self.align.get())).pack(side="left", padx=4)
        self.overlay_on = tk.BooleanVar(value=True)
        ttk.Checkbutton(pos, text="resaltar sobre el panel", variable=self.overlay_on,
                        command=self.overlay).pack(side="right")

        ttk.Separator(f).pack(fill="x", pady=10)
        tb = ttk.Frame(f)
        tb.pack(fill="x")
        ttk.Label(tb, text="Ventana:").grid(row=0, column=0, sticky="w")
        for i, (txt, ww, hh) in enumerate(TAMANOS):
            ttk.Button(tb, text=txt, command=lambda a=ww, b=hh: self.tamano(a, b)).grid(
                row=i // 3, column=1 + i % 3, padx=2, pady=2, sticky="ew")
        sb = ttk.Frame(f)
        sb.pack(fill="x", pady=(4, 0))
        self.sw, self.sh = tk.IntVar(value=TAMANOS[0][1]), tk.IntVar(value=TAMANOS[0][2])
        ttk.Spinbox(sb, from_=800, to=4000, width=6, textvariable=self.sw).pack(side="left")
        ttk.Label(sb, text="×").pack(side="left", padx=4)
        ttk.Spinbox(sb, from_=500, to=3000, width=6, textvariable=self.sh).pack(side="left")
        ttk.Button(sb, text="Aplicar", command=lambda: self.tamano(self.sw.get(), self.sh.get())).pack(
            side="left", padx=6)

        ttk.Separator(f).pack(fill="x", pady=10)
        info = ttk.Frame(f)
        info.pack(fill="x")
        self.info = tk.Label(info, justify="left", anchor="nw", font=("TkFixedFont", 9))
        self.info.pack(side="left", fill="y")
        self.css = tk.Label(info, justify="left", anchor="nw", font=("TkFixedFont", 9), fg="#555")
        self.css.pack(side="left", padx=(16, 0), fill="y")
        bb = ttk.Frame(f)
        bb.pack(fill="x", pady=(12, 0))
        ttk.Button(bb, text="Guardar en el código", command=self.guardar).pack(side="left")
        ttk.Button(bb, text="Volver a lo guardado", command=self.restablecer).pack(side="left", padx=6)
        ttk.Button(bb, text="Salir", command=self.salir).pack(side="right")

        self._setup_panel_edit()
        self.tamano(*TAMANOS[0][1:])
        self.elegir("virt")
        self._loop()

    # ================================================================ recuadro elegido
    @property
    def T(self):
        return TARGETS[self.tgt]

    def get(self, name, tgt=None):
        return getattr(gui.App, TARGETS[tgt or self.tgt]["prefix"] + name)

    def valores(self, tgt=None):
        return {n: self.get(n, tgt) for n in NAMES}

    def m(self, key):
        """Medida actual del recuadro elegido en la app (lado, separación, padding…)."""
        return getattr(self.app, self.T[key])

    def elegir(self, tgt):
        """Edita el recuadro de las teclas virtuales o el del numpad (y lo muestra en el panel)."""
        self.tgt = tgt
        self.tgt_var.set(tgt)
        self.align.set(self.get("ALIGN"))
        self.app._set_view(self.T["view"])
        self.app._refit_soon()
        for t in TARGETS.values():
            getattr(self.app, t["canvas"]).delete("edit")
        self.overlay()
        self.draw_box()

    # ================================================================ valores
    def _set(self, name, value, side=None):
        """Cambia un valor (side = 0..3 para margin/padding) y redibuja la app."""
        if name == "ALIGN":
            new = value
        else:
            lo, hi = LIMITS[name]
            v = int(round(min(hi, max(lo, value))))
            if name in ("MARGIN", "PADDING"):
                cur = list(self.get(name))
                if self.linked[name].get() or side is None:
                    cur = [v] * 4
                else:
                    cur[side] = v
                new = tuple(cur)
            else:
                new = v
        if self.get(name) == new:
            return
        p = self.T["prefix"]
        setattr(gui.App, p + name, new)
        if name == "MIN" and self.get("MAX") < new:
            setattr(gui.App, p + "MAX", new)
        if name == "MAX" and self.get("MIN") > new:
            setattr(gui.App, p + "MIN", new)
        self.app._refit_soon()
        self.draw_box()

    # ================================================================ diagrama de cajas
    def draw_box(self):
        cv = self.box
        cv.delete("all")
        v = self.valores()
        W, H = int(cv.cget("width")), int(cv.cget("height"))
        self.fields = []            # (x0, y0, x1, y1, nombre, lado)

        def layer(x0, y0, x1, y1, col, title):
            cv.create_rectangle(x0, y0, x1, y1, fill=col, outline="#000", dash=(3, 2))
            cv.create_text(x0 + 6, y0 + 4, text=title, anchor="nw", fill=INK, font=("TkDefaultFont", 8))

        def num(x, y, value, name, side, bold=False):
            t = cv.create_text(x, y, text=str(value), fill=INK,
                               font=("TkDefaultFont", 10, "bold" if bold else "normal"))
            x0, y0, x1, y1 = cv.bbox(t)
            self.fields.append((x0 - 6, y0 - 3, x1 + 6, y1 + 3, name, side))

        boxes = [(8, 8, W - 8, H - 8)]
        for _i in range(3):          # cada capa, un poco más adentro (como en el inspector)
            x0, y0, x1, y1 = boxes[-1]
            boxes.append((x0 + 44, y0 + 30, x1 - 44, y1 - 30))
        layer(*boxes[0], COL["margin"], "margin")
        layer(*boxes[1], COL["border"], "border")
        layer(*boxes[2], COL["padding"], "padding")
        layer(*boxes[3], COL["content"], "")
        for k, name in ((0, "MARGIN"), (2, "PADDING")):
            x0, y0, x1, y1 = boxes[k]
            ix0, iy0, ix1, iy1 = boxes[k + 1]
            vals = v[name]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            num(cx, (y0 + iy0) / 2, vals[0], name, 0)
            num((x1 + ix1) / 2, cy, vals[1], name, 1)
            num(cx, (y1 + iy1) / 2, vals[2], name, 2)
            num((x0 + ix0) / 2, cy, vals[3], name, 3)
        x0, y0, x1, y1 = boxes[1]
        num((x0 + x1) / 2, (y0 + boxes[2][1]) / 2, v["BORDER"], "BORDER", None)
        x0, y0, x1, y1 = boxes[3]
        cx = (x0 + x1) / 2
        t = self.T
        cv.create_text(cx, y0 + 10, text=f"content · {t['cols']} × {t['rows']} teclas", fill=INK,
                       font=("TkDefaultFont", 8, "bold"))
        cv.create_text(cx, y0 + 24, text=f"ahora: tecla {self.m('unit')} px · separación {self.m('gap')} px",
                       fill=INK, font=("TkDefaultFont", 8))
        row = y0 + 50
        for i, (label, name) in enumerate((("mín.", "MIN"), ("máx.", "MAX"), ("lado ÷", "GAP_DIV"))):
            x = x0 + (x1 - x0) * (i + .5) / 3
            cv.create_text(x, row - 8, text=label, fill=INK, font=("TkDefaultFont", 8))
            num(x, row + 8, v[name], name, None, bold=True)

    def _field_at(self, x, y):
        for x0, y0, x1, y1, name, side in self.fields:
            if x0 <= x <= x1 and y0 <= y <= y1:
                return name, side
        return None

    def _cur(self, name, side):
        cur = self.get(name)
        return cur[side] if side is not None else cur

    def _box_press(self, e):
        hit = self._field_at(e.x, e.y)
        if hit:
            self.drag = ("box", *hit, e.x, self._cur(*hit))

    def _box_drag(self, e):
        if not self.drag or self.drag[0] != "box":
            return
        _k, name, side, x0, start = self.drag
        self._set(name, start + (e.x - x0) / 4, side)       # 4 px de mouse = 1 px

    def _box_wheel(self, e, direction=None):
        hit = self._field_at(e.x, e.y)
        if hit:
            step = direction if direction is not None else (1 if e.delta > 0 else -1)
            self._set(hit[0], self._cur(*hit) + step, hit[1])

    def _box_type(self, e):
        hit = self._field_at(e.x, e.y)
        if not hit:
            return
        name, side = hit
        lo, hi = LIMITS[name]
        label = name.lower() + (f" ({SIDES[side]})" if side is not None else "")
        v = simpledialog.askinteger("Ajustar panel", f"{label}:", parent=self.w, minvalue=lo, maxvalue=hi,
                                    initialvalue=self._cur(name, side))
        if v is not None:
            self._set(name, v, side)

    # ================================================================ resaltado y manijas en el panel
    def _setup_panel_edit(self):
        a = self.app
        orig = a._redraw

        def redraw():
            orig()
            self.overlay()
        a._redraw = redraw
        self.bands = {}
        for key, t in TARGETS.items():
            cv = getattr(a, t["canvas"])
            for tag, cursor in (("h_pad0", "sb_v_double_arrow"), ("h_pad2", "sb_v_double_arrow"),
                                ("h_pad1", "sb_h_double_arrow"), ("h_pad3", "sb_h_double_arrow"),
                                ("h_size", "bottom_right_corner"), ("h_gap", "sb_h_double_arrow")):
                cv.tag_bind(tag, "<ButtonPress-1>", lambda e, tg=tag: setattr(self, "drag", ("panel", tg)))
                cv.tag_bind(tag, "<Enter>", lambda e, c=cursor, w=cv: w.configure(cursor=c))
                cv.tag_bind(tag, "<Leave>", lambda e, w=cv: w.configure(cursor="") if not self.drag else None)
            cv.bind("<B1-Motion>", self._panel_drag, add="+")
            cv.bind("<ButtonRelease-1>", self._stop, add="+")
            # margin: cuatro franjas alrededor del recuadro (fuera del lienzo, como en el inspector)
            bands = []
            for side in range(4):
                band = tk.Frame(cv.master, bg=COL["margin"],
                                cursor="sb_v_double_arrow" if side in (0, 2) else "sb_h_double_arrow")
                band.bind("<ButtonPress-1>", lambda e, s=side: setattr(self, "drag", ("margin", s)))
                band.bind("<B1-Motion>", self._margin_drag)
                band.bind("<ButtonRelease-1>", self._stop)
                bands.append(band)
            self.bands[key] = bands

    def _stop(self, _e=None):
        self.drag = None
        getattr(self.app, self.T["canvas"]).configure(cursor="")

    def overlay(self):
        a = self.app
        for key, bands in self.bands.items():
            if key != self.tgt or not self.overlay_on.get():
                for b in bands:
                    b.place_forget()
        cv = getattr(a, self.T["canvas"])
        cv.delete("edit")
        if not (self.overlay_on.get() and a.left_view == self.T["view"]):
            return
        W, H = int(cv.cget("width")), int(cv.cget("height"))
        b = self.m("border")
        pt, pr, pb, pl = self.m("pad")
        ix0, iy0, ix1, iy1 = b, b, W - b, H - b                     # dentro del border
        cx0, cy0, cx1, cy1 = ix0 + pl, iy0 + pt, ix1 - pr, iy1 - pb  # content
        if b:
            cv.create_rectangle(b / 2, b / 2, W - b / 2, H - b / 2, outline=COL["border"], width=b,
                                tags="edit")
        # padding (verde) y content (azul), semitransparentes
        for x0, y0, x1, y1 in ((ix0, iy0, ix1, cy0), (ix0, cy1, ix1, iy1), (ix0, cy0, cx0, cy1), (cx1, cy0, ix1, cy1)):
            if x1 > x0 and y1 > y0:
                cv.create_rectangle(x0, y0, x1, y1, fill=COL["padding"], stipple="gray50", outline="", tags="edit")
        cv.create_rectangle(cx0, cy0, cx1, cy1, outline=COL["content"], width=2, tags="edit")
        u, g = self.m("unit"), self.m("gap")
        cols, rows = self.T["cols"], self.T["rows"]

        def handle(x, y, col, tag, text=None, anchor="w"):
            h = HANDLE
            cv.create_rectangle(x - h, y - h, x + h, y + h, fill=col, outline="#000", tags=("edit", tag))
            if text:
                cv.create_text(x + (h + 3 if anchor == "w" else -h - 3), y, text=text, anchor=anchor,
                               fill=col, font=("TkDefaultFont", 8, "bold"), tags="edit")
        mx, my = (cx0 + cx1) / 2, (cy0 + cy1) / 2
        handle(mx, (iy0 + cy0) / 2, COL["padding"], "h_pad0", f"padding {pt}")
        handle((cx1 + ix1) / 2, my, COL["padding"], "h_pad1")
        handle(mx, (cy1 + iy1) / 2, COL["padding"], "h_pad2")
        handle((ix0 + cx0) / 2, my, COL["padding"], "h_pad3")
        handle(cx0 + cols * u + (cols - 1) * g, cy0 + rows * u + (rows - 1) * g, COL["content"], "h_size",
               f"tecla {u}", "e")
        handle(cx0 + u + g / 2, cy0 + u / 2, "#7fdbff", "h_gap", f"sep. {g}")
        cv.tag_raise("edit")
        self._place_bands()

    def _place_bands(self):
        a = self.app
        if not (self.overlay_on.get() and a.left_view == self.T["view"]):
            return
        cv = getattr(a, self.T["canvas"])
        mt, mr, mb, ml = self.m("margin")
        try:
            x, y = cv.winfo_x(), cv.winfo_y()
            w, h = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        t = 4                        # grosor mínimo para poder agarrarla aunque el margin sea 0
        rects = ((x - ml, y - max(mt, t), w + ml + mr, max(mt, t)),
                 (x + w, y, max(mr, t), h),
                 (x - ml, y + h, w + ml + mr, max(mb, t)),
                 (x - max(ml, t), y, max(ml, t), h))
        for band, (bx, by, bw, bh) in zip(self.bands[self.tgt], rects):
            band.place(x=bx, y=by, width=bw, height=bh)
            band.lift()

    def _panel_drag(self, e):
        if not self.drag or self.drag[0] != "panel":
            return
        a = self.app
        d = a.dpi
        tag = self.drag[1]
        cv = getattr(a, self.T["canvas"])
        W, H = int(cv.cget("width")), int(cv.cget("height"))
        b = self.m("border")
        pt, pr, pb, pl = self.m("pad")
        cols, rows = self.T["cols"], self.T["rows"]
        if tag == "h_pad0":
            self._set("PADDING", (e.y - b) / d, 0)
        elif tag == "h_pad2":
            self._set("PADDING", (H - b - e.y) / d, 2)
        elif tag == "h_pad1":
            self._set("PADDING", (W - b - e.x) / d, 1)
        elif tag == "h_pad3":
            self._set("PADDING", (e.x - b) / d, 3)
        elif tag == "h_size":
            div = self.get("GAP_DIV")
            side = max((e.x - b - pl) / (cols + (cols - 1) / div), (e.y - b - pt) / (rows + (rows - 1) / div))
            self._set("MAX", side / d)
        elif tag == "h_gap":
            gap = max(1, e.x - (b + pl + self.m("unit")))
            self._set("GAP_DIV", self.m("unit") / gap)

    def _margin_drag(self, e):
        if not self.drag or self.drag[0] != "margin":
            return
        side = self.drag[1]
        cv = getattr(self.app, self.T["canvas"])
        x0, y0 = cv.winfo_rootx(), cv.winfo_rooty()
        x1, y1 = x0 + cv.winfo_width(), y0 + cv.winfo_height()
        dist = (y0 - e.y_root, e.x_root - x1, e.y_root - y1, x0 - e.x_root)[side]
        self._set("MARGIN", max(0, dist) / self.app.dpi, side)

    # ================================================================ ventana y medición
    def tamano(self, w, h):
        self.sw.set(w)
        self.sh.set(h)
        self.root.geometry(f"{int(w)}x{int(h)}")
        self.app._refit_soon()

    def _medir(self):
        a = self.app
        lp = a.left_panel
        cv = getattr(a, self.T["canvas"])
        libre = lp.winfo_height() - lp.winfo_reqheight()
        corte_der = max(0, cv.winfo_rootx() + cv.winfo_reqwidth() - (lp.winfo_rootx() + lp.winfo_width() - 16))
        aplastado = max(cv.winfo_reqheight() - cv.winfo_height(),
                        a.row_canvas.winfo_reqheight() - a.row_canvas.winfo_height() if self.tgt == "numpad" else 0)
        ok = libre >= 0 and corte_der == 0 and aplastado <= 0
        lines = [f"ventana     {self.root.winfo_width()} × {self.root.winfo_height()}",
                 f"escala      {a.dpi:.2f}",
                 f"tecla       {self.m('unit')} px",
                 f"separación  {self.m('gap')} px",
                 f"recuadro    {cv.winfo_reqwidth()} × {cv.winfo_reqheight()}",
                 f"libre abajo {libre} px",
                 f"corte der.  {corte_der} px",
                 "✔ entra completo" if ok else "✘ se corta"]
        self.info.configure(text="\n".join(lines), fg="#1a7f37" if ok else "#c62828")
        self.css.configure(text=css(self.T["css"], self.valores(), self.T["cols"], self.T["rows"]))

    def _loop(self):
        try:
            self.root.update_idletasks()
            self._medir()
            if self.drag is None:
                if self.app.left_view != self.T["view"]:     # se cambió de vista en la app
                    self.elegir("virt" if self.app.left_view == "virt" else "numpad")
                self.draw_box()
                self._place_bands()
        except tk.TclError:
            return
        self.root.after(300, self._loop)

    # ================================================================ guardar
    def guardar(self):
        vals = leer_todo()
        try:
            guardar_codigo(vals)
        except Exception as e:
            messagebox.showerror("Ajustar panel", f"No se pudo guardar:\n{e}", parent=self.w)
            return
        self.saved = vals
        txt = "\n\n".join(css(t["css"], self.valores(k), t["cols"], t["rows"]) for k, t in TARGETS.items())
        messagebox.showinfo("Ajustar panel", "Guardado en npm/gui.py:\n\n" + txt
                            + "\n\nRecompila (./compilar.sh) para llevarlo a la app instalada.", parent=self.w)

    def restablecer(self):
        for attr, v in self.saved.items():
            setattr(gui.App, attr, v)
        self.align.set(self.get("ALIGN"))
        self.app._refit_soon()
        self.draw_box()

    def salir(self):
        if leer_todo() != self.saved and not messagebox.askyesno(
                "Ajustar panel", "Hay cambios sin guardar en el código. ¿Salir igual?", parent=self.w):
            return
        try:
            self.root.destroy()
        finally:
            shutil.rmtree(TMP, ignore_errors=True)
            os._exit(0)


def main():
    root = tk.Tk(className="NumpadMacros")
    app = gui.App(root)
    editor = Editor(root, app)
    root.protocol("WM_DELETE_WINDOW", editor.salir)
    root.mainloop()


if __name__ == "__main__":
    main()
