# Estudio de Temas · Numpad Macros

Programa aparte para crear temas `.npt` (NumPad Theme) para Numpad Macros, en Windows, Linux y macOS.

## Descargar

Tiene sus propias [Releases](https://github.com/OkumaWsX/NumpadMacros/releases?q=Estudio+de+Temas&expanded=true)
(«Estudio de Temas X.Y.Z», aparte de las de Numpad Macros) y su propio [historial de cambios](CHANGELOG.md):

- **Windows**: `EstudioTemas-Windows-Setup.exe` (instalador, no pide administrador) o
  `EstudioTemas-Windows-portable.zip`.
- **Linux**: `EstudioTemas-Linux.tar.gz`. Descomprime y abre `EstudioTemas-NumpadMacros`; se agrega solo al
  menú de aplicaciones.
- **macOS**: `EstudioTemas-macOS.zip`. Muévelo a *Aplicaciones* y ábrelo con clic derecho → *Abrir* la
  primera vez.

## Qué puedes hacer

1. **Editar tema**: cambia las 22 capas de color, cada una con su propia transparencia, y la opacidad de la
   ventana (en uso y cuando no la usas). El **fondo de la ventana** puede ser un color, un **degradado** de
   2 a 5 colores que empieza en una esquina, un lado o el centro, o una **imagen** (subida, la importada o
   generada con la paleta). Con **«Fondo de una pieza»** el fondo pasa también por detrás de los paneles,
   suavizado y teñido con el **«Tinte de los paneles»**. La vista previa es la ventana de Numpad
   Macros 3.4.1, sobre un fondo de escritorio de ejemplo: toca cualquier parte para editar su color. El panel
   de legibilidad avisa si algún texto no se lee.
2. **Transparencia por sección**: el encabezado, el panel de teclas, las teclas, las pestañas, el panel de la
   pestaña y el pie tienen cada uno la transparencia de su fondo y de su contenido, y un borde de realce.
   «Destacar» deja una sección a todo color y atenúa las demás; también hay estilos rápidos.
3. **Colores desde una imagen**: importa (o arrastra) una imagen, el Estudio saca sus colores principales y
   los reparte en el tema, oscuro o claro. Si algún texto queda ilegible, lo corrige solo.
4. **Imágenes y plantillas**: 9 espacios. Cuatro van detrás del contenido (banner del encabezado, fondo de las
   teclas, parte de abajo de la pestaña y banda del pie) y cinco en espacios libres que nunca tapan botones
   (logo, centro del encabezado, final de las pestañas, debajo de las teclas y el pie). Admiten **GIF
   animado** (hasta 120 cuadros), con ajuste, opacidad, oscurecido y desenfoque. Las plantillas llenan los
   espacios de una vez.
5. **Exportar**: crea el `.npt` cifrado y firmado. Con un editor de texto no se puede leer, y si alguien lo
   modifica, Numpad Macros lo rechaza.
6. **Proyecto `.nptproj`**: guarda tu trabajo sin cifrar para seguir editándolo después.

**Más espacio para la vista previa**: con los interruptores «Panel izquierdo» y «Panel derecho» (arriba a la
derecha) ocultas los paneles laterales; arrastrando su borde los haces más anchos o más angostos. La vista
previa queda siempre centrada y crece con el espacio libre.

## Comunidad y creador oficial

Es el mismo programa para todos:

- **Comunidad**: la primera vez el Estudio te pide un nombre de autor y crea tu **firma de autor**. Tus temas
  salen en Numpad Macros como «Comunidad · tu nombre». Guarda una copia de tu firma (pantalla 5) para
  usarla en otra PC.
- **Creador oficial**: si la clave oficial está en la PC, el Estudio abre en modo creador y firma los temas
  como «Oficial · OkumaWsX».

### Modo creador (solo el creador)

El Estudio usa la misma clave de firma de temas que el Publicador (`firma-temas-OkumaWsX.key`). Si el
Publicador ya la tiene configurada en tu PC, el Estudio te ofrece usarla al abrirse. Si no, impórtala en
la pantalla 5 («Importar copia…»). El Estudio solo la acepta si es la clave oficial. Esa clave **nunca** se
sube a GitHub: el repositorio ignora los archivos `*.npkey` y `*.key`.

Carpeta del Estudio: `%APPDATA%\NumpadMacros\estudio` (Windows), `~/Library/Application Support/NumpadMacros/estudio`
(macOS) o `~/.config/NumpadMacros/estudio` (Linux).

## Ejecutar desde el código

```bash
pip install -r tools/estudio/requirements.txt
python tools/estudio/estudio.py
```

Empaquetar: `cd tools/estudio && pyinstaller --noconfirm Estudio.spec`. GitHub Actions también lo compila
para los 3 sistemas («Compilar Estudio de Temas»).

Formato del archivo: [docs/FORMATO_NPT.md](../../docs/FORMATO_NPT.md)
