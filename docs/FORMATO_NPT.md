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
- `imagenes`: PNG ya preparados por el Estudio. Espacios y tamaño máximo: `banner` 1200×120, `keys` 600×520
  (detrás de las teclas), `logo` 64×64.

## Cómo lo ve Numpad Macros

`npt.unpack(datos)` devuelve `(tema, es_oficial)` con las mismas claves de siempre (`name`, `author`,
`version`, `colors` y `alpha` = `{"window", "idle"}` si el tema usa transparencia). Los temas v2 traen además:

| Clave | Qué es |
|---|---|
| `layer_alpha` | Transparencia por capa (0–100) |
| `images` | Espacio → PNG (`banner`, `keys`, `logo`) |
| `description`, `kind` | Descripción y «oscuro» / «claro» |
| `author_key` | Clave pública del autor (hex): identifica a la persona aunque cambie de nombre |
| `reserved_name` | `True` si usa el nombre del creador oficial sin su firma: mostrar como Comunidad con aviso |

**Nombres repetidos**: dos personas pueden elegir el mismo nombre. Lo que las distingue es `author_key`:
Numpad Macros puede recordar qué clave usó cada nombre y avisar si cambia.

## Pendiente en Numpad Macros

Importar temas v2 ya funciona (colores y transparencia de la ventana). Falta aplicar `layer_alpha` (solo con
el Laboratorio activo), mostrar las imágenes (encabezado, detrás de la tabla de teclas y junto al título) y
el aviso de `reserved_name`. «Exportar» desde Numpad Macros guarda en versión 1 (sin imágenes ni capas).
