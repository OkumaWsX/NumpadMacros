# Protocolo PC ↔ celular (Numpad Macros 3.3.1)

La app Android habla con Numpad Macros del PC usando **un único protocolo**,
igual por los tres caminos:

| Camino     | Cómo llega                                                   |
|------------|--------------------------------------------------------------|
| Wi-Fi      | TCP al puerto **47800** del PC (misma red)                    |
| Cable USB  | El celular activa *Compartir conexión por USB*: se crea una red entre los dos y se usa el mismo TCP 47800 |
| Bluetooth  | RFCOMM (puerto serie). UUID de servicio `8f3c6a52-5e0b-4c6e-9b7b-1d2a9f0e7a12`, canal fijo **22** como respaldo |

## Formato

Cada mensaje es **un objeto JSON en una línea** (UTF-8, termina en `\n`).
Siempre tiene `"t"` (tipo). Máximo 1 MB por línea. Campos desconocidos se ignoran.

## Descubrimiento (Wi-Fi y USB)

1. El celular envía por UDP al puerto **47801**, a la dirección de broadcast de
   cada interfaz de red (wlan, rndis/usb/ncm) y a `255.255.255.255`:
   `{"t":"descubrir","v":1}`
2. El PC (si «Permitir conexiones» está activo) responde por UDP a quien preguntó:
   `{"t":"pc","v":1,"id":"<id del PC>","name":"PC-Jona","port":47800,"app":"3.3.1","os":"linux"}`

El celular usa la IP de origen del paquete como dirección del PC. Si la interfaz
por la que llegó se llama `rndis*`, `usb*` o `ncm*` lo muestra como «Cable USB»;
si no, «Wi-Fi».

Bluetooth no usa descubrimiento: el celular lista los equipos **ya vinculados**
en los ajustes de Bluetooth y prueba a conectarse a cada uno (UUID y, si falla,
canal 22).

## Código QR

El PC muestra un QR con:
`nmacros://vincular?h=192.168.1.20,192.168.42.10&p=47800&c=4821&n=PC-Jona&id=<id del PC>`
(`h` = todas las IP del PC, `c` = código actual). El celular prueba cada IP y
vincula con ese código sin que el usuario escriba nada.

## Vinculación y entrada

```
celular → {"t":"hola","v":1,"dev":"<id del celular>","name":"Pixel 7 de Jona","app":"1.0.0"}
PC      → {"t":"reto","nonce":"<hex 32>","pc":"<id del PC>","name":"PC-Jona","app":"3.3.1","known":true|false}
```

- Si `known` es **true** (el celular ya tiene un token de este PC):
  `celular → {"t":"prueba","mac":"<hex HMAC-SHA256(token, nonce)>"}`
- Si es **false** (primera vez, o el PC lo olvidó):
  `celular → {"t":"codigo","code":"4821"}`
  El PC acepta 5 intentos por conexión; al 5º fallo cambia el código.

Respuestas:
- `{"t":"bienvenido","token":"<hex 64, solo si se vinculó con código>","pc":"…","name":"…"}`
  y a continuación un `estado` y una `biblioteca`.
- `{"t":"rechazado","why":"codigo"|"desactivado"|"olvidado"|"prueba"}` y el PC cierra.

El token nunca viaja otra vez después de la vinculación: en las siguientes
conexiones solo se manda la prueba HMAC del reto (clave = el token como texto
hex en UTF-8, mensaje = el nonce como texto hex en UTF-8, resultado en hex
minúsculas). El PC guarda el token en su configuración, en la carpeta del
usuario.

## Mensajes del celular (después de entrar)

| `t`           | Campos                                          | Qué hace |
|---------------|-------------------------------------------------|----------|
| `tecla`       | `key`, `down` (bool)                            | Igual que apretar/soltar esa tecla del numpad (capa Global y luego banco activo) |
| `banco`       | `i` (índice)                                    | Cambia el banco activo |
| `detener`     | —                                               | Detiene todos los sonidos |
| `volumen`     | `v` (0.0–2.0)                                   | Volumen general |
| `escuchar`    | `lib` (id de la biblioteca)                     | Escucha previa en los audífonos del PC |
| `asignar`     | `layer` (índice de banco o `"global"`), `key`, `act` (acción o `null` para quitar) | Cambia la tecla |
| `subir_ini`   | `name` (nombre de archivo), `size` (bytes), `title` | Empieza a subir un sonido (máx. 50 MB). El PC solo lee **.mp3 .wav .ogg .opus .flac .aiff**: el celular convierte lo demás (m4a, aac, 3gp, amr…) a WAV antes de subirlo, y graba directo en WAV |
| `subir_parte` | `seq`, `data` (base64, ≤ 192 KB decodificados)  | Trozo del archivo |
| `subir_fin`   | `sha256` (hex), opcional `assign` = {`layer`,`key`,`act`} | Termina; el PC lo guarda y lo agrega a la biblioteca |
| `botones`     | `n` (12, 24, 36 o 48)                            | Cuántas teclas virtuales hay por banco |
| `pedir`       | `what`: `"estado"` o `"biblioteca"`             | Pide que se reenvíe |
| `ping`        | `n`                                             | El PC responde `{"t":"pong","n":…}` (para medir la demora) |

### Acciones (`act`)

```
{"type":"file","lib":"<id>","mode":"overlap|restart|toggle|hold","volume":1.0,"color":0}
{"type":"keys","combo":"ctrl+shift+f16"}
{"type":"sound_stop"}
{"type":"bank_next"} / {"type":"bank_prev"} / {"type":"bank_go","bank":2}
```
`color` (0–5) es solo para el celular; el PC lo guarda tal cual.

## Mensajes del PC

**estado** (al entrar y cada vez que algo cambia):
```json
{"t":"estado","active":0,"volume":1.0,
 "banks":[{"name":"Stream","keys":{"47":{"type":"file","title":"Aplausos","mode":"restart","volume":1.0,"lib":"a1b2c3d4e5","color":0}}}],
 "global":{"45":{"type":"bank_next"}},
 "keys":[["45","NumLk",0,0,1,1],["e0:35","/",1,0,1,1], …],
 "groups":[{"id":"celular","name":"Virtuales","cols":4,"rows":6,"keys":[["m1","1",0,0,1,1], …]},
           {"id":"numpad","name":"Numpad","cols":4,"rows":5,"keys":[…]},
           {"id":"fila","name":"Fila 1–0","cols":6,"rows":2,"keys":[["02","1",0,0,1,1], …]},
 "paused":false}
```
`keys` = las teclas del numpad con su posición `[id, etiqueta, col, fila, ancho, alto]`.
`groups` = todos los grupos de teclas que se pueden lanzar y editar desde el celular
(la fila de números solo aparece si está activada en el PC). Una tecla de
cualquier grupo se usa igual en `tecla` y `asignar`.

El grupo `"celular"` («Virtuales», ids `"m1"` … `"m48"`, 4 columnas, siempre el
primero) son las **teclas virtuales**: no corresponden a ninguna tecla física.
(F13–F24 ya no son teclas de entrada desde 3.4.) `estado` trae además
`"phone":{"count":24,"only":false,"counts":[12,24,36,48]}`. Con `only` = true
(modo «Solo celular» del PC, sin teclado) `groups` trae **solo** el grupo `celular`.

**biblioteca**: `{"t":"biblioteca","items":[{"lib":"a1b2c3d4e5","title":"Aplausos","lufs":-12.3}, …]}`
(`lib` = primeros 10 hex de SHA-1 de la ruta normalizada; no cambia mientras el archivo siga ahí.)

**sonando** (hasta 10 veces por segundo mientras suena algo; y uno vacío al terminar):
`{"t":"sonando","keys":{"47":0.64},"level":-14.2}` (avance 0–1 por tecla, nivel en dB)

**subida**: `{"t":"subida","ok":true,"recibido":123456}` (cada trozo) y al final
`{"t":"subida","ok":true,"fin":true,"lib":"…","title":"…"}`, o `{"t":"subida","ok":false,"why":"…"}`.

**aviso**: `{"t":"aviso","text":"…","bad":false}` (mensajes para mostrar).
