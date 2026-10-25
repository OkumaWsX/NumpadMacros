# Banco de pruebas del panel izquierdo (no es parte de la app): ver si las teclas caben.
# Uso: XDG_CONFIG_HOME=/carpeta/copia python tools/probar_panel.py . salida [-|Original] [1366x768 ...]
# VISTA=numpad para medir la vista del numpad. ¡Usa una COPIA de la configuración!
"""Banco de pruebas: abre la app, prueba tamaños de ventana y mide si las teclas virtuales se cortan.
   python probar.py RAIZ SALIDA [tema|-] [AnchoxAlto ...]"""
import os, subprocess, sys, json
root_dir, out = sys.argv[1], sys.argv[2]
theme = sys.argv[3] if len(sys.argv) > 3 else "-"
sizes = [tuple(map(int, s.split("x"))) for s in sys.argv[4:]] or [(1000, 660), (1100, 720), (1280, 720), (1366, 768), (1600, 900), (1920, 1040)]
sys.path.insert(0, root_dir)
os.makedirs(out, exist_ok=True)
if theme != "-":
    from npm import config
    p = config.config_path(); c = json.load(open(p, encoding="utf-8"))
    c["theme"] = {"name": theme, "file": "", "phone": True} if theme == "Original" else c["theme"]
    json.dump(c, open(p, "w", encoding="utf-8"))
import tkinter as tk
from npm import gui
r = tk.Tk(className="NumpadMacros")
app = gui.App(r)
r.update()
app._set_view(os.environ.get("VISTA", "virt"))
res = []

def step(i=0):
    if i >= len(sizes):
        print(json.dumps(res, indent=1)); r.destroy(); return
    w, h = sizes[i]
    r.geometry(f"{w}x{h}")
    def measure():
        r.update_idletasks()
        cv, lp = (app.virt_canvas if app.left_view == "virt" else app.row_canvas), app.left_panel
        cv_bot = cv.winfo_rooty() + cv.winfo_height()
        hint = [c for c in app.view_virt.winfo_children() if isinstance(c, tk.ttk.Label) or c.winfo_class() == "TLabel"][-1]
        hint_bot = hint.winfo_rooty() + hint.winfo_height()
        lp_bot = lp.winfo_rooty() + lp.winfo_height() - 16
        win_bot = r.winfo_rooty() + r.winfo_height()
        res.append(dict(size=f"{w}x{h}", real=f"{r.winfo_width()}x{r.winfo_height()}", VUNIT=app.VUNIT,
                        canvas_h=cv.winfo_height(), canvas_req=cv.winfo_reqheight(),
                        canvas_w=cv.winfo_width(), canvas_reqw=cv.winfo_reqwidth(),
                        corte_derecha=max(0, cv.winfo_rootx() + cv.winfo_reqwidth()
                                          - (lp.winfo_rootx() + lp.winfo_width() - 16)),
                        panel_w=lp.winfo_width(), panel_reqw=lp.winfo_reqwidth(),
                        corte_canvas=max(0, cv_bot - lp_bot), corte_texto=max(0, hint_bot - lp_bot),
                        sobra=lp_bot - hint_bot, panel_req=lp.winfo_reqheight(), panel_h=lp.winfo_height()))
        fid = int(r.wm_frame(), 16) if r.wm_frame() else r.winfo_id()
        subprocess.run(["import", "-window", str(fid), os.path.join(out, f"{w}x{h}.png")],
                       stderr=subprocess.DEVNULL)
        step(i + 1)
    r.after(900, measure)
r.after(800, step)
r.mainloop()
