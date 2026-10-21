# Formato de temas `.npt` (NumPad Theme)

El código está en `npm/npt.py` y lo comparten Numpad Macros, el Publicador y el Estudio de Temas.
Numpad Macros lee las dos versiones del formato.

| Versión | La crean | Firma | Qué trae |
|---|---|---|---|
| 1 | Numpad Macros («Exportar»), el Publicador y `tools/crear_tema.py` | Opcional, solo la oficial | 14+ colores y transparencia de la ventana |
| 2 | Estudio de Temas | Siempre: oficial o firma de autor | 22 colores, transparencia por capa, ventana e imágenes |

## Versión 1

`"NPT"` + `1` + opciones (bit 0 = firmado) + nonce (12) + largo (4) + contenido cifrado (AES-256-GCM) +
firma Ed25519 de `OFFICIAL_KEY` (64, si va firmado). El contenido es el JSON del tema (`name`, `author`,
`version`, `colors`, `alpha`) comprimido.

## Versión 2

| Parte | Tamaño | Qué es |
|---|---|---|
| Encabezado | 5 bytes | `NPT` + `2` + opciones (0) |
| Clave del autor | 32 bytes | Clave pública Ed25519 de quien firmó |
| Nonce | 12 bytes | Aleatorio en cada archivo |
| Contenido | variable | Cifrado con AES-256-GCM (incluye su sello de 16 bytes) |
| Firma | 64 bytes | Ed25519 de todo lo anterior, con la clave del autor |

- **Firma**: si cambia un solo byte, el archivo se rechaza. Si la clave del autor es `OFFICIAL_KEY` el tema
  es oficial; si no, es de la comunidad, y la clave identifica siempre a la misma persona.
- **Cifrado**: solo impide leerlo o editarlo con un editor de texto. Como el código es abierto, la clave de
  contenido no es secreta; lo que nadie puede falsificar es la firma.
- **Contenido**: `NPTC` + largo del JSON (4 bytes) + JSON + imágenes, comprimido con zlib.
- **Peso máximo**: 5 MB por tema (las dos versiones).

### JSON del contenido

```json
{
  "formato": 2, "nombre": "Neón Tokio", "autor": "@kaori", "version": "1.0",
  "descripcion": "…", "tipo": "oscuro", "creado": "2026-10-20",
  "colores": {"bg": "#14161b", "panel": "#1c1f26", "…": "las 22 capas"},
  "alfa": {"panel": 85, "key": 80},
  "ventana": {"opacidad": 92, "sin_usar": 75},
  "admite_transparencia": true,
  "imagenes": {"banner": {"inicio": 0, "largo": 48211, "formato": "png"}}
}
```

- `colores`: las 22 capas (`npt.TOKENS`), en `#rrggbb`.
- `alfa`: transparencia de cada capa, 0–100 (las que faltan son 100). Cada capa se mezcla con la de abajo
  (`npt.PARENT`). El fondo (`bg`) no tiene: usa la opacidad de la ventana.
- `ventana`: opacidad de la ventana en uso y cuando el mouse sale, 50–100 (igual que el Laboratorio).
- `imagenes`: imágenes ya preparadas por el Estudio (recortadas, oscurecidas y desenfocadas), en
  9 espacios. PNG en todos; **GIF animado** solo en los espacios libres marcados con ★:

  | Espacio | Dónde va | Máximo |
  |---|---|---|
  | `banner` | Encabezado completo, detrás del título | 1200 × 120 |
  | `keys` | Detrás de la tabla de teclas | 600 × 520 |
  | `corner` | Pestaña · parte de abajo, detrás de los botones | 600 × 200 |
  | `footband` | Pie · banda completa, detrás de Novedades / Soporte / Donar | 1200 × 40 |
  | `logo` | Junto al título | 64 × 64 |
  | `headmid` ★ | Encabezado · espacio central | 360 × 48 |
  | `tabsend` ★ | Pestañas · espacio al final | 240 × 28 |
  | `leftbot` ★ | Panel de teclas · espacio de abajo | 360 × 160 |
  | `foot` ★ | Pie · espacio libre | 420 × 28 |

- `fondo` (opcional): fondo de toda la ventana. Sin la clave = color sólido (`colores.bg`).
  ```json
  "fondo": {"tipo": "degradado", "colores": [["#14161b", 0], ["#3a2c14", 55], ["#33294a", 100]], "desde": "c"}
  ```
  De 2 a 5 colores, cada uno con su posición 0–100. `desde` = dónde empieza: `tl` `t` `tr` `l` `c` `r` `bl`
  `b` `br` (4 esquinas, 4 lados y el centro). Termina en el lado opuesto; desde `c` es circular.
- `secciones` (opcional): transparencia propia de cada sección de la ventana.
  ```json
  "secciones": {"head": {"fondo": 70, "contenido": 100, "realce": true}, "foot": {"fondo": 60}}
  ```
  Secciones: `head` (encabezado), `left` (panel izquierdo), `keys` (tabla de teclas), `tabs` (pestañas),
  `body` (contenido de la pestaña) y `foot` (pie). `fondo` y `contenido` van de 0 a 100 (falta = 100);
  `realce` = borde de realce.

### Compatibilidad hacia adelante (para el Estudio y las próximas versiones)

- Estas claves son **del formato 2**: el byte de versión sigue siendo `2`. Subirlo a `3` hace que las
  versiones anteriores de Numpad Macros rechacen el tema con «actualiza el programa»; solo se hace si
  algo antiguo dejaría de verse bien.
- Al **leer**, Numpad Macros (desde 3.4.1) **ignora** lo que no conoce: espacios de imagen nuevos,
  secciones nuevas, tipos de `fondo` nuevos y claves nuevas del JSON. Lo que sí conoce tiene que estar
  bien, si no el tema se rechaza como dañado. Así un Estudio más nuevo puede agregar zonas sin romper
  los programas que ya tiene la gente.
- Al **escribir**, el Estudio valida todo de forma estricta (`npt.validate(tema)`).

## Cómo lo ve Numpad Macros

`npt.unpack(datos)` devuelve `(tema, es_oficial)` con las mismas claves de siempre (`name`, `author`,
`version`, `colors` y `alpha` = `{"window", "idle"}` si el tema usa transparencia). Los temas v2 traen además:

| Clave | Qué es |
|---|---|
| `layer_alpha` | Transparencia por capa (0–100) |
| `images` | Espacio → PNG o GIF (los 9 espacios de arriba) |
| `background` | El `fondo` (degradado) o `{}` |
| `sections` | Las `secciones` o `{}` |
| `description`, `kind` | Descripción y «oscuro» / «claro» |
| `author_key` | Clave pública del autor (hex): identifica a la persona aunque cambie de nombre |
| `reserved_name` | `True` si usa el nombre del creador oficial sin su firma: mostrar como Comunidad con aviso |

**Nombres repetidos**: dos personas pueden elegir el mismo nombre. Lo que las distingue es `author_key`:
Numpad Macros puede recordar qué clave usó cada nombre y avisar si cambia.

## Cómo se dibuja en Numpad Macros (desde 3.4.1)

Código: `npm/theme_art.py` (y el encabezado y el pie en `npm/gui.py`).

| Zona | Cómo se ve |
|---|---|
| `fondo` degradado | Detrás de toda la ventana: bordes, espacios entre paneles, encabezado y pie. Lo que se pinta con color sólido (barra de pestañas, campos) usa el **promedio** del degradado. |
| `banner`, `logo`, `headmid` | El encabezado es un lienzo: el banner lo cubre entero, el logo va antes del título y `headmid` entre el título y los medidores (si no cabe, se oculta). |
| `keys` | Detrás de la tabla de teclas (numpad o virtuales). Las teclas dejan ver la imagen según `secciones.keys.contenido`; las vacías siempre un poco. |
| `leftbot` | Abajo del panel de teclas. |
| `tabsend` | A la derecha de la última pestaña, si hay espacio. |
| `corner` | Al fondo de la pestaña Tecla, detrás del contenido (se ve en el espacio libre de abajo). |
| `footband`, `foot` | El pie también es un lienzo: la banda lo cubre entero y `foot` va a la izquierda de los botones. |
| `secciones` | `head`, `foot` y `keys`: plancha del color del panel con su opacidad sobre el fondo, y el texto según `contenido`. `left`, `body` y `tabs`: su color se mezcla con el de debajo (Tk no tiene transparencia real en los paneles). `realce`: borde del color de acento. |
| GIF | Se animan y se **pausan** cuando el mouse sale de la ventana (como «cuando no usas la ventana» en el Estudio) o la ventana está oculta. |

## Pendiente en Numpad Macros

El aviso de `reserved_name`, y `contenido` de las secciones `left`, `body` y `tabs` (sus textos no se
atenúan). «Exportar» desde Numpad Macros guarda en versión 1 (sin imágenes ni capas).
