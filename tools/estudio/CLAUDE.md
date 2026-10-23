# Estudio de Temas: indicaciones para Claude Code

**En esta copia se trabaja solo con el Estudio de Temas (el editor de temas).** Numpad Macros, la app
Android y el Publicador tienen sus propios chats: no los modifiques aquí.

- Puedes cambiar: `tools/estudio/**`, `tests/test_estudio.py`, `.github/workflows/estudio.yml`,
  `.github/workflows/publicar-estudio.yml`, `docs/TRASPASO_ESTUDIO.md`, `assets/icon-estudio.*`,
  `installer/EstudioTemas.iss` y la sección del Estudio en `README.md`.
- Compartidos (solo si el Estudio de verdad lo necesita, y avisándole a Jona porque afecta a Numpad
  Macros): `npm/npt.py`, `docs/FORMATO_NPT.md`, `tests/test_npt*.py`.
- Todo lo demás (`npm/` salvo `npt.py`, `android/`, `tools/publicador*/`, `CHANGELOG.md` de la raíz,
  `publicar.yml`…) es de solo lectura: se puede leer para entender, no se edita.
- Los comandos de pruebas se corren desde la raíz del repositorio (`../..` si abriste Claude Code en
  esta carpeta).

Antes de trabajar aquí, lee `docs/TRASPASO_ESTUDIO.md`: cómo trabajamos, comandos, dónde está cada
cosa, publicación y trampas conocidas. Lo más importante:

- Todo en español. El Estudio es un proyecto aparte de Numpad Macros, con su propia versión
  (`VERSION` en `estudio.py`) y su propio historial (`CHANGELOG.md` de esta carpeta, en «Sin publicar»).
  No lo menciones en el `CHANGELOG.md` de la raíz.
- `git pull --rebase` antes de empezar y antes de subir: otros chats y los robots suben a `main`.
- Nunca crees etiquetas ni Releases a mano: se publica con Actions → «Publicar Estudio de Temas».
- La clave oficial (`*.key`, `*.npkey`) nunca va al repositorio.
- `npm/npt.py` y `docs/FORMATO_NPT.md` son compartidos con Numpad Macros; lo que dibuja `vista.py`
  tiene que verse igual que en `npm/theme_art.py`.
- Antes de subir: `python -m unittest discover -s tests` y `python tools/estudio/estudio.py --probar`.
