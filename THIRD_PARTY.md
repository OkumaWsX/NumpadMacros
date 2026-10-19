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
| [NumPy](https://numpy.org/) | Mezcla, medición de volumen y compresor | BSD-3-Clause | Empaquetado (todos los sistemas) |
| [python-sounddevice](https://github.com/spatialaudio/python-sounddevice) / PortAudio | Salida y entrada de audio | MIT | Empaquetado (Windows y macOS) |
| [python-soundfile](https://github.com/bastibe/python-soundfile) / libsndfile | Lectura de archivos de audio | BSD-3-Clause / LGPL-2.1 | Empaquetado (todos los sistemas) |
| [certifi](https://github.com/certifi/python-certifi) | Certificados para conectarse a GitHub (actualizaciones) | MPL-2.0 | Empaquetado, sin modificar |
| [PipeWire](https://pipewire.org/) / PulseAudio (`pactl`, `pw-cat`, `pacat`) | Salida de audio y micrófono virtual en Linux | MIT / LGPL-2.1 | **No se incluye**: se usa el que trae el sistema |
| [python-evdev](https://github.com/gvalkov/python-evdev) | Captura de teclado en Linux | BSD-3-Clause | Empaquetado (Linux) |
| [segno](https://github.com/heuer/segno) | Código QR para vincular el celular | BSD-3-Clause | Empaquetado (todos los sistemas) |
| [PyObjC](https://github.com/ronaldoussoren/pyobjc) (IOBluetooth) | Bluetooth con el celular en macOS | MIT | Empaquetado (macOS) |

### App Android (carpeta `android/`)

| Componente | Uso | Licencia |
|---|---|---|
| [Kotlin](https://kotlinlang.org/) y [Jetpack Compose / AndroidX](https://developer.android.com/jetpack) | Lenguaje e interfaz | Apache-2.0 |
| [ZXing Android Embedded](https://github.com/journeyapps/zxing-android-embedded) / [ZXing](https://github.com/zxing/zxing) | Escanear el código QR | Apache-2.0 |
| [Gradle](https://gradle.org/) y Android Gradle Plugin | Compilar el APK | Apache-2.0 (solo para compilar) |

### Solo en el Publicador (herramienta del creador, no se entrega a los usuarios)

| Componente | Uso | Licencia |
|---|---|---|
| [tkinterdnd2](https://github.com/Eliav2/tkinterdnd2) / [tkdnd](https://github.com/petasis/tkdnd) | Arrastrar y soltar archivos | MIT / BSD |
| [certifi](https://github.com/certifi/python-certifi) | Conexión segura con GitHub | MPL-2.0 |

### Normas y servicios

- La medición de volumen sigue la norma pública **ITU-R BS.1770** (LUFS); el código que la implementa es propio.
- Las actualizaciones y publicaciones usan la **API de GitHub** y **GitHub Actions** (servicios de GitHub).

**Nota sobre Interception:** su licencia gratuita cubre el uso no comercial. Numpad Macros es gratuito (las donaciones son voluntarias). Una distribución comercial requeriría la licencia comercial de Interception.
