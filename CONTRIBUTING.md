# Cómo contribuir

¡Gracias por querer mejorar Numpad Macros! Toda ayuda suma: reportar errores, proponer ideas, mejorar la documentación o enviar código.

## Reportar un error o pedir una función

1. Revisa que no exista ya en [Issues](https://github.com/OkumaWsX/NumpadMacros/issues).
2. Abre un issue con la plantilla que corresponda (*Reporte de error* o *Idea / mejora*).
3. Para errores incluye: sistema operativo, versión de la app (pestaña **Creador**), modelo de numpad y el mensaje que aparece abajo en la ventana.

¿Duda rápida? Pregunta en el [servidor de Discord](https://discord.gg/hcutJcBx9).

## Preparar el entorno

```bash
git clone https://github.com/OkumaWsX/NumpadMacros.git
cd NumpadMacros
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python NumpadMacros.pyw
```

- **Linux:** instala `tk` y `python-evdev` (o `python3-tk` y `python3-evdev` en Debian/Ubuntu) y da permisos con `./permisos_linux.sh`.
- **macOS:** usa Python de python.org (incluye tkinter) y da permisos de *Monitoreo de entrada* y *Accesibilidad* a tu terminal.

## Pruebas

Antes de enviar cambios, corre las pruebas:

```bash
python -m unittest discover -s tests -v
```

Las pruebas simulan los dispositivos, así que funcionan sin un numpad conectado. Si agregas una función, agrega también su prueba.

## Estilo del código

- Python 3.10+ y solo la biblioteca estándar en el núcleo (`engine.py`, `keys.py`, `config.py`); las dependencias externas van en los módulos de cada sistema.
- Textos de la interfaz y comentarios en **español**.
- Cada archivo nuevo lleva la cabecera de licencia:
  ```python
  # SPDX-License-Identifier: LGPL-3.0-or-later
  # Copyright (C) 2026 OkumaWsX
  ```
- Mantén el código de cada sistema operativo en su propio módulo (`capture_win.py`, `capture_linux.py`, `capture_mac.py`, etc.).

## Enviar un pull request

1. Haz un *fork* y crea una rama: `git checkout -b mi-mejora`.
2. Haz commits pequeños con mensajes claros.
3. Verifica que las pruebas pasen.
4. Abre el pull request explicando qué cambia y cómo lo probaste.

Al contribuir aceptas que tu código se publique bajo la licencia del proyecto ([LGPL-3.0-or-later](LICENSE)).
