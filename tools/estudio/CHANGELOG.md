# Historial de cambios · Estudio de Temas

El Estudio de Temas es un programa aparte de Numpad Macros, con su propio número de versión. Crea los
temas `.npt` que Numpad Macros importa. Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Sin publicar]
### Corregido
- Los paneles laterales ya no se pueden «subir» más allá del principio cuando todo su contenido cabe (pasaba en «Transparencia por sección» e «Imágenes y plantillas»: quedaba un hueco arriba).
- Al maximizar o cambiar mucho el tamaño de la ventana (sobre todo en Linux con KDE), ya no desaparecen botones, interruptores ni partes de los paneles: se vuelve a pintar toda la ventana, y sin parpadeos al arrastrar el borde de a poco.
- La vista previa se reajusta más rápido al cambiar el tamaño de la ventana: reutiliza el último dibujo en vez de rehacerlo entero, y la ventana se queda menos tiempo trabada.

## [1.0.0] - pendiente
### Añadido
- **Primera versión oficial** del Estudio de Temas, para Windows (instalador y portátil), Linux y macOS, sin instalar Python. En Windows, los proyectos `.nptproj` se abren con doble clic.
- **Editar tema**: las 22 capas de color, cada una con su propia transparencia, y la opacidad de la ventana (en uso y cuando no la usas). Toca cualquier parte de la vista previa para editar su color; el panel de legibilidad avisa si algún texto no se lee.
- **Fondo de la ventana**: color sólido, **degradado** de 2 a 5 colores (desde una esquina, un lado o el centro) o **imagen** (subida, la importada o generada con la paleta). Con **«Fondo de una pieza»** el fondo pasa también por detrás de los paneles, suavizado con el **«Tinte de los paneles»**.
- **Transparencia por sección**: encabezado, panel de teclas, teclas, pestañas, panel de la pestaña y pie, cada una con la transparencia de su fondo y de su contenido y un borde de realce. «Destacar» resalta una sección; estilos rápidos Normal, Destacar teclas, Destacar la pestaña y Cristal.
- **Colores desde una imagen**: saca los colores principales de una imagen y los reparte en el tema, oscuro o claro, corrigiendo lo que quede ilegible.
- **9 espacios para imágenes**: 4 detrás del contenido (banner, fondo de las teclas, parte de abajo de la pestaña y banda del pie) y 5 en espacios libres que nunca tapan botones. Los libres admiten **GIF animado** (hasta 120 cuadros), con opción de pausarlos cuando no usas la ventana. Plantillas: Solo colores, Banner, Teclas con fondo, Completa, Stickers animados y Todo.
- **Vista previa** igual a la ventana de Numpad Macros, con transparencia real y un fondo de escritorio de ejemplo. Se ajusta al tamaño de la ventana y queda siempre centrada.
- **Paneles laterales ocultables y con ancho ajustable**: interruptores «Panel izquierdo» y «Panel derecho», y bordes que se arrastran (con límites para que el contenido no se deforme).
- **Firma de los temas**: los del creador salen como «Oficial · OkumaWsX» y los de los demás como «Comunidad · su nombre», con una firma de autor que se crea sola. Temas cifrados: si alguien los modifica, Numpad Macros los rechaza.
- **Proyectos `.nptproj`** para seguir editando un tema después.
- Icono propio: una «T» caligráfica y un pincel de artista.
