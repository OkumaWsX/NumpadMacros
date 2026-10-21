# -*- mode: python ; coding: utf-8 -*-
# Empaqueta Numpad Macros como aplicación independiente (no necesita Python instalado).
#   pyinstaller --noconfirm NumpadMacros.spec
# Windows -> dist/NumpadMacros/NumpadMacros.exe
# Linux   -> dist/NumpadMacros            (un solo archivo)
# macOS   -> dist/Numpad Macros.app
import os
import sys

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = not IS_WIN and not IS_MAC
ROOT = os.path.abspath(SPECPATH)
sys.path.insert(0, ROOT)
from npm import __version__  # noqa: E402

datas = [(os.path.join(ROOT, "assets", "icon.png"), "assets"),
         (os.path.join(ROOT, "assets", "fonts"), os.path.join("assets", "fonts")),
         (os.path.join(ROOT, "CHANGELOG.md"), ".")]   # ventana de novedades
binaries = []
if IS_WIN and os.path.isfile(os.path.join(ROOT, "interception.dll")):
    binaries.append((os.path.join(ROOT, "interception.dll"), "."))

hidden = ["npm.capture_win", "npm.capture_linux", "npm.capture_mac",
          "npm.send_win", "npm.send_linux", "npm.send_mac", "npm.linux_perms", "npm.desktop_linux",
          "npm.remote", "npm.remote_bt", "npm.devices_tab", "segno",
          "npm.npt", "npm.themes", "npm.themes_tab", "npm.sound_picker", "npm.covers", "npm.aa", "npm.theme_art"]
if IS_WIN:
    hidden += ["pystray._win32"]
elif IS_LINUX:
    hidden += ["pystray._xorg", "pystray._appindicator", "pystray._gtk",
               "npm.tray_sni", "jeepney", "jeepney.io.blocking", "jeepney.bus_messages"]

# En Linux la salida va por PipeWire: no hace falta empaquetar PortAudio
excludes = ["tests"]
if IS_LINUX:
    excludes += ["unittest", "pydoc", "sounddevice", "_sounddevice_data"]

a = Analysis(
    [os.path.join(ROOT, "NumpadMacros.pyw")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

icon = os.path.join(ROOT, "assets", "icon.ico" if IS_WIN else "icon.png")

if IS_LINUX:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="NumpadMacros",
              console=False, strip=False, upx=False)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="NumpadMacros",
              console=False, icon=icon, upx=False,
              version=None)
    coll = COLLECT(exe, a.binaries, a.datas, name="NumpadMacros", upx=False)
    if IS_MAC:
        app = BUNDLE(
            coll,
            name="Numpad Macros.app",
            icon=icon,
            bundle_identifier="com.numpadmacros.app",
            info_plist={
                "CFBundleShortVersionString": __version__,
                "CFBundleVersion": __version__,
                "NSHighResolutionCapable": True,
                "NSMicrophoneUsageDescription":
                    "Numpad Macros usa el micrófono solo si activas «Mezclar mi micrófono real».",
                "LSMinimumSystemVersion": "11.0",
            },
        )
