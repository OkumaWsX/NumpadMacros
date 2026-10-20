# Estudio de Temas · Numpad Macros

Programa aparte para crear temas `.npt` (NumPad Theme) para Numpad Macros, en Windows, Linux y macOS.

## Descargar

Viene en cada [Release](https://github.com/OkumaWsX/NumpadMacros/releases/latest) de Numpad Macros:

- **Windows**: `EstudioTemas-Windows-Setup.exe` (instalador, no pide administrador) o
  `EstudioTemas-Windows-portable.zip`.
- **Linux**: `EstudioTemas-Linux.tar.gz`. Descomprime y abre `EstudioTemas-NumpadMacros`; se agrega solo al
  menú de aplicaciones.
- **macOS**: `EstudioTemas-macOS.zip`. Muévelo a *Aplicaciones* y ábrelo con clic derecho → *Abrir* la
  primera vez.

## Qué puedes hacer

1. **Editar tema**: cambia las 22 capas de color, cada una con su propia transparencia, y la opacidad de la
   ventana (en uso y cuando no la usas). La vista previa es la ventana de Numpad Macros 3.4: toca cualquier
   parte para editar su color. El panel de legibilidad avisa si algún texto no se lee.
2. **Colores desde una imagen**: importa (o arrastra) una imagen, el Estudio saca sus colores principales y
   los reparte en el tema, oscuro o claro. Si algún texto queda ilegible, lo corrige solo.
3. **Imágenes y plantillas**: pon imágenes en el banner del encabezado, detrás de las teclas o como logo, con
   ajuste, opacidad, oscurecido y desenfoque. Las plantillas llenan los espacios de una vez.
4. **Exportar**: crea el `.npt` cifrado y firmado. Con un editor de texto no se puede leer, y si alguien lo
   modifica, Numpad Macros lo rechaza.
5. **Proyecto `.nptproj`**: guarda tu trabajo sin cifrar para seguir editándolo después.

## Comunidad y creador oficial

Es el mismo programa para todos:

- **Comunidad**: la primera vez el Estudio te pide un nombre de autor y crea tu **firma de autor**. Tus temas
  salen en Numpad Macros como «Comunidad · tu nombre». Guarda una copia de tu firma (pantalla 4) para
  usarla en otra PC.
- **Creador oficial**: si la clave oficial está en la PC, el Estudio abre en modo creador y firma los temas
  como «Oficial · OkumaWsX».

### Modo creador (solo el creador)

El Estudio usa la misma clave de firma de temas que el Publicador (`firma-temas-OkumaWsX.key`). Si el
Publicador ya la tiene configurada en tu PC, el Estudio te ofrece usarla al abrirse. Si no, impórtala en
la pantalla 4 («Importar copia…»). El Estudio solo la acepta si es la clave oficial. Esa clave **nunca** se
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
