# Capturas por versión

Cada carpeta (`3.3.0/`, …) guarda las capturas tomadas con **esa** versión de la app.

- Al publicar la versión X.Y.Z, si existe `docs/capturas/X.Y.Z/`, el robot agrega sus capturas a las notas
  de la Release con enlaces fijos a esa versión: aunque el README cambie después, la Release sigue
  mostrando cómo era la app en esa versión.
- `capturas.txt` dice qué capturas van en la Release y con qué descripción (`archivo | descripción`).
- Para agregar capturas a una versión ya publicada: Actions → «Capturas en una Release» → Run workflow.
- Las versiones sin cambios visibles (por ejemplo, correcciones) no necesitan carpeta.
