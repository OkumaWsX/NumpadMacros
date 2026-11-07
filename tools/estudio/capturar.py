# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Saca las capturas de esta versión del Estudio para su Release (tools/estudio/capturas/<versión>/).

Se ven como en el PC de un usuario común: modo comunidad, una firma de autor de ejemplo («Ana») creada
solo para las capturas y el tema de ejemplo «Atardecer» (colores de la imagen de ejemplo, plantilla
«Todo» y fondo de una pieza). Corre en una carpeta temporal aislada (HOME, configuración y envíos):
nunca lee ni muestra las claves reales (oficial.npkey / autor.npkey) del PC donde se ejecuta.

Uso, desde la raíz del repositorio (Linux, con una pantalla virtual):
    xvfb-run -a -s "-screen 0 1600x1000x24" python tools/estudio/capturar.py [--salida carpeta]
"""
import os
import shutil
import sys
import tempfile
import time

# --- aislamiento: antes de cargar el Estudio ---------------------------------------------------------
_CASA = tempfile.mkdtemp(prefix="capturas-estudio-")
for _k, _v in {"HOME": _CASA, "XDG_CONFIG_HOME": os.path.join(_CASA, ".config"),
               "APPDATA": os.path.join(_CASA, "AppData"), "NPT_ESTUDIO_DIR": os.path.join(_CASA, "estudio"),
               "NPT_ENVIOS_DIR": os.path.join(_CASA, "envios")}.items():
    os.environ[_k] = _v
    os.makedirs(_v, exist_ok=True)
# sin red y sin versiones nuevas: si no, al capturar una versión vieja sale encima el aviso de actualización
_API = os.path.join(_CASA, "releases.json")
with open(_API, "w", encoding="utf-8") as _f:
    _f.write("[]")
os.environ["ESTUDIO_API"] = "file://" + _API

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import estudio as E  # noqa: E402
from PIL import ImageGrab  # noqa: E402

K = E.K
CAPTURAS = [  # (pantalla, archivo, descripción para la Release)
    ("edit", "editar.png", "Editar tema: las 22 capas de color, la vista previa igual a Numpad Macros y los colores desde una imagen"),
    ("sec", "secciones.png", "Transparencia por sección, con estilos rápidos y la legibilidad de cada sección"),
    ("img", "imagenes.png", "Imágenes y plantillas: 9 espacios para imágenes y GIF animados"),
    ("exp", "exportar.png", "Exportar: la revisión «comunidad» (la misma que usa el bot) antes de enviar tu tema a Discord"),
    ("key", "firma.png", "Mi firma de autor: así apareces en Numpad Macros como «Comunidad · tu nombre»"),
    ("about", "acerca.png", "Acerca de: avisos de versión nueva y novedades de la versión instalada"),
    ("avisos", "avisos.png", "Avisos de legibilidad: cada uno dice qué hacer y «Ir» te lleva al ajuste que lo arregla"),
]


def main():
    salida = os.path.join(HERE, "capturas", E.VERSION)
    if "--salida" in sys.argv:
        salida = sys.argv[sys.argv.index("--salida") + 1]
    os.makedirs(salida, exist_ok=True)

    # seguridad: solo la carpeta aislada y nunca una clave oficial
    if not os.path.realpath(K.folder()).startswith(os.path.realpath(_CASA)):
        sys.exit(f"La configuración no quedó aislada ({K.folder()}): no saco capturas.")
    if K.official_info() is not None or K.mode() != "comunidad":
        sys.exit("Hay una clave oficial a la vista: no saco capturas.")
    K.save_settings({"nombre": "Ana"})
    K.create_author_key("Ana")                  # firma desechable, solo para las capturas

    E.App.startup = lambda self: None          # sin el asistente de la primera vez
    root = E._make_root("EstudioTemasNumpadMacros")
    root.title(E.APP)
    app = E.App(root)
    if app.mode != "comunidad":
        sys.exit("El Estudio no abrió en modo comunidad: no saco capturas.")
    root.geometry("1420x900+0+0")
    app.name_var.set("Atardecer")
    app.desc_var.set("Tonos cálidos de un atardecer en la montaña.")
    app.on_meta()

    def grab(nombre):
        root.update()
        x, y, w, h = root.winfo_rootx(), root.winfo_rooty(), root.winfo_width(), root.winfo_height()
        img = ImageGrab.grab(bbox=(x, y, x + w, y + h), xdisplay=os.environ.get("DISPLAY"))
        img.save(os.path.join(salida, nombre), optimize=True)
        print("✓", nombre)

    def avisos():
        """Un tema a medio hacer (una tecla que no se lee y las pestañas atenuadas): «Ir» al primer aviso y
        la lista de lo que conviene mejorar."""
        app.colors["key_set_text"] = app.colors["key_set"]
        app.sections = {**app.sections, "tabs": {"fondo": 100, "contenido": 40, "realce": False}}
        app.mark()
        app._show_now("edit")
        app._render_now()
        app.go(app.problems()[0])
        root.update()
        app.open_problems()

    pasos = [(lambda: (app.apply_palette(), app.apply_template("todo"), app.bg_generate(),
                       app.onep_var.set(True), app.on_one_piece()), 600),
             (lambda: (app.image_check(sync=True), app._render_now()), 300)]     # sin «midiendo…»
    for sid, nombre, _t in CAPTURAS:
        if sid == "avisos":
            pasos.append((avisos, 900))
            pasos.append((lambda nombre=nombre: grab(nombre), 300))
            continue
        if sid == "exp":              # la revisión «comunidad» corre en otro hilo: se espera a que termine
            pasos.append((lambda: app._show_now("exp"), 600))
            pasos.append((lambda: [root.update() or time.sleep(0.05) for _ in range(600)
                                   if app._rev["result"] is None], 100))
            pasos.append((lambda nombre=nombre: grab(nombre), 300))
            continue
        pasos.append((lambda sid=sid, nombre=nombre: (app._show_now(sid), grab(nombre)), 900))

    def run(i=0):
        if i >= len(pasos):
            root.destroy()
            return
        fn, espera = pasos[i]
        fn()
        root.after(espera, lambda: run(i + 1))

    root.after(1500, run)
    root.mainloop()

    with open(os.path.join(salida, "capturas.txt"), "w", encoding="utf-8") as f:
        f.write(f"# Capturas del Estudio de Temas {E.VERSION} (archivo | descripción).\n"
                "# Se agregan a las notas de su Release. Hechas con tools/estudio/capturar.py.\n")
        for _sid, nombre, texto in CAPTURAS:
            f.write(f"{nombre} | {texto}\n")
    print(f"Capturas en {salida}")


if __name__ == "__main__":
    try:
        main()
    finally:
        shutil.rmtree(_CASA, ignore_errors=True)   # la firma desechable no queda en el PC
