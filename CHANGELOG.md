# Historial de cambios

Todas las versiones de Numpad Macros. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [versionado semántico](https://semver.org/lang/es/).

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

[3.2.1]: https://github.com/OkumaWsX/NumpadMacros/releases/tag/v3.2.1
