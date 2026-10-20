# Traspaso: app Android de Numpad Macros

Este documento junta **todo lo de la app del celular** para seguir en un chat
aparte. El programa de escritorio sigue en su propio chat. Fecha: 2026-10-20.

## 1. Quién y cómo trabajamos
- Creador: **Jona (OkumaWsX)**, Chile, usa CachyOS. Todo en **español**.
- Cuando pide algo «sencillo»: fácil de entender pero sin omitir lo importante.
- Se diseña primero (mockup) y se programa cuando dice **«manos a la obra»**.
- Repositorio: `OkumaWsX/NumpadMacros` (LGPL-3.0, código abierto).
- Commits terminan con:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` y la línea `Claude-Session` de la sesión.
- **Nunca** crear etiquetas ni Releases desde el chat: se publica solo con el
  robot (Actions → «Publicar versión», o el programa Publicador que usa Jona).
- Antes de entregar algo: `git pull` (el robot guarda la versión y el CHANGELOG en `main`).

## 2. Dónde está la app
| Qué | Dónde |
|---|---|
| Código (Kotlin + Jetpack Compose) | `android/` (14 archivos en `android/app/src/main/java/com/okumawsx/numpadmacros/`) |
| Notas técnicas de la app | `android/LEEME.md` |
| Contrato PC ↔ celular | `docs/PROTOCOLO_CELULAR.md` |
| Temas aprobados (colores) | `docs/temas/temas.json` |
| Compilación | `.github/workflows/android.yml` («Compilar app Android»): en cada push a `android/**`, artefacto `NumpadMacros-Android` |
| Publicación | `publicar.yml` incluye el job `android`: cada Release trae `NumpadMacros-Android-<versión>.apk` |
| Firma | llave de desarrollo `android/app/numpadmacros-dev.jks` (alias `numpadmacros`, clave `numpadmacros-dev`); si existen los secretos `ANDROID_KEYSTORE_B64` / `ANDROID_KEYSTORE_PASS` se usa esa |

- Paquete `com.okumawsx.numpadmacros`, minSdk 26, target 35.
- AGP 8.9.1, Gradle 8.14.3, Kotlin 2.1.20, Compose BOM 2025.04.00, zxing-android-embedded 4.3.0.
- **El APK solo se compila en GitHub Actions** (el entorno del chat no llega a Maven/Google).
  Se revisa con `gh run list --workflow android.yml` y `gh run watch <id> --exit-status`.
  Los artefactos no se pueden descargar desde el chat: Jona los baja de la página de Actions o de la Release.

## 3. Versiones
- **1.0.0**: publicada dentro de la Release **v3.3.1** (19-10-2026).
- **1.1.0** (versionCode 2): en `main`, **sin publicar**; va en la beta 3.4.0.
  Trae: grupo de teclas virtuales primero, elegir cuántas en Ajustes, versión desde BuildConfig.
- Nada se ha probado todavía en un celular real (ni el Bluetooth del PC).

## 4. Lo que ya hace la app
- Conectar por **Wi-Fi, cable USB (anclaje USB) y Bluetooth** (RFCOMM, UUID `8f3c6a52-5e0b-4c6e-9b7b-1d2a9f0e7a12`, canal 22 de respaldo).
- Vincular con **código de 4 números** o **QR** (`nmacros://vincular?...`); después entra solo con HMAC.
- Botonera en 3 diseños (forma real, cuadrícula de 4, grandes de 2) y pantalla completa.
- Bancos, Detener, volumen general, medidor del PC, aviso de reconexión.
- Editar teclas desde el celular: pestañas **Sonido / Atajo / Otro**, escuchar en el PC,
  modo al pulsar, volumen %·dB, color (hoy 6 colores).
- Subir sonidos: elegir archivo o **grabar** (WAV 48 kHz). Lo que el PC no lee (m4a, aac…)
  se convierte a WAV en el celular.
- Ajustes, PCs guardados, Acerca de (Instagram, Discord, GitHub, Donar).

## 5. Diseños APROBADOS que falta programar en la app
Todos están en el lienzo de diseño (https://claude.ai/artifact/JZMYNqgdzLjMFWhNgm3eTL),
páginas «App Android» y «Teclas virtuales (beta)».

1. **Teclas virtuales**
   - Son el primer grupo, en una pestaña o selector propio («Virtuales · Numpad · Fila 1–0»).
   - Son **30 teclas fijas**: 5 columnas × 6 filas en vertical y **6 × 5 en horizontal**.
   - En horizontal (pantalla responsiva), los controles pasan a una **barra lateral izquierda**:
     selector de grupo, bancos, Detener, Editar, pantalla completa, volumen y menú.
   - La pantalla completa en horizontal muestra solo las teclas, con una píldora arriba a la
     derecha (banco, demora, Detener, salir).
   - El numpad en horizontal se ve centrado, ajustado al alto.
2. **Color por botón**
   - **12 colores** más «sin color»: Naranja `#f2a33a`, Amarillo `#e2c340`, Lima `#9bd14a`,
     Verde `#4cc38a`, Turquesa `#3cc7c0`, Celeste `#6aa8ff`, Azul `#4a6cf0`, Morado `#9b7fe0`,
     Rosa `#e06fb8`, Rojo `#e5534b`, Café `#b07a4a` y Gris `#8b909b`.
   - Se eligen en la hoja de edición, en círculos grandes, con el nombre del color elegido.
   - La tecla se pinta con su color.
   - Las teclas **Global** ya no se marcan en morado: llevan una etiqueta **«G»**.
3. **Temas**
   - Son los mismos del PC: Original, Medianoche, Bosque, Vino, Grafito, Synthwave, Océano,
     Claro, Papel, Nórdico y **Atardecer** (nuevo). Se eligen en Ajustes → Apariencia, en
     círculos (fondo + acento).
   - Los colores de cada tema están en `docs/temas/temas.json`.
   - Colores propios del celular, calculados de cada tema:
     - `tecla vacía` = mezcla 55 % de tecla→fondo;
     - `borde de tecla vacía` = mezcla 45 % de línea→fondo;
     - `fondo de Detener` = 82 % de error→panel;
     - `borde de Detener` = 50 % de error→panel;
     - `texto de Detener` = error (temas claros) o error aclarado 50 % con blanco (temas oscuros).
   - Los temas claros (Claro y Papel) usan **texto blanco sobre el acento y sobre «ACTIVO»**
     (`on_ok`).
4. **Opciones aparte en Ajustes → Apariencia** (no son temas de la lista):
   - **Alto contraste**: negro y amarillo.
   - **Pantalla AMOLED / OLED**: negro puro; solo se activa con su interruptor.
   - Solo una a la vez. Mientras alguna está activa, los temas quedan atenuados con el aviso
     «Desactívalo para elegir un tema». Al apagarla vuelve el tema elegido.
   - Estas dos opciones **no** se pasan al PC.
   - Colores en `docs/temas/temas.json` → `solo_celular`.
5. **El tema elegido en el PC se puede pasar al celular** (casilla «Usar también en el celular
   conectado» del PC). Falta definir el mensaje del protocolo (ver punto 7).

Imágenes entregadas a Jona como referencia:
- `celular-00` a `celular-11` (temas con flechas);
- `celular-amoled.png`;
- `ajustes-apariencia.png`;
- el mockup horizontal;
- el mockup de colores.

## 6. Pendiente de Jona
- Publicar la **beta 3.4.0** con el Publicador (zip `NumpadMacros-codigo_3.4.0-beta.zip`,
  casilla «Versión de prueba (beta)»). Incluye el APK 1.1.0.
- Probar en un celular real: Wi-Fi, USB, Bluetooth, vincular, subir y grabar sonidos.

## 7. Cosas que dependen del PC (coordinar con el chat de escritorio)
El **protocolo** (`docs/PROTOCOLO_CELULAR.md`) es el contrato entre los dos chats.
Cualquier cambio se anota ahí y se avisa al otro chat.

- Hoy el PC permite 12/24/36/48 teclas virtuales. El diseño aprobado deja **30 fijas**
  (5 × 6). Hay que cambiarlo en el PC (`npm/keys.py`, `npm/remote.py`) y en la app (quitar
  los chips de cantidad de Ajustes).
- Los 12 colores: el PC hoy acepta `color` 0–5. Hay que ampliarlo a 0–11 (o -1 = sin color)
  en `npm/remote.py` y en la app.
- Para mandar el tema del PC al celular falta un mensaje nuevo, por ejemplo
  `{"t":"tema","nombre":"Océano","colores":{...}}`.
- Los temas `.npt` (archivo cifrado y firmado) son **solo del escritorio** por ahora.

## 8. Mensaje para empezar el chat nuevo
Pega esto en el chat nuevo:

> Este chat es solo para la **app Android de Numpad Macros** (repo OkumaWsX/NumpadMacros,
> carpeta `android/`). Lee primero `docs/TRASPASO_APP_ANDROID.md`, `android/LEEME.md`,
> `docs/PROTOCOLO_CELULAR.md` y `docs/temas/temas.json`: ahí está todo lo decidido y lo
> que falta. El programa de escritorio se trabaja en otro chat; los cambios al protocolo
> se anotan en `docs/PROTOCOLO_CELULAR.md`.
