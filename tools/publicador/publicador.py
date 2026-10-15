# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Publicador de Numpad Macros: arrastra la versión nueva y pulsa «Publicar».

Solo para el creador. Revisa el archivo, lo sube a GitHub y pone a trabajar al
robot «Publicar versión», que compila, crea la Release y avisa en Discord.
"""
import os
import queue
import sys
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nucleo as core  # noqa: E402

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception:          # sin la librería se puede elegir el archivo con un botón
    TkinterDnD = None

VERSION = "1.0.0"
FONT = "Segoe UI" if os.name == "nt" else ("Helvetica Neue" if sys.platform == "darwin" else "DejaVu Sans")
BASE = 13 if sys.platform == "darwin" else 10
C = {"bg": "#14161b", "panel": "#1c1f26", "panel2": "#232730", "line": "#2e333d", "text": "#e9e9ec",
     "muted": "#8b909b", "accent": "#f2a33a", "ok": "#4cc38a", "bad": "#e5534b", "warn": "#e2b340"}


def open_url(url):
    try:
        webbrowser.open(url)
    except Exception:
        pass


class App:
    def __init__(self, root):
        self.root = root
        self.settings = core.load_settings()
        self.q: queue.Queue = queue.Queue()
        self.gh = None
        self.pkg = None
        self.rv = None
        self.page = None
        self.version = None
        self.run_id = None
        self.user = ""
        self._style()
        self._chrome()
        root.after(60, self._pump)
        if self.settings.get("token"):
            self.gh = core.GitHub(self.settings["token"])
            self.show_home()
        else:
            self.show_connect()

    # ================================================================ base
    def _style(self):
        r = self.root
        r.title("Publicador · Numpad Macros")
        r.configure(bg=C["bg"])
        r.geometry("880x700")
        r.minsize(760, 600)
        s = ttk.Style(r)
        s.theme_use("clam")
        s.configure(".", background=C["panel"], foreground=C["text"], fieldbackground=C["panel2"],
                    bordercolor=C["line"], lightcolor=C["line"], darkcolor=C["line"], font=(FONT, BASE))
        s.configure("TButton", background=C["panel2"], foreground=C["text"], padding=(12, 6))
        s.map("TButton", background=[("active", C["line"]), ("disabled", C["panel"])],
              foreground=[("disabled", C["muted"])])
        s.configure("Accent.TButton", background=C["accent"], foreground="#1a1306", font=(FONT, BASE + 1, "bold"),
                    padding=(18, 9))
        s.map("Accent.TButton", background=[("active", "#ffb855"), ("disabled", C["panel2"])])
        s.configure("TCheckbutton", background=C["panel"], foreground=C["text"])
        s.map("TCheckbutton", background=[("active", C["panel"])],
              indicatorcolor=[("selected", C["accent"]), ("!selected", C["panel2"])])
        s.configure("TEntry", foreground=C["text"], insertcolor=C["text"])
        s.configure("Horizontal.TProgressbar", background=C["accent"], troughcolor=C["panel2"],
                    bordercolor=C["panel2"], lightcolor=C["accent"], darkcolor=C["accent"])
        s.configure("Vertical.TScrollbar", background=C["line"], troughcolor=C["panel2"], arrowcolor=C["muted"])

    def _chrome(self):
        r = self.root
        r.columnconfigure(0, weight=1)
        r.rowconfigure(1, weight=1)
        head = tk.Frame(r, bg=C["bg"])
        head.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 10))
        head.columnconfigure(0, weight=1)
        tk.Label(head, text="Publicador · Numpad Macros", bg=C["bg"], fg=C["text"],
                 font=(FONT, BASE + 7, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(head, text="Solo para ti (el creador). Los usuarios nunca ven esta ventana.", bg=C["bg"],
                 fg=C["muted"], font=(FONT, BASE - 1)).grid(row=1, column=0, sticky="w")
        self.who = tk.Label(head, bg=C["bg"], fg=C["ok"], font=(FONT, BASE - 1), anchor="e")
        self.who.grid(row=0, column=1, sticky="e")
        self.pub_lbl = tk.Label(head, bg=C["bg"], fg=C["muted"], font=(FONT, BASE - 1), anchor="e")
        self.pub_lbl.grid(row=1, column=1, sticky="e")
        self.body = tk.Frame(r, bg=C["panel"], highlightbackground=C["line"], highlightthickness=1)
        self.body.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(0, weight=1)

    def _new_page(self):
        if self.page is not None:
            self.page.destroy()
        self.page = tk.Frame(self.body, bg=C["panel"])
        self.page.grid(row=0, column=0, sticky="nsew", padx=22, pady=20)
        self.page.columnconfigure(0, weight=1)
        return self.page

    def _label(self, parent, text, size=0, bold=False, color=None, wrap=780, **grid):
        lbl = tk.Label(parent, text=text, bg=parent["bg"], fg=color or C["text"], justify="left", anchor="w",
                       font=(FONT, BASE + size, "bold" if bold else "normal"), wraplength=wrap)
        if grid:
            lbl.grid(sticky="w", **grid)
        return lbl

    def _bg(self, job, done):
        """Ejecuta job() en otro hilo y llama done(resultado, error) en la ventana."""
        def run():
            try:
                res = job()
                self.q.put((done, res, None))
            except core.PubError as e:
                self.q.put((done, None, str(e)))
            except Exception as e:      # nunca dejar la ventana colgada
                self.q.put((done, None, f"Error inesperado: {e}"))
        threading.Thread(target=run, daemon=True).start()

    def _pump(self):
        try:
            while True:
                fn, res, err = self.q.get_nowait()
                fn(res, err)
        except queue.Empty:
            pass
        self.root.after(60, self._pump)

    # ================================================================ conectar
    def show_connect(self, error=""):
        p = self._new_page()
        self.who.configure(text="")
        self._label(p, "Conectar con GitHub (una sola vez)", 5, True, row=0, column=0)
        self._label(p, "El Publicador necesita un «token»: una llave que le permite subir versiones a tu "
                       "repositorio NumpadMacros. Se guarda solo en este PC.", color=C["muted"],
                    row=1, column=0, pady=(4, 14))
        steps = [
            "Pulsa «Crear el token en GitHub» (se abre tu navegador, con tu sesión de GitHub).",
            "Nombre: «Publicador Numpad Macros». Expiración: 1 año.",
            "En «Repository access» elige «Only select repositories» → NumpadMacros.",
            "En «Permissions → Repository permissions» pon en «Read and write»: Actions, Contents y Workflows.",
            "Pulsa «Generate token», copia el texto que empieza con github_pat_ y pégalo abajo.",
        ]
        for i, s in enumerate(steps):
            self._label(p, f"{i + 1}.  {s}", row=2 + i, column=0, pady=2)
        ttk.Button(p, text="Crear el token en GitHub ↗", command=lambda: open_url(core.TOKEN_URL)).grid(
            row=8, column=0, sticky="w", pady=(12, 14))
        row = tk.Frame(p, bg=C["panel"])
        row.grid(row=9, column=0, sticky="ew")
        row.columnconfigure(0, weight=1)
        self.token_var = tk.StringVar()
        e = ttk.Entry(row, textvariable=self.token_var, show="•", font=(FONT, BASE + 1))
        e.grid(row=0, column=0, sticky="ew", ipady=4)
        e.focus_set()
        self.btn_save = ttk.Button(row, text="Guardar y probar", style="Accent.TButton", command=self._save_token)
        self.btn_save.grid(row=0, column=1, padx=(10, 0))
        self.connect_msg = self._label(p, error, color=C["bad"], row=10, column=0, pady=(10, 0))

    def _save_token(self):
        tok = self.token_var.get().strip()
        if not tok:
            return
        self.btn_save.state(["disabled"])
        self.connect_msg.configure(text="Probando…", fg=C["muted"])
        gh = core.GitHub(tok)

        def job():
            access = gh.check_access()
            return gh.whoami(), access

        def done(res, err):
            self.btn_save.state(["!disabled"])
            if err:
                self.connect_msg.configure(text=err, fg=C["bad"])
                return
            self.settings["token"] = tok
            core.save_settings(self.settings)
            self.gh = gh
            self.show_home()
        self._bg(job, done)

    # ================================================================ inicio
    def show_home(self):
        self._cleanup()
        p = self._new_page()
        p.rowconfigure(2, weight=1)
        drop = tk.Frame(p, bg="#1a1d23", highlightbackground="#3a3f4a", highlightthickness=2, cursor="hand2")
        drop.grid(row=0, column=0, sticky="ew")
        drop.columnconfigure(0, weight=1)
        tk.Label(drop, text="⬆", bg="#1a1d23", fg=C["accent"], font=(FONT, BASE + 18, "bold")).grid(
            row=0, column=0, pady=(28, 0))
        tk.Label(drop, text="Arrastra aquí la versión nueva" if TkinterDnD else "Elige la versión nueva",
                 bg="#1a1d23", fg=C["text"], font=(FONT, BASE + 5, "bold")).grid(row=1, column=0, pady=(6, 0))
        tk.Label(drop, text="El archivo NumpadMacros-codigo_X.Y.Z.zip que te entrego (o la carpeta del proyecto)",
                 bg="#1a1d23", fg="#b9bdc6").grid(row=2, column=0, pady=(4, 0))
        tk.Label(drop, text="No hace falta el .exe: el instalador se fabrica solo en GitHub.", bg="#1a1d23",
                 fg=C["muted"], font=(FONT, BASE - 1)).grid(row=3, column=0, pady=(6, 0))
        btns = tk.Frame(drop, bg="#1a1d23")
        btns.grid(row=4, column=0, pady=(12, 26))
        ttk.Button(btns, text="Elegir archivo .zip…", command=self._pick_file).pack(side="left", padx=4)
        ttk.Button(btns, text="Elegir carpeta…", command=self._pick_dir).pack(side="left", padx=4)
        for w in [drop] + drop.winfo_children():
            if TkinterDnD:
                try:
                    w.drop_target_register(DND_FILES)
                    w.dnd_bind("<<Drop>>", self._on_drop)
                    w.dnd_bind("<<DropEnter>>", lambda e: (drop.configure(highlightbackground=C["accent"]), e.action)[1])
                    w.dnd_bind("<<DropLeave>>", lambda e: (drop.configure(highlightbackground="#3a3f4a"), e.action)[1])
                except Exception:
                    pass
        self._label(p, "Versiones publicadas", 1, True, row=1, column=0, pady=(18, 6))
        self.hist = tk.Frame(p, bg=C["panel"])
        self.hist.grid(row=2, column=0, sticky="nsew")
        self.hist.columnconfigure(2, weight=1)
        self._label(self.hist, "Cargando…", color=C["muted"], row=0, column=0)
        foot = tk.Frame(p, bg=C["panel"])
        foot.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        link = tk.Label(foot, text="Cambiar token", bg=C["panel"], fg=C["muted"], cursor="hand2",
                        font=(FONT, BASE - 1, "underline"))
        link.pack(side="right")
        link.bind("<Button-1>", lambda e: self.show_connect())
        tk.Label(foot, text=f"Publicador {VERSION}", bg=C["panel"], fg=C["muted"], font=(FONT, BASE - 2)).pack(side="left")

        def job():
            return self.gh.whoami(), self.gh.releases(6), self.gh.last_published()

        def done(res, err):
            if err:
                if "no acepta" in err or "401" in err:
                    self.show_connect(err)
                    return
                for w in self.hist.winfo_children():
                    w.destroy()
                self._label(self.hist, err, color=C["bad"], row=0, column=0)
                return
            self.user, rels, last = res
            self.who.configure(text=f"● Conectado a GitHub como {self.user}")
            self.pub_lbl.configure(text=f"Última versión publicada: {core.vstr(last)}")
            for w in self.hist.winfo_children():
                w.destroy()
            if not rels:
                self._label(self.hist, "Todavía no hay versiones publicadas: esta será la primera.",
                            color=C["muted"], row=0, column=0, columnspan=3)
            for i, rel in enumerate(rels):
                tag = rel.get("tag_name", "")
                date = (rel.get("published_at") or "")[:10]
                extra = " · beta" if rel.get("prerelease") else ""
                tk.Label(self.hist, text=tag + extra, bg=C["panel2"], fg=C["text"], font=(FONT, BASE, "bold"),
                         padx=10, pady=6, anchor="w", width=14).grid(row=i, column=0, sticky="ew", pady=2)
                tk.Label(self.hist, text=date, bg=C["panel2"], fg=C["muted"], padx=10, pady=6, anchor="w",
                         width=12).grid(row=i, column=1, sticky="ew", pady=2)
                lnk = tk.Label(self.hist, text="Ver en GitHub ↗", bg=C["panel2"], fg=C["accent"], padx=10, pady=6,
                               anchor="e", cursor="hand2")
                lnk.grid(row=i, column=2, sticky="ew", pady=2)
                lnk.bind("<Button-1>", lambda e, u=rel.get("html_url", ""): open_url(u))
        self._bg(job, done)

    def _pick_file(self):
        path = filedialog.askopenfilename(parent=self.root, title="Elige la versión (.zip)",
                                          filetypes=[("Código de Numpad Macros", "*.zip"), ("Todos", "*")])
        if path:
            self.start_review(path)

    def _pick_dir(self):
        path = filedialog.askdirectory(parent=self.root, title="Elige la carpeta del proyecto")
        if path:
            self.start_review(path)

    def _on_drop(self, ev):
        paths = self.root.tk.splitlist(ev.data)
        if paths:
            self.start_review(paths[0])
        return ev.action

    # ================================================================ revisar
    CHECKS = ["Leer el archivo", "Es Numpad Macros", "La versión es más nueva", "Tiene novedades anotadas",
              "Comparar con lo publicado"]

    def start_review(self, path):
        p = self._new_page()
        self._label(p, f"Revisando {os.path.basename(path.rstrip('/'))}…", 5, True, row=0, column=0)
        self.check_rows = []
        for i, name in enumerate(self.CHECKS):
            f = tk.Frame(p, bg=C["panel"])
            f.grid(row=1 + i, column=0, sticky="ew", pady=4)
            icon = tk.Label(f, text="·", bg=C["panel"], fg=C["muted"], font=(FONT, BASE + 1, "bold"), width=2)
            icon.pack(side="left", anchor="n")
            col = tk.Frame(f, bg=C["panel"])
            col.pack(side="left", fill="x")
            title = tk.Label(col, text=name, bg=C["panel"], fg=C["muted"], font=(FONT, BASE), anchor="w")
            title.pack(anchor="w")
            detail = tk.Label(col, text="", bg=C["panel"], fg=C["muted"], font=(FONT, BASE - 1), anchor="w",
                              justify="left", wraplength=700)
            detail.pack(anchor="w")
            self.check_rows.append((icon, title, detail))
        self.fail_box = tk.Frame(p, bg=C["panel"])
        self.fail_box.grid(row=10, column=0, sticky="ew", pady=(16, 0))
        self._mark(0, "run")
        rv = core.Review()
        self.rv = rv

        def step(i, state, detail=""):
            self.q.put((lambda _r, _e: self._mark(i, state, detail), None, None))

        def job():
            self._cleanup()
            pkg = core.Package(path)
            self.pkg = pkg
            step(0, "ok", os.path.basename(path.rstrip("/")))
            step(1, "run")
            if not pkg.is_numpad_macros():
                raise core.PubError("No es Numpad Macros: el identificador de la app no coincide. Así se evita "
                                    "publicar por error otra aplicación encima de esta.|1")
            step(1, "ok", "Mismo identificador de app: se instala encima, no como una app distinta.")
            step(2, "run")
            rv.version = pkg.version()
            rv.published = self.gh.last_published()
            if not rv.version:
                raise core.PubError("No encontré el número de versión en npm/__init__.py.|2")
            if rv.published and rv.version <= rv.published:
                raise core.PubError(f"La versión {core.vstr(rv.version)} no es más nueva que la publicada "
                                    f"({core.vstr(rv.published)}). Puede que hayas arrastrado una entrega anterior.|2")
            rv.kind = core.kind_of(rv.version, rv.published)
            step(2, "ok", f"{core.vstr(rv.version)} es mayor que {core.vstr(rv.published)}")
            step(3, "run")
            rv.notes = pkg.unreleased() or ""
            if not any(line.strip().startswith(("-", "*")) for line in rv.notes.splitlines()):
                raise core.PubError("La sección «Sin publicar» del CHANGELOG está vacía. Pídeme que anote los "
                                    "cambios o escríbelos en la siguiente pantalla… (no hay nada que mostrar a "
                                    "los usuarios).|3")
            n = sum(1 for line in rv.notes.splitlines() if line.strip().startswith(("-", "*")))
            step(3, "ok", f"{n} cambios anotados en el CHANGELOG")
            step(4, "run")
            core.compare(pkg, self.gh, rv)
            total = len(rv.added) + len(rv.changed) + len(rv.deleted)
            step(4, "ok", f"{total} archivos cambiados" if total else "El código ya está en GitHub (solo falta publicar)")
            return rv

        def done(res, err):
            if err:
                msg, _, idx = err.rpartition("|")
                if not msg:
                    msg, idx = err, None
                i = int(idx) if idx and idx.isdigit() else next(
                    (k for k, (ic, *_x) in enumerate(self.check_rows) if ic["text"] == "●"), 0)
                self._mark(i, "bad")
                box = tk.Frame(self.fail_box, bg="#3a1a1a", highlightbackground="#7a2e2e", highlightthickness=1)
                box.pack(fill="x")
                self._label(box, "No se puede publicar este archivo.", 0, True, wrap=740).pack(anchor="w", padx=12, pady=(10, 0))
                self._label(box, msg, color="#e3b5b5", wrap=740).pack(anchor="w", padx=12)
                ttk.Button(box, text="Elegir otro archivo", command=self.show_home).pack(anchor="w", padx=12, pady=10)
                return
            self.root.after(400, self.show_review)
        self._bg(job, done)

    def _mark(self, i, state, detail=""):
        icon, title, det = self.check_rows[i]
        icon.configure(text={"run": "●", "ok": "✓", "bad": "✕"}[state],
                       fg={"run": C["accent"], "ok": C["ok"], "bad": C["bad"]}[state])
        title.configure(fg=C["text"], font=(FONT, BASE, "bold" if state == "run" else "normal"))
        if detail:
            det.configure(text=detail)

    # ================================================================ confirmar
    def show_review(self):
        rv = self.rv
        p = self._new_page()
        p.rowconfigure(1, weight=1)
        top = tk.Frame(p, bg=C["panel"])
        top.grid(row=0, column=0, sticky="ew")
        tk.Label(top, text=core.vstr(rv.published), bg=C["panel2"], fg=C["muted"], font=(FONT, BASE + 7, "bold"),
                 padx=14, pady=6).pack(side="left")
        tk.Label(top, text="→", bg=C["panel"], fg=C["muted"], font=(FONT, BASE + 7)).pack(side="left", padx=10)
        tk.Label(top, text=core.vstr(rv.version), bg="#3a2c14", fg=C["accent"], font=(FONT, BASE + 7, "bold"),
                 padx=14, pady=6, highlightbackground="#7a5520", highlightthickness=1).pack(side="left")
        info = tk.Frame(top, bg=C["panel"])
        info.pack(side="left", padx=16)
        self._label(info, f"Tipo detectado: {rv.kind}", bold=True).pack(anchor="w")
        self._label(info, "Se instalará encima de la que tienen los usuarios, como actualización de la misma app.",
                    color="#b9bdc6", wrap=420).pack(anchor="w")

        mid = tk.Frame(p, bg=C["panel"])
        mid.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        mid.columnconfigure(0, weight=1)
        mid.columnconfigure(1, weight=0, minsize=300)
        mid.rowconfigure(1, weight=1)
        self._label(mid, "Notas de la versión (salen del CHANGELOG; puedes corregirlas aquí)", bold=True).grid(
            row=0, column=0, sticky="w")
        tbox = tk.Frame(mid, bg=C["panel"])
        tbox.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        tbox.columnconfigure(0, weight=1)
        tbox.rowconfigure(0, weight=1)
        self.notes_txt = tk.Text(tbox, bg=C["panel2"], fg=C["text"], insertbackground=C["text"], bd=0,
                                 highlightthickness=1, highlightbackground=C["line"], wrap="word",
                                 font=(FONT, BASE), padx=10, pady=8, undo=True)
        self.notes_txt.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(tbox, orient="vertical", command=self.notes_txt.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.notes_txt.configure(yscrollcommand=sb.set)
        self.notes_txt.insert("1.0", rv.notes)
        files = rv.added + rv.changed
        summary = (f"Archivos: {len(rv.changed)} cambiados, {len(rv.added)} nuevos"
                   + (f", {len(rv.deleted)} que se borran" if rv.deleted else "") + ".")
        if files:
            summary += " " + ", ".join(os.path.basename(f) for f in files[:5]) + (" y más." if len(files) > 5 else ".")
        if not (rv.added or rv.changed or rv.deleted):
            summary = "El código ya está en GitHub: solo se publica."
        self._label(mid, summary, -1, color=C["muted"], wrap=480).grid(row=2, column=0, sticky="w", pady=(6, 0))
        if rv.deleted:
            self._label(mid, "Se borran: " + ", ".join(rv.deleted[:6]) + (" y más" if len(rv.deleted) > 6 else ""),
                        -1, color=C["warn"], wrap=480).grid(row=3, column=0, sticky="w")

        opt = tk.Frame(mid, bg=C["panel"])
        opt.grid(row=0, column=1, rowspan=4, sticky="nsew", padx=(18, 0))
        self._label(opt, "Opciones", bold=True).pack(anchor="w")
        self.beta = tk.BooleanVar(value=False)
        self.important = tk.BooleanVar(value=False)
        self.discord = tk.BooleanVar(value=self.settings.get("discord", True))
        for var, text, sub in ((self.beta, "Versión de prueba (beta)", "Solo la reciben quienes activaron las betas"),
                               (self.important, "Importante", "Los usuarios no pueden omitirla"),
                               (self.discord, "Anunciar en mi Discord", "Necesita el webhook configurado en GitHub")):
            ttk.Checkbutton(opt, text=text, variable=var, command=self._paint_discord).pack(anchor="w", pady=(10, 0))
            self._label(opt, sub, -1, color=C["muted"], wrap=260).pack(anchor="w", padx=(24, 0))
        self.discord_prev = tk.Label(opt, bg="#313338", fg=C["text"], justify="left", anchor="w", wraplength=250,
                                     font=(FONT, BASE - 1), padx=10, pady=8)
        self.discord_prev.pack(anchor="w", fill="x", pady=(12, 0))
        self._paint_discord()

        btns = tk.Frame(p, bg=C["panel"])
        btns.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        ttk.Button(btns, text=f"Aceptar y publicar {core.vstr(rv.version)}", style="Accent.TButton",
                   command=self.publish).pack(side="left")
        ttk.Button(btns, text="Cancelar", command=self.show_home).pack(side="left", padx=10)

    def _paint_discord(self):
        if not hasattr(self, "discord_prev"):
            return
        if not self.discord.get():
            self.discord_prev.pack_forget()
            return
        extra = " (versión de prueba)" if self.beta.get() else ""
        extra += " · actualización importante" if self.important.get() else ""
        self.discord_prev.configure(text=f"Numpad Macros · bot\n🎉 Numpad Macros {core.vstr(self.rv.version)}{extra} "
                                         "ya está disponible. Abre la app y pulsa «Actualizar», o descárgala en GitHub.")
        self.discord_prev.pack(anchor="w", fill="x", pady=(12, 0))

    # ================================================================ publicar
    def publish(self):
        rv, pkg = self.rv, self.pkg
        notes = self.notes_txt.get("1.0", "end").strip()
        if not any(line.strip().startswith(("-", "*")) for line in notes.splitlines()):
            self._label(self.page, "Las notas necesitan al menos una línea que empiece con «- ».", color=C["bad"],
                        row=3, column=0, pady=(8, 0))
            return
        if notes != rv.notes.strip():
            pkg.set_unreleased(notes)
        beta, important, discord = self.beta.get(), self.important.get(), self.discord.get()
        self.settings["discord"] = discord
        core.save_settings(self.settings)
        self.version = rv.version
        p = self._new_page()
        self.pub_title = self._label(p, f"Publicando {core.vstr(rv.version)}…", 5, True, row=0, column=0)
        self.pub_sub = self._label(p, "Primero se sube el código; después GitHub compila en sus servidores (unos "
                                      "10–15 minutos). Puedes cerrar esta ventana o apagar el PC: GitHub te avisa "
                                      "por correo si algo falla.", color=C["muted"], row=1, column=0, pady=(4, 14))
        self.stage_rows = {}
        rows = [("up", "Subir el código a GitHub"), ("go", "Poner a trabajar al robot")] + \
               [(sid, label) for sid, label, _k in core.STAGES]
        if discord:
            rows.append(("dc", "Anunciar en Discord"))
        for i, (sid, label) in enumerate(rows):
            f = tk.Frame(p, bg=C["panel"])
            f.grid(row=2 + i, column=0, sticky="ew", pady=3)
            f.columnconfigure(1, weight=1)
            icon = tk.Label(f, text="·", bg=C["panel"], fg=C["muted"], font=(FONT, BASE + 1, "bold"), width=2)
            icon.grid(row=0, column=0)
            title = tk.Label(f, text=label, bg=C["panel"], fg=C["muted"], anchor="w")
            title.grid(row=0, column=1, sticky="w")
            right = tk.Label(f, text="", bg=C["panel"], fg=C["muted"], font=(FONT, BASE - 1))
            right.grid(row=0, column=2, sticky="e")
            bar = None
            if sid in ("win", "lin", "mac"):
                bar = ttk.Progressbar(f, mode="determinate", maximum=100)
                bar.grid(row=1, column=1, columnspan=2, sticky="ew", pady=(3, 0))
            self.stage_rows[sid] = (icon, title, right, bar)
        self.pub_box = tk.Frame(p, bg=C["panel"])
        self.pub_box.grid(row=20, column=0, sticky="ew", pady=(14, 0))
        self._stage("up", "run")

        def progress(msg):
            self.q.put((lambda _r, _e, m=msg: self.stage_rows["up"][2].configure(text=m), None, None))

        def job():
            sha = core.upload(pkg, self.gh, rv, rv.version, progress)
            self.q.put((lambda _r, _e: (self._stage("up", "ok", "listo" if sha else "ya estaba subido"),
                                        self._stage("go", "run")), None, None))
            since = core.start_robot(self.gh, rv.version, beta, important, discord)
            run = None
            for _ in range(30):
                run = core.find_run(self.gh, since)
                if run:
                    break
                time.sleep(3)
            if not run:
                raise core.PubError("El robot no arrancó. Revisa la pestaña Actions de tu repositorio.")
            return run["id"]

        def done(run_id, err):
            if err:
                self._pub_failed(err, "")
                return
            self.run_id = run_id
            self._stage("go", "ok")
            self._follow()
        self._bg(job, done)

    def _stage(self, sid, state, right=None, frac=None):
        if sid not in self.stage_rows:
            return
        icon, title, rlbl, bar = self.stage_rows[sid]
        icon.configure(text={"run": "●", "ok": "✓", "bad": "✕", "pending": "·"}[state],
                       fg={"run": C["accent"], "ok": C["ok"], "bad": C["bad"], "pending": C["muted"]}[state])
        title.configure(fg=C["muted"] if state == "pending" else C["text"],
                        font=(FONT, BASE, "bold" if state == "run" else "normal"))
        if right is not None:
            rlbl.configure(text=right)
        if bar is not None and frac is not None:
            bar.configure(value=100 * frac)

    def _follow(self):
        def job():
            return core.run_status(self.gh, self.run_id)

        def done(st, err):
            if err:                         # error de red pasajero: seguir intentando
                self.root.after(8000, self._follow)
                return
            mapping = {"done": "ok", "failed": "bad", "running": "run", "pending": "pending"}
            for sid, (frac, state) in st["stages"].items():
                right = f"{frac * 100:.0f} %" if sid in ("win", "lin", "mac") and state == "running" else ""
                self._stage(sid, mapping[state], right, frac)
            if st.get("discord") == "success":
                self._stage("dc", "ok")
            elif st.get("discord") in ("failure",):
                self._stage("dc", "bad", "revisa el webhook")
            if st["state"] == "running":
                self.root.after(5000, self._follow)
            elif st["state"] == "success":
                self._done()
            else:
                self._pub_failed(f"Falló: {st.get('failed') or 'un paso del robot'}.", st.get("url", ""))
        self._bg(job, done)

    def _pub_failed(self, msg, url):
        self.pub_title.configure(text="Publicación detenida")
        self.pub_sub.configure(text="")
        box = tk.Frame(self.pub_box, bg="#3a1a1a", highlightbackground="#7a2e2e", highlightthickness=1)
        box.pack(fill="x")
        self._label(box, "Se detuvo antes de terminar: los usuarios no recibieron nada nuevo.", 0, True, wrap=740).pack(
            anchor="w", padx=12, pady=(10, 0))
        self._label(box, msg + " Mándame una captura de esta ventana (y del enlace) y lo arreglo; luego vuelves a "
                    "arrastrar la versión corregida.", color="#e3b5b5", wrap=740).pack(anchor="w", padx=12)
        row = tk.Frame(box, bg="#3a1a1a")
        row.pack(anchor="w", padx=12, pady=10)
        if url:
            ttk.Button(row, text="Ver el detalle en GitHub ↗", command=lambda: open_url(url)).pack(side="left")
        ttk.Button(row, text="Volver al inicio", command=self.show_home).pack(side="left", padx=8)

    def _done(self):
        ver = self.version

        def job():
            return core.release_assets(self.gh, ver)

        def done(res, err):
            p = self._new_page()
            self._label(p, f"✓  Numpad Macros {core.vstr(ver)} publicada", 6, True, color=C["ok"], row=0, column=0)
            beta = self.beta.get()
            self._label(p, ("Como beta: solo la reciben quienes activaron las versiones de prueba." if beta else
                            "Los usuarios verán el aviso la próxima vez que abran la app."), color="#b9bdc6",
                        row=1, column=0, pady=(4, 14))
            url = ""
            if res:
                url, assets = res
                self._label(p, "Archivos en la Release", bold=True, row=2, column=0)
                for i, (name, size) in enumerate(assets):
                    f = tk.Frame(p, bg=C["panel2"])
                    f.grid(row=3 + i, column=0, sticky="ew", pady=2)
                    tk.Label(f, text=name, bg=C["panel2"], fg=C["text"], padx=10, pady=6).pack(side="left")
                    tk.Label(f, text=f"{size / 1e6:.1f} MB" if size > 1e5 else f"{size / 1e3:.0f} KB",
                             bg=C["panel2"], fg=C["muted"], padx=10).pack(side="right")
            btns = tk.Frame(p, bg=C["panel"])
            btns.grid(row=20, column=0, sticky="w", pady=(16, 0))
            if url:
                ttk.Button(btns, text="Ver en GitHub ↗", command=lambda: open_url(url)).pack(side="left")
            ttk.Button(btns, text="Listo", style="Accent.TButton", command=self.show_home).pack(side="left", padx=8)
        self._bg(job, done)

    def _cleanup(self):
        if self.pkg is not None:
            self.pkg.cleanup()
            self.pkg = None


def main():
    root = TkinterDnD.Tk() if TkinterDnD else tk.Tk()
    try:
        icon = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "icon.png")
        if os.path.isfile(icon):
            root.iconphoto(True, tk.PhotoImage(file=icon))
    except tk.TclError:
        pass
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app._cleanup(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
