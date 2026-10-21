# Cómo publicar una versión nueva

Guía para el creador (OkumaWsX). Publicar una versión deja la Release en GitHub con los programas
para Windows, Linux y macOS, y hace que la app de cada usuario muestre el aviso «Hay una nueva versión».

## Lo que se hace una sola vez

1. **Publicador:** descarga el archivo `Publicador-NumpadMacros` (Linux) que te entregó Claude, dale permiso de
   ejecución (clic derecho → Propiedades → Permisos → «Permitir ejecutar como programa», o
   `chmod +x Publicador-NumpadMacros`) y ábrelo. También puede ejecutarse desde el código:
   `pip install -r tools/publicador/requirements.txt` y `python tools/publicador/publicador.py`.
2. **Conectar con GitHub:** la primera vez el Publicador pide un *token*. Pulsa «Crear el token en GitHub» y:
   - Nombre: `Publicador Numpad Macros` · Expiración: 1 año.
   - *Repository access* → **Only select repositories** → `NumpadMacros`.
   - *Repository permissions* → **Read and write** en **Actions**, **Contents** y **Workflows**.
   - **Generate token**, copia el texto (`github_pat_…`), pégalo en el Publicador y pulsa «Guardar y probar».
   El token queda guardado solo en tu PC. Cuando venza (en un año), el Publicador te lo pedirá de nuevo.
3. **Anuncio en Discord (opcional):** en Discord, *Editar canal → Integraciones → Webhooks → Nuevo webhook →
   Copiar URL*. En GitHub: *Settings → Secrets and variables → Actions → New repository secret*, nombre
   `DISCORD_WEBHOOK`, valor: la URL copiada.

## Cada vez que sale una versión

1. Claude te entrega `NumpadMacros-codigo_X.Y.Z.zip` (ya trae el número nuevo y las novedades anotadas en
   la sección **«Sin publicar»** del `CHANGELOG.md`).
2. Arrástralo al Publicador. Revisa que sea Numpad Macros, que la versión sea más nueva y que tenga novedades.
3. Revisa las notas (puedes corregirlas), marca las opciones y pulsa **«Aceptar y publicar»**.
4. El robot de GitHub tarda unos 10–15 minutos. Puedes cerrar el Publicador: si algo falla, GitHub te avisa
   por correo y **no se publica nada**.

### Desde el teléfono (Publicador para Android)

Para cuando no tienes el PC a mano. Hace lo mismo que el del escritorio, con las mismas pantallas.

1. Instálalo una vez: *Actions → Compilar Publicador Android* → la ejecución más reciente → descarga
   `Publicador-Android` (un .zip con el APK) y ábrelo en el teléfono.
2. La primera vez pide el token: sirve el mismo del PC (o crea otro con los mismos permisos).
3. Elige el `NumpadMacros-codigo_X.Y.Z.zip` con «Elegir .zip…», o *Compártelo* desde Archivos, Drive o
   Telegram con «Publicador NM». Revisa, corrige las notas si quieres y pulsa «Aceptar y publicar».
4. El avance se ve en la app y en una notificación; puedes salir de la app mientras GitHub compila.

«Crear tema .npt…» también está: eliges el tema en JSON y tu clave de firma (se guarda cifrada en el
teléfono; nunca la subas a GitHub).

### Sin el Publicador (desde la web de GitHub)

*Actions → Publicar versión → Run workflow*. Elige el tipo (corrección, mejora o grande) o deja
«automatico» para usar el número que ya trae el código. Las novedades deben estar en «Sin publicar».

> Para quien prepara las versiones (desarrollo): el robot guarda en `main` el número y el CHANGELOG ya
> convertido. Antes de preparar la siguiente versión, actualiza tu copia con `git pull`.

## Capturas de cada versión

Las capturas de la versión X.Y.Z van en `docs/capturas/X.Y.Z/` (con `capturas.txt` para elegir cuáles y su
descripción). Al publicar esa versión, el robot las agrega a las notas de su Release con enlaces fijos a
esa versión. Para una versión ya publicada: *Actions → Capturas en una Release → Run workflow*.

## Opciones

| Opción | Qué hace |
|---|---|
| **Beta** | La Release se marca como *pre-release*: solo la reciben quienes activaron «Recibir también versiones de prueba» en la pestaña Creador. |
| **Importante** | Los usuarios no pueden omitirla (desaparece «Omitir esta versión»). Para arreglos graves. |
| **Anunciar en Discord** | Publica un mensaje en el canal del webhook. |

## Qué hace el robot (`.github/workflows/publicar.yml`)

1. **Preparar** (`tools/release.py prepare`): calcula el número, revisa las novedades, convierte «Sin publicar»
   en `## [X.Y.Z] - fecha` y escribe el número en `npm/__init__.py`.
2. **Compilar** (`compilar.yml`): pruebas automáticas + Windows (instalador y portátil), Linux y macOS.
3. **Publicar**, solo si todo salió bien: guarda el número en `main`, crea la etiqueta `vX.Y.Z`, la Release con
   los archivos y `SHA256SUMS.txt` (las huellas que la app usa para comprobar las descargas), y avisa en Discord.

## Números de versión

- **Corrección** (3.3.0 → 3.3.1): solo arreglos.
- **Mejora** (3.3.0 → 3.4.0): funciones nuevas.
- **Grande** (3.3.0 → 4.0.0): cambios importantes (por ejemplo, cómo se guarda la configuración).

Todas comparten el mismo identificador de app (`APP_ID` en `npm/about.py` y `AppId` del instalador): por eso
cada versión se instala **encima** de la anterior y no como otra aplicación. No cambies ese identificador.

## Nombre de la carpeta al descomprimir

Los paquetes de cada versión (Windows portátil, Linux y macOS) y los zip de código que te entrego
se descomprimen en una carpeta con la versión: `NumpadMacros-3.4.0`. Si la versión es de prueba,
lleva además `-beta`: `NumpadMacros-3.4.0-beta`. Si el zip que arrastras al Publicador dice
`-beta`, la casilla «Versión de prueba (beta)» aparece marcada (puedes cambiarla).
