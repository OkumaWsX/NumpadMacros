# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Controles dibujados a mano: medidor de volumen y curva del compresor."""
import math
import time
import tkinter as tk

from . import loudness as ld
from .theme import BASE, C, FONT

FLOOR = -60.0          # dB que se ven como medidor vacío


def _db_x(db, width):
    return max(0.0, min(1.0, (db - FLOOR) / -FLOOR)) * width


class Meter(tk.Canvas):
    """Medidor horizontal por segmentos: verde, amarillo (desde −18 dB) y rojo
    (desde −6 dB), con marca del pico más alto de los últimos 1,5 s."""
    SEGS = 30

    def __init__(self, master, width=210, height=11, bg=None):
        super().__init__(master, width=width, height=height, bg=bg or C["bg"],
                         highlightthickness=0, bd=0)
        self.W, self.H = width, height
        gap = 2
        sw = (width - (self.SEGS - 1) * gap) / self.SEGS
        self.rects, self.thr = [], []
        for i in range(self.SEGS):
            x0 = i * (sw + gap)
            self.rects.append(self.create_rectangle(x0, 0, x0 + sw, height, width=0, fill=C["panel2"]))
            self.thr.append(FLOOR + (i + 1) * (-FLOOR) / self.SEGS)
        self.mark = self.create_rectangle(0, 0, 0, 0, width=0, fill=C["text"], state="hidden")
        self.shown = FLOOR
        self.hold, self.hold_t = FLOOR, 0.0
        self._lit = -1

    @staticmethod
    def _colors(db):
        if db >= -6:
            return "#e5534b", "#3a1c1c"
        if db >= -18:
            return "#e2b340", "#33301c"
        return "#4cc38a", "#1a3027"

    def set(self, peak_db):
        """Llamar ~20 veces por segundo con el pico actual (dB, −inf = silencio)."""
        now = time.monotonic()
        peak = FLOOR if peak_db is None or math.isinf(peak_db) else max(FLOOR, peak_db)
        self.shown = peak if peak >= self.shown else max(peak, self.shown - 1.5)   # cae ~30 dB/s
        if peak >= self.hold or now - self.hold_t > 1.5:
            self.hold, self.hold_t = peak, now
        lit = sum(1 for t in self.thr if self.shown >= t - (-FLOOR) / self.SEGS / 2) - 1
        if lit != self._lit:
            for i, r in enumerate(self.rects):
                on, off = self._colors(self.thr[i])
                self.itemconfigure(r, fill=on if i <= lit else off)
            self._lit = lit
        if self.hold > FLOOR + 1:
            x = _db_x(self.hold, self.W)
            self.coords(self.mark, x - 2, 0, x, self.H)
            self.itemconfigure(self.mark, state="normal")
        else:
            self.itemconfigure(self.mark, state="hidden")
        return self.shown

    def clear(self):
        self.set(None)


class CompCurve(tk.Canvas):
    """Curva entrada → salida del compresor (−60 a 0 dB)."""

    def __init__(self, master, size=150):
        super().__init__(master, width=size, height=size, bg=C["panel2"], highlightthickness=0)
        self.S = size

    def draw(self, thr, ratio, ceil, on=True):
        S = self.S
        self.delete("all")
        for db in (-48, -36, -24, -12):
            p = _db_x(db, S)
            self.create_line(p, 0, p, S, fill=C["line"])
            self.create_line(0, S - p, S, S - p, fill=C["line"])
        self.create_line(0, S, S, 0, fill=C["muted"], dash=(3, 3))
        pts = []
        for i in range(61):
            x_db = FLOOR + i
            y_db = ld.curve(x_db, thr, ratio) if on else x_db
            y_db = min(y_db, ceil) if on else y_db
            pts += [_db_x(x_db, S), S - _db_x(y_db, S)]
        self.create_line(*pts, fill=C["accent"] if on else C["muted"], width=2)
        if on:
            p = _db_x(thr, S)
            self.create_oval(p - 3, S - p - 3, p + 3, S - p + 3, fill=C["accent"], outline="")
            yc = S - _db_x(ceil, S)
            self.create_line(0, yc, S, yc, fill=C["bad"], dash=(2, 2))
        self.create_text(4, 4, anchor="nw", text="salida", fill=C["muted"], font=(FONT, BASE - 2))
        self.create_text(S - 4, S - 4, anchor="se", text="entrada", fill=C["muted"], font=(FONT, BASE - 2))
