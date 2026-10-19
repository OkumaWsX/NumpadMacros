# Numpad Macros para Android

App del celular para lanzar los sonidos y atajos de Numpad Macros del PC por
Wi-Fi, cable USB (compartir conexión por USB) o Bluetooth. Kotlin + Jetpack Compose.

- Protocolo: `docs/PROTOCOLO_CELULAR.md`.
- Prueba de vinculación (HMAC): `HMAC-SHA256(clave = token como texto hex en UTF-8,
  mensaje = nonce como texto hex en UTF-8)`, resultado en hex minúsculas.
- Compilación: GitHub Actions → «Compilar app Android» (`.github/workflows/android.yml`).
  El APK queda en los artefactos de la ejecución (`NumpadMacros-Android`).
- Compilar en tu PC: instala Android Studio (o el SDK + JDK 17) y ejecuta
  `./gradlew assembleRelease` dentro de `android/`.

## Firma

Si el repositorio tiene los secretos `ANDROID_KEYSTORE_B64` (la llave .jks en base64)
y `ANDROID_KEYSTORE_PASS` (y opcionalmente `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASS`),
el APK se firma con esa llave. Si no, con la llave de desarrollo incluida
(`app/numpadmacros-dev.jks`, contraseña `numpadmacros-dev`): sirve para probar y para
que cada APK nuevo se instale encima del anterior, pero no es secreta. Antes de
publicar en Google Play conviene crear una llave propia y guardarla en los secretos
(ojo: un APK firmado con otra llave no se instala encima; hay que desinstalar el anterior).

## Notas de comportamiento

- Grabaciones: WAV 48 kHz mono 16 bits. Archivos que el PC no abre (m4a, aac, amr…)
  se convierten a WAV en el celular antes de enviarlos.
- Si el PC dice `known: true` pero el celular perdió su token (por ejemplo tras
  reinstalar), el celular pide el código y responde con `codigo`.
- `subir_fin.assign.act` lleva `lib: ""`: el PC debe completar el id del archivo recién subido.
