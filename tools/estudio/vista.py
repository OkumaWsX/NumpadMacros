# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Vista previa de la ventana principal de Numpad Macros 3.4, dibujada en un Canvas.

Cada parte lleva la etiqueta «t:<capa>» con el color que la pinta (al tocarla se
elige esa capa) y las zonas con imagen llevan «z:<espacio>».
"""
from __future__ import annotations

import sys

from PIL import Image, ImageTk

import logica as L

W, H = 640, 420
FONT = "Segoe UI" if sys.platform == "win32" else ("Helvetica Neue" if sys.platform == "darwin" else "DejaVu Sans")
FS = 2 if sys.platform == "darwin" else 0          # macOS dibuja las fuentes más chicas

# Colores por botón (los mismos 12 del PC y del celular)
KEY_COLORS = {
    "Naranja": "#f2a33a", "Amarillo": "#e2c340", "Lima": "#9bd14a", "Verde": "#4cc38a",
    "Turquesa": "#3cc7c0", "Celeste": "#6aa8ff", "Azul": "#4a6cf0", "Morado": "#9b7fe0",
    "Rosa": "#e06fb8", "Rojo": "#e5534b", "Café": "#b07a4a", "Gris": "#8b909b",
}
# Teclas virtuales de ejemplo: número -> (texto, color o None, es global)
SAMPLE_KEYS = {
    1: ("Aplausos", "Verde", False), 2: ("Vine boom", "Azul", False), 3: ("Air horn", "Rojo", False),
    4: ("Risas", "Amarillo", False), 5: ("Detener", "Rojo", True), 6: ("Suspenso", "Morado", False),
    7: ("Tambores", "Turquesa", False), 8: ("Ctrl+F16", "Celeste", False), 9: ("Wow", None, False),
    11: ("Bruh", "Naranja", False), 12: ("Sad trombone", None, False), 16: ("Error", "Rosa", False),
    21: ("Banco ▶", None, True), 26: ("Victoria", "Lima", False),
}
# Zonas de los espacios con imagen (x1, y1, x2, y2)
ZONES = {"banner": (0, 0, W, 56), "keys": (22, 162, 258, 384), "logo": (14, 10, 40, 36)}


def f(size, bold=False):
    return (FONT, size + FS, "bold") if bold else (FONT, size + FS)


def rrect(cv, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
           x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


class Preview:
    """Dibuja la vista previa. ``slot_image(slot, size, bg)`` devuelve una imagen PIL RGBA o None."""

    def __init__(self, cv):
        self.cv = cv
        self._photos = []

    def _photo(self, im):
        p = ImageTk.PhotoImage(im)
        self._photos.append(p)
        return p

    def _img(self, slot, under, slot_image, tags):
        x1, y1, x2, y2 = ZONES[slot]
        im = slot_image(slot, (x2 - x1, y2 - y1), under)
        if im is None:
            return False
        base = Image.new("RGBA", im.size, L.hex2rgb(under) + (255,))
        self.cv.create_image(x1, y1, anchor="nw", image=self._photo(Image.alpha_composite(base, im)), tags=tags)
        return True

    def draw(self, e: dict, slot_image=None, zones=False, sel_zone=None, hover=False):
        cv = self.cv
        cv.delete("all")
        self._photos = []
        slot_image = slot_image or (lambda *a: None)
        T = lambda t: ("t:" + t,)  # noqa: E731
        cv.create_rectangle(0, 0, W, H, fill=e["bg"], width=0, tags=T("bg"))

        # ---- encabezado
        self._img("banner", e["bg"], slot_image, T("bg"))
        x = 16
        if self._img("logo", e["bg"], slot_image, T("bg")):
            x = 48
        cv.create_text(x, 11, anchor="nw", text="Numpad Macros", fill=e["text"], font=f(14, True), tags=T("text"))
        cv.create_text(x, 37, anchor="nw", text="● Numpad conectado", fill=e["ok"], font=f(8), tags=T("ok"))
        cv.create_text(x + 128, 37, anchor="nw", text="● Celular conectado: Pixel 7", fill=e["ok"], font=f(8),
                       tags=T("ok"))
        for x1, ch in ((372, "◀"), (494, "▶")):
            rrect(cv, x1, 12, x1 + 34, 36, 4, fill=e["panel2"], outline=e["line"], tags=T("panel2"))
            cv.create_text(x1 + 17, 24, text=ch, fill=e["text"], font=f(9), tags=T("panel2"))
        cv.create_text(450, 24, text="1. Stream", fill=e["text"], font=f(10, True), tags=T("text"))
        rrect(cv, 538, 12, 628, 36, 4, fill=e["ok"], outline="", tags=T("ok"))
        cv.create_text(583, 24, text="● ACTIVO", fill=e["on_ok"], font=f(9, True), tags=T("on_ok"))

        # ---- panel izquierdo: teclas virtuales
        cv.create_rectangle(12, 62, 262, 390, fill=e["panel"], width=0, tags=T("panel"))
        cv.create_text(76, 82, text="Numpad y fila 1–0", fill=e["muted"], font=f(8), tags=T("muted"))
        cv.create_rectangle(22, 95, 135, 97, fill=e["line"], width=0, tags=T("line"))
        rrect(cv, 139, 70, 252, 97, 5, fill=e["panel2"], outline="", tags=T("panel2"))
        cv.create_text(195, 82, text="Teclas virtuales", fill=e["text"], font=f(8, True), tags=T("text"))
        cv.create_rectangle(139, 94, 252, 97, fill=e["acc"], width=0, tags=T("acc"))
        cv.create_text(22, 104, anchor="nw", text="Capa que estás editando", fill=e["muted"], font=f(7),
                       tags=T("muted"))
        cv.create_rectangle(22, 118, 160, 138, fill=e["panel2"], outline=e["line"], tags=T("panel2"))
        cv.create_text(28, 128, anchor="w", text="1. Stream", fill=e["text"], font=f(8), tags=T("text"))
        for i, ch in enumerate("＋✎✕"):
            x1 = 166 + i * 30
            cv.create_rectangle(x1, 118, x1 + 26, 138, fill=e["panel2"], outline=e["line"], tags=T("panel2"))
            cv.create_text(x1 + 13, 128, text=ch, fill=e["text"], font=f(8), tags=T("panel2"))
        cv.create_text(22, 150, anchor="w", text="Teclas virtuales · 30", fill=e["text"], font=f(8, True),
                       tags=T("text"))
        cv.create_text(252, 150, anchor="e", text="G = capa Global", fill=e["muted"], font=f(7), tags=T("muted"))
        self._img("keys", e["panel"], slot_image, T("panel"))
        kw, kh, gap, x0, y0 = 38, 31, 6, 30, 167
        for n in range(1, 31):
            r, c = divmod(n - 1, 5)
            x1, y1 = x0 + c * (kw + gap), y0 + r * (kh + gap)
            v = SAMPLE_KEYS.get(n)
            g = None
            if v and v[1]:
                col = KEY_COLORS[v[1]]
                fill, line, txt, tag = L.mix(e["panel"], col, 0.2), col, e["text"], "text"
                g = (col, e["bg"]) if v[2] else None
            elif v and v[2]:
                fill, line, txt, tag = e["key_global"], e["key_global_line"], e["key_global_text"], "key_global"
                g = (e["key_global_line"], e["bg"])
            elif v:
                fill, line, txt, tag = e["key_set"], e["key_set_line"], e["key_set_text"], "key_set"
            else:
                fill, line, txt, tag = e["key"], e["line"], e["text"], "key"
            if n == 7:
                rrect(cv, x1 - 3, y1 - 3, x1 + kw + 3, y1 + kh + 3, 8, fill="", outline=e["text"], width=2,
                      tags=T("text"))
            rrect(cv, x1, y1, x1 + kw, y1 + kh, 7, fill=fill, outline=line, width=2, tags=T(tag))
            cv.create_text(x1 + 5, y1 + 3, anchor="nw", text=str(n), fill=txt, font=f(7, True), tags=T(tag))
            if g:
                cv.create_rectangle(x1 + kw - 12, y1 + 3, x1 + kw - 3, y1 + 12, fill=g[0], width=0, tags=T(tag))
                cv.create_text(x1 + kw - 7, y1 + 8, text="G", fill=g[1], font=f(5, True), tags=T(tag))
            if v:
                lab = v[0] if len(v[0]) <= 8 else v[0][:7] + "…"
                cv.create_text(x1 + kw / 2, y1 + kh - 7, text=lab, fill=txt, font=f(6), tags=T(tag))

        # ---- panel derecho: pestaña Tecla
        x = 272
        for i, name in enumerate(("Tecla", "Sonidos", "Numpad y opciones", "Audio", "Celular", "Temas", "Creador")):
            w = 12 + len(name) * 5.6
            on = i == 0
            cv.create_rectangle(x, 62, x + w, 82, fill=e["panel"] if on else e["bg"], outline=e["line"],
                                tags=T("panel" if on else "bg"))
            cv.create_text(x + w / 2, 72, text=name, fill=e["text"] if on else e["muted"], font=f(7, True),
                           tags=T("text" if on else "muted"))
            x += w + 2
        cv.create_rectangle(272, 82, 628, 390, fill=e["panel"], outline=e["line"], tags=T("panel"))
        cv.create_line(273, 82, 272 + 12 + 5 * 5.6, 82, fill=e["panel"], tags=T("panel"))
        cv.create_text(286, 92, anchor="nw", text="Virtual 7 · Stream", fill=e["text"], font=f(11, True),
                       tags=T("text"))
        cv.create_text(286, 114, anchor="nw", text="Tecla virtual: solo se toca en la app del celular.",
                       fill=e["muted"], font=f(7), tags=T("muted"))
        rows = (("Acción", "Sonido ▾"), ("Sonido", None), ("Al pulsar", "Superponer ▾"), ("Volumen", "vol"))
        for i, (lab, val) in enumerate(rows):
            y = 134 + i * 23
            cv.create_text(286, y + 9, anchor="w", text=lab, fill=e["muted"], font=f(8), tags=T("muted"))
            if val == "vol":
                cv.create_text(352, y + 9, anchor="w", text="110 % · +0.8 dB", fill=e["acc"], font=f(9, True),
                               tags=T("acc"))
                continue
            cv.create_rectangle(350, y, 614, y + 19, fill=e["panel2"], outline=e["line"], tags=T("panel2"))
            if val is None:
                cv.create_rectangle(355, y + 3, 420, y + 16, fill=e["acc_dim"], width=0, tags=T("acc_dim"))
                cv.create_text(360, y + 9, anchor="w", text="Tambores", fill=e["text"], font=f(8), tags=T("acc_dim"))
            else:
                cv.create_text(356, y + 9, anchor="w", text=val, fill=e["text"], font=f(8), tags=T("panel2"))
        cv.create_rectangle(286, 228, 614, 250, fill=e["acc_bg"], outline=e["acc_dim"], tags=T("acc_bg"))
        cv.create_text(292, 239, anchor="w", text="Igualar volumen: este sonido se ajusta −4.3 dB para quedar en −16 LUFS.",
                       fill=e["text"], font=f(7), tags=T("acc_bg"))
        cv.create_text(286, 264, anchor="w", text="Color del botón", fill=e["text"], font=f(8, True), tags=T("text"))
        cv.create_text(614, 264, anchor="e", text="Elegido: Turquesa", fill=e["muted"], font=f(7), tags=T("muted"))
        cx = 294
        cv.create_oval(cx - 7, 280, cx + 7, 294, outline=e["muted"], dash=(2, 2), tags=T("muted"))
        for name, col in KEY_COLORS.items():
            cx += 22
            if name == "Turquesa":
                cv.create_oval(cx - 10, 277, cx + 10, 297, outline=e["text"], width=2, tags=T("text"))
            cv.create_oval(cx - 7, 280, cx + 7, 294, fill=col, width=0, tags=T("panel"))
        cv.create_text(286, 312, anchor="w", text="✕ No se encontró el archivo", fill=e["bad"], font=f(8),
                       tags=T("bad"))
        cv.create_text(450, 312, anchor="w", text="▲ Volumen alto", fill=e["warn"], font=f(8), tags=T("warn"))
        rrect(cv, 468, 344, 530, 368, 4, fill=e["panel2"], outline=e["line"], tags=T("panel2"))
        cv.create_text(499, 356, text="Quitar", fill=e["text"], font=f(8), tags=T("panel2"))
        btn = "acc_hover" if hover else "acc"
        rrect(cv, 538, 344, 614, 368, 4, fill=e[btn], outline="", tags=T(btn))
        cv.create_text(576, 356, text="▶ Probar", fill=e["on_acc"], font=f(9, True), tags=T("on_acc"))

        # ---- pie
        cv.create_rectangle(250, 398, 380, 416, fill=e["bg"], outline=e["line"], tags=T("line"))
        cv.create_text(315, 407, text="v3.4.0 beta · Novedades", fill=e["muted"], font=f(7), tags=T("muted"))
        cv.create_rectangle(386, 398, 554, 416, fill=e["panel2"], width=0, tags=T("panel2"))
        cv.create_text(470, 407, text="Creado por OkumaWsX · Soporte", fill=e["text"], font=f(7), tags=T("panel2"))
        cv.create_rectangle(560, 398, 628, 416, fill=e["acc"], width=0, tags=T("acc"))
        cv.create_text(594, 407, text="♥ Donar", fill=e["on_acc"], font=f(7, True), tags=T("on_acc"))

        # ---- zonas de imágenes (pantalla «Imágenes y plantillas»)
        if zones:
            for slot in ("banner", "keys", "logo"):
                x1, y1, x2, y2 = ZONES[slot]
                on = slot == sel_zone
                cv.create_rectangle(x1 + 1, y1 + 1, x2 - 1, y2 - 1, outline="#f2a33a" if on else "#ffffff",
                                    width=2 if on else 1, dash=() if on else (4, 3), fill="", tags=("z:" + slot,))
                # rectángulo invisible pero «tocable» encima de la zona
                cv.create_rectangle(x1, y1, x2, y2, outline="", fill="", tags=("z:" + slot, "hit"))

    def tag_at(self, x, y, prefix):
        """Etiqueta (sin el prefijo) del elemento más arriba bajo el mouse."""
        for item in reversed(self.cv.find_overlapping(x, y, x, y)):
            for t in self.cv.gettags(item):
                if t.startswith(prefix):
                    return t[len(prefix):]
        return None
