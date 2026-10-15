# Componentes de terceros

Numpad Macros usa o integra los siguientes componentes. Cada uno conserva su propia licencia.

| Componente | Uso | Licencia | Cómo se distribuye |
|---|---|---|---|
| [Interception](https://github.com/oblitum/Interception) | Driver de teclado en Windows (captura por dispositivo) | LGPL-3.0 (uso no comercial) | Incluido en el instalador de Windows (`drivers/`), con su licencia |
| [VB-CABLE](https://vb-audio.com/Cable/) | Micrófono virtual en Windows | Donationware de VB-Audio | **No se incluye**: el instalador lo descarga del sitio oficial si el usuario lo elige |
| [BlackHole](https://existential.audio/blackhole/) | Micrófono virtual en macOS | GPL-3.0 | No se incluye; lo instala el usuario |
| [Python](https://www.python.org/) y tkinter | Lenguaje e interfaz | PSF License / Tcl-Tk License | Empaquetado en la app |
| [PyInstaller](https://pyinstaller.org/) | Empaquetado de la app | GPL-2.0 con excepción de bootloader | Solo para compilar |
| [Inno Setup](https://jrsoftware.org/isinfo.php) | Instalador de Windows | Licencia de Inno Setup | Solo para compilar |
| [pystray](https://github.com/moses-palmer/pystray) | Icono en la bandeja del sistema | LGPL-3.0 | Empaquetado (Windows y Linux) |
| [Pillow](https://python-pillow.org/) | Imágenes del icono | MIT-CMU (HPND) | Empaquetado (Windows y Linux) |
| [NumPy](https://numpy.org/) | Mezcla de audio | BSD-3-Clause | Empaquetado (Windows y macOS) |
| [python-sounddevice](https://github.com/spatialaudio/python-sounddevice) / PortAudio | Salida y entrada de audio | MIT | Empaquetado (Windows y macOS) |
| [python-soundfile](https://github.com/bastibe/python-soundfile) / libsndfile | Lectura de archivos de audio | BSD-3-Clause / LGPL-2.1 | Empaquetado (Windows y macOS) |
| [python-evdev](https://github.com/gvalkov/python-evdev) | Captura de teclado en Linux | BSD-3-Clause | Empaquetado (Linux) |

**Nota sobre Interception:** su licencia gratuita cubre el uso no comercial. Numpad Macros es gratuito (las donaciones son voluntarias). Una distribución comercial requeriría la licencia comercial de Interception.
