# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Pestaña «Temas»: los temas instalados y los del catálogo en línea, en una sola vista.

- «Instalados»: los incluidos y los importados (.npt), como siempre.
- «Disponibles para descargar»: los del catálogo (repositorio NumpadMacros-Temas) que aún no
  tienes; se ven translúcidos. Un solo botón: Descargar → progreso (con el mouse encima dice
  «Descargando…» y un clic cancela) → Aplicar → En uso. Si algo falla, nada se instala y el botón
  ofrece «Reintentar».
- Buscador y filtros (origen, instalados/disponibles, estilo, color, extras) y orden; la lógica está
  en theme_filter.py. Con ancho de sobra van arriba; si no, en una columna a la izquierda que se
  puede ocultar. En la ventana mínima el detalle se abre encima de la lista.
- Vista de lista o de cuadrícula con «Tamaño» (2 a 10 por fila), como en el selector de sonidos.
Las descargas, el catálogo y los filtros se guardan en la app (no en la pestaña): siguen aunque la
ventana se vuelva a dibujar al cambiar de tema. La vista, el tamaño y si los filtros están ocultos
se recuerdan en cfg["ui"]["temas_vista"].
"""
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from . import catalogo, npt, sysutil, theme_filter, themes
from . import aa, xbg
from .theme import BASE, C, FONT, mix

DOTS = [("bg", "Fondo"), ("panel", "Panel"), ("panel2", "Panel 2"), ("line", "Línea"), ("text", "Texto"),
        ("muted", "Suave"), ("acc", "Acento"), ("key", "Tecla"), ("key_set", "Asignada"),
        ("key_global", "Global"), ("ok", "Bien"), ("bad", "Error")]
# color de marca de cada red: solo para la inicial de respaldo (sin Pillow o sin el PNG); los íconos van
# a color en assets/redes/ (TikTok y X en blanco, porque su negro no se vería sobre fondo oscuro)
BRAND = {"twitch": "#9146ff", "youtube": "#ff0000", "tiktok": "#ffffff", "x": "#ffffff", "kick": "#53fc18",
         "instagram": "#e4405f", "facebook": "#0866ff", "discord": "#5865f2"}
EXTRA_NAMES = (("imagenes", "Imágenes"), ("gif", "GIF animado"), ("transparencia", "Transparencia"),
               ("degradado", "Degradado"))
_RED_ICONS = {}                # (red, px, claro) -> imagen (se guardan: Tk las borra si nadie las referencia)
AVATAR_PX = 26                 # diámetro del círculo del creador (se escala con el dpi)
_AVATAR_PATHS = {}             # sha256 -> ruta de la foto ya verificada (en memoria: no se repite la descarga)
_AVATAR_BUSY = set()           # sha256 que se están bajando ahora
_AVATAR_FAIL = {}              # sha256 -> cuándo falló (se reintenta pasado un rato, p. ej. sin red)
_AVATAR_IMGS = {}              # (sha256, px, borde) -> imagen del círculo (Tk borra las que nadie referencia)
AVATAR_RETRY = 90              # segundos antes de volver a intentar una foto que falló
FADE = .58                     # cuánto se apaga un tema disponible (no instalado)
CHECK_EVERY = 6 * 3600         # el catálogo se vuelve a consultar solo cada 6 horas


class MFont(tkfont.Font):
    """Una letra que siempre está lista. Si ningún widget la usa, Tk la cierra y cada medida o cada
    texto nuevo la vuelve a abrir (en Linux unos 2–4 ms cada vez): una etiqueta sin mostrar la
    mantiene abierta, y lo ya medido se recuerda. Al cambiar el tamaño de la ventana se miden y
    dibujan cientos de textos y sin esto la pestaña se quedaba atrás."""

    def __init__(self, master, **kw):
        super().__init__(root=master, **kw)
        self._hold = tk.Label(master, font=self)          # nunca se muestra
        self._w, self._m = {}, {}

    def measure(self, text, displayof=None):
        w = self._w.get(text)
        if w is None:
            w = self._w[text] = super().measure(text)
        return w

    def metrics(self, *options, **kw):
        if kw:
            return super().metrics(*options, **kw)
        m = self._m.get(options)
        if m is None:
            m = self._m[options] = super().metrics(*options)
        return m


class FastCanvas(tk.Canvas):
    """Lienzo que crea sus figuras sin el trámite de tkinter (que lee y convierte cada opción): la
    misma llamada a Tk, unas 3 veces más rápida. Al cambiar el tamaño de la ventana las tarjetas se
    vuelven a dibujar en cada cuadro y cada milisegundo cuenta."""

    def _create(self, itemType, args, kw):
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            args = args[0]
        opts = []
        for k, v in kw.items():
            if v is not None:
                opts += ("-" + k.rstrip("_"), v)
        return int(self.tk.call(self._w, "create", itemType, *args, *opts))


def draw_preview(cv, c, w, h):
    """Miniatura del programa pintado con los colores de un tema (ocupa todo el lienzo)."""
    cv.delete("all")
    draw_preview_at(cv, c, 0, 0, w, h)


def draw_preview_at(cv, c, ox, oy, w, h, tags=()):
    """La miniatura en (ox, oy) de un lienzo, sin borrar lo demás."""
    g = lambda k, d="#000000": c.get(k, d)

    def rect(x0, y0, x1, y1, col, outline=""):
        cv.create_rectangle(ox + x0, oy + y0, ox + x1, oy + y1, fill=col, outline=outline, tags=tags)
    rect(0, 0, w, h, g("bg"), g("line"))
    if h < 50:                                  # miniatura chica (vista de lista): solo lo esencial
        p = 3
        rect(p, p, p + w * .3, p + 3, g("text"))
        lw = w * .36
        rect(p, p + 6, p + lw, h - p, g("panel"))
        kw, kh = (lw - 6) / 2, (h - p - (p + 6) - 6) / 2
        for i, col in enumerate((g("key_global"), g("key_set"), g("key"), g("key_set"))):
            x, y = p + 2 + (i % 2) * (kw + 2), p + 8 + (i // 2) * (kh + 2)
            rect(x, y, x + kw, y + kh, col)
        x0 = p + lw + 3
        rect(x0, p + 6, w - p, h - p, g("panel"))
        rect(x0 + 3, p + 9, x0 + 3 + (w - p - x0) * .6, p + 11, g("text"))
        rect(w - p - 3 - (w - p - x0) * .35, h - p - 7, w - p - 3, h - p - 3, g("acc"))
        return
    p = max(4, w // 25)
    rect(p, p, p + w * .28, p + 5, g("text"))
    rect(w - p - w * .14, p, w - p, p + 7, g("ok"))
    top = p + 12
    lw = w * .34
    rect(p, top, p + lw, h - p, g("panel"))
    cols, rows = 3, 3
    kw = (lw - 4 * 3) / cols
    kh = (h - p - top - 4 * 4) / rows
    keys = [g("key_global"), g("key"), g("key"), g("key_set"), g("key_set"), g("key"), g("key"), g("key_set"), g("key")]
    for i, col in enumerate(keys):
        x = p + 3 + (i % cols) * (kw + 3)
        y = top + 4 + (i // cols) * (kh + 4)
        rect(x, y, x + kw, y + kh, col)
    x0 = p + lw + p
    rect(x0, top, w - p, h - p, g("panel"))
    rect(x0 + 6, top + 6, x0 + 6 + (w - p - x0) * .55, top + 10, g("text"))
    rect(x0 + 6, top + 15, x0 + 6 + (w - p - x0) * .8, top + 18, g("muted"))
    rect(x0 + 6, top + 24, w - p - 6, top + 32, g("panel2"))
    rect(w - p - 6 - (w - p - x0) * .3, h - p - 14, w - p - 6, h - p - 5, g("acc"))


# Colores FIJOS de marca del sello ★ CREADOR y de la ficha del creador: no dependen del tema aplicado.
# (oscuro, claro): la variante «claro» es algo más oscura para que se lea sobre fondos claros;
# el tono (dorado / azul / violeta) es siempre el mismo.
CREATOR_BRAND = {
    "creador": {"bg": ("#8B5CF6", "#7C5CD6"), "fg": ("#FFFFFF", "#FFFFFF"),
                "line": ("#8B5CF6", "#7C5CD6"), "cap": ("#A78BFA", "#6D45C9")},
}


def _theme_is_light() -> bool:
    c = C["panel"]
    r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
    return (0.299 * r + 0.587 * g + 0.114 * b) > 140


def brand(kind: str, part: str) -> str:
    """Color de marca ``part`` de ``kind`` (variante clara u oscura según la luminancia del fondo del tema)."""
    return CREATOR_BRAND[kind][part][1 if _theme_is_light() else 0]


def fade(col, t=FADE):
    return mix(col, C["panel"], t)


def faded(colors: dict) -> dict:
    return {k: fade(v) if isinstance(v, str) and v.startswith("#") and len(v) == 7 else v for k, v in colors.items()}


class ActionButton(tk.Canvas):
    """El botón principal del detalle. Cambia de estado en el mismo lugar:
    descargar · bajando (se llena con el progreso) · reintentando · error · aplicar · actualizar · en uso."""
    W, H = 168, 32

    def __init__(self, master, command):
        super().__init__(master, width=self.W, height=self.H, highlightthickness=0, bd=0,
                         bg=C["panel2"], cursor="hand2")
        self.command = command
        self.mode, self.text, self.frac = "descargar", "Descargar", 0.0
        self.hover = False
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))
        self.bind("<Button-1>", lambda e: self.command() if self.mode != "uso" else None)

    def _hover(self, on):
        self.hover = on
        self.draw()

    def set(self, mode, text="", frac=0.0):
        self.mode, self.text, self.frac = mode, text, frac
        self.configure(cursor="arrow" if mode == "uso" else "hand2")
        self.draw()

    def draw(self):
        self.delete("all")
        w, h, m = self.W, self.H, self.mode
        font = (FONT, BASE, "bold")
        if m == "bajando":
            self.create_rectangle(0, 0, w - 1, h - 1, fill=C["accent_bg"], outline=C["accent"])
            if self.frac > 0:
                self.create_rectangle(1, 1, 1 + (w - 2) * self.frac, h - 1, fill=C["accent"], outline="")
            pct = f"{int(self.frac * 100)} %"
            txt = f"Descargando… {pct}" if self.hover else pct
            col = C["on_accent"] if self.frac >= .55 else C["text"]
            self.create_text((w - 16) / 2 if self.hover else w / 2, h / 2, text=txt, fill=col, font=font)
            if self.hover:                            # la X: un clic cancela
                x, y = w - 14, h / 2
                xc = C["on_accent"] if self.frac >= .9 else C["text"]
                self.create_line(x - 4, y - 4, x + 4, y + 4, fill=xc, width=2)
                self.create_line(x - 4, y + 4, x + 4, y - 4, fill=xc, width=2)
            return
        bg, fg, outline = {
            "descargar": (C["accent"], C["on_accent"], C["accent"]),
            "actualizar": (C["accent"], C["on_accent"], C["accent"]),
            "reintentando": (mix(C["warn"], C["panel2"], .8), C["warn"], C["warn"]),
            "error": (C["bad"], "#ffffff", C["bad"]),
            "aplicar": (C["ok"], C["on_ok"], C["ok"]),
            "uso": (C["panel"], C["muted"], C["line"]),
        }[m]
        if self.hover and m in ("descargar", "actualizar", "aplicar", "error"):
            bg = mix(bg, "#ffffff", .12)
        self.create_rectangle(0, 0, w - 1, h - 1, fill=bg, outline=outline)
        if m in ("descargar", "actualizar"):          # flecha de descarga dibujada (no depende de la letra)
            x, y = 20, h / 2 - 1
            self.create_line(x, y - 6, x, y + 3, fill=fg, width=2)
            self.create_polygon(x - 4, y, x + 4, y, x, y + 5, fill=fg, outline=fg)
            self.create_line(x - 6, y + 8, x + 6, y + 8, fill=fg, width=2)
            self.create_text(w / 2 + 10, h / 2, text=self.text, fill=fg, font=font)
        else:
            self.create_text(w / 2, h / 2, text=self.text, fill=fg, font=font)


class FilterView(FastCanvas):
    """Los filtros, dibujados en un lienzo (los widgets anidados dejan restos en XWayland).
    ``column`` False: en una fila sobre la lista; los grupos que no caben pasan a otra línea.
    ``column`` True: la columna de la izquierda (cada grupo con su título; se desplaza con la rueda)."""
    GROUPS = (("origen", "Origen", (("todos", "Todos"), ("oficial", "Oficiales"),
                                      ("creador", "Creadores"), ("comunidad", "Comunidad"))),
              ("mostrar", "Mostrar", (("todos", "Todos"), ("instalados", "Instalados"),
                                      ("disponibles", "Disponibles"), ("actualizar", "Con actualización"))),
              ("estilo", "Estilo", (("todos", "Todos"), ("oscuro", "Oscuro"), ("claro", "Claro"))),
              ("color", "Color", ()),
              ("extras", "Extras", (("imagenes", "Imágenes"), ("gif", "GIF"), ("transparencia", "Transparencia"),
                                    ("degradado", "Degradado"))))

    def __init__(self, master, tab, column=False):
        super().__init__(master, highlightthickness=0, bd=0, bg=C["panel"], width=100, height=30)
        self.tab, self.column, self.d = tab, column, tab.d
        self.f_lbl = MFont(self, font=(FONT, BASE - 3, "bold"))
        self.f_chip = MFont(self, font=(FONT, BASE - 1))
        self.f_on = MFont(self, font=(FONT, BASE - 1, "bold"))
        self.overflow = False                 # (columna) el contenido no cabe a lo alto
        self.on_overflow = None
        self._size = (0, 0)
        self.bind("<Configure>", self._on_resize)
        if column:
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.bind(seq, self._wheel)

    def _on_resize(self, e):
        if (abs(e.width - self._size[0]) >= 2 or self.column and abs(e.height - self._size[1]) >= 2):
            self._size = (e.width, e.height)
            self.draw()

    def _wheel(self, e):
        if not self.overflow:
            return
        if getattr(e, "num", 0) in (4, 5):
            self.yview_scroll(-2 if e.num == 4 else 2, "units")
        else:
            self.yview_scroll(-1 if e.delta > 0 else 1, "units")

    # ---- piezas: cada una es (ancho, función que la dibuja en x, y)
    def _chip(self, key, value, text, on):
        f = self.f_on if on else self.f_chip
        w = f.measure(text) + int(20 * self.d)

        def paint(x, y, h):
            tag = f"f:{key}:{value}"
            fill, line, fg = (C["accent_bg"], C["accent"], C["accent"]) if on else (C["panel2"], C["line"], C["text"])
            self.create_rectangle(x, y, x + w, y + h, fill=fill, outline=line, tags=(tag, "chip"))
            self.create_text(x + w / 2, y + h / 2, text=text, fill=fg, font=f, tags=(tag, "chip"))
            self.tag_bind(tag, "<Button-1>", lambda e: self.tab.set_filter(key, value))
        return w, paint

    def _dot(self, name, on):
        size = int(18 * self.d)
        w = size + int(8 * self.d)

        def paint(x, y, h):
            tag = f"f:color:{name}"
            cx, cy = x + w / 2, y + h / 2
            r = size / 2
            if on:                               # anillo del color elegido
                self.create_oval(cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3, outline=C["accent"], width=2,
                                 tags=(tag, "chip"))
            img = aa.dot(self, size, theme_filter.SWATCH[name], outline=C["line"], width=1)
            if img is not None:
                self.create_image(cx - r, cy - r, image=img, anchor="nw", tags=(tag, "chip"))
            else:
                self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=theme_filter.SWATCH[name], outline=C["line"],
                                 tags=(tag, "chip"))
            # zona de clic un poco más grande que el círculo
            self.create_rectangle(x, y, x + w, y + h, outline="", fill="", tags=(tag, "chip"))
            self.tag_bind(tag, "<Button-1>", lambda e: self.tab.set_filter("color", name))
        return w, paint

    def _pieces(self, key, opts):
        filt = self.tab.filt
        if key == "color":
            return [self._dot(n, filt.get("color") == n) for n in self.tab.color_names()]
        if key == "extras":
            have = filt.get("extras") or []
            return [self._chip(key, v, ("✓ " if v in have else "") + t, v in have) for v, t in opts]
        return [self._chip(key, v, t, filt.get(key, "todos") == v) for v, t in opts]

    def _title(self, key, title):
        filt = self.tab.filt
        if key == "color" and filt.get("color"):
            title += " · " + filt["color"]
        return title.upper()

    def draw(self):
        try:
            self.delete("all")
            W = max(60, self.winfo_width())
        except tk.TclError:
            return
        s = self.d
        h = int(self.f_chip.metrics("linespace") + 10 * s)       # alto de un chip
        gap = int(5 * s)
        on = theme_filter.active(self.tab.filt)
        groups = [(key, self._title(key, title), self._pieces(key, opts)) for key, title, opts in self.GROUPS]
        groups = [g for g in groups if g[2]]
        clear = self._chip("clear", "", "✕ Quitar filtros", False) if on else None
        if not self.column:
            # bloques (título + chips) en líneas: el que no cabe pasa a la siguiente
            blocks = []
            for key, title, pieces in groups:
                tw = self.f_lbl.measure(title) + int(8 * s)
                blocks.append((tw + sum(w for w, _ in pieces) + gap * (len(pieces) - 1), title, tw, pieces))
            if clear:
                blocks.append((clear[0], "", 0, [clear]))
            x = y = 0
            line_h = h + int(8 * s)
            for bw, title, tw, pieces in blocks:
                if x and x + bw > W:
                    x, y = 0, y + line_h
                if title:
                    self.create_text(x, y + h / 2, text=title, anchor="w", fill=C["muted"], font=self.f_lbl)
                px = x + tw
                for w, paint in pieces:
                    paint(px, y, h)
                    px += w + gap
                x += bw + int(20 * s)
            want = y + h + 2
            if abs(int(self.cget("height")) - want) > 1:
                self.configure(height=want)
        else:
            y = 0
            for key, title, pieces in groups:
                self.create_text(0, y, text=title, anchor="nw", fill=C["muted"], font=self.f_lbl)
                y += self.f_lbl.metrics("linespace") + int(5 * s)
                x = 0
                for w, paint in pieces:
                    if x and x + w > W:
                        x, y = 0, y + h + gap
                    paint(x, y, h)
                    x += w + gap
                y += h + int(14 * s)
            if clear:
                clear[1](0, y, h)
                y += h
            self.configure(scrollregion=(0, 0, W, y + 4))
            over = y + 4 > self.winfo_height() > 1
            if over != self.overflow:
                self.overflow = over
                if not over:
                    self.yview_moveto(0)
                if self.on_overflow:
                    self.on_overflow(over)
        self.tag_bind("chip", "<Enter>", lambda e: self.configure(cursor="hand2"))
        self.tag_bind("chip", "<Leave>", lambda e: self.configure(cursor=""))


class ThemesTab:
    CARD_W, CARD_H = 128, 74                # proporción de la miniatura de las tarjetas
    BIG_W, BIG_H, BIG_MIN = 260, 150, 56    # vista previa del detalle (se achica si no cabe)
    SAFE = 8                                # margen de seguridad bajo los botones del detalle
    MIN_COLS, MAX_COLS = 2, 10              # tarjetas por fila (deslizador «Tamaño»)
    MIN_CARD = 112                          # ancho mínimo de una miniatura (más chica no se lee)
    ROW_H = 46                              # alto de una fila en la vista de lista
    FILTER_W, STRIP_W = 214, 26             # columna de filtros y su franja cuando está oculta
    # según el ancho de la pestaña: filtros arriba (≥ TOP_W) o en columna; detalle encima (< OVERLAY_W)
    TOP_W, OVERLAY_W = 1380, 1080
    ORDERS = (("nombre", "Nombre"), ("recientes", "Más recientes"), ("oficiales", "Oficiales primero"))

    def __init__(self, parent, app):
        self.app = app
        self.t = parent
        self.d = d = getattr(app, "dpi", 1.0)
        # lo que sobrevive a que la pestaña se vuelva a dibujar (al cambiar de tema)
        self.cat = app.__dict__.setdefault("theme_catalog", {"cat": catalogo.cached(), "error": "",
                                                              "busy": False, "checked": 0.0, "new": False})
        self.dls = app.__dict__.setdefault("theme_downloads", {})          # id -> Download
        self.filt = app.__dict__.setdefault("theme_filters", theme_filter.new_filters())
        st = app.cfg.setdefault("ui", {}).get("temas_vista") or {}
        self.view = st.get("view") if st.get("view") in ("grid", "list") else "grid"
        try:
            self.cols = max(self.MIN_COLS, min(self.MAX_COLS, int(st.get("cols", 5))))
        except (TypeError, ValueError):
            self.cols = 5
        self.side_hidden = bool(st.get("filtros_ocultos", False))
        self._mode = None                   # ("top" o "side", detalle encima: True/False)
        self._overlay = False               # el detalle está abierto encima de la lista
        self._just_picked = False
        self._q_job = None
        t = parent
        t.columnconfigure(1, weight=1)
        t.rowconfigure(2, weight=1)
        head = ttk.Frame(t, style="Panel.TFrame")
        head.grid(row=0, column=0, columnspan=3, sticky="ew")
        head.columnconfigure(0, weight=1)
        ttk.Label(head, text="Temas", style="H.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(head, style="Muted.TLabel", wraplength=250, justify="left", text=(
            "Cambia los colores del programa. Instalados y disponibles para descargar, en un solo "
            "lugar.")).grid(row=1, column=0, sticky="w")
        ttk.Button(head, text="⬆ Importar tema (.npt)…", style="Accent.TButton",
                   command=self._import).grid(row=0, column=1, rowspan=2, padx=(10, 0))
        ttk.Button(head, text="Abrir carpeta de temas", command=self._open_folder).grid(
            row=0, column=2, rowspan=2, padx=(6, 0))
        # crear temas propios: abre el Estudio (o sugiere instalarlo si no está)
        ttk.Button(head, text="🎨 Crear o editar temas…", command=app.open_estudio).grid(
            row=0, column=3, rowspan=2, padx=(6, 0))
        self.btn_refresh = ttk.Button(head, text="⟳ Actualizar lista", command=lambda: self.fetch(manual=True))
        self.btn_refresh.grid(row=0, column=4, rowspan=2, padx=(6, 0))
        # en esta pestaña el panel de teclas se oculta para ganar espacio; este botón lo muestra
        self.btn_keys = ttk.Button(head, command=app.toggle_theme_keys)
        self.btn_keys.grid(row=0, column=5, rowspan=2, padx=(6, 0))

        # buscador y orden: compartidos por la barra de arriba y la columna de la izquierda
        self.q_var = tk.StringVar(value=self.filt.get("q", ""))
        self.q_var.trace_add("write", lambda *_: self._on_query())
        names = dict(self.ORDERS)
        self.order_var = tk.StringVar(value=names.get(self.filt.get("orden"), "Nombre"))

        def order_box(master):
            cb = ttk.Combobox(master, textvariable=self.order_var, state="readonly", width=16,
                              values=[n for _, n in self.ORDERS])
            cb.bind("<<ComboboxSelected>>", lambda e: self._on_order())
            return cb

        # ---- filtros arriba (ventanas anchas): una fila que se parte en dos si no cabe
        top = self.topbar = ttk.Frame(t, style="Panel.TFrame")
        top.columnconfigure(2, weight=1)
        ttk.Label(top, text="Buscar", style="Panel.TLabel").grid(row=0, column=0, sticky="nw", pady=(4, 0))
        ttk.Entry(top, textvariable=self.q_var, width=20).grid(row=0, column=1, sticky="nw", padx=(6, 18))
        self.fv_top = FilterView(top, self)
        self.fv_top.grid(row=0, column=2, sticky="new")
        ttk.Label(top, text="Ordenar", style="Panel.TLabel").grid(row=0, column=3, sticky="nw", padx=(14, 6),
                                                                  pady=(4, 0))
        order_box(top).grid(row=0, column=4, sticky="ne")

        # ---- filtros en una columna (pantallas chicas), que se puede ocultar
        side = self.side = ttk.Frame(t, style="Panel.TFrame", width=int(self.FILTER_W * d))
        side.grid_propagate(False)
        side.columnconfigure(0, weight=1)
        side.rowconfigure(5, weight=1)
        ttk.Button(side, text="◀ Ocultar filtros", command=lambda: self.set_side_hidden(True)).grid(
            row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(side, text="Buscar (nombre, autor, etiqueta)", style="Muted.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(10, 2))
        ttk.Entry(side, textvariable=self.q_var).grid(row=2, column=0, columnspan=2, sticky="ew")
        ttk.Label(side, text="Ordenar", style="Muted.TLabel").grid(row=3, column=0, columnspan=2, sticky="w",
                                                                   pady=(10, 2))
        order_box(side).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        self.fv_side = FilterView(side, self, column=True)
        self.fv_side.grid(row=5, column=0, sticky="nsew")
        self.side_sb = ttk.Scrollbar(side, orient="vertical", command=self.fv_side.yview)
        self.fv_side.configure(yscrollcommand=self.side_sb.set)
        self.fv_side.on_overflow = lambda over: self.side_sb.grid(row=5, column=1, sticky="ns") if over \
            else self.side_sb.grid_remove()
        # oculta: una franja delgada «▶ FILTROS» que la vuelve a abrir
        self.strip = FastCanvas(t, width=int(self.STRIP_W * d), bg=C["panel2"], highlightthickness=0, bd=0,
                               cursor="hand2")
        self.strip.bind("<Button-1>", lambda e: self.set_side_hidden(False))
        self.strip.bind("<Configure>", lambda e: self._paint_strip())

        # ---- lista o cuadrícula de temas
        wrap = self.wrap = ttk.Frame(t, style="Panel.TFrame")
        wrap.grid(row=2, column=1, sticky="nsew", pady=(10, 0))
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(1, weight=1)
        bar = ttk.Frame(wrap, style="Panel.TFrame")
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self.count_lbl = ttk.Label(bar, style="Muted.TLabel")
        self._build_viewbar(bar)       # primero los botones (pack side=right): tienen prioridad de ancho
        self.count_lbl.pack(side="left", padx=(0, 12))
        self.cv = FastCanvas(wrap, bg=C["panel"], highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self._yview)
        self.cv.configure(yscrollcommand=sb.set)
        self.cv.grid(row=1, column=0, sticky="nsew")
        sb.grid(row=1, column=1, sticky="ns")
        # las tarjetas se dibujan directamente en este lienzo (sin ventanas anidadas, que en algunos
        # sistemas dejan restos de dibujo al moverse)
        self._cv_w = 0
        self._content_h = 0              # alto de lo dibujado (para la rueda y el desplazamiento)
        self._bound = {}                # etiqueta de tarjeta -> tema ya asociado al clic
        self._drawn_part = False        # se dibujó solo lo que se ve (falta el resto)
        self._full_job = None
        self.cv.bind("<Configure>", lambda e: self._on_cv_resize(e.width))
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.cv.bind(seq, self._wheel)

        # detalle del tema elegido: a la derecha o, si no hay ancho, encima de la lista
        self.dbox = tk.Frame(t, bg=C["panel"], bd=0, highlightthickness=0,
                             highlightbackground=C["accent"], highlightcolor=C["accent"])
        d = ttk.Frame(self.dbox, style="Card.TFrame", padding=14)
        d.pack(fill="both", expand=True)
        self.detail = d
        self.big_h = self.BIG_H
        d.bind("<Configure>", lambda e: self._fit_detail(), add="+")
        # (solo encima de la lista) cerrar con ✕, Escape o un clic fuera
        self.d_top = ttk.Frame(d, style="Card.TFrame")
        ttk.Label(self.d_top, text="DETALLE DEL TEMA", style="CardMuted.TLabel",
                  font=(FONT, BASE - 3, "bold")).pack(side="left")
        ttk.Button(self.d_top, text="✕", width=3, command=self._close_overlay).pack(side="right")
        self.big = FastCanvas(d, width=self.BIG_W, height=self.BIG_H, highlightthickness=0, bd=0, bg=C["panel2"])
        self.big.pack()
        self.d_name = ttk.Label(d, style="Card.TLabel", font=(FONT, BASE + 4, "bold"))
        self.d_name.pack(anchor="w", pady=(10, 0))
        self.d_sub = ttk.Label(d, style="CardMuted.TLabel")
        self.d_sub.pack(anchor="w")
        # lo que sigue al nombre: ficha del creador (solo temas de creadores) o recuadro de estado, y
        # «Sobre el tema». Un solo contenedor siempre a la vista; adentro se muestra lo que toca
        self.d_info = tk.Frame(d, bg=C["panel2"], bd=0, highlightthickness=0)
        self.d_info.pack(fill="x")
        self._build_creator_box(self.d_info)
        self.d_status = tk.Label(self.d_info, font=(FONT, BASE - 1), justify="left", anchor="w", wraplength=250,
                                 padx=10, pady=8)
        self._build_about(self.d_info)
        self._chips_hidden = False
        self._note_hidden = False       # la línea de nota de «Sobre el tema» se esconde si falta alto
        self._info_kind = None          # qué partes están a la vista (para no re-empaquetar sin necesidad)
        self.d_dots = tk.Canvas(d, width=260, height=96, highlightthickness=0, bd=0, bg=C["panel2"])
        self.d_dots.pack(pady=(10, 0))
        self.phone_var = tk.BooleanVar(value=app.cfg["theme"].get("phone", True))
        self.phone_chk = ttk.Checkbutton(d, text="Usar también en el celular conectado", variable=self.phone_var,
                                         style="Card.TCheckbutton", command=self._on_phone)
        self.phone_chk.pack(anchor="w", pady=(6, 0))
        self.act = ActionButton(d, self._act)
        self.act.pack(anchor="w", pady=(10, 0))
        # botones secundarios en otra línea: así el panel no cambia de ancho según el estado
        bb = ttk.Frame(d, style="Card.TFrame")
        bb.pack(fill="x", pady=(6, 0))
        self.btn_both = ttk.Button(bb, text="Descargar y aplicar", command=lambda: self._download(apply=True))
        self.btn_export = ttk.Button(bb, text="Exportar .npt", command=self._export)
        self.d_msg = tk.Label(d, font=(FONT, BASE - 2), justify="left", anchor="w", wraplength=250,
                              bg=C["panel2"], fg=C["bad"])
        self.btn_del = ttk.Button(d, text="Quitar este tema", command=self._remove)

        # Escape y el clic fuera cierran el detalle encima (una sola vez por ventana: la pestaña se
        # vuelve a armar al cambiar de tema, la ventana principal no)
        if not getattr(app, "_themes_keys_bound", False):
            app._themes_keys_bound = True
            app.root.bind("<Escape>", lambda e: _tab_call(app, "_on_escape"), add="+")
            app.root.bind("<Button-1>", lambda e: _tab_call(app, "_on_click_anywhere", e), add="+")

        self.items = []                 # [{"th": tema instalado o None, "entry": del catálogo o None, "facts": …}]
        self.shown = []                 # los que pasan los filtros, en orden
        self._cur = None                # el tema en uso (de la lista ya leída: no relee los archivos)
        self._fonts = {"name": MFont(t, font=(FONT, BASE, "bold")), "small": MFont(t, font=(FONT, BASE - 2)),
                       "sec": MFont(t, font=(FONT, BASE - 3, "bold")), "pill": MFont(t, font=(FONT, BASE - 4, "bold")),
                       "msg": MFont(t, font=(FONT, BASE + 1, "bold")), "btn": MFont(t, font=(FONT, BASE - 1, "bold")),
                       "pct": MFont(t, font=(FONT, BASE - 2, "bold")),
                       "chip": MFont(t, font=(FONT, BASE - 3))}
        self.sel = None                 # el elemento elegido (uno de self.items)
        self._fetch_q = queue.Queue()
        self._av_q = queue.Queue()      # fotos de creador que ya llegaron (sha256), para el hilo de Tk
        self._av_want = None            # la foto que el detalle espera / muestra (sha256) y cómo se pinta
        t.bind("<Configure>", lambda e: self._on_tab_resize(e.width) if e.widget is t else None, add="+")
        self._on_tab_resize(t.winfo_width())
        self.refresh(keep=app.__dict__.pop("_theme_sel_keep", None))
        self.paint_header()
        t.after(150, self._poll)
        if time.time() - self.cat["checked"] > CHECK_EVERY and not self.cat["busy"]:
            t.after(400, self.fetch)

    # ------------------------------------------------------------ catálogo
    def fetch(self, manual=False):
        """Consulta el catálogo en segundo plano (sin internet se usa la lista guardada)."""
        if self.cat["busy"]:
            return
        self.cat["busy"] = True
        self._paint_count()

        def job():
            try:
                cat = catalogo.fetch()
                self.cat.update(cat=cat, error="")
            except catalogo.CatalogError as e:
                self.cat["error"] = str(e)
            finally:
                self.cat.update(busy=False, checked=time.time(), new=True)
        threading.Thread(target=job, daemon=True).start()

    def _paint_count(self):
        n = len(self.shown)
        total = len(self.items)
        txt = f"{total} tema" + ("" if total == 1 else "s") if n == total else f"{n} de {total} temas"
        if self.cat["busy"]:
            txt += " · Buscando temas disponibles…"
        elif self.cat["error"] and self.cat["cat"]:
            txt += f" · Sin conexión: lista guardada {_ago(self.cat['cat'].get('obtenido', 0))}"
        elif self.cat["error"]:
            txt += " · Sin conexión: no se pudo ver el catálogo de temas"
        try:
            self.count_lbl.configure(text=txt)
            self._fit_viewbar()
            self.btn_refresh.state(["disabled"] if self.cat["busy"] else ["!disabled"])
        except tk.TclError:
            pass

    # ------------------------------------------------------------ datos
    def refresh(self, keep=None):
        """Vuelve a armar la lista. ``keep``: el elemento a dejar elegido (nombre de tema o id del catálogo)."""
        installed = themes.all_themes()
        items = [{"th": th, "entry": None} for th in installed]
        imported = [th for th in installed if not th.get("builtin")]
        for e in catalogo.entries(self.cat["cat"]):
            th = catalogo.installed_for(e, imported)
            if th is not None:                       # ya lo tienes: va arriba, con su entrada (actualizaciones)
                for it in items:
                    if it["th"] is th:
                        it["entry"] = e
                continue
            items.append({"th": None, "entry": e})
        for it in items:
            it["facts"] = theme_filter.facts(it, catalogo.has_update)
        self.items = items
        cfg_th = self.app.cfg.get("theme") or {}
        self._cur = next((th for th in installed if th["name"] == cfg_th.get("name")
                          and th.get("file", "") == cfg_th.get("file", "")), installed[0])
        want = keep if keep is not None else self._key(self.sel) if self.sel else None
        self.sel = next((it for it in items if want is not None and self._key(it) == want), None)
        if self.sel is None and want and want[0] == "cat":
            # recién descargado: ahora es un tema instalado (con su entrada del catálogo)
            self.sel = next((it for it in items if it["entry"] is not None and it["entry"]["id"] == want[1]), None)
        if self.sel is None:
            self.sel = next((it for it in items if it["th"] is self._cur), items[0])
        self._filter()
        self._paint()

    def _filter(self):
        """Aplica el buscador, los filtros y el orden (y vuelve a dibujar la lista y los filtros)."""
        self.shown = theme_filter.apply(self.items, self.filt)
        if self.filt.get("color") and self.filt["color"] not in self.color_names():
            self.filt["color"] = ""                 # ese color ya no está en ningún tema
            self.shown = theme_filter.apply(self.items, self.filt)
        self._paint_filters()
        self._paint_count()
        self._draw()

    def color_names(self):
        return theme_filter.colors_in(self.items)

    def set_filter(self, key, value):
        """Clic en un chip de los filtros. Color y extras se prenden y apagan con el mismo clic."""
        f = self.filt
        if key == "clear":
            theme_filter.clear(f)
            self.q_var.set("")
        elif key == "color":
            f["color"] = "" if f.get("color") == value else value
        elif key == "extras":
            ex = list(f.get("extras") or [])
            if value in ex:
                ex.remove(value)
            else:
                ex.append(value)
            f["extras"] = ex
        else:
            f[key] = value
        self.cv.yview_moveto(0)                     # antes de dibujar: se dibuja lo que se verá arriba
        self._filter()

    def _on_query(self):
        """El buscador filtra mientras escribes (con una pausa corta para no redibujar en cada letra)."""
        if self._q_job:
            self.t.after_cancel(self._q_job)
        self._q_job = self.t.after(150, self._apply_query)

    def _apply_query(self):
        self._q_job = None
        try:
            if not self.cv.winfo_exists():         # la pestaña se recreó mientras esperaba la pausa
                return
            q = self.q_var.get()
            if q != self.filt.get("q", ""):
                self.filt["q"] = q
                self.cv.yview_moveto(0)
                self._filter()
        except tk.TclError:
            pass

    def _on_order(self):
        names = {n: k for k, n in self.ORDERS}
        self.filt["orden"] = names.get(self.order_var.get(), "nombre")
        self._filter()

    def _paint_filters(self):
        for fv, on in ((self.fv_top, self._mode and self._mode[0] == "top"),
                       (self.fv_side, self._mode and self._mode[0] == "side" and not self.side_hidden)):
            if on:
                fv.draw()
        self._paint_strip()

    def _paint_strip(self):
        """La franja de los filtros ocultos: «▶ FILTROS» vertical (y cuántos hay puestos)."""
        cv = self.strip
        try:
            cv.delete("all")
            w = cv.winfo_width()
        except tk.TclError:
            return
        x = max(w, int(self.STRIP_W * self.d)) / 2
        cv.create_polygon(x - 4, 10, x + 5, 16, x - 4, 22, fill=C["accent"], outline="")
        cv.create_text(x, 32, text="FILTROS", angle=90, anchor="e", fill=C["text"], font=self._fonts["sec"])
        n = sum(1 for k in ("origen", "mostrar", "estilo") if self.filt.get(k, "todos") != "todos") \
            + bool(self.filt.get("color")) + len(self.filt.get("extras") or []) + bool(self.filt.get("q", "").strip())
        if n:                                       # filtros puestos aunque la columna esté oculta
            y = 32 + self._fonts["sec"].measure("FILTROS") + 18
            cv.create_oval(x - 9, y - 9, x + 9, y + 9, fill=C["accent"], outline="")
            cv.create_text(x, y, text=str(n), fill=C["on_accent"], font=self._fonts["pill"])

    # ------------------------------------------------------------ vista: lista o cuadrícula
    def _build_viewbar(self, bar):
        """«☰ Lista | ▦ Cuadrícula · Tamaño», igual que el selector de sonidos."""
        d = self.d
        app = self.app
        self._vb = bar
        self._seg_icons = False
        self._vb_level = 0             # 0 todo, 1 sin «N por fila», 2 sin bloque Tamaño
        size_box = self.size_box = ttk.Frame(bar, style="Panel.TFrame")
        ttk.Label(size_box, text="Tamaño", style="Muted.TLabel").pack(side="left", padx=(16, 6))
        si = int(round(13 * d))
        self._icons = {"more": aa.grid_icon(app.root, si, 3, C["muted"]),
                       "less": aa.grid_icon(app.root, si, 2, C["muted"])}
        ttk.Button(size_box, image=self._icons["more"], width=2,
                   command=lambda: self.set_cols(self.cols + 1)).pack(side="left")
        self._quiet = False
        self.size_var = tk.DoubleVar(value=self.MIN_COLS + self.MAX_COLS - self.cols)
        ttk.Scale(size_box, from_=self.MIN_COLS, to=self.MAX_COLS, variable=self.size_var, length=int(110 * d),
                  command=self._on_scale).pack(side="left", padx=6)
        ttk.Button(size_box, image=self._icons["less"], width=2,
                   command=lambda: self.set_cols(self.cols - 1)).pack(side="left")
        self.size_lbl = ttk.Label(size_box, style="Panel.TLabel", width=14)
        self.size_lbl.pack(side="left", padx=(8, 0))
        seg = self._seg = ttk.Frame(bar, style="Panel.TFrame")
        seg.pack(side="right")         # lo primero empaquetado a la derecha: nunca se recorta
        bar.bind("<Configure>", lambda e: self._fit_viewbar())
        ic = int(round(14 * d))
        self._icons.update(list_on=aa.list_icon(app.root, ic, C["accent"]), list_off=aa.list_icon(app.root, ic, C["muted"]),
                           grid_on=aa.grid_icon(app.root, ic, 2, C["accent"]),
                           grid_off=aa.grid_icon(app.root, ic, 2, C["muted"]))
        self.btn_list = ttk.Button(seg, text=" Lista", compound="left", width=-1, command=lambda: self.set_view("list"))
        self.btn_grid = ttk.Button(seg, text=" Cuadrícula", compound="left", width=-1,
                                   command=lambda: self.set_view("grid"))
        self.btn_list.pack(side="left")
        self.btn_grid.pack(side="left")
        s = ttk.Style(app.root)
        s.configure("SegOn.TButton", background=C["accent_bg"], foreground=C["accent"], lightcolor=C["accent_bg"],
                    darkcolor=C["accent_bg"], bordercolor=C["line"], font=(FONT, BASE - 1, "bold"), padding=(10, 5))
        s.map("SegOn.TButton", background=[("active", C["accent_bg"])])
        s.configure("Seg.TButton", foreground=C["muted"], font=(FONT, BASE - 1), padding=(10, 5))
        self._paint_viewbar()

    def _paint_viewbar(self):
        grid = self.view == "grid"
        self.btn_grid.configure(style="SegOn.TButton" if grid else "Seg.TButton",
                                image=self._icons["grid_on" if grid else "grid_off"])
        self.btn_list.configure(style="Seg.TButton" if grid else "SegOn.TButton",
                                image=self._icons["list_off" if grid else "list_on"])
        # el tamaño solo sirve en la cuadrícula (como en el selector de sonidos)
        if not grid:
            self.size_box.pack_forget()
        self._paint_size_lbl()
        self._fit_viewbar()
        # los botones cambian de sitio: en XWayland lo movido no se repinta solo
        self.app.root.after_idle(self.app._repaint_moved)

    def _fit_viewbar(self):
        """Decide qué cabe en la barra, en el mismo <Configure> (sin after): Lista/Cuadrícula siempre
        enteros; si falta ancho se quita primero «N por fila» y luego el bloque Tamaño. Histéresis de
        24 px para no parpadear al borde. Solo usa tamaños pedidos (reqwidth), sin medir fuentes."""
        bar = getattr(self, "_vb", None)
        if bar is None or not hasattr(self, "_seg"):
            return
        grid = self.view == "grid"
        avail = bar.winfo_width()
        if avail <= 1:
            return
        sb = self.size_box
        lbl = self.size_lbl
        w_lbl = lbl.winfo_reqwidth() + 8
        w_box = sum(c.winfo_reqwidth() for c in sb.winfo_children() if c is not lbl) + 16 + 6 * 3 + 12
        # barra extremadamente estrecha: los botones quedan solo con su icono
        full = getattr(self, "_seg_full", 0)
        if not self._seg_icons:
            full = self._seg_full = max(full, self._seg.winfo_reqwidth())
        icons = avail < full + (24 if self._seg_icons else 0)
        if icons != self._seg_icons:
            self._seg_icons = icons
            self.btn_list.configure(text="" if icons else " Lista")
            self.btn_grid.configure(text="" if icons else " Cuadrícula")
        base = self._seg.winfo_reqwidth() + self.count_lbl.winfo_reqwidth() + 12 + 12
        lv = self._vb_level
        if not grid:
            want = lv
        else:
            need = (base + w_box + w_lbl, base + w_box)       # niveles 0 y 1
            want = 2
            for i in (0, 1):
                if avail >= need[i] + (24 if lv > i else 0):
                    want = i
                    break
        self._vb_level = want
        show_box = grid and want < 2
        show_lbl = show_box and want == 0
        if show_box:
            if not sb.winfo_manager():
                sb.pack(side="right", before=self.count_lbl, padx=(0, 12))
        elif sb.winfo_manager():
            sb.pack_forget()
        if show_lbl and not lbl.winfo_manager():
            lbl.pack(side="left", padx=(8, 0))
        elif not show_lbl and lbl.winfo_manager():
            lbl.pack_forget()
        if want != lv or (show_box != bool(sb.winfo_ismapped()) and bar.winfo_ismapped()):
            self.app.root.after_idle(self.app._repaint_moved)

    def _paint_size_lbl(self):
        if self.view != "grid":
            txt = ""
        else:
            fit = getattr(self, "_cols_fit", self.cols)
            txt = f"{self.cols} por fila" if fit >= self.cols else f"{fit} por fila (máx.)"
        try:
            self.size_lbl.configure(text=txt)
        except tk.TclError:
            pass

    def set_view(self, view):
        if view == self.view:
            return
        self.view = view
        self._remember()
        self._paint_viewbar()
        self._draw()

    def set_cols(self, n):
        n = max(self.MIN_COLS, min(self.MAX_COLS, int(n)))
        if n == self.cols:
            return
        self.cols = n
        self._quiet = True
        self.size_var.set(self.MIN_COLS + self.MAX_COLS - n)
        self._quiet = False
        self._remember()
        self._draw()
        self._paint_size_lbl()

    def _on_scale(self, _v):
        if not self._quiet:
            self.set_cols(round(self.MIN_COLS + self.MAX_COLS - self.size_var.get()))

    def set_side_hidden(self, hidden):
        """«◀ Ocultar filtros» / la franja «▶ FILTROS» (se recuerda)."""
        self.side_hidden = bool(hidden)
        self._remember()
        if self._mode and self._mode[0] == "side":
            self._show_side()
            self.t.after(60, self.app._repaint_moved)      # lo que se movió, entero (XWayland)

    def _remember(self):
        with self.app.engine.lock:
            self.app.cfg.setdefault("ui", {})["temas_vista"] = {"view": self.view, "cols": self.cols,
                                                                "filtros_ocultos": self.side_hidden}
        self.app._save_later()

    # ------------------------------------------------------------ dónde va cada cosa según el ancho
    def _on_tab_resize(self, width):
        """Filtros arriba o en columna, y detalle a la derecha o encima, según el ancho de la pestaña.
        Solo cambia algo al cruzar un umbral (no en cada evento: así no parpadea)."""
        if width < 50:
            width = 1366                            # aún sin medir: un tamaño intermedio
        d, m = self.d, self._mode
        hyst = 12 * d                               # un margen para no ir y volver en el borde
        top_w = self.TOP_W * d + (-hyst if m and m[0] == "top" else hyst if m else 0)
        ov_w = self.OVERLAY_W * d + (hyst if m and m[1] else -hyst if m else 0)
        mode = ("top" if width >= top_w else "side", width < ov_w)
        if mode != m:
            self._apply_mode(mode)

    def _apply_mode(self, mode):
        old = self._mode
        self._mode = mode
        top, overlay = mode[0] == "top", mode[1]
        if old is None or old[0] != mode[0]:
            if top:
                self.side.grid_remove()
                self.strip.grid_remove()
                self.topbar.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(12, 0))
            else:
                self.topbar.grid_remove()
                self._show_side()
        if old is None or old[1] != overlay:
            if overlay:
                self.dbox.grid_remove()
                self._overlay = False
                self.dbox.place_forget()
                self.dbox.configure(highlightthickness=1)
                self.d_top.pack(fill="x", pady=(0, 8), before=self.big if self.big.winfo_manager() else self.d_name)
            else:
                self.dbox.place_forget()
                self._overlay = False
                self.dbox.configure(highlightthickness=0)
                self.d_top.pack_forget()
                self.dbox.grid(row=2, column=2, sticky="ns", padx=(14, 0), pady=(10, 0))
        if old is not None:
            self._paint_filters()

    def _show_side(self):
        if self.side_hidden:
            self.side.grid_remove()
            self.strip.grid(row=2, column=0, sticky="ns", padx=(0, 12), pady=(10, 0))
            self._paint_strip()
        else:
            self.strip.grid_remove()
            self.side.grid(row=2, column=0, sticky="nsew", padx=(0, 14), pady=(10, 0))
            self.fv_side.draw()

    def _open_overlay(self):
        """Ventanas chicas: el detalle se abre encima de la lista (a la derecha)."""
        if self._overlay:
            return
        self._overlay = True
        # todo el alto de la pestaña (también sobre la cabecera): en ventanas bajas los botones caben enteros
        self.dbox.place(in_=self.t, relx=1.0, x=-int(18 * self.d), y=0, anchor="ne", relheight=1.0)
        self.dbox.lift()
        self.t.after(30, self._fit_detail)

    def _close_overlay(self):
        if not self._overlay:
            return
        self._overlay = False
        self.dbox.place_forget()
        self._draw()                                # lo que estaba debajo, entero (XWayland)

    def _on_escape(self):
        self._close_overlay()

    def _on_click_anywhere(self, e):
        """Un clic fuera del detalle (encima de la lista) lo cierra."""
        if not self._overlay:
            return
        if self._just_picked:                       # el clic que lo abrió (una tarjeta)
            self._just_picked = False
            return
        try:
            if str(e.widget).startswith(str(self.dbox)):
                return
        except (tk.TclError, AttributeError):
            return
        self._close_overlay()

    @staticmethod
    def _key(it):
        if it["th"] is not None:
            return ("th", it["th"]["name"], it["th"].get("file", ""))
        return ("cat", it["entry"]["id"])

    # ------------------------------------------------------------ ficha del creador y «sobre el tema»
    CARD_TEXT_W = 250                       # ancho de texto del detalle (el de la vista previa menos un poco)

    def _build_creator_box(self, parent):
        """Recuadro «★ CREADOR DIGITAL» (violeta, con franja a la izquierda): avatar, nombre, verificado,
        bio y redes. Son widgets tk con color propio: no dependen del fondo nativo de ttk (xbg)."""
        box = self.d_creator = tk.Frame(parent, bd=0, highlightthickness=1)
        self.cb_strip = tk.Frame(box, width=3, bd=0, highlightthickness=0)
        self.cb_strip.pack(side="left", fill="y")
        body = self.cb_body = tk.Frame(box, bd=0, highlightthickness=0)
        body.pack(side="left", fill="both", expand=True, padx=(8, 8), pady=(6, 8))
        top = self.cb_top = tk.Frame(body, bd=0, highlightthickness=0)
        top.pack(fill="x")
        self.cb_cap = tk.Label(top, text="★ CREADOR DIGITAL", font=(FONT, BASE - 3, "bold"), bd=0, padx=0, pady=0)
        self.cb_cap.pack(side="left")
        # «Abrir Twitch» al pasar el mouse por una red (en la misma línea: el recuadro no cambia de alto)
        self.cb_hint = tk.Label(top, font=(FONT, BASE - 3), bd=0, padx=0, pady=0)
        self.cb_hint.pack(side="right")
        who = self.cb_who = tk.Frame(body, bd=0, highlightthickness=0)
        who.pack(fill="x", pady=(5, 0))
        self.cb_avatar = tk.Label(who, bd=0, padx=0, pady=0, font=(FONT, BASE, "bold"), compound="center")
        self.cb_avatar.pack(side="left")
        names = self.cb_names = tk.Frame(who, bd=0, highlightthickness=0)
        names.pack(side="left", padx=(8, 0), fill="x", expand=True)
        self.cb_name = tk.Label(names, font=(FONT, BASE, "bold"), anchor="w", bd=0, padx=0, pady=0)
        self.cb_name.pack(fill="x")
        self.cb_verified = tk.Label(names, text="✓ verificado por OkumaWsX", font=(FONT, BASE - 3), anchor="w",
                                    bd=0, padx=0, pady=0)
        self.cb_verified.pack(fill="x")
        self.cb_bio = tk.Label(body, font=(FONT, BASE - 1), justify="left", anchor="w", bd=0, padx=0, pady=0,
                               wraplength=self.CARD_TEXT_W - 8)
        self.cb_icons = tk.Frame(body, bd=0, highlightthickness=0)
        self._cb_nets = None                    # las redes que ya están dibujadas (y sus colores)

    def _build_about(self, parent):
        """«SOBRE EL TEMA»: descripción, extras (como etiquetas) y una línea de nota."""
        a = self.d_about = tk.Frame(parent, bd=0, highlightthickness=0)
        self.ab_cap = tk.Label(a, text="SOBRE EL TEMA", font=(FONT, BASE - 3, "bold"), anchor="w", bd=0,
                               padx=0, pady=0)
        self.ab_cap.pack(fill="x")
        self.ab_desc = tk.Label(a, font=(FONT, BASE - 1), justify="left", anchor="w", bd=0, padx=0, pady=0,
                                wraplength=self.CARD_TEXT_W)
        self.ab_chips = tk.Frame(a, bd=0, highlightthickness=0)
        self.ab_note = tk.Label(a, font=(FONT, BASE - 3), justify="left", anchor="w", bd=0, padx=0, pady=0,
                                wraplength=self.CARD_TEXT_W)
        self.d_sep = tk.Frame(parent, height=1, bd=0, highlightthickness=0)

    def _set_info_layout(self, creator, about):
        """Muestra la ficha del creador (o el recuadro de estado) y «Sobre el tema», en orden."""
        kind = (creator, about)
        if kind == self._info_kind:
            return
        self._info_kind = kind
        for w in (self.d_creator, self.d_status, self.d_sep, self.d_about):
            w.pack_forget()
        if creator:
            self.d_creator.pack(fill="x", pady=(10, 0))
        else:
            self.d_status.pack(fill="x", pady=(10, 0))
        if about:
            if creator:
                self.d_sep.pack(fill="x", pady=(10, 0))
            self.d_about.pack(fill="x", pady=(10, 0))
        # los widgets que aparecen reciben ya su fondo nativo (los tk lo traen; por si hay alguno ttk)
        self.t.after_idle(lambda: xbg.paint(self.app.root, only_mapped=True))

    def _paint_about(self, it, creator, note):
        e = it["entry"]
        desc = " ".join(str(e.get("descripcion") or "").split()) if e else ""
        labels = [n for k, n in EXTRA_NAMES if k in it["facts"]["extras"]]
        show = bool(desc or labels or note)
        bg = C["panel2"]
        if show:
            for w in (self.d_about, self.ab_cap, self.ab_desc, self.ab_chips, self.ab_note):
                w.configure(bg=bg)
            self.ab_cap.configure(fg=C["accent"])
            self.ab_desc.configure(text=desc, fg=C["text"])
            self.ab_note.configure(text=note, fg=C["muted"])
            for c in self.ab_chips.winfo_children():
                c.destroy()
            if labels:
                self._flow_chips(self.ab_chips, labels, mix(C["muted"], bg, .8), C["muted"])
            self._pack_about_parts()
        self._set_info_layout(creator, show)
        if show:
            self.d_sep.configure(bg=mix(C["line"], C["muted"], .35))

    def _pack_about_parts(self):
        """Descripción, etiquetas y nota de «Sobre el tema», en orden (menos lo que falta de alto)."""
        for w in (self.ab_desc, self.ab_chips, self.ab_note):
            w.pack_forget()
        if self.ab_desc.cget("text"):
            self.ab_desc.pack(fill="x", pady=(3, 0))
        if self.ab_chips.winfo_children() and not self._chips_hidden:
            self.ab_chips.pack(fill="x", pady=(6, 0))
        if self.ab_note.cget("text") and not self._note_hidden:
            self.ab_note.pack(fill="x", pady=(2, 0))

    def _flow_chips(self, frame, labels, bg, fg):
        """Etiquetas pequeñas una tras otra; si no caben en el ancho, siguen en otra fila."""
        font = self._fonts["chip"]
        x = row = col = 0
        for text in labels:
            w = font.measure(text) + 12 + 6
            if col and x + w > self.CARD_TEXT_W:
                row, col, x = row + 1, 0, 0
            tk.Label(frame, text=text, font=font, bg=bg, fg=fg, padx=6, pady=1, bd=0).grid(
                row=row, column=col, sticky="w", padx=(0, 5), pady=(0, 4))
            x += w
            col += 1

    def _paint_creator(self, it, th, e):
        """La ficha del creador con el violeta fijo de marca (el del sello ★ CREADOR)."""
        info = catalogo.creator_info(e) or {"nombre": "", "bio": "", "redes": []}
        name = info["nombre"] or it["facts"]["creator_name"] or (e or {}).get("autor", "")
        vio = brand("creador", "line")
        bg = mix(vio, C["panel2"], .85)
        _txt, seal_bg, seal_fg = self._seal(it)
        for w in (self.cb_body, self.cb_top, self.cb_who, self.cb_names, self.cb_icons):
            w.configure(bg=bg)
        self.d_creator.configure(bg=bg, highlightbackground=vio, highlightcolor=vio)
        self.cb_strip.configure(bg=vio)
        self.cb_cap.configure(bg=bg, fg=brand("creador", "cap"))
        self.cb_hint.configure(bg=bg, fg=C["muted"], text="")
        self.cb_name.configure(bg=bg, fg=C["text"], text=name)
        self.cb_verified.configure(bg=bg, fg=C["muted"])
        self.cb_bio.configure(bg=bg, fg=C["text"], text=info["bio"])
        if info["bio"]:
            if not self.cb_bio.winfo_manager():
                opts = {"before": self.cb_icons} if self.cb_icons.winfo_manager() else {}
                self.cb_bio.pack(fill="x", pady=(6, 0), **opts)
        else:
            self.cb_bio.pack_forget()
        av = info.get("avatar")
        self._av_want = (av["sha256"] if av else None, name, seal_bg, seal_fg, bg)
        self._show_avatar()
        if av:
            self._fetch_avatar(av)
        self._paint_networks(info["redes"], bg)

    def _show_avatar(self):
        """El círculo del creador: su foto si ya está verificada en memoria; si no, la inicial sobre el color
        del sello. Los dos miden lo mismo, así que cuando llega la foto nada se mueve."""
        sha, name, seal_bg, seal_fg, bg = self._av_want
        d = getattr(self.app, "dpi", 1.0)
        px = int(round(AVATAR_PX * d))
        img = None
        path = _AVATAR_PATHS.get(sha) if sha else None
        if path:
            ring = max(1.5, 1.5 * d)
            vio = brand("creador", "line")
            key = (sha, px, vio, ring)
            img = _AVATAR_IMGS.get(key)
            if img is None:
                img = avatar_circle(self.cb_avatar, path, px, vio, ring)
                if img is None:
                    _AVATAR_PATHS.pop(sha, None)        # no se pudo leer: mejor la inicial
                else:
                    _AVATAR_IMGS[key] = img
        if img is not None:
            self.cb_avatar.configure(bg=bg, image=img, text="", width=px)
            return
        dot = aa.dot(self.cb_avatar, px, seal_bg)
        self.cb_avatar.configure(bg=bg, fg=seal_fg, text=(name[:1] or "?").upper(), image=dot or "",
                                 width=px if dot is not None else 0)

    def _fetch_avatar(self, av):
        """Baja la foto en un hilo (la comprueba y la deja en la caché de la carpeta de configuración).
        Una sola vez por huella: si ya está en memoria, o se está bajando, o falló hace poco, no hace nada."""
        sha = av["sha256"]
        if sha in _AVATAR_PATHS or sha in _AVATAR_BUSY or time.time() - _AVATAR_FAIL.get(sha, 0) < AVATAR_RETRY:
            return
        _AVATAR_BUSY.add(sha)
        q = self._av_q

        def run():
            try:
                _AVATAR_PATHS[sha] = catalogo.avatar_get(av)
                _AVATAR_FAIL.pop(sha, None)
            except Exception:                   # sin red, huella distinta, sin Pillow…: se queda la inicial
                _AVATAR_FAIL[sha] = time.time()
            finally:
                _AVATAR_BUSY.discard(sha)
                q.put(sha)
        threading.Thread(target=run, daemon=True).start()

    def _avatar_arrived(self, sha):
        """Llegó (o falló) una foto: se cambia el círculo solo si el detalle sigue mostrando ese creador."""
        if self._av_want is not None and self._av_want[0] == sha and sha in _AVATAR_PATHS:
            self._show_avatar()
            xbg.paint(self.app.root, only_mapped=True)

    def _paint_networks(self, nets, bg):
        """Una fila de íconos sin recuadro (con los colores originales de cada red). Cada uno abre su
        perfil en el navegador; al pasar el mouse dice «Abrir <red>» arriba a la derecha."""
        key = (tuple((n["red"], n["url"]) for n in nets), bg)
        if key == self._cb_nets:
            return
        self._cb_nets = key
        for c in self.cb_icons.winfo_children():
            c.destroy()
        if not nets:
            self.cb_icons.pack_forget()
            return
        d = getattr(self.app, "dpi", 1.0)
        px = int(round(18 * d))
        per_row = max(1, (self.CARD_TEXT_W - 40) // (px + 12))
        # sin recuadro: el ícono va sobre el fondo del recuadro del creador; al pasar el mouse, un velo violeta
        chip, hover = bg, mix(bg, brand("creador", "line"), .25)
        light = _theme_is_light()
        for i, n in enumerate(nets):
            col = BRAND.get(n["red"], "#ffffff")          # solo para la inicial de respaldo
            if light and n["red"] in ("tiktok", "x"):
                col = "#111111"          # sus logos oficiales son negros sobre fondo claro
            img = red_icon(self.cb_icons, n["red"], px, light)
            lb = tk.Label(self.cb_icons, bg=chip, bd=0, padx=4, pady=4, cursor="hand2",
                          **({"image": img} if img is not None else {"text": n["nombre"][:1], "fg": col,
                                                                    "font": (FONT, BASE - 1, "bold")}))
            lb.grid(row=i // per_row, column=i % per_row, padx=(0, 6), pady=(0, 4))
            lb.bind("<Enter>", lambda ev, w=lb, nn=n: self._hover_net(w, nn, hover))
            lb.bind("<Leave>", lambda ev, w=lb: self._hover_net(w, None, chip))
            lb.bind("<Button-1>", lambda ev, nn=n: self._open_net(nn))
        self.cb_icons.pack(fill="x", pady=(8, 0))

    def _hover_net(self, w, net, bg):
        try:
            w.configure(bg=bg)
            self.cb_hint.configure(text=f"Abrir {net['nombre']}" if net else "")
        except tk.TclError:
            pass

    def _open_net(self, net):
        """Abre el perfil en el navegador, solo si el enlace pasa la lista de dominios oficiales."""
        if catalogo.red_url_valida(net.get("red"), net.get("url")):
            sysutil.open_url(net["url"])

    def _fit_detail(self):
        """La vista previa grande toma el alto que sobra, para que los botones del detalle
        siempre se vean enteros. Si ni con la vista previa mínima caben, se esconde por pasos lo
        menos importante: los círculos de colores, la línea de nota de «Sobre el tema», la vista previa
        y, al final, las etiquetas de extras. Cada paso se decide con la misma cuenta para esconder y
        para mostrar, así que no va y viene."""
        d = self.detail
        try:
            have = d.winfo_height()
            if have < 50:
                return
            big_on = bool(self.big.winfo_manager())
            dots_on = bool(self.d_dots.winfo_manager())
            note_on = bool(self.ab_note.winfo_manager())
            chips_on = bool(self.ab_chips.winfo_manager())
            dots_h = self.d_dots.winfo_reqheight() + 10
            note_h = self.ab_note.winfo_reqheight() + 2
            chips_h = self.ab_chips.winfo_reqheight() + 6
            has_note = bool(self.ab_note.cget("text")) and bool(self.d_about.winfo_manager())
            has_chips = bool(self.ab_chips.winfo_children()) and bool(self.d_about.winfo_manager())
            note_h, chips_h = (note_h if has_note else 0), (chips_h if has_chips else 0)
            # lo que no se puede esconder: el alto pedido sin las partes que hoy están a la vista
            fixed = (d.winfo_reqheight() - (self.big.winfo_reqheight() if big_on else 0)
                     - (dots_h if dots_on else 0) - (note_h if note_on else 0) - (chips_h if chips_on else 0))
            m, s = self.BIG_MIN, self.SAFE
            needs = (fixed + dots_h + note_h + chips_h + m + s,        # todo
                     fixed + note_h + chips_h + m + s,                 # sin círculos de colores
                     fixed + chips_h + m + s,                          # … ni nota
                     fixed + chips_h + s,                              # … ni vista previa
                     fixed + s)                                        # … ni etiquetas de extras
            lvl = next((i for i, n in enumerate(needs) if have >= n), 4)
            if lvl >= 1 and dots_on:
                self.d_dots.pack_forget()
            elif lvl < 1 and not dots_on:
                self.d_dots.pack(pady=(10, 0), before=self.phone_chk)
            for flag, hide, widget in (("_note_hidden", lvl >= 2, self.ab_note),
                                       ("_chips_hidden", lvl >= 4, self.ab_chips)):
                if getattr(self, flag) != hide:
                    setattr(self, flag, hide)
                    if hide:
                        widget.pack_forget()
                    elif (widget is self.ab_note and has_note) or (widget is self.ab_chips and has_chips):
                        self._pack_about_parts()
            if (lvl >= 3) == big_on:                 # la vista previa se esconde del todo en vez de quedar de 1 px
                if lvl >= 3:
                    self.big.pack_forget()
                else:
                    self.big.pack(before=self.d_name)
            below = (dots_h if lvl < 1 else 0) + (note_h if lvl < 2 else 0) + (chips_h if lvl < 4 else 0)
            h = int(max(self.BIG_MIN, min(self.BIG_H, have - fixed - below - s)))
        except tk.TclError:
            return
        if h != self.big_h and lvl < 3:
            self.big_h = h
            self.big.configure(height=h)
            if self.sel is not None:
                draw_preview(self.big, self._colors(self.sel), self.BIG_W, h)
        elif lvl < 3 and self.sel is not None and not big_on:
            draw_preview(self.big, self._colors(self.sel), self.BIG_W, self.big_h)

    @staticmethod
    def _same(a, b):
        return a["name"] == b["name"] and a.get("file", "") == b.get("file", "")

    @staticmethod
    def _colors(it):
        return it["th"]["colors"] if it["th"] is not None else _theme_colors(it["entry"]["colores"])

    @staticmethod
    def _official(it):
        if it["th"] is not None:
            return bool(it["th"].get("builtin") or it["th"].get("official"))
        return it["entry"]["origen"] == "oficial"

    @staticmethod
    def _seal(it, avail=False):
        """Sello del origen: (texto, fondo, letra). Oficial = acento del tema (dorado), comunidad =
        azul del tema; creador = violeta fijo de marca (CREATOR_BRAND), igual en cualquier tema."""
        if it["facts"]["creator"]:
            txt, bg, fg = "★ CREADOR", brand("creador", "bg"), brand("creador", "fg")
        elif ThemesTab._official(it):
            txt, bg, fg = "✓ OFICIAL", C["accent"], C["on_accent"]
        else:
            txt, bg, fg = "◆ COMUNIDAD", C["key_set"], C["key_set_text"]
        if avail:
            bg, fg = fade(bg, .45), fade(fg, .3)
        return txt, bg, fg

    @staticmethod
    def _byline(it):
        """Lo que va bajo el nombre: el autor (oficial: sin «por»), «por <creador>» o «por <autor>»."""
        f = it["facts"]
        if f["creator"]:
            return "por " + (f["creator_name"] or f["author"])
        return f["author"] if ThemesTab._official(it) else "por " + f["author"]

    @staticmethod
    def _fit(text, font, width):
        """Acorta el texto con «…» para que quepa en `width` píxeles."""
        text = str(text or "")
        if font.measure(text) <= width:
            return text
        while text and font.measure(text + "…") > width:
            text = text[:-1]
        return text.rstrip() + "…"

    def _on_cv_resize(self, width):
        if abs(width - self._cv_w) >= 2:
            self._cv_w = width
            self._draw()
        elif self._content_h:                       # solo cambió el alto: la zona desplazable se ajusta
            try:
                self._set_region(width, self._content_h)
            except tk.TclError:
                pass

    def _layout(self):
        self._draw()

    def _draw(self, full=False):
        """Dibuja las secciones y todos los temas (tarjetas o filas) en el lienzo.
        Lo anterior se borra al final, no al principio: así Tk no suelta y vuelve a pedir cada
        color (cada uno es una consulta al servidor gráfico) y nunca queda un instante vacío."""
        cv = self.cv
        try:
            cv.addtag_all("old")
            width = max(200, cv.winfo_width())
        except tk.TclError:
            return
        try:
            self._draw_items(cv, width, full)
        finally:
            try:
                cv.delete("old")
            except tk.TclError:
                pass

    def _draw_items(self, cv, width, full=False):
        f = self._fonts
        gap = 8
        if self.view == "grid":
            # tantas por fila como pida «Tamaño», sin bajar del mínimo legible
            fit = max(1, int((width + gap) // (self.MIN_CARD * self.d + 12 + gap)))
            cols = max(1, min(self.cols, fit))
            if fit != getattr(self, "_cols_fit", None):
                self._cols_fit = fit
                self._paint_size_lbl()
            cw = (width - gap * (cols - 1)) / cols
            pw = int(cw - 12)
            ph = int(pw * self.CARD_H / self.CARD_W)
            ch = ph + 56
        else:
            cols, cw, ch, pw, ph = 1, width, int(self.ROW_H * self.d), 0, 0
        filtered = theme_filter.active(self.filt)
        if not self.shown:
            self._draw_empty(width, filtered)
            return
        # 1) dónde va cada cosa (barato); 2) se fija el alto del desplazamiento; 3) se dibuja lo que se ve
        ops = []                                    # (y0, y1, función, argumentos)
        y = 0
        for title, inst in (("Instalados", True), ("Disponibles para descargar", False)):
            group = [it for it in self.shown if it["facts"]["installed"] == inst]
            total = sum(1 for it in self.items if it["facts"]["installed"] == inst)
            if not group and (not filtered or not total):
                continue
            if y:
                y += 10
            count = f"{len(group)}" if len(group) == total else f"{len(group)} de {total}"
            ops.append((y, y + 20, self._draw_title, (y, f"{title.upper()} ({count})", f["sec"])))
            y += 20
            if not group:
                ops.append((y, y + 22, self._draw_title, (y, "Ninguno coincide con los filtros.", f["small"])))
                y += 22
                continue
            if self.view == "grid":
                for i, it in enumerate(group):
                    x = (i % cols) * (cw + gap)
                    cy = y + (i // cols) * (ch + gap)
                    ops.append((cy, cy + ch, self._draw_card, (it, x, cy, cw, ch, pw, ph)))
                y += ((len(group) + cols - 1) // cols) * (ch + gap)
            else:
                for i, it in enumerate(group):
                    ry = y + i * (ch + 4)
                    ops.append((ry, ry + ch, self._draw_row, (it, 0, ry, width, ch)))
                y += len(group) * (ch + 4)
        self._set_region(width, y)
        # solo lo que se ve (y un cuarto de pantalla de margen): con muchos temas, redibujar todo en cada
        # cuadro de un cambio de tamaño no alcanza; el resto se completa en cuanto la ventana se queda quieta
        h = max(1, cv.winfo_height())
        top = cv.canvasy(0)
        lo, hi = (float("-inf"), float("inf")) if full else (top - h / 4, top + h * 1.25)
        skipped = False
        for y0, y1, fn, args in ops:
            if y1 < lo or y0 > hi:
                skipped = True
                continue
            fn(*args)
        self._drawn_part = skipped
        if skipped:
            self._full_later()

    def _set_region(self, width, content_h):
        """Zona desplazable: nunca más baja que lo visible (si no, la rueda «subía» más allá del
        principio y los temas quedaban abajo con un hueco vacío arriba)."""
        self._content_h = max(1, content_h)
        cv = self.cv
        h = max(1, cv.winfo_height())
        cv.configure(scrollregion=(0, 0, width, max(self._content_h, h)))
        if self._content_h <= h and cv.canvasy(0) != 0:
            cv.yview_moveto(0)

    def _fits(self):
        """¿Todo el contenido cabe en lo visible? (entonces la rueda no desplaza)"""
        try:
            return self._content_h <= self.cv.winfo_height()
        except tk.TclError:
            return True

    def _draw_title(self, y, text, font):
        self.cv.create_text(0, y, text=text, anchor="nw", fill=C["muted"], font=font)

    def _full_later(self):
        """Dibuja también lo que quedó fuera de la vista (no se ve: puede esperar a que la ventana se
        quede quieta)."""
        if self._full_job is not None:
            self.t.after_cancel(self._full_job)
        self._full_job = self.t.after(200, self._full_now)

    def _full_now(self):
        self._full_job = None
        if not self._drawn_part:
            return
        try:
            if self.cv.winfo_exists():
                self._draw(full=True)
        except tk.TclError:
            pass

    def _ensure_full(self):
        """Antes de desplazar: lo que va a aparecer tiene que estar dibujado."""
        if self._drawn_part:
            if self._full_job is not None:
                self.t.after_cancel(self._full_job)
                self._full_job = None
            self._draw(full=True)

    def _yview(self, *args):
        self._ensure_full()
        self.cv.yview(*args)

    def _draw_empty(self, width, filtered):
        """Nada que mostrar: lo dice claro y ofrece quitar los filtros."""
        cv, f = self.cv, self._fonts
        msg = "Ningún tema coincide con la búsqueda y los filtros." if filtered else "No hay temas para mostrar."
        cv.create_text(width / 2, 60, text=msg, fill=C["text"], font=f["msg"], width=width - 20, justify="center")
        if filtered:
            cv.create_text(width / 2, 88, text="Prueba con otras palabras o quita algún filtro.", fill=C["muted"],
                           font=f["small"])
            txt = "✕  Quitar filtros"
            bw, bh = f["btn"].measure(txt) + 32, 32
            x0, y0 = width / 2 - bw / 2, 112
            cv.create_rectangle(x0, y0, x0 + bw, y0 + bh, fill=C["accent"], outline=C["accent"], tags=("clear",))
            cv.create_text(width / 2, y0 + bh / 2, text=txt, fill=C["on_accent"], font=f["btn"], tags=("clear",))
            cv.tag_bind("clear", "<Button-1>", lambda e: self.set_filter("clear", ""))
            cv.tag_bind("clear", "<Enter>", lambda e: cv.configure(cursor="hand2"))
            cv.tag_bind("clear", "<Leave>", lambda e: cv.configure(cursor=""))
        self._set_region(width, 160)

    def _status_of(self, it):
        """Estado de un tema para la tarjeta o la fila: uso · nueva · bajando · error · disponible · instalado."""
        dl = self._dl(it)
        if dl is not None and dl.state in ("bajando", "reintentando"):
            return "bajando", dl
        if dl is not None and dl.state == "error":
            return "error", dl
        if it["th"] is None:
            return "disponible", dl
        if self._same(it["th"], self._cur):
            return "uso", dl
        if catalogo.has_update(it["entry"] or {}, it["th"]):
            return "nueva", dl
        return "instalado", dl

    def _badge(self, it):
        """«uso» o «nueva» si el tema instalado está en uso o tiene versión nueva (aunque se esté bajando)."""
        if it["th"] is None:
            return None
        if self._same(it["th"], self._cur):
            return "uso"
        return "nueva" if catalogo.has_update(it["entry"] or {}, it["th"]) else None

    def _bind_item(self, tag, it):
        # lo asociado a una etiqueta sigue aunque se borren las figuras: se hace una sola vez por
        # tema (si no, cada redibujo dejaba tres funciones nuevas registradas en Tk)
        if self._bound.get(tag) is it:
            return
        self._bound[tag] = it
        cv = self.cv
        cv.tag_bind(tag, "<Button-1>", lambda e, it=it: self._pick(it))
        cv.tag_bind(tag, "<Enter>", lambda e: cv.configure(cursor="hand2"))
        cv.tag_bind(tag, "<Leave>", lambda e: cv.configure(cursor=""))

    def _arrow(self, x, y, col, tag):
        """Flecha de descarga dibujada (no depende de la letra). (x, y): punta de arriba."""
        cv = self.cv
        cv.create_line(x, y, x, y + 7, fill=col, width=2, tags=(tag,))
        cv.create_polygon(x - 3, y + 4, x + 3, y + 4, x, y + 8, fill=col, outline=col, tags=(tag,))
        cv.create_line(x - 4, y + 10, x + 4, y + 10, fill=col, width=1, tags=(tag,))

    def _draw_card(self, it, x, y, cw, ch, pw, ph):
        cv, f = self.cv, self._fonts
        avail = it["th"] is None
        tag = f"card{id(it)}"
        bg = fade(C["panel2"], .5) if avail else C["panel2"]
        on = it is self.sel
        line = C["accent"] if on else (fade(C["line"], .4) if avail else C["line"])
        cv.create_rectangle(x, y, x + cw, y + ch, fill=bg, outline=line, width=2, tags=(tag,))
        colors = self._colors(it)
        px, py = x + 6, y + 6
        draw_preview_at(cv, faded(colors) if avail else colors, px, py, pw, ph, (tag,))
        # sello del origen (la firma manda: incluidos y firmados por OkumaWsX son oficiales)
        stxt, sbg, sfg = self._seal(it, avail)
        self._pill(px + 3, py + 3, stxt, sbg, sfg, tag)
        state, dl = self._status_of(it)
        badge = self._badge(it)                    # las píldoras se ven también al bajar o fallar
        if badge == "uso":
            self._pill(px + pw - 3, py + 3, "EN USO", C["ok"], C["on_ok"], tag, right=True)
        elif badge == "nueva":
            self._pill(px + pw - 3, py + 3, "NUEVA VERSIÓN", C["accent"], C["on_accent"], tag, right=True)
        name = it["facts"]["name"]
        ty = py + ph + 4
        cv.create_text(px, ty, text=self._fit(name, f["name"], pw), anchor="nw", font=f["name"],
                       fill=fade(C["text"], .45) if avail else C["text"], tags=(tag,))
        author = self._byline(it)
        ay = ty + f["name"].metrics("linespace") + 1
        cv.create_text(px, ay, text=self._fit(author, f["small"], pw - 36), anchor="nw", font=f["small"],
                       fill=fade(C["muted"], .4) if avail else C["muted"], tags=(tag,))
        if state == "bajando":
            cv.create_text(px + pw, ay, text=f"{int(dl.fraction * 100)} %", anchor="ne",
                           font=f["pct"], fill=C["accent"], tags=(tag,))
            by = y + ch - 9
            cv.create_rectangle(px, by, px + pw, by + 4, fill=C["line"], outline="", tags=(tag,))
            cv.create_rectangle(px, by, px + pw * dl.fraction, by + 4, fill=C["accent"], outline="", tags=(tag,))
        elif state == "error":
            cv.create_text(px + pw, ay, text="⚠", anchor="ne", font=f["small"], fill=C["bad"], tags=(tag,))
        elif state == "disponible":
            self._arrow(px + pw - 5, ay + 3, fade(C["muted"], .2), tag)
        self._bind_item(tag, it)

    def _draw_row(self, it, x, y, w, rh):
        """Vista de lista: miniatura, nombre, autor, sello y el estado a la derecha."""
        cv, f = self.cv, self._fonts
        avail = it["th"] is None
        tag = f"card{id(it)}"
        on = it is self.sel
        bg = C["accent_bg"] if on else (fade(C["panel2"], .5) if avail else C["panel2"])
        line = C["accent"] if on else (fade(C["line"], .4) if avail else C["line"])
        cv.create_rectangle(x, y, x + w, y + rh, fill=bg, outline=line, width=2 if on else 1, tags=(tag,))
        th_h = rh - 12
        th_w = int(th_h * self.CARD_W / self.CARD_H)
        colors = self._colors(it)
        draw_preview_at(cv, faded(colors) if avail else colors, x + 6, y + 6, th_w, th_h, (tag,))
        tx = x + 6 + th_w + 12
        name_w = int(max(150, min(260, w * .26)))
        fg = fade(C["text"], .45) if avail else C["text"]
        mfg = fade(C["muted"], .4) if avail else C["muted"]
        mid = y + rh / 2
        cv.create_text(tx, mid - 1, text=self._fit(it["facts"]["name"], f["name"], name_w), anchor="sw",
                       font=f["name"], fill=fg, tags=(tag,))
        author = self._byline(it)
        cv.create_text(tx, mid + 1, text=self._fit(author, f["small"], name_w), anchor="nw", font=f["small"],
                       fill=mfg, tags=(tag,))
        stxt, sbg, sfg = self._seal(it, avail)
        ph = f["pill"].metrics("linespace") + 2
        self._pill(tx + name_w + 14, mid - ph / 2, stxt, sbg, sfg, tag)
        # a la derecha, el estado
        state, dl = self._status_of(it)
        rx = x + w - 14
        badge = self._badge(it)
        btxt, bcol = {"uso": ("EN USO", (C["ok"], C["on_ok"])),
                      "nueva": ("NUEVA VERSIÓN", (C["accent"], C["on_accent"]))}.get(badge, (None, None))
        if state in ("uso", "nueva"):
            self._pill(rx, mid - ph / 2, btxt, *bcol, tag, right=True)
        elif state == "instalado":
            cv.create_text(rx, mid, text="Instalado", anchor="e", font=f["small"], fill=C["muted"], tags=(tag,))
        elif state == "bajando":
            pct = f"{int(dl.fraction * 100)} %"
            cv.create_text(rx, mid, text=pct, anchor="e", font=f["pct"], fill=C["accent"], tags=(tag,))
            bx1 = rx - f["small"].measure("100 %") - 8
            bx0 = bx1 - 110
            self._row_badge(btxt, bcol, bx0 - 10, mid - ph / 2, tx + name_w + 14, tag)
            cv.create_rectangle(bx0, mid - 2, bx1, mid + 3, fill=C["line"], outline="", tags=(tag,))
            cv.create_rectangle(bx0, mid - 2, bx0 + (bx1 - bx0) * dl.fraction, mid + 3, fill=C["accent"], outline="",
                                tags=(tag,))
        elif state == "error":
            cv.create_text(rx, mid, text="⚠ Falló", anchor="e", font=f["small"], fill=C["bad"], tags=(tag,))
            self._row_badge(btxt, bcol, rx - f["small"].measure("⚠ Falló") - 10, mid - ph / 2, tx + name_w + 14, tag)
        else:
            col = fade(C["muted"], .2)
            cv.create_text(rx, mid, text="Descargar", anchor="e", font=f["small"], fill=col, tags=(tag,))
            self._arrow(rx - f["small"].measure("Descargar") - 10, mid - 6, col, tag)
        self._bind_item(tag, it)

    def _row_badge(self, text, cols, right_x, y, left_min, tag):
        """Píldora de «en uso»/«nueva versión» junto al progreso o error de la lista, solo si cabe sin solapar."""
        if not text:
            return
        w = self._fonts["pill"].measure(text) + 8
        # a la izquierda hay un sello (~110 px): se exige hueco para él además de la píldora
        if right_x - w >= left_min + 120:
            self._pill(right_x, y, text, *cols, tag, right=True)

    def _pill(self, x, y, text, bg, fg, tag, right=False):
        f = self._fonts["pill"]
        w = f.measure(text) + 8
        h = f.metrics("linespace") + 2
        if right:
            x -= w
        self.cv.create_rectangle(x, y, x + w, y + h, fill=bg, outline="", tags=(tag,))
        self.cv.create_text(x + w / 2, y + h / 2, text=text, fill=fg, font=f, tags=(tag,))

    def paint_header(self):
        """Texto del botón de teclas según si el panel está a la vista."""
        try:
            hidden = self.app.themes_wide() or not self.app.left_panel.winfo_manager()
            self.btn_keys.configure(text="⌨ Mostrar teclas" if hidden else "⌨ Ocultar teclas")
        except (tk.TclError, AttributeError):
            pass

    def repaint_after_move(self):
        """Después de que la pestaña cambia de ancho: el detalle se vuelve a mostrar entero (si no, el
        sistema gráfico puede dejar zonas sin pintar) y las tarjetas se reacomodan."""
        try:
            self._on_tab_resize(self.t.winfo_width())
            if self._mode and not self._mode[1]:
                self.dbox.grid_remove()
                self.t.update_idletasks()
                self.dbox.grid()
            self._draw()
        except tk.TclError:
            pass

    def _wheel(self, e):
        if e.state & 0x4:                          # Ctrl + rueda: tamaño de la cuadrícula
            up = getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0
            if self.view == "grid":
                self.set_cols(self.cols - 1 if up else self.cols + 1)
                return
            # en Lista no hay tamaño que cambiar: la rueda desplaza como siempre
        if self._fits():
            return                                # todo cabe: no hay nada que desplazar (3.4.4)
        self._ensure_full()
        if getattr(e, "num", 0) in (4, 5):
            self.cv.yview_scroll(-2 if e.num == 4 else 2, "units")
        else:
            self.cv.yview_scroll(-1 if e.delta > 0 else 1, "units")

    def _pick(self, it):
        self.sel = it
        self._paint()
        if self._mode and self._mode[1]:
            self._just_picked = True
            self.t.after_idle(lambda: setattr(self, "_just_picked", False))
            self._open_overlay()

    def _dl(self, it):
        return self.dls.get(it["entry"]["id"]) if it["entry"] is not None else None

    # ------------------------------------------------------------ pintar
    def _paint_cards(self):
        self._draw()

    def _paint(self):
        self._paint_cards()
        it = self.sel
        if it is None:
            return
        th, e = it["th"], it["entry"]
        colors = self._colors(it)
        draw_preview(self.big, colors, self.BIG_W, self.big_h)
        name = th["name"] if th is not None else e["nombre"]
        self.d_name.configure(text=name)
        official = self._official(it)
        creator = it["facts"]["creator"]
        if creator:
            author = it["facts"]["creator_name"] or e.get("autor", "")
            self.d_sub.configure(text=f"por {author} · versión "
                                      + str((th or e).get("version", "1.0"))
                                      + (f" · {e['fecha']}" if th is None and e.get("fecha") else ""))
        elif th is not None:
            author = "OkumaWsX" if official else th.get("author", "")
            self.d_sub.configure(text=f"por {author} · versión {th.get('version', '1.0')}")
        else:
            self.d_sub.configure(text=f"por {e.get('autor', '')} · versión {e.get('version', '1.0')}"
                                      + (f" · {e['fecha']}" if e.get("fecha") else ""))
        # recuadro de estado (los creadores tienen su ficha: ver _paint_creator) y «sobre el tema»
        note = ""
        if th is not None and th.get("builtin"):
            txt, col = "✓ Tema incluido con Numpad Macros", C["ok"]
        elif creator:
            txt = col = None
            note = "Archivo íntegro: no fue modificado." if th is not None else "La firma se comprueba al descargarlo."
        elif official:
            txt, col = "✓ Tema oficial · firmado por OkumaWsX", C["ok"]
            txt += "\nArchivo íntegro: no fue modificado." if th is not None else "\nLa firma se comprueba al descargarlo."
        else:
            author = th.get("author", "") if th is not None else e.get("autor", "")
            txt, col = f"ⓘ Tema de la comunidad\nAutor: {author} · firma de autor verificada.", C["warn"]
            huella = e.get("huella_autor") if e else ""
            if huella:
                txt += f"\nHuella: {huella}"
            txt += "\nNo está firmado por OkumaWsX."
        if creator:
            self._paint_creator(it, th, e)
        else:
            self.d_status.configure(text=txt, fg=C["text"], bg=mix(col, C["panel2"], .85),
                                    highlightthickness=1, highlightbackground=col)
        self.d_info.configure(bg=C["panel2"])
        self._paint_about(it, bool(creator), note)
        cv = self.d_dots
        cv.delete("all")
        for i, (k, label) in enumerate(DOTS):
            x = 22 + (i % 6) * 43
            y = 16 + (i // 6) * 48
            img = aa.dot(cv, 26, colors.get(k, "#000000"), outline=C["line"], width=1)
            if img is not None:
                cv.create_image(x - 13, y - 13, image=img, anchor="nw")
            else:
                cv.create_oval(x - 13, y - 13, x + 13, y + 13, fill=colors.get(k, "#000000"), outline=C["line"])
            cv.create_text(x, y + 22, text=label, fill=C["muted"], font=(FONT, BASE - 3))
        self._paint_actions()
        # otro tema puede traer más o menos texto: el detalle no cambia de tamaño, así que se reajusta aquí
        self.t.after_idle(self._fit_detail)

    def _paint_actions(self):
        """El botón principal y los secundarios, según el estado del tema elegido."""
        it = self.sel
        th, e = it["th"], it["entry"]
        dl = self._dl(it)
        msg = ""
        both = export = remove = False
        if dl is not None and dl.state == "bajando":
            self.act.set("bajando", frac=dl.fraction)
        elif dl is not None and dl.state == "reintentando":
            self.act.set("reintentando", self._retry_txt.get(e["id"], "Reintentando…"))
        elif dl is not None and dl.state == "error":
            self.act.set("error", "↻  Reintentar")
            msg = dl.error
            both = th is None
        elif th is None:
            self.act.set("descargar", "Descargar")
            both = True
        elif catalogo.has_update(e or {}, th):
            self.act.set("actualizar", f"Actualizar a {e['version']}")
            export = remove = not th.get("builtin")
        elif self._same(th, self._cur):
            self.act.set("uso", "✓  En uso")
            export = remove = not th.get("builtin")
        else:
            self.act.set("aplicar", "Aplicar")
            export = remove = not th.get("builtin")
        export = export and th is not None
        # winfo_manager y no winfo_ismapped: con el detalle cerrado (encima de la lista) nada está a la vista
        for w, on in ((self.btn_both, both), (self.btn_export, export)):
            if on and not w.winfo_manager():
                w.pack(side="left", padx=(0, 6))
            elif not on:
                w.pack_forget()
        self.d_msg.configure(text=msg)
        if msg and not self.d_msg.winfo_manager():
            if self.btn_del.winfo_manager():
                self.d_msg.pack(fill="x", pady=(6, 0), before=self.btn_del)
            else:
                self.d_msg.pack(fill="x", pady=(6, 0))
        elif not msg:
            self.d_msg.pack_forget()
        if remove and not self.btn_del.winfo_manager():
            self.btn_del.pack(anchor="w", pady=(8, 0))
        elif not remove:
            self.btn_del.pack_forget()

    # ------------------------------------------------------------ descargas
    _retry_txt = {}

    def _act(self):
        """Clic en el botón principal: hace lo que dice (o cancela si está descargando)."""
        it = self.sel
        th, e = it["th"], it["entry"]
        dl = self._dl(it)
        if dl is not None and dl.state in ("bajando", "reintentando"):
            dl.cancel()                               # el mismo botón cancela
            return
        if th is None or (dl is not None and dl.state == "error") or catalogo.has_update(e or {}, th):
            self._download(apply=bool(dl is not None and getattr(dl, "apply_after", False)))
            return
        if not self._same(th, self._cur):
            self._use_now(th)

    def _download(self, apply=False):
        e = self.sel["entry"]
        if e is None:
            return
        old = self.dls.get(e["id"])
        if old is not None and old.state in ("bajando", "reintentando"):
            return
        dl = catalogo.Download(e, replace=self.sel["th"])
        dl.apply_after = apply
        self.dls[e["id"]] = dl
        dl.start()
        self._paint()

    def _poll(self):
        """Atiende los avisos de las descargas y del catálogo (los hilos no tocan la ventana)."""
        try:
            if not self.t.winfo_exists():
                return
        except tk.TclError:
            return
        changed = refresh = False
        done_apply = None
        while True:
            try:
                self._avatar_arrived(self._av_q.get_nowait())
            except queue.Empty:
                break
        for eid, dl in list(self.dls.items()):
            while True:
                try:
                    ev = dl.events.get_nowait()
                except queue.Empty:
                    break
                changed = True
                if ev[0] == "retry":
                    self._retry_txt[eid] = f"Reintentando… {ev[1]} de {ev[2]}"
                elif ev[0] == "done":
                    del self.dls[eid]
                    refresh = True
                    self.app._set_status(f"Tema instalado: {ev[1]['name']}")
                    if getattr(dl, "apply_after", False):
                        done_apply = ev[1]
                    break
                elif ev[0] == "cancelled":
                    self.dls.pop(eid, None)
                    self.app._set_status("Descarga cancelada. Tu tema actual no cambió.")
                    break
                elif ev[0] == "error":
                    self.app._set_status(ev[1], bad=True)
        if self.cat.get("new"):
            self.cat["new"] = False
            refresh = True
        if refresh:
            keep = self._key(self.sel) if self.sel else None
            if done_apply is None and self.sel and self.sel["th"] is None:
                keep = ("cat", self.sel["entry"]["id"])
            self.refresh(keep=keep)
        elif changed:
            self._paint_cards()
            self._paint_actions()
        if done_apply is not None:
            th = next((x["th"] for x in self.items if x["th"] is not None and x["th"].get("file") == done_apply["file"]),
                      done_apply)
            self._use_now(th)
            return
        self.t.after(120, self._poll)

    # ------------------------------------------------------------ acciones
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
            if th["result"] == "anterior":
                # es una versión más vieja del mismo tema: se pregunta, y por defecto no se toca
                if not messagebox.askyesno("Versión anterior",
                                           f"Ya tienes «{th['name']}» en la versión {th['old_version']} y este "
                                           f"archivo es la {th['version']}, más antigua.\n\n"
                                           "¿Reemplazar la versión instalada por la anterior?",
                                           default="no", parent=self.t):
                    self.refresh(keep=("th", th["name"], th.get("file", "")))
                    return
                th = themes.install(path, downgrade=True)
        except npt.NptError as e:
            messagebox.showerror("No se pudo importar el tema",
                                 f"{os.path.basename(path)}: {e}.\n\nTu tema actual no se tocó.", parent=self.t)
            return
        except OSError as e:
            messagebox.showerror("No se pudo importar el tema", str(e), parent=self.t)
            return
        self.refresh(keep=("th", th["name"], th.get("file", "")))
        if th["result"] == "igual":
            messagebox.showinfo("Tema ya instalado", f"Ya tienes este tema instalado: «{th['name']}».",
                                parent=self.t)
            return
        if th["result"] == "actualizado":
            messagebox.showinfo("Tema actualizado",
                                f"Se actualizó «{th['name']}» a la versión {th['version']}.", parent=self.t)
            cfg_th = self.app.cfg.get("theme") or {}
            if cfg_th.get("name") == th["name"] and cfg_th.get("file", "") == th.get("file", ""):
                self._use_now(th)                     # estaba aplicado: sigue aplicado, con la versión nueva
            return
        who = "Tema oficial, firmado por OkumaWsX." if th["official"] else \
            "Tema de la comunidad: no está firmado por OkumaWsX."
        if messagebox.askyesno("Tema instalado",
                               f"«{th['name']}» (por {th['author']}) quedó instalado.\n"
                               f"✓ Archivo íntegro.\n{who}\n\n¿Usarlo ahora?", parent=self.t):
            self._use_now(th)

    def _use_now(self, th):
        with self.app.engine.lock:
            self.app.cfg["theme"].update(name=th["name"], file=th.get("file", ""))
        self.app._save()
        self.app._theme_sel_keep = ("th", th["name"], th.get("file", ""))
        # se aplica al instante (después de que termine el clic en el botón, que se va a borrar)
        self.app.root.after(10, lambda: self.app.apply_theme_live(th))

    def _export(self):
        th = self.sel["th"]
        if th is None:
            return
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
        th = self.sel["th"]
        if th is None or th.get("builtin"):
            return
        if not messagebox.askyesno("Quitar tema", f"¿Quitar «{th['name']}» de tus temas?", parent=self.t):
            return
        themes.remove(th)
        self.sel = None
        self.refresh()

    def _open_folder(self):
        os.makedirs(themes.themes_dir(), exist_ok=True)
        self.app._open(themes.themes_dir())


def red_icon(master, red, px, claro=False):
    """El ícono a COLOR de una red (Simple Icons, CC0, con los colores de su marca), de ``px`` píxeles, o None.
    En assets/redes/ hay un PNG por red a 20 y 40 px (HiDPI; los genera tools/generar_iconos_redes.py): se
    elige el que sirve y, si no coincide el tamaño, se escala con Pillow (sin teñir). TikTok y X tienen
    una variante para fondo claro (``claro=True``, en negro); sin Pillow solo sirve el tamaño exacto."""
    sufijo = "-claro" if claro and red in ("tiktok", "x") else ""
    key = (red, px, sufijo)
    img = _RED_ICONS.get(key)
    if img is not None:
        return img
    try:
        ruta = sysutil.resource("assets", "redes", f"{red}-color{sufijo}-{20 if px <= 20 else 40}.png")
        if aa.HAVE_PIL:
            from PIL import Image
            im = Image.open(ruta).convert("RGBA")
            if im.size != (px, px):
                im = im.resize((px, px), Image.LANCZOS)
            img = aa._photo(master, im)
        elif px in (20, 40):
            img = tk.PhotoImage(master=master, file=ruta)
        else:
            return None
    except (OSError, ValueError, tk.TclError):
        return None
    _RED_ICONS[key] = img
    return img


def avatar_circle(master, path, px, border, ring_px):
    """La foto de ``path`` recortada en círculo de ``px`` píxeles con un borde de color ``border`` de
    ``ring_px``, o None si no se puede (sin Pillow, archivo roto). Se dibuja a 4× y se reduce, como el
    resto de las formas (aa.py), para que el borde no tenga dientes de sierra. Una foto que no es
    exactamente cuadrada se centra y se recorta."""
    if not aa.HAVE_PIL:
        return None
    try:
        from PIL import Image, ImageDraw
        S = px * aa.SS
        k = max(1, int(round(ring_px * aa.SS)))
        with Image.open(path) as im:
            im = im.convert("RGBA")
        lado = min(im.size)
        l, t = (im.width - lado) // 2, (im.height - lado) // 2
        foto = im.crop((l, t, l + lado, t + lado)).resize((S - 2 * k, S - 2 * k), Image.LANCZOS)
        big = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        ImageDraw.Draw(big).ellipse((0, 0, S - 1, S - 1), fill=aa._rgba(border))
        mask = Image.new("L", foto.size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, foto.width - 1, foto.height - 1), fill=255)
        big.paste(foto, (k, k), mask)
        return aa._photo(master, big.resize((px, px), Image.LANCZOS))
    except Exception:                       # archivo roto, imagen enorme…: se queda la inicial
        return None


def _tab_call(app, name, *args):
    """Llama a un método de la pestaña Temas actual (se vuelve a crear al cambiar de tema)."""
    tab = getattr(app, "themestab", None)
    try:
        if tab is not None and tab.t.winfo_exists():
            getattr(tab, name)(*args)
    except tk.TclError:
        pass


def _theme_colors(colores: dict) -> dict:
    """Colores del catálogo (nombres de los .npt) -> los mismos nombres que usa draw_preview."""
    return dict(colores)


def _ago(ts) -> str:
    s = max(0, time.time() - float(ts or 0))
    if s < 90:
        return "hace un momento"
    if s < 3600:
        return f"hace {int(s // 60)} min"
    if s < 86400:
        return f"hace {int(s // 3600)} h"
    return f"hace {int(s // 86400)} días"
