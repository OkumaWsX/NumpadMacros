# Arquitectura

Resumen para quien quiera entender o modificar el código.

## Flujo de una pulsación

```
 teclado / numpad ──► captura (capture_*.py) ──► Engine.decide() / Engine.main_key()
                                                   │
                       ┌───────────────────────────┼──────────────────────────┐
                       ▼                           ▼                          ▼
              consumir la tecla           dejarla pasar al sistema     cola de acciones
              (el sistema no la ve)       (o reenviarla en Linux)      (hilo trabajador)
                                                                              │
                                              ┌───────────────────────────────┼────────────┐
                                              ▼                               ▼            ▼
                                     soundboard.py (sonido)        send_*.py (atajo)   bancos
```

- **La captura** corre en su propio hilo y llama a `Engine.decide(id_tecla, presionada)` por cada tecla del numpad, o a `Engine.main_key(...)` por cada tecla del teclado principal (combinación que activa o pausa el modo macros, y fila de números). La combinación no cambia el estado desde ese hilo: deja `("active_toggle",)` en `Engine.events` y la GUI hace lo mismo que el botón ACTIVO / PAUSADO. Estas funciones responden al instante: solo consultan diccionarios.
- **Las acciones lentas** (sonidos, atajos, guardar) se encolan y las ejecuta un hilo trabajador, para no frenar el teclado.
- **La ventana** (`gui.py`, tkinter) lee los eventos del motor desde una cola cada 30 ms.

## Identificadores de tecla

Todas las plataformas traducen sus códigos a un mismo id basado en el *scancode* de PC (`keys.py`):

| Tecla | Id |
|---|---|
| Num 7 | `47` |
| Enter del numpad | `e0:1c` |
| Fila: tecla 1 | `02` |
| Ctrl derecho | `e0:1d` |

Linux convierte con `evdev_kid()` y macOS con `hid_kid()` (numpad) y `MAC_TO_KID` (teclado principal).

## Módulos

| Módulo | Qué hace |
|---|---|
| `engine.py` | Decide qué hacer con cada tecla: capas Global y bancos, bloqueo de teclas sin acción, modo macros, autorrepetición y teclas mantenidas. |
| `keys.py` | Ids de tecla, distribución del numpad y de la fila, tablas de atajos. |
| `config.py` | Carga y guarda `config.json` (escritura atómica) y migra versiones antiguas. |
| `library.py` | Biblioteca de sonidos, importación de listas `.spl` de Soundpad. |
| `soundboard.py` | `MixerBoard` (Windows/macOS: mezclador propio con sounddevice) y `PipeWireBoard` (Linux: crea el micrófono virtual con `pactl`). |
| `capture.py` | Elige el método de captura según el sistema. |
| `capture_win.py` | `InterceptionBackend` (driver, por dispositivo) y `HookBackend` (`WH_KEYBOARD_LL`). |
| `capture_linux.py` | `EvdevBackend`: toma el numpad con `EVIOCGRAB` (solo si está activo); el teclado principal se toma siempre que haya combinación (también en pausa) y todo lo que no se consume (todos los tipos de evento) se reenvía por su propia copia `uinput` (`send_linux.clone`, `UInput.from_device`). Los dispositivos con `EV_REL`/`EV_ABS` (puntero) y los que no admiten copia solo se leen. Al cerrar o desconectar se sueltan las teclas apretadas en el motor y en la copia. |
| `capture_mac.py` | `IOKitBackend`: numpad con `IOHIDManager` en modo *seize* y teclado principal con `CGEventTap`. |
| `send_*.py` | Envío de atajos: `SendInput`, `uinput` o eventos Quartz. |
| `linux_perms.py` | Regla udev (`uaccess`) y botón «Dar permisos…» con `pkexec`. |
| `sysutil.py` | Una sola instancia, inicio con el sistema, abrir enlaces. |
| `gui.py` | Ventana principal. |

## Decisiones de diseño

- **Nada queda "pegado":** si se pausa la app o se cambia de banco con una tecla apretada, su soltar se procesa por el mismo camino que su presión (`_pressed` / `_passed` en `Engine`).
- **Linux, teclado principal:** se toma o se suelta solo cuando no tiene teclas apretadas, para que el sistema nunca reciba un "soltar" de una tecla que no vio presionar.
- **Windows sin driver:** si Interception no está instalado, la app usa el hook de teclado sola.
- **Sin dependencias en el núcleo:** `engine.py`, `keys.py` y `config.py` usan solo la biblioteca estándar, así las pruebas corren en cualquier sistema.

## Pruebas

`tests/` simula numpads, teclados, PipeWire y el mezclador de audio, así que no hace falta hardware:

```bash
python -m unittest discover -s tests -v
```

## Compilación y publicación

- `NumpadMacros.spec` empaqueta con PyInstaller (carpeta en Windows, binario único en Linux, `.app` en macOS).
- `installer/NumpadMacros.iss` crea el instalador de Windows con Inno Setup.
- `.github/workflows/build.yml` corre las pruebas y compila en Windows, Linux y macOS. Al subir una etiqueta `vX.Y.Z` publica una Release con los archivos.
