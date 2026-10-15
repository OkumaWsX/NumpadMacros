# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Ventanas de novedades y de actualización."""
import queue
import threading
import tkinter as tk
from tkinter import ttk

from . import updater
from .about import REPO
from .theme import BASE, C, FONT

# Secciones del CHANGELOG -> cómo se muestran
SECTION = {
    "añadido": ("Novedades", "＋", C["ok"]),
    "cambiado": ("Mejoras", "↑", "#6aa8ff"),
    "mejorado": ("Mejoras", "↑", "#6aa8ff"),
    "corregido": ("Correcciones", "✓", C["accent"]),
    "eliminado": ("Eliminado", "−", C["muted"]),
    "seguridad": ("Seguridad", "!", C["bad"]),
}


def _section(name):
    return SECTION.get(name.strip().lower(), (name, "•", C["muted"]))


def _notes_text(parent, height=12):
    box = tk.Frame(parent, bg=C["panel"])
    box.columnconfigure(0, weight=1)
    box.rowconfigure(0, weight=1)
    txt = tk.Text(box, bg=C["panel"], fg=C["text"], bd=0, highlightthickness=0, wrap="word",
                  font=(FONT, BASE), height=height, padx=4, pady=4, cursor="arrow")
    txt.grid(row=0, column=0, sticky="nsew")
    sb = ttk.Scrollbar(box, orient="vertical", command=txt.yview)
    sb.grid(row=0, column=1, sticky="ns")
    txt.configure(yscrollcommand=sb.set)
    txt.tag_configure("h", font=(FONT, BASE + 1, "bold"), spacing1=10, spacing3=4)
    txt.tag_configure("li", lmargin1=6, lmargin2=28, spacing1=2, spacing3=2)
    for name, (_t, _i, color) in SECTION.items():
        txt.tag_configure("ic_" + name, foreground=color, font=(FONT, BASE, "bold"))
    txt.tag_configure("ic_otro", foreground=C["muted"], font=(FONT, BASE, "bold"))
    return box, txt


def _fill_notes(txt, groups):
    """groups: [(sección, [líneas])]"""
    txt.configure(state="normal")
    txt.delete("1.0", "end")
    merged: dict[str, list] = {}
    for name, lines in groups:
        merged.setdefault(name, []).extend(lines)
    first = True
    for name, lines in merged.items():
        if not lines:
            continue
        title, icon, _c = _section(name)
        key = name.strip().lower()
        tag = "ic_" + key if key in SECTION else "ic_otro"
        txt.insert("end", title + "\n", "h")
        first = False
        for line in lines:
            txt.insert("end", icon + "  ", ("li", tag))
            txt.insert("end", line + "\n", "li")
    if first:
        txt.insert("end", "Esta versión no trae notas.", "li")
    txt.configure(state="disabled")


def _center(win, parent, w, h):
    parent.update_idletasks()
    try:
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 3
    except tk.TclError:
        x = y = 100
    win.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")


def _button(parent, text, cmd, accent=False):
    return ttk.Button(parent, text=text, command=cmd, style="Accent.TButton" if accent else "TButton")


# ============================================================================ novedades
class NewsDialog(tk.Toplevel):
    """Novedades y correcciones de la versión instalada (y de las anteriores)."""

    def __init__(self, root, versions, installed, show_var: tk.BooleanVar, on_show_change):
        super().__init__(root, bg=C["panel"])
        self.title("Novedades de Numpad Macros")
        self.transient(root)
        self.versions = [v for v in versions if not updater.newer(v["version"], installed)][:8]
        self.installed = installed
        _center(self, root, 640, 560)
        self.minsize(520, 420)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        head = tk.Frame(self, bg=C["panel"])
        head.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 6))
        self.kicker = tk.Label(head, bg=C["panel"], fg=C["muted"], font=(FONT, BASE - 1))
        self.kicker.pack(anchor="w")
        self.title_lbl = tk.Label(head, bg=C["panel"], fg=C["text"], font=(FONT, BASE + 8, "bold"))
        self.title_lbl.pack(anchor="w")
        self.date_lbl = tk.Label(head, bg=C["panel"], fg=C["muted"], font=(FONT, BASE - 1))
        self.date_lbl.pack(anchor="w")

        chips = tk.Frame(self, bg=C["panel"])
        chips.grid(row=1, column=0, sticky="ew", padx=22, pady=(6, 8))
        self.chips = []
        for v in self.versions:
            label = v["version"] + (" (instalada)" if v["version"] == installed else "")
            b = tk.Label(chips, text=label, font=(FONT, BASE - 1), padx=10, pady=3, cursor="hand2")
            b.pack(side="left", padx=(0, 6))
            b.bind("<Button-1>", lambda e, ver=v: self.show(ver))
            self.chips.append((v, b))

        box, self.txt = _notes_text(self, 14)
        box.grid(row=2, column=0, sticky="nsew", padx=22)

        foot = tk.Frame(self, bg=C["panel"])
        foot.grid(row=3, column=0, sticky="ew", padx=22, pady=14)
        ttk.Checkbutton(foot, text="Mostrar al abrir una versión nueva", variable=show_var,
                        command=on_show_change).pack(side="left")
        link = tk.Label(foot, text="Todas las versiones ↗", bg=C["panel"], fg=C["accent"],
                        cursor="hand2", font=(FONT, BASE - 1))
        link.pack(side="left", padx=16)
        link.bind("<Button-1>", lambda e: self._open(updater.RELEASES_URL))
        _button(foot, "Entendido", self.destroy, accent=True).pack(side="right")
        self.bind("<Escape>", lambda e: self.destroy())

        cur = next((v for v in self.versions if v["version"] == installed), None)
        if cur:
            self.show(cur)
        elif self.versions:
            self.show(self.versions[0])
        else:
            self.title_lbl.configure(text=f"Numpad Macros {installed}")
            _fill_notes(self.txt, [])
        self.lift()
        self.focus_force()

    def _open(self, url):
        from .sysutil import open_url
        open_url(url)

    def show(self, v):
        mine = v["version"] == self.installed
        self.kicker.configure(text="Versión instalada · novedades y correcciones" if mine else "Versión anterior")
        self.title_lbl.configure(text=f"Numpad Macros {v['version']}")
        self.date_lbl.configure(text=f"Publicada el {v['date']}" if v.get("date") else "")
        for ver, b in self.chips:
            on = ver is v
            b.configure(bg=C["accent"] if on else C["panel2"], fg="#1a1306" if on else C["text"])
        _fill_notes(self.txt, v["groups"])


# ============================================================================ actualización
class UpdateDialog(tk.Toplevel):
    """Novedades de la versión nueva → descarga → verificación → instalación."""

    def __init__(self, root, rel: updater.Release, kind: str, on_skip, on_ready):
        super().__init__(root, bg=C["panel"])
        self.title("Actualizar Numpad Macros")
        self.transient(root)
        self.rel, self.kind = rel, kind
        self.on_skip, self.on_ready = on_skip, on_ready
        self.q: queue.Queue = queue.Queue()
        self.cancel = False
        self.busy = False
        _center(self, root, 600, 540)
        self.minsize(500, 440)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._build_notes()
        self.lift()
        self.focus_force()

    # ---------------------------------------------------------------- paso 1: novedades
    def _build_notes(self):
        rel = self.rel
        f = tk.Frame(self, bg=C["panel"])
        f.grid(row=0, column=0, sticky="nsew", padx=22, pady=18)
        f.columnconfigure(0, weight=1)
        f.rowconfigure(3, weight=1)
        self.page = f
        tag = " · importante" if rel.important else (" · versión de prueba" if rel.prerelease else "")
        tk.Label(f, text="Nueva versión disponible" + tag, bg=C["panel"],
                 fg=C["bad"] if rel.important else C["muted"], font=(FONT, BASE - 1)).grid(row=0, column=0, sticky="w")
        tk.Label(f, text=f"Numpad Macros {rel.version}", bg=C["panel"], fg=C["text"],
                 font=(FONT, BASE + 8, "bold")).grid(row=1, column=0, sticky="w")
        size = rel.asset()[1] if rel.asset() else 0
        sub = (f"Publicada el {rel.published}" if rel.published else "") + \
            (f" · {size / 1e6:.0f} MB" if size >= 1e6 and self.kind != "manual" else "")
        tk.Label(f, text=sub.strip(" ·"), bg=C["panel"], fg=C["muted"],
                 font=(FONT, BASE - 1)).grid(row=2, column=0, sticky="w", pady=(0, 8))
        box, txt = _notes_text(f, 10)
        box.grid(row=3, column=0, sticky="nsew")
        groups: list = []
        for section, line in rel.notes_lines():
            if not groups or groups[-1][0] != section:
                groups.append((section, []))
            groups[-1][1].append(line)
        _fill_notes(txt, groups)
        info = {
            "installer": "Tu configuración, bancos y sonidos se mantienen. Windows te pedirá permiso una "
                         "vez; la app se cerrará un momento y volverá a abrirse sola.",
            "binary": "Tu configuración, bancos y sonidos se mantienen. La app se cerrará un momento y "
                      "volverá a abrirse sola.",
            "manual": "En esta instalación la actualización no puede hacerse sola: se abrirá la página "
                      "de descarga. Tu configuración, bancos y sonidos se mantienen.",
        }[self.kind]
        tk.Label(f, text=info, bg=C["panel2"], fg="#b9bdc6", font=(FONT, BASE - 1), justify="left",
                 wraplength=520, padx=12, pady=10, anchor="w").grid(row=4, column=0, sticky="ew", pady=(12, 0))
        btns = tk.Frame(f, bg=C["panel"])
        btns.grid(row=5, column=0, sticky="ew", pady=(14, 0))
        _button(btns, "Ir a la descarga" if self.kind == "manual" else "Actualizar ahora",
                self._start, accent=True).pack(side="left")
        _button(btns, "Más tarde", self._close).pack(side="left", padx=8)
        if not self.rel.important:
            skip = tk.Label(btns, text="Omitir esta versión", bg=C["panel"], fg=C["muted"],
                            cursor="hand2", font=(FONT, BASE - 1, "underline"))
            skip.pack(side="right")
            skip.bind("<Button-1>", lambda e: self._skip())

    def _skip(self):
        self.on_skip(self.rel.version)
        self.destroy()

    def _close(self):
        if self.busy:
            self.cancel = True
            return
        self.destroy()

    # ---------------------------------------------------------------- paso 2: descarga
    def _start(self):
        if self.kind == "manual":
            from .sysutil import open_url
            open_url(self.rel.url)
            self.destroy()
            return
        self.page.destroy()
        f = tk.Frame(self, bg=C["panel"])
        f.grid(row=0, column=0, sticky="nsew", padx=22, pady=22)
        f.columnconfigure(0, weight=1)
        self.page = f
        self.p_title = tk.Label(f, bg=C["panel"], fg=C["text"], font=(FONT, BASE + 5, "bold"), anchor="w")
        self.p_title.grid(row=0, column=0, sticky="ew")
        self.p_sub = tk.Label(f, bg=C["panel"], fg=C["muted"], font=(FONT, BASE - 1), anchor="w",
                              justify="left", wraplength=520)
        self.p_sub.grid(row=1, column=0, sticky="ew", pady=(2, 14))
        self.bar = ttk.Progressbar(f, mode="determinate", maximum=100)
        self.bar.grid(row=2, column=0, sticky="ew")
        self.p_info = tk.Label(f, bg=C["panel"], fg=C["muted"], font=(FONT, BASE - 1), anchor="w")
        self.p_info.grid(row=3, column=0, sticky="ew", pady=(6, 12))
        self.steps = []
        for i, name in enumerate(("Descargar", "Verificar que el archivo es el original", "Instalar",
                                  "Volver a abrir la app")):
            lbl = tk.Label(f, text="·  " + name, bg=C["panel"], fg=C["muted"], font=(FONT, BASE), anchor="w")
            lbl.grid(row=4 + i, column=0, sticky="ew", pady=1)
            self.steps.append((name, lbl))
        self.btn_cancel = _button(f, "Cancelar", self._close)
        self.btn_cancel.grid(row=9, column=0, sticky="w", pady=(16, 0))
        self._step(0)
        self.p_title.configure(text=f"Descargando {self.rel.version}…")
        self.p_sub.configure(text=f"Desde GitHub · {REPO}")
        self.busy = True
        threading.Thread(target=self._work, daemon=True).start()
        self.after(80, self._pump)

    def _step(self, n):
        for i, (name, lbl) in enumerate(self.steps):
            if i < n:
                lbl.configure(text="✓  " + name, fg=C["ok"], font=(FONT, BASE))
            elif i == n:
                lbl.configure(text="›  " + name, fg=C["text"], font=(FONT, BASE, "bold"))
            else:
                lbl.configure(text="·  " + name, fg=C["muted"], font=(FONT, BASE))

    def _work(self):
        try:
            def prog(done, total):
                self.q.put(("prog", done, total))
            path = updater.download(self.rel, prog, lambda: self.cancel)
            self.q.put(("ok", path))
        except updater.UpdateError as e:
            self.q.put(("err", str(e)))
        except Exception as e:      # nunca dejar la ventana colgada
            self.q.put(("err", f"Error inesperado: {e}"))

    def _pump(self):
        try:
            while True:
                ev = self.q.get_nowait()
                if ev[0] == "prog":
                    _, done, total = ev
                    pct = 100 * done / total if total else 0
                    self.bar.configure(value=pct)
                    self.p_info.configure(text=(f"{done / 1e6:.1f} de {total / 1e6:.1f} MB · {pct:.0f} %"
                                                if total else f"{done / 1e6:.1f} MB"))
                elif ev[0] == "err":
                    self.busy = False
                    self.p_title.configure(text="No se pudo actualizar")
                    self.p_sub.configure(text=ev[1] + " No se cambió nada.", fg=C["bad"])
                    self.btn_cancel.configure(text="Cerrar", command=self.destroy)
                    return
                elif ev[0] == "ok":
                    self.busy = False
                    self.bar.configure(value=100)
                    self._step(2)
                    self.p_title.configure(text="Instalando…")
                    self.p_sub.configure(text="Numpad Macros se cerrará y volverá a abrirse sola.")
                    self.btn_cancel.grid_remove()
                    self.after(600, lambda p=ev[1]: self.on_ready(p, self))
                    return
        except queue.Empty:
            pass
        if self.busy:
            self.after(80, self._pump)

    def fail(self, msg):
        """La instalación no se pudo iniciar (por ejemplo, Windows no dio permiso)."""
        self.p_title.configure(text="No se instaló")
        self.p_sub.configure(text=msg + " Puedes volver a intentarlo más tarde.", fg=C["bad"])
        self.btn_cancel.configure(text="Cerrar", command=self.destroy)
        self.btn_cancel.grid()
