# Historial de cambios

Todas las versiones de Numpad Macros. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [versionado semántico](https://semver.org/lang/es/).

## [Sin publicar]
### Corregido
- **Estudio de Temas 1.1.2**:
  - La **vista previa se ajusta al tamaño de la ventana**: en pantalla completa crece (hasta el doble, nítida) y en pantallas chicas se achica, siempre entera y sin barra de desplazamiento ni espacio vacío. Las zonas se siguen tocando igual.
  - **Zonas a medio dibujar** (artefactos) al aplicar cambios o al maximizar, en escritorios Linux: los cambios seguidos se juntan en un solo dibujo, las listas de legibilidad, secciones, plantillas y espacios ya no se rehacen enteras en cada cambio, y las columnas se vuelven a pintar después de cambiar de tamaño o de pantalla.

## [3.4.4] - 2026-10-22
### Corregido
- **Teclas completas con temas que traen imagen abajo del panel**: en ventana (no maximizada) la última fila de teclas quedaba cortada; ahora las teclas se achican para dejar sitio a la imagen.
- **Rueda del mouse en la pestaña Temas**: si todos los temas caben, la rueda ya no los desplaza hacia abajo dejando un hueco vacío arriba.
- **Ventanas bajas (p. ej. 1280 × 720)**: si las teclas no caben junto con la imagen de abajo del panel, la imagen se esconde y las teclas (y la fila de números) se ven completas.
- **Selector de sonidos con pocas por fila**: cada tarjeta se ve entera, con su nombre (antes, con 3 por fila, las portadas eran más altas que el selector).
- **Bancos con nombre largo**: en la cabecera el nombre se acorta con «…» en vez de quedar cortado bajo las flechas.
- **Rectángulos negros** después de cambiar de tema o de pasar a pantalla completa (en escritorios Linux con efectos): la ventana se vuelve a dibujar entera.

## [3.4.3] - 2026-10-22
### Corregido
- **Pestaña Temas ordenada**: todas las tarjetas miden lo mismo, así que un tema con nombre largo ya no descuadra la rejilla; el nombre se acorta con «…» (completo a la derecha) y la marca «En uso» va sobre la vista previa.

## [3.4.2] - 2026-10-22
### Corregido
- **Imágenes de los temas con el mismo recorte que en el Estudio**: el Estudio de Temas guardaba cada imagen con otra forma que la de su vista previa, así que en Numpad Macros se veía otro pedazo (por ejemplo, un texto ancho debajo de las teclas salía cortado por los lados). Ahora el tema guarda exactamente lo que ves en la vista previa (Estudio de Temas 1.1.1). Los temas ya creados se arreglan volviendo a guardarlos desde su proyecto `.nptproj`.
- **Espacio de abajo del panel de teclas**: la imagen ocupa todo el ancho del panel, como en la vista previa, se ve completa y ya no le quita espacio a la última fila de teclas.

## [3.4.1] - 2026-10-21
### Añadido
- **App Android 1.3**: **busca actualizaciones sola** (una vez al día, en GitHub, igual que el escritorio): avisa en la botonera, muestra las novedades, descarga el APK, lo comprueba con su huella SHA256 y abre el instalador de Android (sin perder los PCs vinculados ni los ajustes). En Ajustes → Actualizaciones se puede apagar, recibir betas y «Buscar ahora». Además, los menús son **píldoras flotantes de vidrio** como en el escritorio: barra inferior flotante, selector de grupo y pestañas en un riel, bancos y Detener + volumen en píldoras, y hojas esmeriladas (desenfoque en Android 12 o más nuevo; con Alto contraste se vuelven sólidas).
- **Estudio de Temas para descargar**: cada versión trae el Estudio listo para usar, sin instalar Python: instalador para Windows (no pide administrador), versión portátil, Linux y macOS. En Windows, los proyectos `.nptproj` se abren con doble clic.

- **Estudio de Temas 1.1**, con todo lo de las maquetas:
  - **Fondo de imagen y «Fondo de una pieza»**: el fondo de la ventana también puede ser una imagen (subida, la importada para los colores o generada con la paleta), con opción de oscurecerla. Con «Fondo de una pieza», el degradado o la imagen pasa también por detrás del panel de teclas, las pestañas y su contenido; el «Tinte de los paneles» los suaviza para que el texto se lea. La vista previa lo muestra igual que Numpad Macros.
  - **Fondo degradado** para toda la ventana: de 2 a 5 colores, que empieza en una esquina, un lado o el centro (circular). Se arma a mano, con los colores del tema o con los de la imagen.
  - **Transparencia por sección** (pantalla nueva): encabezado, panel de teclas, teclas, pestañas, panel de la pestaña y pie, cada una con la transparencia de su fondo y de su contenido y un borde de realce. «Destacar» resalta una sección y atenúa las demás; hay estilos rápidos (Normal, Destacar teclas, Destacar la pestaña y Cristal).
  - **9 espacios para imágenes**: además del banner, el fondo de las teclas y el logo, la parte de abajo de la pestaña y la banda del pie (detrás de los botones, también detrás de Donar) y cuatro espacios libres que nunca tapan botones. Admiten **GIF animado** (hasta 120 cuadros), con opción de pausarlos cuando no usas la ventana. Plantillas nuevas: «Stickers animados» y «Todo».
  - La **vista previa** es ahora la ventana de Numpad Macros 3.4.1, con la letra Inter, transparencia real y un fondo de escritorio de ejemplo.

### Cambiado
- **Estudio de Temas con icono propio**: una «T» caligráfica y un pincel de artista con un trazo de colores, para distinguirlo de Numpad Macros en el escritorio, la barra de tareas, el instalador y el menú de aplicaciones.

### Corregido
- Estudio de Temas: la versión compilada se cerraba apenas se abría (le faltaba una pieza para mostrar imágenes). Si algo falla al abrirse, ahora lo muestra en una ventana y lo anota en `error.log`.
- Linux: el icono de la bandeja no mostraba opciones (en KDE / CachyOS, GNOME, XFCE…), así que no había cómo cerrar el programa. Ahora, con **clic derecho**, aparece el menú del escritorio con **Mostrar ventana, Pausar / Reanudar, Ayuda y soporte y Salir**; clic izquierdo muestra u oculta la ventana y clic central pausa o reanuda. En escritorios sin ese tipo de bandeja, el clic en el icono abre el mismo menú.
- Al cerrar la ventana por primera vez, el programa pregunta si quieres **dejarlo en la bandeja o salir**, y puede recordar tu elección (se cambia en «Numpad y opciones» → «Al cerrar la ventana»).
- La ventana podía dejar de responder (al numpad, al celular y a la bandeja) justo después de la búsqueda automática de actualizaciones al iniciar. Ya no pasa.

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

[3.4.4]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.4.4
[3.4.3]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.4.3
[3.4.2]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.4.2
[3.4.1]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.4.1
[3.4.0]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.4.0
[3.3.1]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.3.1
[3.3.0]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.3.0
[3.2.1]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.2.1
