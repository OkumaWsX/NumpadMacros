# Historial de cambios

Todas las versiones de Numpad Macros. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [versionado semántico](https://semver.org/lang/es/).

## [Sin publicar]

## [3.3.0] - 2026-10-15
### Añadido
- **Medidores de volumen en tiempo real** para tus audífonos y el micrófono virtual, con aviso cuando satura o cuando actúa el compresor.
- **Igualar volumen**: mide cuánto «suena» cada sonido (LUFS) y los deja a todos al mismo nivel. Objetivo ajustable (−16 LUFS recomendado).
- **Compresor / limitador** con presets Suave, Media, Fuerte y Personalizada: los picos ya no saturan ni se cortan en Discord.
- **Actualizaciones con un clic**: la app avisa cuando hay una versión nueva, muestra sus novedades, la descarga, comprueba que sea la original y se instala sola.
- **Ventana de novedades** de la versión instalada (botón «Novedades» abajo y en la pestaña Creador).
- **Grabar combinaciones** pulsando las teclas, para los atajos y para el modo macros, con aviso si eliges una combinación que ya usan otros programas (Ctrl+C, Alt+F4…).
- Pestaña **Audio**: si falta el micrófono virtual, botón para instalar VB-Cable (Windows) o descargar BlackHole (macOS).

### Cambiado
- El volumen de cada tecla y el volumen general se ven en % y en dB mientras los mueves.
- La biblioteca muestra el volumen medido de cada sonido y cuánto se ajusta.
- Linux: los sonidos pasan por el mismo mezclador que en Windows y macOS (mejor sincronía y medidores).

### Corregido
- Al actualizar, el instalador de Windows ya no vuelve a instalar VB-Cable ni Interception ni pide reiniciar.

## [3.2.1] - 2026-10-09
### Añadido
- Publicación en GitHub con documentación completa, licencia LGPL-3.0 y compilación automática.
- Enlace al repositorio de GitHub en la pestaña **Creador**.
- Los textos de licencia se instalan junto a la app.

### Cambiado
- Las etiquetas de las teclas del numpad se ajustan mejor en teclas angostas.

## [3.2.0] - 2026-10-09
### Añadido
- **Instalador de Windows** (*Siguiente → Siguiente → Instalar*) en español: incluye el driver Interception, descarga VB-Cable desde su sitio oficial, crea accesos directos y desinstalador.
- Pestaña **Creador** con Instagram y Discord de soporte, y botón **Donar**.

## [3.1.0] - 2026-10-09
### Añadido
- **Modo macros de la fila de números**: con `Ctrl+Alt+M` (configurable), las teclas `1–0`, `-` y `=` del teclado principal lanzan sus propias acciones. Sirve cuando no tienes numpad.

## [3.0.0] - 2026-10-09
### Añadido
- **Biblioteca de sonidos propia** (pestaña *Sonidos*): agregar archivos o carpetas, buscar, escuchar y asignar.
- Importar listas de Soundpad (`.spl`).
- Modos de reproducción por tecla: Superponer, Reiniciar, Alternar y Mientras se mantiene.
- App independiente empaquetada (no requiere Python).
- Linux: botón **Dar permisos…** (sin cerrar sesión).
- Windows: si falta el driver Interception, pasa solo al modo sin driver.

### Eliminado
- Dependencia de Soundpad. Las teclas configuradas con Soundpad se convierten solas a sonidos propios.

## [2.0.0] - 2026-10-09
### Añadido
- Soporte para **Linux** (evdev + uinput) y **macOS** (IOKit + Quartz).
- Botonera propia con micrófono virtual (PipeWire en Linux, VB-Cable / BlackHole en Windows y macOS).

## [1.0.0] - 2026-10-09
### Añadido
- Primera versión para Windows: numpad como panel de sonidos de Soundpad y atajos, con bancos.

[3.3.0]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.3.0
[3.2.1]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.2.1
