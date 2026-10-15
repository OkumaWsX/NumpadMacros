# SPDX-License-Identifier: LGPL-3.0-or-later
"""Pruebas del Publicador contra un GitHub falso (sin internet)."""
import base64
import hashlib
import http.server
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import unittest
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools", "publicador"))
import nucleo as core  # noqa: E402


def sha(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


class FakeGitHub:
    """Lo mínimo de la API de GitHub que usa el Publicador."""

    def __init__(self, files):
        self.blobs = {}
        self.trees = {}
        self.commits = {}
        self.dispatches = []
        self.releases = [{"tag_name": "v3.2.1", "draft": False, "prerelease": False, "html_url": "u",
                          "published_at": "2026-10-09T00:00:00Z", "assets": []}]
        tree = {}
        for p, d in files.items():
            self.blobs[sha(d)] = d
            tree[p] = (sha(d), "100644")
        self.trees["t0"] = tree
        self.commits["c0"] = "t0"
        self.head = "c0"
        self.n = 0
        self.compare_status = {}

    def handle(self, method, path, body):
        p = path.split("/repos/OkumaWsX/NumpadMacros", 1)[-1]
        if path == "/user":
            return 200, {"login": "OkumaWsX"}
        if method == "GET" and p.startswith("/releases?"):
            return 200, self.releases
        if method == "GET" and p.startswith("/tags"):
            return 200, [{"name": "v3.2.1"}]
        if p == "/git/ref/heads/main":
            return 200, {"object": {"sha": self.head}}
        m = re.match(r"/git/commits/(\w+)$", p)
        if m and method == "GET":
            return 200, {"tree": {"sha": self.commits[m.group(1)]}}
        m = re.match(r"/git/trees/(\w+)", p)
        if m and method == "GET":
            t = self.trees[m.group(1)]
            return 200, {"truncated": False, "tree": [{"path": k, "sha": v[0], "mode": v[1], "type": "blob"}
                                                      for k, v in t.items()]}
        if p == "/git/blobs":
            d = base64.b64decode(body["content"])
            self.blobs[sha(d)] = d
            return 201, {"sha": sha(d)}
        if p == "/git/trees":
            t = dict(self.trees[body["base_tree"]])
            for e in body["tree"]:
                if e["sha"] is None:
                    t.pop(e["path"], None)
                else:
                    t[e["path"]] = (e["sha"], e["mode"])
            self.n += 1
            self.trees[f"t{self.n}"] = t
            return 201, {"sha": f"t{self.n}"}
        if p == "/git/commits":
            self.n += 1
            assert body["parents"] == [self.head]
            self.commits[f"c{self.n}"] = body["tree"]
            return 201, {"sha": f"c{self.n}"}
        if p == "/git/refs/heads/main" and method == "PATCH":
            self.head = body["sha"]
            return 200, {}
        m = re.match(r"/compare/(\w+)\.\.\.main$", p)
        if m:
            return 200, {"status": self.compare_status.get(m.group(1), "identical")}
        if p.endswith("/dispatches"):
            self.dispatches.append(body)
            return 204, None
        if "/runs?" in p:
            return 200, {"workflow_runs": [{"id": 7, "created_at": "2099-01-01T00:00:00Z"}]}
        if p == "/actions/runs/7":
            return 200, {"status": "completed", "conclusion": "success", "html_url": "run"}
        if p.startswith("/actions/runs/7/jobs"):
            ok = {"status": "completed", "conclusion": "success"}
            return 200, {"jobs": [
                dict(ok, name="Preparar", steps=[dict(ok, name="x")]),
                dict(ok, name="Compilar / build (windows-latest, NumpadMacros-Windows)", steps=[dict(ok, name="x")]),
                dict(ok, name="Compilar / build (ubuntu-22.04, NumpadMacros-Linux)", steps=[dict(ok, name="x")]),
                dict(ok, name="Compilar / build (macos-14, NumpadMacros-macOS)", steps=[dict(ok, name="x")]),
                dict(ok, name="Publicar", steps=[dict(ok, name="Anunciar en Discord")])]}
        return 404, {"message": "Not Found"}

    def tree_files(self):
        return {k: self.blobs[v[0]] for k, v in self.trees[self.commits[self.head]].items()}


class PublicadorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # paquete: copia del proyecto real como zip, con versión 3.3.0 y novedades
        self.zip = os.path.join(self.tmp, "NumpadMacros-codigo_3.3.0.zip")
        with zipfile.ZipFile(self.zip, "w") as z:
            for rel in ("npm/__init__.py", "npm/about.py", "installer/NumpadMacros.iss",
                        "README.md", "compilar.sh", ".gitignore"):
                z.write(os.path.join(HERE, rel), "NumpadMacros/" + rel)
            # CHANGELOG propio: el real puede tener «Sin publicar» vacío (justo después de publicar)
            z.writestr("NumpadMacros/CHANGELOG.md", "# Historial\n\n## [Sin publicar]\n### Añadido\n"
                       "- Algo nuevo\n\n## [3.2.1] - 2026-10-09\n### Añadido\n- Antes\n")
            z.writestr("NumpadMacros/npm/__pycache__/x.pyc", b"basura")
            z.writestr("NumpadMacros/crear_instalador.bat", b"@echo off\r\nrem prueba\r\n")
        with open(os.path.join(HERE, "npm/about.py"), "rb") as f:
            about = f.read()
        remote = {"README.md": b"viejo", "npm/about.py": about,
                  "descargas/NumpadMacros-Windows-Setup.exe": b"exe"}
        self.fake = FakeGitHub(remote)
        fake = self.fake

        class H(http.server.BaseHTTPRequestHandler):
            def _do(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n)) if n else None
                assert self.headers["Authorization"] == "Bearer tok"
                code, data = fake.handle(self.command, self.path, body)
                raw = json.dumps(data).encode() if data is not None else b""
                self.send_response(code)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            do_GET = do_POST = do_PATCH = _do

            def log_message(self, *a):
                pass
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.gh = core.GitHub("tok", api=f"http://127.0.0.1:{self.srv.server_address[1]}")

    def tearDown(self):
        self.srv.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_full_flow(self):
        pkg = core.Package(self.zip)
        self.assertTrue(pkg.is_numpad_macros())
        self.assertEqual(pkg.version(), tuple(int(x) for x in __import__("npm").__version__.split(".")))
        self.assertIn("- ", pkg.unreleased())
        self.assertEqual(self.gh.last_published(), (3, 2, 1))
        rv = core.Review()
        core.compare(pkg, self.gh, rv)
        self.assertIn("README.md", rv.changed)
        self.assertIn("CHANGELOG.md", rv.added)
        self.assertNotIn("npm/about.py", rv.changed + rv.added)          # igual que el publicado
        self.assertIn("descargas/NumpadMacros-Windows-Setup.exe", rv.deleted)
        self.assertFalse(any("__pycache__" in p for p in rv.added))
        pkg.set_unreleased("### Añadido\n- Nota corregida a mano")
        commit = core.upload(pkg, self.gh, rv, (3, 3, 0))
        self.assertTrue(commit)
        files = self.fake.tree_files()
        self.assertIn(b"Nota corregida a mano", files["CHANGELOG.md"])
        self.assertNotIn("descargas/NumpadMacros-Windows-Setup.exe", files)
        self.assertEqual(files["crear_instalador.bat"], b"@echo off\nrem prueba\n")   # CRLF -> LF
        mode = self.fake.trees[self.fake.commits[self.fake.head]]["compilar.sh"][1]
        self.assertEqual(mode, "100755")
        # sin cambios: no crea otro commit
        self.assertIsNone(core.upload(pkg, self.gh, core.Review(), (3, 3, 0)))
        since = core.start_robot(self.gh, (3, 3, 0), False, True, True, wait=lambda s: None)
        d = self.fake.dispatches[-1]
        self.assertEqual(d["inputs"]["version"], "3.3.0")
        self.assertEqual(d["inputs"]["importante"], "true")
        self.assertEqual(d["inputs"]["beta"], "false")
        run = core.find_run(self.gh, since)
        st = core.run_status(self.gh, run["id"])
        self.assertEqual(st["state"], "success")
        self.assertTrue(all(v[1] == "done" for v in st["stages"].values()))
        self.assertEqual(st["discord"], "success")
        pkg.cleanup()

    def test_rejects_stale_package(self):
        old = os.path.join(self.tmp, "vieja.zip")
        sha_old, sha_new = "a" * 40, "b" * 40
        self.fake.compare_status = {sha_old: "ahead", sha_new: "behind"}
        for path, sha in ((old, sha_old), (self.zip, sha_new)):
            with zipfile.ZipFile(self.zip) as src, zipfile.ZipFile(path + ".tmp", "w") as z:
                for item in src.infolist():
                    z.writestr(item, src.read(item.filename))
                z.writestr("NumpadMacros/ENTREGA.txt", f"commit={sha}\nfecha=x\n")
            os.replace(path + ".tmp", path)
        with self.assertRaises(core.PubError):
            core.check_not_stale(core.Package(old), self.gh)          # GitHub tiene cambios posteriores
        core.check_not_stale(core.Package(self.zip), self.gh)         # entrega más nueva: OK

    def test_rejects_other_app(self):
        other = os.path.join(self.tmp, "otra.zip")
        with zipfile.ZipFile(other, "w") as z:
            z.writestr("bot/npm/about.py", 'APP_ID = "otra-cosa"\n')
            z.writestr("bot/npm/__init__.py", '__version__ = "9.0.0"\n')
        self.assertFalse(core.Package(other).is_numpad_macros())
        with self.assertRaises(core.PubError):
            core.Package(os.path.join(HERE, "README.md"))


if __name__ == "__main__":
    unittest.main()
