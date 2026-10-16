# -*- mode: python ; coding: utf-8 -*-
# Empaqueta el Publicador en un solo archivo:  pyinstaller --noconfirm Publicador.spec
import os
import sys
from PyInstaller.utils.hooks import collect_data_files

HERE = os.path.abspath(SPECPATH)
ROOT = os.path.dirname(os.path.dirname(HERE))
datas = [(os.path.join(ROOT, "assets", "icon.png"), ".")]
try:
    datas += collect_data_files("tkinterdnd2")      # arrastrar y soltar (tkdnd)
except Exception:
    pass

a = Analysis([os.path.join(HERE, "publicador.py")], pathex=[HERE, ROOT], datas=datas,
             hiddenimports=["tkinterdnd2", "nucleo", "npm.desktop_linux"], excludes=["numpy", "unittest", "pydoc"])
pyz = PYZ(a.pure)
icon = os.path.join(ROOT, "assets", "icon.ico" if sys.platform == "win32" else "icon.png")
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="Publicador-NumpadMacros",
          console=False, upx=False, icon=icon if sys.platform != "darwin" else None)
