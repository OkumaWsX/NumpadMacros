# Historial de cambios

Todas las versiones de Numpad Macros. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [versionado semántico](https://semver.org/lang/es/).

## [Sin publicar]
### Cambiado
- **Ctrl+Alt+M activa o pausa todo el modo macros**: ahora hace lo mismo que el botón ACTIVO / PAUSADO, desde cualquier programa, y muestra un aviso en pantalla. Activo: el numpad y, si su casilla está marcada, la fila 1–0, - y = lanzan tus acciones; pausado: escriben normal. La fila ya no se enciende aparte: sigue al modo macros. Las teclas virtuales del celular funcionan siempre, también en pausa. La combinación funciona aunque la fila de números esté desmarcada y también en pausa (para volver a activarlo). Se cambia en «Numpad y opciones» → «Modo macros» (antes estaba dentro de la fila de números); si ya la habías cambiado, se conserva. Aparece en el menú de la bandeja («Pausar (Ctrl+Alt+M)»).
- **Teclado principal en Linux**: para que la combinación funcione también en pausa sin llegarle al programa del frente, la app toma el teclado principal siempre y reenvía todo lo demás por una copia virtual de ese mismo teclado (todas sus teclas, también Fn y multimedia). Los dispositivos que además mueven un puntero (mouse, touchpad o rueda en el mismo teclado) no se toman: solo se leen, así el puntero nunca se pierde. Si la copia virtual no tiene permisos o el teclado está tomado por otro programa, solo se lee (la combinación funciona, pero también llega a la ventana activa) y la app lo avisa una vez. Al desconectar un teclado con teclas apretadas, se sueltan solas. Con una combinación de solo Alt o Win, la app evita que al soltarla se abra el menú del escritorio. Si la combinación estaba vacía, sigue desactivada.

### Corregido
- **Grabar la combinación**: mientras se graba, la combinación actual ya no pausa ni activa el programa, y llega a la ventana para poder grabarla.

## [3.5.0] - 2026-10-25
### Añadido
- **Temas para descargar**: la pestaña Temas muestra, junto a tus temas, los del catálogo en línea (repositorio NumpadMacros-Temas). Los que aún no tienes se ven translúcidos, con el sello **OFICIAL** o **COMUNIDAD** (con su autor y su huella de firma). Un solo botón: **Descargar** → se llena con el progreso (con el mouse encima dice «Descargando…» y un clic cancela) → **Aplicar** → **En uso**; también **Descargar y aplicar**, y **Actualizar** cuando sale una versión nueva de un tema que tienes. Nada se instala sin comprobar su huella SHA256 y su firma; si la conexión se corta, reintenta solo y continúa donde quedó, y si no puede, ofrece «Reintentar» sin tocar tu tema actual. Sin internet se usa la última lista guardada.
- **Estudio de Temas desde el instalador**: al instalar por primera vez eliges si quieres también el Estudio de Temas (editor para crear tus propios temas). En Windows se descarga de GitHub y se comprueba con su huella SHA256 antes de instalarlo; en Linux, `instalar_linux.sh` lo pregunta (o usa `--estudio` / `--sin-estudio`). Si ya tienes Numpad Macros, la casilla «Estudio de Temas» en Actualizaciones lo instala.
- **Actualizaciones del Estudio**: con esa opción activa, Numpad Macros busca también las versiones nuevas del Estudio y avisa en la cabecera. Si está apagada, solo busca las suyas.
- **Empieza en pausa**: al abrir, Numpad Macros arranca en PAUSADO y el numpad funciona normal hasta que pulses ACTIVO, para evitar que tome el numpad por sorpresa. Se puede desactivar en «Numpad y opciones» → «Comportamiento».
- **Más espacio en Temas**: al entrar en la pestaña Temas se oculta el panel de teclas y la lista usa todo el ancho de la ventana. El botón «⌨ Mostrar teclas» lo vuelve a mostrar, y la app recuerda la elección. En las demás pestañas el panel sigue a la vista.
- **Buscar y filtrar temas**: en la pestaña Temas puedes buscar por nombre, autor o etiqueta y filtrar por origen (oficiales o de la comunidad), por lo que tienes (instalados, disponibles o con actualización), por estilo (oscuro o claro), por color y por extras (imágenes, GIF, transparencia, degradado); también ordenar por nombre, por los más recientes u oficiales primero. Funciona igual con tus temas que no vienen del catálogo (el estilo y el color se deducen de sus colores). Cada sección dice cuántos quedan, y si ninguno coincide aparece «Quitar filtros».
- **Temas en lista o en cuadrícula**: como en el selector de sonidos, «Lista» muestra una fila por tema con su estado a la derecha (En uso, Instalado, Descargar o el progreso), y «Cuadrícula» tiene «Tamaño» para elegir de 2 a 10 por fila (o Ctrl + rueda). La app recuerda la vista y el tamaño.
- **Temas en pantallas chicas**: con ventana ancha, los filtros van arriba; si no caben, pasan a una columna a la izquierda que se oculta con «◀ Ocultar filtros» (y se vuelve a abrir con la franja «▶ FILTROS»; la app lo recuerda). Con la ventana al mínimo, el detalle del tema se abre encima de la lista al tocar un tema y se cierra con «✕», con Escape o con un clic fuera. Si falta alto, el detalle esconde los círculos de colores para que los botones se vean siempre enteros.
- **Temas de creadores digitales**: streamers y artistas ya tienen su lugar en la pestaña Temas, con el sello **★ CREADOR** (violeta) y su nombre bajo el del tema. Los revisa y firma OkumaWsX, y la app comprueba esa firma al descargarlos. Se filtran con «Creadores» en Origen, salen después de los oficiales en «Oficiales primero» y el buscador también encuentra por el nombre del creador.
- **Ficha del creador digital**: al elegir un tema de un creador, el detalle muestra su recuadro violeta «★ CREADOR DIGITAL» (el violeta del sello y del recuadro es fijo: se ve igual con cualquier tema, con una variante más oscura en los claros) con su nombre, una breve presentación y sus redes (Twitch, YouTube, TikTok…), con íconos con los colores originales de cada red (multicolor: degradado de Instagram, sombras de TikTok, etc.), sin recuadro, directo sobre la ficha (TikTok y X en blanco en temas oscuros y en negro en los claros, como sus logos oficiales): pasa el mouse para ver a dónde lleva y haz clic para abrir su perfil en el navegador. Debajo, «Sobre el tema» con la descripción y lo que trae el tema. Si falta alto en la ventana, el detalle esconde lo menos importante para que los botones se vean siempre. Si el creador tiene foto de perfil, aparece en un círculo con borde violeta en lugar de la inicial: se baja en segundo plano (sin frenar la ventana), se comprueba su huella SHA256 y su tamaño antes de usarla y se guarda en tu equipo para verla sin internet. Mientras llega, o si no hay conexión, se ve la inicial de siempre.
- **«Crear o editar temas…»** en la pestaña Temas: abre el Estudio y, si no está instalado en el equipo, te ofrece instalarlo.

### Corregido
- **Restos de dibujo en la pestaña Temas**: las tarjetas se dibujan ahora sobre un solo lienzo y el panel de detalle se repinta entero al moverse, así que ya no quedan rectángulos oscuros ni sellos cortados.
- **Zonas vacías al maximizar o redimensionar la ventana**: en algunos escritorios Linux (XWayland), lo que cambiaba de lugar al agrandar la ventana quedaba sin pintar (en Temas, el panel de detalle salía vacío: sin vista previa, colores ni botones). Ahora la app vuelve a dibujar todo mientras cambias el tamaño y al terminar, sin parpadeos.
- **Cambiar el tamaño de la ventana es mucho más fluido** (sobre todo en Temas): al maximizar, restaurar o arrastrar el borde, la pestaña se acomoda unas 3–4 veces más rápido (al restaurar, de ~0,6 s a ~0,15 s), las tarjetas ya no se ven un instante gigantes, vacías o a medio dibujar mientras se reacomodan, y en Linux los huecos que aún no se pintaron toman el color del panel del tema en vez de mostrar restos oscuros de lo que había antes. Con muchos temas, al cambiar el tamaño se dibuja primero lo que está a la vista.
- **Arranque con el audio del sistema trabado**: si PipeWire no respondía, Numpad Macros se cerraba al abrir. Ahora arranca igual y no se congela esperando al audio.
- **Teclas cortadas en modo ventana**: las teclas virtuales (y el numpad con la fila 1–0) ya no se cortan abajo cuando la ventana no está maximizada. El tamaño de las teclas se calcula con lo que de verdad ocupa el resto del panel, incluida la imagen de abajo del tema.
- **Pestañas sin desplazarse cuando hay espacio**: en la pestaña Tecla, el selector de sonidos toma el alto que sobra, así que la barra de desplazamiento ya no aparece cuando todo cabe (antes faltaban unos píxeles incluso en ventanas grandes). En Temas, la vista previa del tema se achica en ventanas bajas, así que «Usar este tema», «Exportar» y «Quitar» se ven siempre enteros.
- **Instalar en Linux sin mover archivos**: `instalar_linux.sh` ya no exige que el programa y `icon.png` estén en su misma carpeta. Los encuentra solo en el `.tar.gz` descargado o en la carpeta del código después de `./compilar.sh` (`dist/NumpadMacros` y `assets/icon.png`), funciona aunque lo ejecutes desde otra carpeta y acepta las rutas del programa y del icono como argumentos (`./instalar_linux.sh /ruta/a/NumpadMacros`). Si no está compilado, ofrece compilarlo; si falta el icono, instala igual y lo avisa.
- **Celular**: si una conexión fallaba al aceptarse, el PC dejaba de aceptar celulares hasta reiniciar la app. En Windows, un error de red podía detener la búsqueda de celulares.
- Un posible error al consultar los numpads mientras se conectaba uno (Linux), y un archivo `.tmp` que quedaba suelto si fallaba el guardado de la configuración.
- **Importar un tema que ya tienes**: ya no crea copias «Nombre (2)». Si el archivo es el mismo tema (mismo nombre y misma firma) con el mismo contenido o versión, avisa «Ya tienes este tema instalado» y lo selecciona; si es una versión más nueva, reemplaza la instalada (sin dejar el tema a medias) y, si estaba aplicado, sigue aplicado; si es una más vieja, pregunta antes de reemplazar (por defecto no). Descargar del catálogo un tema que ya importaste también lo reemplaza en vez de duplicarlo, así que conserva su sello ★ CREADOR u OFICIAL. Dos temas distintos (otra firma) con el mismo nombre siguen conviviendo.

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
- **Imágenes de los temas con su recorte exacto**: algunas imágenes de los temas se veían con otro recorte que el diseñado (por ejemplo, un texto ancho debajo de las teclas salía cortado por los lados). Los temas nuevos se ven tal cual se diseñaron.
- **Espacio de abajo del panel de teclas**: la imagen ocupa todo el ancho del panel, como en la vista previa, se ve completa y ya no le quita espacio a la última fila de teclas.

## [3.4.1] - 2026-10-21
### Añadido
- **App Android 1.3**: **busca actualizaciones sola** (una vez al día, en GitHub, igual que el escritorio): avisa en la botonera, muestra las novedades, descarga el APK, lo comprueba con su huella SHA256 y abre el instalador de Android (sin perder los PCs vinculados ni los ajustes). En Ajustes → Actualizaciones se puede apagar, recibir betas y «Buscar ahora». Además, los menús son **píldoras flotantes de vidrio** como en el escritorio: barra inferior flotante, selector de grupo y pestañas en un riel, bancos y Detener + volumen en píldoras, y hojas esmeriladas (desenfoque en Android 12 o más nuevo; con Alto contraste se vuelven sólidas).

### Corregido
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
- **Temas de la comunidad**: Numpad Macros importa temas `.npt` firmados: los del creador salen como «Oficial» y los de los demás como «Comunidad · su nombre», con una firma de autor que nadie más puede usar.

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

[3.5.0]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.5.0
[3.4.4]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.4.4
[3.4.3]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.4.3
[3.4.2]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.4.2
[3.4.1]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.4.1
[3.4.0]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.4.0
[3.3.1]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.3.1
[3.3.0]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.3.0
[3.2.1]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.2.1
