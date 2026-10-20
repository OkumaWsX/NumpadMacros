# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Lógica del Publicador (sin ventana): revisar una versión, subirla a GitHub
y seguir al robot «Publicar versión».

Usa la API de GitHub con un token personal del creador (se guarda solo en su PC).
"""
import base64
import fnmatch
import hashlib
import json
import os
import re
import shutil
import ssl
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

REPO = "OkumaWsX/NumpadMacros"
APP_ID = "8F3C6A52-5E0B-4C6E-9B7B-1D2A9F0E7A11"      # el mismo de npm/about.py y del instalador
WORKFLOW = "publicar.yml"
BRANCH = "main"
API = os.environ.get("PUBLICADOR_API", "https://api.github.com")
TOKEN_URL = ("https://github.com/settings/personal-access-tokens/new?name=Publicador%20Numpad%20Macros"
             "&description=Publicar%20versiones%20de%20Numpad%20Macros&expires_in=366"
             "&contents=write&actions=write&workflows=write&metadata=read")

# Archivos que nunca se suben (además de lo que diga .gitignore)
NEVER = [".git/*", "*/__pycache__/*", "__pycache__/*", "*.pyc", ".venv/*", "build/*", "dist/*",
         "dist-installer/*", "third_party/*", "interception.dll", "notas.md", "resumen.txt", ".DS_Store",
         "*/.DS_Store", "Thumbs.db", "ENTREGA.txt"]


class PubError(RuntimeError):
    pass


# ============================================================================ configuración
def config_dir():
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif os.uname().sysname == "Darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "NumpadMacros-Publicador")


def load_settings():
    try:
        with open(os.path.join(config_dir(), "config.json"), encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data):
    os.makedirs(config_dir(), exist_ok=True)
    path = os.path.join(config_dir(), "config.json")
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)   # solo tu usuario
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(path + ".tmp", path)


# ============================================================================ GitHub
def _context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


class GitHub:
    def __init__(self, token, repo=REPO, api=None):
        self.token = token.strip()
        self.repo = repo
        self.api = (api or API).rstrip("/")

    def call(self, method, path, body=None, ok=(200, 201, 204), timeout=60):
        url = path if path.startswith("http") else f"{self.api}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "NumpadMacros-Publicador",
            **({"Content-Type": "application/json"} if data is not None else {})})
        try:
            ctx = _context() if url.startswith("https") else None
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                raw = r.read()
                status = r.status
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        except (urllib.error.URLError, OSError) as e:
            raise PubError(f"No pude conectar con GitHub ({e}). ¿Hay internet?")
        if status not in ok:
            try:
                msg = json.loads(raw).get("message", "")
            except ValueError:
                msg = raw[:200].decode("utf-8", "replace")
            raise HTTPFail(status, msg)
        return json.loads(raw) if raw else None

    def r(self, path):
        return f"/repos/{self.repo}{path}"

    # ---- comprobaciones
    def whoami(self):
        return self.call("GET", "/user").get("login", "?")

    def check_access(self):
        """Lanza PubError con una explicación si al token le faltan permisos."""
        try:
            self.call("GET", self.r(""))
        except HTTPFail as e:
            if e.status in (401, 403):
                raise PubError("GitHub no acepta el token (¿lo copiaste completo? ¿venció?).")
            if e.status == 404:
                raise PubError(f"El token no tiene acceso al repositorio {self.repo}. "
                               "Al crearlo, en «Repository access» elige NumpadMacros.")
            raise
        try:
            self.call("GET", self.r(f"/actions/workflows/{WORKFLOW}"))
        except HTTPFail as e:
            if e.status == 404:
                return "falta-robot"          # aún no se ha subido publicar.yml (se sube con la versión)
            if e.status in (401, 403):
                raise PubError("Al token le falta el permiso «Actions: Read and write».")
            raise
        return "ok"

    # ---- versiones publicadas
    def releases(self, n=20):
        return [x for x in self.call("GET", self.r(f"/releases?per_page={n}")) if not x.get("draft")]

    def last_published(self):
        best = None
        for rel in self.releases():
            v = parse_version(rel.get("tag_name", ""))
            if v and (best is None or v > best):
                best = v
        try:
            for tag in self.call("GET", self.r("/tags?per_page=50")):
                v = parse_version(tag.get("name", ""))
                if v and (best is None or v > best):
                    best = v
        except HTTPFail:
            pass
        return best

    def compare(self, base, head=BRANCH):
        """'ahead' si head tiene cambios que base no tiene, 'identical', 'behind' o 'diverged'.
        None si GitHub no conoce base."""
        try:
            return self.call("GET", self.r(f"/compare/{base}...{head}")).get("status")
        except HTTPFail as e:
            if e.status in (404, 422):
                return None
            raise

    # ---- árbol del repositorio
    def head(self):
        ref = self.call("GET", self.r(f"/git/ref/heads/{BRANCH}"))
        commit = ref["object"]["sha"]
        tree = self.call("GET", self.r(f"/git/commits/{commit}"))["tree"]["sha"]
        return commit, tree

    def remote_files(self, tree_sha):
        data = self.call("GET", self.r(f"/git/trees/{tree_sha}?recursive=1"))
        if data.get("truncated"):
            raise PubError("El repositorio es demasiado grande para compararlo.")
        return {e["path"]: (e["sha"], e["mode"]) for e in data["tree"] if e["type"] == "blob"}


class HTTPFail(PubError):
    def __init__(self, status, msg):
        super().__init__(f"GitHub respondió {status}: {msg}")
        self.status = status


# ============================================================================ versión local
def parse_version(text):
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (text or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def vstr(v):
    return ".".join(map(str, v)) if v else "ninguna"


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


class Package:
    """Una versión entregada: un .zip con el código o una carpeta."""

    def __init__(self, path):
        self.source = path
        self.tmp = None
        self.exec_bits = set()
        if os.path.isdir(path):
            base = path
        elif zipfile.is_zipfile(path):
            self.tmp = tempfile.mkdtemp(prefix="publicador-")
            with zipfile.ZipFile(path) as z:
                for info in z.infolist():
                    name = info.filename.replace("\\", "/")
                    if name.startswith("/") or ".." in name.split("/"):
                        raise PubError("El zip trae rutas no válidas.")
                    if (info.external_attr >> 16) & 0o111:
                        self.exec_bits.add(name)
                z.extractall(self.tmp)
            base = self.tmp
        else:
            raise PubError("Arrastra el .zip con el código (NumpadMacros-codigo_X.Y.Z.zip) o su carpeta.")
        self.root = self._find_root(base)
        prefix = os.path.relpath(self.root, base).replace("\\", "/")
        # «-beta» en el nombre del zip o de su carpeta: se sugiere publicar como beta
        names = os.path.basename(os.path.normpath(path)) + "/" + prefix + "/" + os.path.basename(self.root)
        self.beta_hint = "-beta" in names.lower()
        if prefix != ".":
            self.exec_bits = {p[len(prefix) + 1:] for p in self.exec_bits if p.startswith(prefix + "/")}

    @staticmethod
    def _find_root(base):
        for dirpath, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
            if "about.py" in files and os.path.basename(dirpath) == "npm":
                return os.path.dirname(dirpath)
        raise PubError("Este archivo no es Numpad Macros: no encontré su código (npm/about.py).")

    def cleanup(self):
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)

    def read(self, rel):
        with open(os.path.join(self.root, rel), encoding="utf-8") as f:
            return f.read()

    # ---- comprobaciones
    def base_commit(self):
        """Commit del que salió la entrega (ENTREGA.txt), o None."""
        try:
            m = re.search(r"^commit=([0-9a-f]{40})\s*$", self.read("ENTREGA.txt"), re.M)
        except OSError:
            return None
        return m.group(1) if m else None

    def app_id(self):
        m = re.search(r'APP_ID\s*=\s*"([^"]+)"', self.read("npm/about.py"))
        return m.group(1) if m else None

    def installer_id(self):
        try:
            m = re.search(r"AppId=\{\{([0-9A-Fa-f-]+)\}", self.read("installer/NumpadMacros.iss"))
        except OSError:
            return None
        return m.group(1).upper() if m else None

    def is_numpad_macros(self):
        ids = {self.app_id(), self.installer_id()} - {None}
        return bool(ids) and ids == {APP_ID}

    def version(self):
        m = re.search(r'__version__\s*=\s*"([^"]+)"', self.read("npm/__init__.py"))
        return parse_version(m.group(1)) if m else None

    def unreleased(self):
        """Texto de la sección «## [Sin publicar]» del CHANGELOG."""
        text = self.read("CHANGELOG.md")
        m = re.search(r"^## \[Sin publicar\][^\n]*\n", text, re.M | re.I)
        if not m:
            return None
        nxt = re.search(r"^## \[", text[m.end():], re.M)
        return text[m.end():m.end() + (nxt.start() if nxt else len(text))].strip("\n")

    def set_unreleased(self, body):
        path = os.path.join(self.root, "CHANGELOG.md")
        text = self.read("CHANGELOG.md")
        m = re.search(r"^## \[Sin publicar\][^\n]*\n", text, re.M | re.I)
        nxt = re.search(r"^## \[", text[m.end():], re.M)
        end = m.end() + (nxt.start() if nxt else len(text) - m.end())
        new = text[:m.end()] + body.strip("\n") + "\n\n" + text[end:]
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)

    # ---- archivos
    def _ignored(self, rel, patterns):
        for p in NEVER + patterns:
            p = p.rstrip("/")
            if fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel, p + "/*") or \
                    any(fnmatch.fnmatch(part, p) for part in rel.split("/")[:-1]) or \
                    fnmatch.fnmatch(os.path.basename(rel), p):
                return True
        return False

    def files(self):
        """{ruta: (bytes, modo)} de todo lo que se sube."""
        patterns = []
        try:
            for line in self.read(".gitignore").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("!"):
                    patterns.append(line.lstrip("/"))
        except OSError:
            pass
        self.patterns = patterns
        out = {}
        for dirpath, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if d != ".git"]
            for name in files:
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, self.root).replace("\\", "/")
                if self._ignored(rel, patterns):
                    continue
                with open(full, "rb") as f:
                    data = f.read()
                if b"\0" not in data[:8000]:          # texto: GitHub guarda los finales de línea como LF
                    data = data.replace(b"\r\n", b"\n")
                execb = rel in self.exec_bits or (os.name != "nt" and os.access(full, os.X_OK) and self.tmp is None)
                out[rel] = (data, "100755" if execb or rel.endswith(".sh") else "100644")
        return out


# ============================================================================ revisión
class Review:
    """Resultado de revisar un paquete contra lo publicado."""

    def __init__(self):
        self.version = None
        self.published = None
        self.kind = ""
        self.notes = ""
        self.added, self.changed, self.deleted = [], [], []
        self.local = {}
        self.head = self.tree = None
        self.remote = {}


def kind_of(new, old):
    if not old:
        return "Primera versión publicada"
    if new[0] > old[0]:
        return "Versión grande"
    if new[1] > old[1]:
        return "Mejora (funciones nuevas)"
    return "Corrección de errores"


def check_not_stale(pkg: Package, gh: GitHub):
    """Evita subir una entrega más antigua que el código que ya está en GitHub
    (se desharían cambios posteriores)."""
    base = pkg.base_commit()
    if not base:
        if pkg.tmp:                     # un .zip sin ENTREGA.txt es de antes de esta protección
            raise PubError("Este archivo es una entrega antigua (no dice de qué versión del código salió). "
                           "Usa la entrega más reciente que te pasé.")
        return
    status = gh.compare(base)
    if status in ("ahead", "diverged"):
        raise PubError("Este archivo es más antiguo que el código que ya está en GitHub: subirlo desharía "
                       "cambios posteriores. Usa la entrega más reciente (borra las anteriores para no "
                       "confundirlas).")


def compare(pkg: Package, gh: GitHub, rv: Review):
    rv.local = pkg.files()
    rv.head, rv.tree = gh.head()
    rv.remote = gh.remote_files(rv.tree)
    rv.added, rv.changed, rv.deleted = [], [], []
    for path, (data, mode) in rv.local.items():
        hit = rv.remote.get(path)
        if hit is None:
            rv.added.append(path)
        elif hit[0] != git_blob_sha(data) or hit[1] != mode:
            rv.changed.append(path)
    # lo que nunca se sube (ENTREGA.txt, compilados…) tampoco se borra de GitHub
    rv.deleted = sorted(p for p in rv.remote
                        if p not in rv.local and not pkg._ignored(p, getattr(pkg, "patterns", [])))
    rv.added.sort()
    rv.changed.sort()


# ============================================================================ subir
def upload(pkg: Package, gh: GitHub, rv: Review, version, progress=lambda msg: None):
    """Sube el código como un commit en main. Devuelve el sha (o None si no había cambios)."""
    for attempt in range(2):
        compare(pkg, gh, rv)
        todo = rv.added + rv.changed
        if not todo and not rv.deleted:
            return None
        entries = []
        for i, path in enumerate(todo, 1):
            data, mode = rv.local[path]
            progress(f"Subiendo archivos ({i} de {len(todo)})…")
            blob = gh.call("POST", gh.r("/git/blobs"),
                           {"content": base64.b64encode(data).decode(), "encoding": "base64"})
            entries.append({"path": path, "mode": mode, "type": "blob", "sha": blob["sha"]})
        for path in rv.deleted:
            entries.append({"path": path, "mode": rv.remote[path][1], "type": "blob", "sha": None})
        progress("Guardando la versión en GitHub…")
        tree = gh.call("POST", gh.r("/git/trees"), {"base_tree": rv.tree, "tree": entries})
        commit = gh.call("POST", gh.r("/git/commits"), {
            "message": f"Numpad Macros {vstr(version)} (desde el Publicador)",
            "tree": tree["sha"], "parents": [rv.head]})
        try:
            gh.call("PATCH", gh.r(f"/git/refs/heads/{BRANCH}"), {"sha": commit["sha"], "force": False})
            return commit["sha"]
        except HTTPFail as e:
            if e.status == 422 and attempt == 0:      # main cambió mientras tanto: reintentar
                continue
            if e.status in (403, 404) and any(p.startswith(".github/workflows/") for p in todo):
                raise PubError("Al token le falta el permiso «Workflows: Read and write» "
                               "(hace falta para subir los archivos del robot).")
            raise
    raise PubError("No se pudo guardar: el repositorio cambió mientras subía. Vuelve a intentarlo.")


# ============================================================================ robot
def start_robot(gh: GitHub, version, beta, important, discord, wait=lambda s: time.sleep(s)):
    """Inicia «Publicar versión». Devuelve la hora (UTC, ISO) del inicio."""
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 5))
    yes = lambda v: "true" if v else "false"      # noqa: E731  (GitHub recibe los sí/no como texto)
    body = {"ref": BRANCH, "inputs": {"tipo": "automatico", "version": vstr(version),
                                      "beta": yes(beta), "importante": yes(important),
                                      "discord": yes(discord)}}
    for i in range(12):                # recién subido, GitHub tarda unos segundos en ver el robot
        try:
            gh.call("POST", gh.r(f"/actions/workflows/{WORKFLOW}/dispatches"), body)
            return started
        except HTTPFail as e:
            if e.status in (404, 422) and i < 11:
                wait(5)
                continue
            if e.status == 403:
                raise PubError("Al token le falta el permiso «Actions: Read and write».")
            raise
    return started


def find_run(gh: GitHub, since):
    runs = gh.call("GET", gh.r(f"/actions/workflows/{WORKFLOW}/runs?event=workflow_dispatch&per_page=10"))
    for run in runs.get("workflow_runs", []):
        if run.get("created_at", "") >= since:
            return run
    return None


# Pasos que muestra el Publicador -> cómo reconocer el trabajo del robot
STAGES = [("prep", "Revisar la versión y las novedades", ["preparar"]),
          ("win", "Pruebas y compilar Windows (instalador + portátil)", ["windows"]),
          ("lin", "Compilar Linux", ["ubuntu", "linux"]),
          ("mac", "Compilar macOS", ["macos"]),
          ("pub", "Crear la Release + huellas de seguridad", ["publicar"])]


def run_status(gh: GitHub, run_id):
    """{'state': 'running'|'success'|'failure', 'stages': {id: (fracción, estado)}, 'url', 'failed'}"""
    run = gh.call("GET", gh.r(f"/actions/runs/{run_id}"))
    jobs = gh.call("GET", gh.r(f"/actions/runs/{run_id}/jobs?per_page=50")).get("jobs", [])
    stages, failed = {}, None
    discord = None
    for sid, _label, keys in STAGES:
        job = next((j for j in jobs if any(k in j.get("name", "").lower() for k in keys)), None)
        if not job:
            stages[sid] = (0.0, "pending")
            continue
        steps = job.get("steps") or []
        done = sum(1 for s in steps if s.get("status") == "completed")
        frac = done / len(steps) if steps else (1.0 if job.get("status") == "completed" else 0.05)
        concl = job.get("conclusion")
        state = "done" if concl == "success" else ("failed" if concl in ("failure", "cancelled", "timed_out")
                                                   else ("running" if job.get("status") == "in_progress" else "pending"))
        if state == "failed" and failed is None:
            bad = next((s.get("name") for s in steps if s.get("conclusion") == "failure"), "")
            failed = f"{_label}{': ' + bad if bad else ''}"
        stages[sid] = (1.0 if state == "done" else frac, state)
        if sid == "pub":
            d = next((s for s in steps if "discord" in s.get("name", "").lower()), None)
            if d:
                discord = d.get("conclusion")
    concl = run.get("conclusion")
    state = "running" if run.get("status") != "completed" else ("success" if concl == "success" else "failure")
    # Si la Release se creó, la versión está publicada aunque haya fallado solo el anuncio
    pub = next((j for j in jobs if "publicar" in j.get("name", "").lower()), None)
    if state == "failure" and pub and any("release" in (s.get("name") or "").lower() and s.get("conclusion") == "success"
                                          for s in pub.get("steps") or []):
        state = "success"
        stages["pub"] = (1.0, "done")
        failed = None
    return {"state": state, "stages": stages, "url": run.get("html_url", ""), "failed": failed,
            "discord": discord}


def release_assets(gh: GitHub, version):
    rel = gh.call("GET", gh.r(f"/releases/tags/v{vstr(version)}"))
    return rel.get("html_url", ""), [(a["name"], a.get("size", 0)) for a in rel.get("assets", [])]
