# Reportes de errores

Cómo Numpad Macros avisa al creador cuando algo falla, y qué tiene que hacer el bot que los recibe
(Centinela).

```
Numpad Macros ──HTTPS──▶ bot Centinela (revisa, limita, agrupa) ──▶ canal privado de Discord
```

La app **nunca** lleva la dirección del canal ni un token de Discord: solo conoce la dirección del bot
(`ENDPOINT` en `npm/reportes.py`). Como el código es abierto, cualquiera puede ver esa dirección; por eso
el bot es quien filtra el spam (prueba de trabajo, límites y agrupación), no la app.

## En la app

- **Registro local**: `registro.log` en la carpeta de configuración (`~/.config/NumpadMacros`,
  `%APPDATA%\NumpadMacros`, `~/Library/Application Support/NumpadMacros`). Se recorta solo (2 × 300 KB).
  Botón «Abrir el registro» en *Numpad y opciones → Reportes de errores*.
- **Qué se captura**: errores sin atrapar del programa, de la ventana (Tk), de los hilos y de los
  eventos del numpad/celular. Además, «Informar un problema…» (en *Numpad y opciones* y en
  *Creador y soporte*) manda un reporte escrito por el usuario aunque no haya un error.
- **Permiso** (`cfg["reportes"]["modo"]`): `preguntar` (por defecto: al primer error de la sesión
  aparece «Algo falló…» con *Enviar siempre*, *Solo esta vez*, *No enviar* y «Ver qué se envía»),
  `siempre` (se envía solo y avisa con un mensaje breve) o `nunca`.
- **Agrupación local**: el mismo error (misma huella) en la misma versión se envía como mucho una vez al
  día por equipo.
- **Cola**: sin internet o con el bot caído, el reporte queda en `reportes/cola/` (máx. 20) y se
  reintenta al abrir la app y cada 30 minutos. Si `ENDPOINT` está vacío, todo queda en cola hasta que una
  versión traiga la dirección.

### Datos personales

Antes de enviar, `reportes.clean()`:
- reemplaza la carpeta personal por `~` y el nombre de usuario por `<usuario>`;
- reemplaza el nombre de los archivos del usuario por `archivo.<extensión>` (sonidos, imágenes,
  temas, documentos…); las rutas del propio programa (`npm/gui.py`) quedan;
- nunca incluye la configuración, la biblioteca de sonidos, los códigos del celular ni nombres de
  sonidos o bancos.

`instalacion` es un número al azar de la instalación (no identifica a la persona): sirve para contar en
cuántos equipos pasa un error y para que el bot limite los envíos.

## Lo que recibe el bot

`POST <ENDPOINT>` con `Content-Type: application/json` (máx. 60 000 bytes) y las cabeceras:

| Cabecera | Qué es |
|---|---|
| `X-NM-Version` | versión de la app (`3.5.2`) |
| `X-NM-Prueba` | prueba de trabajo: número tal que `sha256(cuerpo_crudo + número)` < 2^(256−18) |
| `User-Agent` | `NumpadMacros/<versión>` |

Cuerpo (JSON):

```json
{
  "app": "NumpadMacros",
  "version": "3.5.2",
  "tipo": "error",                    // "error" o "manual"
  "fecha": "2026-10-28T00:40:12-0300",
  "sistema": "CachyOS · kernel 6.17 · KDE (wayland)",
  "python": "3.12.9",
  "empaquetada": true,
  "instalacion": "32 hex",
  "huella": "12 hex",                 // mismo error = misma huella (en manual: "manual-xxxxxx")
  "error": "KeyError: 'colors'",      // solo en "error"
  "donde": "npm/gui.py:3812 en apply_theme_live",
  "traza": "Traceback …",             // hasta 12 000 caracteres
  "hilo": "ventana",                  // principal, ventana, eventos, hilo <nombre>
  "descripcion": "texto del usuario", // solo en "manual" (hasta 3 000)
  "contacto": "usuario de Discord",   // opcional
  "contexto": {"tema": "Original", "vista": "virt", "pestaña": "Tecla", "captura": "evdev",
               "numpad_elegido": true, "solo_celular": false, "activo": true, "bancos": 3,
               "sonidos": 24, "ventana": "1366×768 (pantalla 1920×1080)", "celulares": 1, "betas": false},
  "pasos": ["00:39:58 pestaña «Temas»", "00:40:10 cambió el tema a «Claro»"],
  "registro": "últimas líneas de registro.log"
}
```

Respuestas que entiende la app:

| Código | La app… |
|---|---|
| `2xx` | lo da por enviado y lo borra de la cola |
| `400`, `403`, `410`, `413`, `422` | lo descarta (formato, prueba o versión rechazados): no insiste |
| `429` o `5xx` / sin respuesta | lo deja en cola y reintenta más tarde |

## Lo que hace el bot (Centinela)

1. **Revisa** antes de leer el contenido: tamaño ≤ 60 000; prueba de trabajo válida (18 bits);
   JSON válido; `app == "NumpadMacros"`; `version` con forma `X.Y.Z`; `tipo` ∈ {error, manual};
   `instalacion` = 32 hex. Si algo falla → `400/403/422`.
2. **Limita** (si se pasa → `429`): por IP 10 por hora; por `instalacion` 5 por hora y 20 por día
   (manuales: 3 por día); en total 200 por hora. Varias instalaciones nuevas desde la misma IP en poco
   tiempo cuentan como una.
3. **Agrupa** por `version` + `huella`: la primera vez crea un mensaje (o un hilo de foro) en el canal
   privado; las siguientes solo actualizan el contador («visto N veces en M equipos») y agregan las
   descripciones nuevas de los reportes manuales.
4. **Publica sin riesgos**: `allowed_mentions` vacío (nadie es mencionado), el texto del usuario va
   escapado (sin enlaces activos ni @everyone) y el reporte completo va como archivo `reporte.txt`.
   Mensaje sugerido: título `🐞 3.5.2 · KeyError: 'colors'`; campos *Dónde*, *Sistema*, *Estado*,
   *Últimos pasos*, *Veces / equipos*; para los manuales, `📝 Problema informado` y la descripción.
5. **Guarda** los reportes 90 días; botón (solo para el creador) «Marcar arreglado en X.Y.Z» que etiqueta
   el grupo y hace que un reporte nuevo con esa huella en una versión igual o posterior aparezca como
   «volvió a pasar».
6. **Privacidad**: la IP solo se usa para los límites (no se guarda con el reporte); borrar los datos
   de una `instalacion` si alguien lo pide.
