# Numpad Macros — guía de uso

Convierte un numpad USB en una **botonera de sonidos** y un panel de **atajos de teclado**, sin afectar a tu teclado principal. Es una aplicación **independiente**: trae su propia biblioteca de sonidos y su propio reproductor, no necesita Soundpad ni tener Python instalado. Funciona en **Windows, Linux y macOS**.

Al pausar o cerrar la app, el numpad vuelve a funcionar como un numpad normal.

## Qué hace

- **Biblioteca de sonidos** (pestaña *Sonidos*): agrega archivos o carpetas completas (MP3, WAV, OGG, FLAC, OPUS), busca, escucha y asigna a una tecla. Si venías de Soundpad, **«Importar lista de Soundpad»** trae tus sonidos desde un archivo `.spl`.
- **Cada tecla reproduce un sonido** por tus audífonos y/o por un **micrófono virtual**, para que te escuchen en Discord, OBS o el juego. Cada tecla tiene su volumen y su forma de sonar:
  - **Superponer:** cada pulsación suena encima de la anterior.
  - **Reiniciar:** vuelve a empezar desde el principio.
  - **Alternar:** pulsas para que suene y pulsas otra vez para detenerlo (ideal para música).
  - **Mientras se mantiene:** suena solo mientras tienes la tecla apretada.
- **Mezclar tu micrófono real:** hablas y suenan los efectos por el mismo micrófono virtual.
- **Atajos de teclado** (por ejemplo `Ctrl+Shift+F13`) para OBS, Discord u otro programa. Se mantienen apretados mientras mantengas la tecla, así que sirven para push-to-talk.
- **Bancos:** varias páginas de asignaciones. La capa **Global** aplica en todos los bancos; por defecto **NumLock** pasa al banco siguiente.
- **Solo tu numpad:** «Detectar numpad» identifica el numpad exacto; los demás teclados no se tocan.
- **Sin numpad, con la fila de números:** pulsa **Ctrl+Alt+M** para activar el **modo macros**. Con el modo activo, las teclas **1–0, - y =** de tu teclado normal lanzan sus propias acciones (cada banco tiene las suyas, en la fila de números del dibujo). Todas las demás teclas siguen escribiendo normal. Con Ctrl+Alt+M otra vez vuelves a escribir números. La combinación se puede cambiar en «Numpad y opciones».

## Instalación

Descarga el archivo de tu sistema (ver *Cómo obtener los programas* más abajo).

### Windows
1. Abre **`NumpadMacros-Windows-Setup.exe`** y sigue el asistente: **Siguiente → Siguiente → Instalar**.
   La primera vez Windows puede mostrar «Windows protegió su PC»: pulsa **Más información → Ejecutar de todas formas** (pasa con cualquier programa sin firma digital pagada).
2. En el paso de tareas vienen marcados los dos componentes recomendados:
   - **Driver Interception:** para que la app use solo tu numpad. Viene incluido.
   - **VB-Cable:** el micrófono virtual para que te escuchen. Se descarga de la página oficial de VB-Audio durante la instalación y se abre su ventana: pulsa **«Install Driver»**.
3. Al terminar, el instalador pide **reiniciar** (los drivers lo necesitan).
4. Después del reinicio, en la pestaña **Audio** de la app elige «CABLE Input» como micrófono virtual, y en Discord, OBS o el juego elige «CABLE Output» como micrófono.

Queda en el menú Inicio, con acceso directo en el escritorio, y se desinstala desde *Configuración → Aplicaciones* (también quita Interception si lo instaló el asistente). Si prefieres no instalar nada, existe la versión portátil `NumpadMacros-Windows-portable.zip`.

### Linux
1. Descomprime `NumpadMacros-Linux.tar.gz` y, dentro de la carpeta, ejecuta:
   ```
   ./instalar_linux.sh
   ```
   Así queda en el menú de aplicaciones como **Numpad Macros**. También puedes abrir el archivo `NumpadMacros` directamente.
2. La primera vez, en **Numpad y opciones**, pulsa **«Dar permisos…»** y escribe tu contraseña. Funciona al instante, sin cerrar sesión.
3. El micrófono virtual **«NumpadMacros-Mic»** se crea solo (con PipeWire o PulseAudio). Elígelo como micrófono en Discord, OBS o el juego.

### macOS
1. Descomprime `NumpadMacros-macOS.zip` y mueve **Numpad Macros** a *Aplicaciones*.
2. La primera vez: **clic derecho → Abrir → Abrir** (la app no está firmada por Apple).
3. En **Ajustes del Sistema → Privacidad y seguridad**, activa **Numpad Macros** en **Monitoreo de entrada** (para leer el numpad) y en **Accesibilidad** (para enviar atajos). Luego cierra y abre la app.
4. *Opcional — que te escuchen:* instala **BlackHole 2ch** (gratis): <https://existential.audio/blackhole/>. Elígelo como micrófono virtual en la pestaña **Audio** y también como micrófono en Discord, OBS o el juego.

## Primer uso
1. **Numpad y opciones → Detectar numpad**, y pulsa cualquier tecla de tu numpad.
2. **Sonidos → ＋ Carpeta…** para cargar tus efectos.
3. Haz clic en una tecla del dibujo (numpad o fila de números), elige el sonido y pulsa **Asignar**. También puedes hacerlo desde la pestaña **Tecla**.
4. Elige cómo suena (Superponer, Reiniciar, Alternar o Mientras se mantiene) y pruébalo con **▶ Probar**.

## Por qué el micrófono virtual es aparte en Windows y Mac
Para que Discord o un juego "escuchen" los sonidos, el sistema necesita un dispositivo de micrófono extra. Crear uno requiere un **driver de audio**: Soundpad trae el suyo dentro del instalador. En Windows y Mac la app usa VB-Cable o BlackHole, que son gratuitos y se instalan una sola vez. En Linux no hace falta, porque PipeWire permite crearlo sin drivers. Sin micrófono virtual, todo funciona igual, pero los sonidos solo se escuchan en tus audífonos.

## Dónde descargar
Todas las versiones están en **https://github.com/OkumaWsX/NumpadMacros/releases/latest**: el instalador de Windows (`NumpadMacros-Windows-Setup.exe`), la versión portátil de Windows, Linux (`NumpadMacros-Linux.tar.gz`) y macOS (`NumpadMacros-macOS.zip`).

Para compilar desde el código, consulta la sección «Compilar desde el código» del [README](README.md).

## Avisos
- **Si por error elegiste tu teclado principal**, pulsa **PAUSADO** con el mouse y vuelve a detectar el numpad.
- **Anti-cheat (Windows):** algunos juegos con anti-cheat estricto detectan el driver Interception. Si un juego se queja, desinstálalo (`install-interception.exe /uninstall` y reiniciar); la app vuelve sola al modo sin driver.
- **Fila de números en Linux:** con el modo macros activo, la app toma el teclado y reenvía las demás teclas al sistema; si se cierra, el teclado vuelve a la normalidad al instante. Al *activar* el modo, la M de la combinación puede llegar a la ventana activa (con Ctrl+Alt casi nunca hace nada).
- **Fila de números en macOS:** usa el permiso de **Accesibilidad**.
- **Teclas extra** (`00`, `=`, calculadora…): pulsa **Capturar tecla física** y luego esa tecla; aparecerá bajo el dibujo para asignarle algo.
- **Linux con Wayland:** los atajos se envían bien, pero OBS solo tiene atajos *globales* en algunos escritorios. Los sonidos no dependen de esto.
- **macOS:** existen F13–F20 (no F21–F24) y no hay icono en la barra de menú; cierra la ventana para salir.
- Los archivos de sonido no se copian: si mueves o borras uno, aparece con ⚠ en la biblioteca.

La configuración se guarda en `%APPDATA%\NumpadMacros` (Windows), `~/.config/NumpadMacros` (Linux) o `~/Library/Application Support/NumpadMacros` (macOS). Si usabas la versión anterior con Soundpad, tus teclas se convierten solas a sonidos propios.

## Creador y soporte
Numpad Macros es creado por **OkumaWsX**. En la app, el botón de abajo «Creado por OkumaWsX · Soporte» abre la pestaña **Creador**:
- Instagram: <https://www.instagram.com/okumawsx>
- Discord (comunidad y soporte): <https://discord.gg/hcutJcBx9>
- Donaciones: <https://ceneka.net/OkumaWsX>

## Licencias de terceros
- **Interception** (driver de teclado) se distribuye bajo LGPL 3.0 para uso no comercial; el texto va en la carpeta `drivers` de la instalación.
- **VB-Cable** es de VB-Audio (donationware); el instalador no lo incluye, lo descarga de su sitio oficial.
