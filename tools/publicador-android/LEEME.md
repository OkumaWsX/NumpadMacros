# Publicador de Numpad Macros para Android

> Herramienta **solo para el creador** (OkumaWsX). No se publica: no va en las Releases, no sale en las
> novedades del CHANGELOG ni en la app de los usuarios. Sin un token con acceso a este repositorio no sirve de nada.

El mismo Publicador del escritorio (`tools/publicador`), para el teléfono: sirve cuando no tienes el PC a mano.
Hace lo mismo: conecta con GitHub con tu token, revisa la versión nueva (que sea Numpad Macros, que la versión
sea más nueva, que tenga novedades y que no sea una entrega vieja), deja corregir las notas, sube el código,
pone a trabajar al robot «Publicar versión» y muestra cada paso hasta la Release. También crea temas `.npt`
firmados.

- **Instalar:** GitHub → Actions → «Compilar Publicador Android» → la ejecución más reciente → archivo
  `Publicador-Android` (un .zip con el APK adentro).
- **Elegir la versión:** botón «Elegir .zip…», «Elegir carpeta…», o desde Archivos / Drive / Telegram:
  *Compartir* el `NumpadMacros-codigo_X.Y.Z.zip` → Publicador NM.
- **Mientras publica** se ve el avance en una notificación; puedes salir de la app o apagar la pantalla.
- El token y la clave de firma de temas se guardan **cifrados solo en el teléfono** (almacén seguro de Android).

Compilar: `./gradlew assembleRelease` (pruebas: `./gradlew testReleaseUnitTest`).
