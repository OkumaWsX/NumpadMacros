# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Pestaña «Celular»: conectar la app Android por Wi-Fi, cable USB o Bluetooth."""
import time
import tkinter as tk
from tkinter import ttk

from . import remote
from .theme import BASE, C, FONT

TRANSPORT = {"wifi": "Wi-Fi", "usb": "Cable USB", "bluetooth": "Bluetooth"}
APK_URL = "https://github.com/OkumaWsX/NumpadMacros/releases/latest"


def _ago(ts):
    if not ts:
        return "nunca"
    d = time.time() - float(ts)
    if d < 90:
        return "ahora"
    if d < 3600:
        return f"hace {int(d // 60)} min"
    if d < 86400:
        return f"hace {int(d // 3600)} h"
    return f"hace {int(d // 86400)} días"


class DevicesTab:
    QR_SIZE = 196

    def __init__(self, parent, app):
        self.app = app
        self.t = parent
        t = parent
        t.columnconfigure(0, weight=1)
        t.columnconfigure(1, weight=0)

        # ---------- arriba: permitir + nombre
        top = ttk.Frame(t, style="Panel.TFrame")
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="Botonera en el celular", style="H.TLabel").grid(row=0, column=0, sticky="w")
        self.allow_var = tk.BooleanVar(value=remote.settings(app.cfg).get("enabled", True))
        ttk.Checkbutton(top, text="Permitir conexiones", variable=self.allow_var,
                        command=self._on_allow).grid(row=0, column=2, sticky="e")
        ttk.Label(top, style="Muted.TLabel", wraplength=560, justify="left", text=(
            "Instala «Numpad Macros» en tu Android y lanza o edita tus sonidos desde ahí. "
            "El sonido sale de este PC, igual que con el numpad.")).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

        # ---------- izquierda: cómo conectar
        left = ttk.Frame(t, style="Panel.TFrame")
        left.grid(row=1, column=0, sticky="nsew", pady=(14, 0), padx=(0, 16))
        left.columnconfigure(0, weight=1)
        self.ways = {}
        r = 0
        for key, title in (("wifi", "Wi-Fi"), ("usb", "Cable USB"), ("bluetooth", "Bluetooth")):
            card = ttk.Frame(left, style="Card.TFrame", padding=(12, 8))
            card.grid(row=r, column=0, sticky="ew", pady=(0, 6))
            card.columnconfigure(1, weight=1)
            dot = tk.Label(card, text="●", bg=C["panel2"], fg=C["muted"], font=(FONT, BASE + 2))
            dot.grid(row=0, column=0, rowspan=2, padx=(0, 10))
            ttk.Label(card, text=title, style="Card.TLabel", font=(FONT, BASE, "bold")).grid(
                row=0, column=1, sticky="w")
            sub = ttk.Label(card, style="CardMuted.TLabel", wraplength=255, justify="left")
            sub.grid(row=1, column=1, sticky="w")
            self.ways[key] = (dot, sub)
            r += 1

        ttk.Label(left, text="Celulares vinculados", style="Panel.TLabel",
                  font=(FONT, BASE, "bold")).grid(row=r, column=0, sticky="w", pady=(12, 4))
        r += 1
        self.dev_box = ttk.Frame(left, style="Panel.TFrame")
        self.dev_box.grid(row=r, column=0, sticky="ew")
        self.dev_box.columnconfigure(0, weight=1)
        r += 1
        ttk.Label(left, text="Actividad", style="Panel.TLabel",
                  font=(FONT, BASE, "bold")).grid(row=r, column=0, sticky="w", pady=(12, 4))
        r += 1
        self.log_lbl = ttk.Label(left, style="Muted.TLabel", justify="left", wraplength=300)
        self.log_lbl.grid(row=r, column=0, sticky="w")

        # ---------- derecha: QR + código
        right = ttk.Frame(t, style="Card.TFrame", padding=14)
        right.grid(row=1, column=1, sticky="n", pady=(14, 0))
        ttk.Label(right, text="Vincular un celular", style="Card.TLabel",
                  font=(FONT, BASE + 1, "bold")).pack(anchor="w")
        ttk.Label(right, text="Escanea con la app o escribe el código", style="CardMuted.TLabel").pack(
            anchor="w", pady=(2, 8))
        self.qr = tk.Canvas(right, width=self.QR_SIZE, height=self.QR_SIZE, bg="#ffffff",
                            highlightthickness=0)
        self.qr.pack()
        self.pin_lbl = tk.Label(right, bg=C["panel2"], fg=C["accent"], font=(FONT, BASE + 14, "bold"))
        self.pin_lbl.pack(pady=(10, 0))
        self.name_lbl = ttk.Label(right, style="CardMuted.TLabel")
        self.name_lbl.pack()
        ttk.Button(right, text="Nuevo código", command=self._new_pin).pack(fill="x", pady=(10, 0))
        ttk.Label(right, style="CardMuted.TLabel", wraplength=self.QR_SIZE, justify="left", text=(
            "El código solo se pide la primera vez. Después el celular se conecta solo.")).pack(
            anchor="w", pady=(8, 0))
        link = tk.Label(right, text="Descargar la app (APK)", bg=C["panel2"], fg=C["accent"],
                        cursor="hand2", font=(FONT, BASE - 1, "underline"))
        link.pack(anchor="w", pady=(8, 0))
        link.bind("<Button-1>", lambda e: app._open(APK_URL))
        self._qr_text = None
        self.refresh()

    # ------------------------------------------------------------ acciones
    def _on_allow(self):
        with self.app.engine.lock:
            remote.settings(self.app.cfg)["enabled"] = self.allow_var.get()
        self.app._save()
        if not self.allow_var.get():
            for s in list(self.app.remote.sessions):
                s.send({"t": "rechazado", "why": "desactivado"})
                s.close()
        self.refresh()

    def _new_pin(self):
        self.app.remote.new_pin()
        self.refresh()

    def _forget(self, dev_id, name):
        from tkinter import messagebox
        if messagebox.askyesno("Olvidar celular",
                               f"¿Olvidar «{name}»? Para volver a usarlo tendrá que escribir el código.",
                               parent=self.t):
            self.app.remote.forget(dev_id)
            self.refresh()

    # ------------------------------------------------------------ dibujo
    def _draw_qr(self, text):
        if text == self._qr_text:
            return
        self._qr_text = text
        cv = self.qr
        cv.delete("all")
        try:
            import segno
            m = segno.make(text, error="m").matrix
        except Exception:
            cv.create_text(self.QR_SIZE / 2, self.QR_SIZE / 2, text="QR no disponible\nusa el código",
                           justify="center", fill="#333", font=(FONT, BASE))
            return
        n = len(m) + 8                       # 4 módulos de margen por lado
        cell = self.QR_SIZE / n
        for y, row in enumerate(m):
            for x, v in enumerate(row):
                if v:
                    x0, y0 = (x + 4) * cell, (y + 4) * cell
                    cv.create_rectangle(x0, y0, x0 + cell + 0.6, y0 + cell + 0.6, fill="#000", width=0)

    def refresh(self):
        app = self.app
        srv = app.remote
        allowed = self.allow_var.get()
        if allowed:
            self._draw_qr(remote.qr_text(app.cfg, srv.pin))
            self.pin_lbl.configure(text=" ".join(srv.pin))
        else:
            self._qr_text = None
            self.qr.delete("all")
            self.qr.create_text(self.QR_SIZE / 2, self.QR_SIZE / 2, text="Conexiones\ndesactivadas",
                                justify="center", fill="#555", font=(FONT, BASE + 1, "bold"))
            self.pin_lbl.configure(text="— — — —")
        self.name_lbl.configure(text=f"Este PC: {srv.name()}")

        ips = remote.local_ips()
        conn = srv.connected()
        by_tr = {}
        for s in conn:
            by_tr.setdefault(s.transport, []).append(s.name)
        err = srv.errors
        port = remote.settings(app.cfg).get("port", remote.TCP_PORT)
        texts = {
            "wifi": (err.get("wifi") or
                     (f"Misma red que el celular · {', '.join(ips[:3]) or 'sin red'} · puerto {port}")),
            "usb": ("En el celular: Ajustes → Compartir conexión → «Compartir conexión por USB» "
                    "y conecta el cable."),
            "bluetooth": (err.get("bluetooth") or
                          "Vincula el celular con este PC en los ajustes de Bluetooth (una sola vez)."),
        }
        for key, (dot, sub) in self.ways.items():
            names = by_tr.get(key)
            # un solo servidor TCP atiende Wi-Fi y USB
            failed = err.get("bluetooth") if key == "bluetooth" else err.get("wifi")
            if names:
                color, text = C["ok"], "Conectado: " + ", ".join(names)
            elif failed:
                color, text = C["bad"], texts[key] if key == "bluetooth" else failed
            elif not allowed:
                color, text = C["muted"], "Conexiones desactivadas"
            else:
                color, text = C["accent"], texts[key]       # listo, esperando al celular
            dot.configure(fg=color)
            sub.configure(text=text)

        for w in self.dev_box.winfo_children():
            w.destroy()
        devs = sorted(remote.settings(app.cfg)["devices"], key=lambda d: -float(d.get("last") or 0))
        online = {s.dev: s for s in conn}
        if not devs:
            ttk.Label(self.dev_box, text="Todavía no hay ninguno.", style="Muted.TLabel").grid(
                row=0, column=0, sticky="w")
        for i, d in enumerate(devs):
            row = ttk.Frame(self.dev_box, style="Card.TFrame", padding=(12, 6))
            row.grid(row=i, column=0, sticky="ew", pady=(0, 4))
            row.columnconfigure(0, weight=1)
            s = online.get(d.get("id"))
            state = (f"Conectado por {TRANSPORT.get(s.transport, s.transport)}" if s else
                     f"{TRANSPORT.get(d.get('transport'), '')} · último uso: {_ago(d.get('last'))}")
            ttk.Label(row, text=d.get("name", "Celular"), style="Card.TLabel",
                      font=(FONT, BASE, "bold")).grid(row=0, column=0, sticky="w")
            tk.Label(row, text=state, bg=C["panel2"], fg=C["ok"] if s else C["muted"],
                     font=(FONT, BASE - 1)).grid(row=1, column=0, sticky="w")
            ttk.Button(row, text="Olvidar", command=lambda di=d.get("id"), n=d.get("name", ""):
                       self._forget(di, n)).grid(row=0, column=1, rowspan=2)
        self.log_lbl.configure(text="\n".join(reversed(srv.log[-6:])) or "Sin actividad todavía.")
