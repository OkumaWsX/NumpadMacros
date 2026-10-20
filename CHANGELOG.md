# Historial de cambios

Todas las versiones de Numpad Macros. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [versionado semántico](https://semver.org/lang/es/).

## [Sin publicar]

## [3.4.0] - 2026-10-20
### Añadido
- **Teclas virtuales**: 30 teclas por banco (5 × 6) que solo existen en la app del celular. Lanzan sonidos y atajos sin pasar por ningún teclado, así que nunca interfieren con los teclados físicos del equipo. Tienen su propia pestaña, «Teclas virtuales», junto al numpad, y también se editan desde el celular.
- **Color para cada botón**: 12 colores para reconocer tus sonidos de un vistazo, en el PC y en el celular. Las teclas de la capa Global llevan una «G».
- **Temas**: nueva pestaña **Temas** con 11 temas incluidos (Original, Medianoche, Bosque, Vino, Grafito, Synthwave, Océano, Claro, Papel, Nórdico y Atardecer), todos con el texto bien legible. Se pueden **importar y exportar temas .npt** (NumPad Theme): van cifrados, se revisa que no estén dañados ni modificados, y los temas oficiales vienen firmados por OkumaWsX. El tema elegido también se puede usar en el celular.
- 🔍 Esta versión esconde algunas sorpresas. ¿Las encontrarás?
- **App Android 1.2**: **temas** (los 11 del PC) en Ajustes → Apariencia, más **Alto contraste** y **Pantalla AMOLED / OLED** (negro puro); **12 colores** por botón más «sin color», y las teclas Global llevan una «G»; las teclas virtuales se ordenan en **5 × 6**; con el celular **acostado** los controles pasan a una barra lateral y la pantalla completa muestra solo las teclas con una píldora arriba. La app ya acepta el tema que le mande el PC.
- **Modo «Solo celular»**: Numpad Macros funciona sin ningún teclado ni numpad conectado. Se activa en «Numpad y opciones»; no muestra avisos de captura y en vez del numpad dibuja las teclas virtuales.
- **Estudio de Temas** (programa aparte, en `tools/estudio/`): crea temas `.npt` con las 22 capas de color, transparencia por capa, opacidad de la ventana, colores sacados de una imagen y plantillas con imágenes (banner, fondo de las teclas y logo). Los temas van cifrados y firmados: los del creador salen como «Oficial» y los de los demás como «Comunidad · su nombre», con una firma de autor que nadie más puede usar. Numpad Macros ya los importa (colores y transparencia de la ventana); las imágenes y la transparencia por capa llegarán en una próxima versión.

### Cambiado
- **F13–F24 ya no se usan como teclas de entrada**: las reemplazan las teclas virtuales. Lo que tenías asignado a F13–F24 se mueve solo a las primeras teclas virtuales libres del mismo banco. (Los atajos que *envían* F13–F24 a OBS u otros programas siguen igual.)
- La pestaña «Numpad y opciones» ahora se puede desplazar (ya no se cortan las últimas opciones).
- **Creador y soporte** ya no es una pestaña: se abre con el botón «Creado por OkumaWsX · Soporte» de abajo (redes, actualizaciones y donaciones en una sola ventana).
- **La ventana se adapta a tu pantalla**: el numpad y las teclas virtuales crecen o se achican al cambiar el tamaño de la ventana (más grandes en pantallas Full HD o 4K, y caben en laptops de 768 px de alto). Las letras de las teclas se ajustan a su tamaño.

### Corregido
- Linux: el icono de la bandeja no mostraba opciones (en KDE / CachyOS, GNOME, XFCE…), así que no había cómo cerrar el programa. Ahora, con **clic derecho**, aparece el menú del escritorio con **Mostrar ventana, Pausar / Reanudar, Ayuda y soporte y Salir**; clic izquierdo muestra u oculta la ventana y clic central pausa o reanuda. En escritorios sin ese tipo de bandeja, el clic en el icono abre el mismo menú.
- Al cerrar la ventana por primera vez, el programa pregunta si quieres **dejarlo en la bandeja o salir**, y puede recordar tu elección (se cambia en «Numpad y opciones» → «Al cerrar la ventana»).

## [3.3.1] - 2026-10-19
### Añadido
- **App para Android** (nueva): lanza y edita tus sonidos desde el celular por **Wi-Fi, cable USB o Bluetooth**. Nueva pestaña **Celular** con código QR y código de 4 números para vincular (solo la primera vez), lista de celulares vinculados y actividad. Desde el celular puedes cambiar de banco, detener, ajustar el volumen, asignar sonidos y atajos a cualquier tecla y **subir sonidos nuevos** (o grabarlos en el momento).
- **Teclas F13–F24 como botones**: casi ningún teclado las trae, pero las envían el software de teclados y mouse gamer, un Stream Deck o AutoHotkey. Se asignan con el botón «F13–F24» bajo el dibujo del numpad (y desde el celular). Las que no tienen acción pasan normal a los demás programas.
- Linux: elegir por dónde escuchas los sonidos (audífonos, parlantes, HDMI…) en la pestaña **Audio**, con botón para refrescar la lista y **▶ Probar** (pitido corto solo en tus audífonos).
- Linux: la app se agrega sola al menú de aplicaciones con su propio icono, así la barra de tareas (KDE, GNOME…) muestra el icono de Numpad Macros en vez de uno genérico, aunque la abras sin usar `instalar_linux.sh`.

### Corregido
- Linux: se escuchaba estática al abrir la app con versiones nuevas de PipeWire (como la de CachyOS). Ahora el audio se entrega en el formato que esas versiones esperan.
- Linux: la salida de audio ya no queda abierta todo el tiempo; se cierra sola tras unos segundos de silencio y se abre con el siguiente sonido.
- El aviso del compresor y de saturación ya no queda cortado junto a los medidores: ahora aparece con los demás indicadores.
- Mensaje más claro cuando no se puede buscar actualizaciones por falta de conexión.

## [3.3.0] - 2026-10-15
### Añadido
- **Medidores de volumen en tiempo real** para tus audífonos y el micrófono virtual, con aviso cuando satura o cuando actúa el compresor.
- **Igualar volumen**: mide cuánto «suena» cada sonido (LUFS) y los deja a todos al mismo nivel. Objetivo ajustable (−16 LUFS recomendado).
- **Compresor / limitador** con presets Suave, Media, Fuerte y Personalizada: los picos ya no saturan ni se cortan en Discord.
- **Actualizaciones con un clic**: la app avisa cuando hay una versión nueva, muestra sus novedades, la descarga, comprueba que sea la original y se instala sola.
- **Ventana de novedades** de la versión instalada (botón «Novedades» abajo y en la pestaña Creador).
- **Grabar combinaciones** pulsando las teclas, para los atajos y para el modo macros, con aviso si eliges una combinación que ya usan otros programas (Ctrl+C, Alt+F4…).
- Pestaña **Audio**: si falta el micrófono virtual, botón para instalar VB-Cable (Windows) o descargar BlackHole (macOS).

### Cambiado
- El volumen de cada tecla y el volumen general se ven en % y en dB mientras los mueves.
- La biblioteca muestra el volumen medido de cada sonido y cuánto se ajusta.
- Linux: los sonidos pasan por el mismo mezclador que en Windows y macOS (mejor sincronía y medidores).

### Corregido
- Al actualizar, el instalador de Windows ya no vuelve a instalar VB-Cable ni Interception ni pide reiniciar.

## [3.2.1] - 2026-10-09
### Añadido
- Publicación en GitHub con documentación completa, licencia LGPL-3.0 y compilación automática.
- Enlace al repositorio de GitHub en la pestaña **Creador**.
- Los textos de licencia se instalan junto a la app.

### Cambiado
- Las etiquetas de las teclas del numpad se ajustan mejor en teclas angostas.

## [3.2.0] - 2026-10-09
### Añadido
- **Instalador de Windows** (*Siguiente → Siguiente → Instalar*) en español: incluye el driver Interception, descarga VB-Cable desde su sitio oficial, crea accesos directos y desinstalador.
- Pestaña **Creador** con Instagram y Discord de soporte, y botón **Donar**.

## [3.1.0] - 2026-10-09
### Añadido
- **Modo macros de la fila de números**: con `Ctrl+Alt+M` (configurable), las teclas `1–0`, `-` y `=` del teclado principal lanzan sus propias acciones. Sirve cuando no tienes numpad.

## [3.0.0] - 2026-10-09
### Añadido
- **Biblioteca de sonidos propia** (pestaña *Sonidos*): agregar archivos o carpetas, buscar, escuchar y asignar.
- Importar listas de Soundpad (`.spl`).
- Modos de reproducción por tecla: Superponer, Reiniciar, Alternar y Mientras se mantiene.
- App independiente empaquetada (no requiere Python).
- Linux: botón **Dar permisos…** (sin cerrar sesión).
- Windows: si falta el driver Interception, pasa solo al modo sin driver.

### Eliminado
- Dependencia de Soundpad. Las teclas configuradas con Soundpad se convierten solas a sonidos propios.

## [2.0.0] - 2026-10-09
### Añadido
- Soporte para **Linux** (evdev + uinput) y **macOS** (IOKit + Quartz).
- Botonera propia con micrófono virtual (PipeWire en Linux, VB-Cable / BlackHole en Windows y macOS).

## [1.0.0] - 2026-10-09
### Añadido
- Primera versión para Windows: numpad como panel de sonidos de Soundpad y atajos, con bancos.

[3.4.0]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.4.0
[3.3.1]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.3.1
[3.3.0]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.3.0
[3.2.1]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.2.1
