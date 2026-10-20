# -*- mode: python ; coding: utf-8 -*-
# Empaqueta el Estudio de Temas:  pyinstaller --noconfirm Estudio.spec
import os
import sys
from PyInstaller.utils.hooks import collect_data_files

HERE = os.path.abspath(SPECPATH)
ROOT = os.path.dirname(os.path.dirname(HERE))
datas = [(os.path.join(ROOT, "assets", "icon.png"), "."),
         (os.path.join(ROOT, "docs", "temas", "temas.json"), ".")]
try:
    datas += collect_data_files("tkinterdnd2")      # arrastrar y soltar (tkdnd)
except Exception:
    pass

a = Analysis([os.path.join(HERE, "estudio.py")], pathex=[HERE, ROOT], datas=datas,
             hiddenimports=["tkinterdnd2", "logica", "claves", "vista", "npm.npt", "npm.config",
                            "npm.desktop_linux", "PIL.ImageTk"],
             excludes=["numpy", "unittest", "pydoc"])
pyz = PYZ(a.pure)
icon = os.path.join(ROOT, "assets", "icon.ico" if sys.platform == "win32" else "icon.png")
if sys.platform == "darwin":
    # macOS: app en carpeta (onedir) dentro del .app, como Numpad Macros
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="EstudioTemas-NumpadMacros", console=False, upx=False)
    coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="EstudioTemas")
    app = BUNDLE(coll, name="Estudio de Temas.app", icon=None, bundle_identifier="com.okumawsx.estudiotemas")
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="EstudioTemas-NumpadMacros",
              console=False, upx=False, icon=icon)
