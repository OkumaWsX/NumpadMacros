# Traspaso: Estudio de Temas (para seguir en local con Claude Code)

Este documento junta todo lo del **Estudio de Temas**: qué es, cómo se trabaja, dónde está cada cosa,
cómo se prueba y publica, y qué queda pendiente. Fecha: 2026-10-23. Versión del Estudio: **1.0.0**
(lista para publicar).

## 1. Quién y cómo trabajamos
- Creador: **Jona (OkumaWsX)**, Chile, usa **CachyOS** (KDE). Todo en **español**.
- Cuando pide algo «sencillo»: fácil de entender, pero sin omitir lo importante.
- Primero se diseña (maqueta) y se programa cuando lo aprueba («manos a la obra», «procedamos»).
- Repositorio: `OkumaWsX/NumpadMacros` (LGPL-3.0). El Estudio vive en `tools/estudio/`.
- **El Estudio es un proyecto aparte de Numpad Macros**: tiene su propio número de versión, su
  propio historial (`tools/estudio/CHANGELOG.md`) y sus propias Releases. Las Releases y el
  `CHANGELOG.md` de Numpad Macros **no lo mencionan**.
- Commits: terminan con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (y la línea
  `Claude-Session` si la sesión la da).
- **Nunca** crear etiquetas ni Releases a mano desde el chat: se publica solo con los workflows
  (ver §6). Siempre `git pull --rebase` antes de empezar y antes de subir: otro chat (el de
  escritorio, Numpad Macros) y los robots también suben cambios a `main`.
- **La clave oficial nunca va a GitHub**: `firma-temas-OkumaWsX.key` / `oficial.npkey`. El
  repositorio ignora `*.npkey` y `*.key`.

## 2. Preparar la PC (CachyOS)
```bash
sudo pacman -S --needed git python tk github-cli     # tk: ventanas de Python (tkinter)
git clone https://github.com/OkumaWsX/NumpadMacros.git
cd NumpadMacros
python -m venv .venv && source .venv/bin/activate
pip install -r tools/estudio/requirements.txt pyinstaller==6.22.3 pyflakes
```
Luego abre Claude Code dentro de la carpeta `NumpadMacros`. `tools/estudio/CLAUDE.md` le indica que
lea este documento.

## 3. Comandos del día a día
| Para qué | Comando (desde la raíz del repo) |
|---|---|
| Abrir el Estudio desde el código | `python tools/estudio/estudio.py` |
| Abrir un proyecto o tema | `python tools/estudio/estudio.py archivo.nptproj` (o `.npt`) |
| Todas las pruebas | `python -m unittest discover -s tests` |
| Solo formato y Estudio | `python -m unittest tests.test_npt tests.test_npt_zonas tests.test_estudio` |
| Prueba automática de la ventana (abre todas las pantallas, exporta un tema, se cierra sola) | `python tools/estudio/estudio.py --probar` |
| Revisar errores de código | `python -m pyflakes tools/estudio/*.py npm/npt.py` |
| Compilar el programa | `cd tools/estudio && pyinstaller --noconfirm Estudio.spec` → `dist/` |
| Probar el compilado | `tools/estudio/dist/EstudioTemas-NumpadMacros --probar` |

- `NPT_ESTUDIO_DIR=/tmp/estudio-prueba` hace que el Estudio use otra carpeta de ajustes y claves
  (para probar sin tocar las tuyas). La carpeta normal en Linux es `~/.config/NumpadMacros/estudio`
  (Windows: `%APPDATA%\NumpadMacros\estudio`; macOS: `~/Library/Application Support/NumpadMacros/estudio`).
- Si algo falla al abrir, queda en `error.log` dentro de esa carpeta.

## 4. Dónde está cada cosa
| Archivo | Qué hace |
|---|---|
| `tools/estudio/estudio.py` | La ventana (Tkinter): 5 pantallas, paneles laterales, exportar, claves. `VERSION` está arriba. |
| `tools/estudio/vista.py` | Vista previa de la ventana de Numpad Macros, dibujada con Pillow (al doble y reducida), con transparencia real, degradado, imagen de fondo, «fondo de una pieza», secciones, 9 zonas y GIF. Escala 0,4×–2×. `export_size()` decide con qué forma se guarda cada imagen. |
| `tools/estudio/logica.py` | Lógica sin ventana: colores, legibilidad, paleta desde imagen, imágenes y GIF (APNG), degradado, fondo de imagen, secciones, proyecto `.nptproj`. |
| `tools/estudio/claves.py` | Firma de autor / clave oficial, modo creador o comunidad, ajustes (`ajustes.json`). |
| `tools/estudio/Estudio.spec` | PyInstaller (incluye la letra Inter, el icono y `PIL._tkinter_finder`; excluye numpy). |
| `tools/estudio/CHANGELOG.md` | Historial propio del Estudio. Las novedades nuevas van en «Sin publicar». |
| `tools/estudio/LEEME.md` | Guía para usuarios. |
| `npm/npt.py` | **Formato `.npt` compartido con Numpad Macros** (lo usan los dos programas). |
| `docs/FORMATO_NPT.md` | El contrato del formato (campos, espacios, tamaños). Leerlo antes de tocar `npt.py`. |
| `npm/theme_art.py` | Cómo Numpad Macros dibuja los temas. La vista previa del Estudio tiene que verse igual. |
| `assets/icon-estudio.png/.ico` | Icono del Estudio (T caligráfica y pincel). |
| `installer/EstudioTemas.iss` | Instalador de Windows (Inno Setup, sin administrador, asocia `.nptproj`). |
| `tests/test_estudio.py`, `tests/test_npt.py`, `tests/test_npt_zonas.py` | Pruebas. |
| `.github/workflows/estudio.yml` | Compila y prueba en Windows, Linux y macOS (en cada push a `tools/estudio/**`). |
| `.github/workflows/publicar-estudio.yml` | Publica el Estudio (ver §6). |

## 5. Qué hace el Estudio 1.0.0
- **Pantallas**: 1 Editar tema · 2 Transparencia por sección · 3 Imágenes y plantillas · 4 Exportar ·
  5 Clave de firma / Mi firma de autor.
- **Colores**: 22 capas con transparencia propia, ventana (opacidad en uso y sin usar), colores
  sacados de una imagen, panel de legibilidad (bloquea exportar si algo no se lee).
- **Fondo de la ventana**: Sólido / Degradado (2–5 colores, 9 puntos de inicio) / Imagen (subida,
  la importada o generada con la paleta; «Oscurecer»). «Fondo de una pieza» + «Tinte de los paneles».
- **Secciones**: head, left, keys, tabs, body, foot con fondo, contenido y realce; «Destacar» y estilos.
- **Imágenes**: 9 espacios (4 detrás: banner, keys, corner, footband; 5 libres: logo, headmid, tabsend,
  leftbot, foot). GIF solo se animan en los libres (menos el logo); se guardan como PNG animado.
- **Interfaz**: vista previa centrada y a la medida de la ventana (sin barra de desplazamiento);
  paneles laterales ocultables (interruptores arriba a la derecha) y redimensionables arrastrando el
  borde (izquierdo 290–480 px, derecho 320–520 px); se guarda cómo quedaron.
- **Firma**: modo creador si existe `oficial.npkey` en la carpeta del Estudio (firma «Oficial ·
  OkumaWsX»); si no, modo comunidad con firma de autor propia («Comunidad · nombre»). El nombre
  OkumaWsX (y parecidos) está reservado. La clave PEM del Publicador se puede importar en la pantalla 5.

## 6. Versiones y publicación
- Número: `VERSION` en `tools/estudio/estudio.py`. Se sube a mano (1.0.1 arreglos, 1.1.0 novedades).
- Novedades: en `tools/estudio/CHANGELOG.md`, bajo «## [Sin publicar]».
- Publicar: Actions → **«Publicar Estudio de Temas»** → Run workflow.
  - **«Privado (borrador)»** (marcado por defecto): compila y deja una Release en borrador que solo ve
    Jona, para descargar y probar. No crea etiqueta ni toca el historial. Cada corrida reemplaza el
    borrador anterior.
  - Sin marcar: crea la etiqueta `estudio-vX.Y.Z` y la Release «Estudio de Temas X.Y.Z» (sin marcarla
    como «la última»: esa es siempre la de Numpad Macros), pone la fecha en el historial y actualiza
    el enlace de descarga del README.
- El actualizador de Numpad Macros solo considera etiquetas `vX.Y.Z`, así que las del Estudio no lo
  confunden.
- Numpad Macros se publica aparte con «Publicar versión» (o el programa Publicador) y ya no incluye el
  Estudio.

## 7. Coordinación con Numpad Macros (otro chat)
- `npm/npt.py` es de los dos. Regla del formato: al **leer** se ignora lo desconocido (espacios,
  secciones o claves nuevas); al **escribir** se valida todo. El byte de versión sigue en 2.
- Lo que el Estudio guarda tiene que verse igual en Numpad Macros: si cambias cómo se dibuja algo en
  `vista.py`, revisa `npm/theme_art.py` (y al revés).
- Campos del fondo: `fondo = {"tipo": "degradado"|"imagen", "colores", "desde", "una_pieza", "tinte"}`,
  imagen en el espacio `fondo` (hasta 1920 × 1200). Secciones solo las que cambian.

## 8. Trampas conocidas (ya resueltas, pero que vuelven si se toca)
- **Tk no reacomoda** una pantalla después de `grid_remove()` de un panel: hay que volver a ubicarla
  (`f.grid_remove(); f.grid()`), ver `_apply_panel`.
- Un `tk.Canvas` sin `width` pide ~380 px y ensancha toda la columna.
- Pillow: dibujar con `ImageDraw.Draw(im, "RGBA")` sobre una capa RGBA **reemplaza** el alfa (no
  mezcla): las capas semitransparentes se dibujan aparte y se combinan con `alpha_composite`.
- Los controles `tk.Scale` llaman a su comando también cuando el programa cambia el valor: los
  manejadores comparan con el valor actual antes de marcar cambios.
- `render()` se junta con `after_idle` (un solo dibujo por tanda de cambios). En KDE quedaban zonas
  a medio pintar: las columnas se repintan tras cambiar de tamaño (`Scrollable.refresh`).
- Compilado: sin `PIL._tkinter_finder` el programa se cierra al abrir. numpy está excluido.
- En macOS el workflow usa `perl -e 'alarm 90; exec @ARGV'` porque no existe `timeout`.

## 9. Probar la interfaz sin mirarla (útil para Claude Code)
Con `xvfb-run` se abre el Estudio en una pantalla virtual y se sacan capturas con
`PIL.ImageGrab.grab(xdisplay=...)`, por ejemplo para comprobar tamaños (2000 × 1100, 1420 × 900,
1100 × 660) o paneles ocultos. La prueba `--probar` ya recorre todas las pantallas y exporta un tema.

## 10. Pendiente / ideas ofrecidas
- **Publicar la 1.0**: primero en privado (borrador), probar en los 3 sistemas, y luego público.
- Ofrecido, sin decidir: selector **«Firmar como: Oficial / Comunidad»** en el modo creador (hoy hay
  que sacar `oficial.npkey` de la carpeta para volver a comunidad).
- Ofrecido, sin decidir: botón en el **Publicador** para publicar también el Estudio.
- **Galería de temas** (opción 2: galería dentro de Numpad Macros, «Enviar a la galería» en el Estudio,
  «Revisar envíos» en el Publicador): hay maqueta aprobada en dirección, falta implementar.
- Confirmar en CachyOS/KDE que ya no quedan zonas a medio dibujar.
