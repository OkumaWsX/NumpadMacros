# SPDX-License-Identifier: LGPL-3.0-or-later
"""Pruebas del catálogo de temas en línea (sin internet: servidor local)."""
import hashlib
import http.server
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from npm import catalogo, npt, themes  # noqa: E402


class _Srv(http.server.SimpleHTTPRequestHandler):
    """Sirve una carpeta; con ``cut`` corta una vez cada .npt a mitad (para probar el reintento)."""
    cut = 0
    cut_done = set()
    ranges = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        path = self.translate_path(self.path)
        if not path.endswith(".npt"):
            return super().do_GET()
        with open(path, "rb") as f:
            data = f.read()
        start = 0
        rng = self.headers.get("Range", "")
        if rng:
            start = int(rng[6:].split("-")[0])
            type(self).ranges.append(start)
            self.send_response(206)
        else:
            self.send_response(200)
        body = data[start:]
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.cut and self.path not in self.cut_done and start == 0:
            type(self).cut_done.add(self.path)
            self.wfile.write(body[:self.cut])
            return                                   # se corta la conexión a mitad
        self.wfile.write(body)


def _theme(name, author, key, version="1.0"):
    th = npt.Theme(name=name, author=author, colors=dict(themes.BUILTIN[1][1]), version=version)
    return npt.write(th, key)



def aislar_config(test, cfg):
    """La carpeta de configuración de la prueba en ``cfg`` en todos los sistemas (en macOS no depende de
    variables de entorno, y en Windows de APPDATA): se cambia ``config_dir`` donde se usa."""
    carpeta = lambda: os.path.join(cfg, "NumpadMacros")  # noqa: E731
    for mod in ("npm.config", "npm.catalogo", "npm.themes", "npm.sysutil"):
        p = mock.patch(mod + ".config_dir", carpeta)
        p.start()
        test.addCleanup(p.stop)

class CatalogoTest(unittest.TestCase):
    def setUp(self):
        self.cfg = tempfile.mkdtemp()
        self.web = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.cfg, "APPDATA": self.cfg})
        self.env.start()
        aislar_config(self, self.cfg)
        self.key = npt.SigningKey.generate("autor", "kenji")
        big = npt.Theme(name="Sakura", author="kenji", colors=dict(themes.BUILTIN[3][1]), version="1.0",
                        description="x" * 10)
        self.data = npt.write(big, self.key)
        os.makedirs(os.path.join(self.web, "comunidad", "kenji", "sakura", "1.0"))
        with open(os.path.join(self.web, "comunidad", "kenji", "sakura", "1.0", "tema.npt"), "wb") as f:
            f.write(self.data)
        self.entry = {"id": "comunidad/kenji/sakura", "origen": "comunidad", "nombre": "Sakura", "autor": "kenji",
                      "huella_autor": npt.fingerprint(self.key.public_hex), "version": "1.0",
                      "archivo": "comunidad/kenji/sakura/1.0/tema.npt",
                      "sha256": hashlib.sha256(self.data).hexdigest(), "tamano": len(self.data),
                      "colores": dict(themes.BUILTIN[3][1]), "requiere_app": "3.0.0"}
        cat = {"formato": 1, "temas": [self.entry, dict(self.entry, id="x", nombre="Futuro", requiere_app="99.0.0")]}
        with open(os.path.join(self.web, "catalogo.json"), "w") as f:
            json.dump(cat, f)
        _Srv.cut, _Srv.cut_done, _Srv.ranges = 0, set(), []
        handler = lambda *a, **k: _Srv(*a, directory=self.web, **k)  # noqa: E731
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}/catalogo.json"
        self.url_env = mock.patch.dict(os.environ, {"NUMPADMACROS_TEMAS_URL": self.url})
        self.url_env.start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.url_env.stop()
        self.env.stop()

    def _wait(self, dl, timeout=20):
        end = time.time() + timeout
        last = None
        while time.time() < end:
            try:
                ev = dl.events.get(timeout=.2)
            except Exception:
                continue
            last = ev
            if ev[0] in ("done", "error", "cancelled"):
                return ev
        self.fail(f"la descarga no terminó (último aviso: {last})")

    def test_fetch_cache_and_filter(self):
        cat = catalogo.fetch()
        self.assertEqual([e["nombre"] for e in catalogo.entries(cat)], ["Sakura"])   # «Futuro» pide otra versión
        self.assertEqual(catalogo.cached()["temas"][0]["nombre"], "Sakura")          # quedó guardado
        with mock.patch.dict(os.environ, {"NUMPADMACROS_TEMAS_URL": "http://127.0.0.1:9/no"}):
            with self.assertRaises(catalogo.CatalogError):
                catalogo.fetch(timeout=2)
        self.assertIsNotNone(catalogo.cached())                                      # sin red: la copia sigue

    def test_download_install_and_match(self):
        ev = self._wait(catalogo.Download(self.entry).start())
        self.assertEqual(ev[0], "done", ev)
        inst = themes.imported()
        self.assertEqual(len(inst), 1)
        self.assertIs(catalogo.installed_for(self.entry, inst), inst[0])
        self.assertFalse(catalogo.has_update(self.entry, inst[0]))
        self.assertTrue(catalogo.has_update(dict(self.entry, version="1.1"), inst[0]))
        # otro autor con el mismo nombre NO es el mismo tema
        otro = dict(self.entry, huella_autor=npt.fingerprint(npt.SigningKey.generate().public_hex))
        self.assertIsNone(catalogo.installed_for(otro, inst))

    def test_download_reemplaza_el_tema_ya_importado(self):
        """Importado a mano y luego bajado del catálogo (o al revés): un solo archivo, sin «(2)»."""
        src = os.path.join(self.web, self.entry["archivo"])
        t = themes.install(src)
        self.assertEqual(t["file"], "Sakura.npt")
        ev = self._wait(catalogo.Download(self.entry).start())
        self.assertEqual(ev[0], "done", ev)
        self.assertEqual(ev[1]["file"], "Sakura.npt")
        self.assertEqual(os.listdir(themes.themes_dir()), ["Sakura.npt"])
        # una versión nueva del catálogo reemplaza el archivo, aunque no se pase ``replace``
        nueva = npt.Theme(name="Sakura", author="kenji", colors=dict(themes.BUILTIN[3][1]), version="1.1")
        data = npt.write(nueva, self.key)
        ruta = os.path.join(self.web, "comunidad", "kenji", "sakura", "1.1")
        os.makedirs(ruta)
        with open(os.path.join(ruta, "tema.npt"), "wb") as f:
            f.write(data)
        e2 = dict(self.entry, version="1.1", archivo="comunidad/kenji/sakura/1.1/tema.npt",
                  sha256=hashlib.sha256(data).hexdigest(), tamano=len(data))
        ev = self._wait(catalogo.Download(e2).start())
        self.assertEqual(ev[0], "done", ev)
        self.assertEqual(os.listdir(themes.themes_dir()), ["Sakura.npt"])
        self.assertEqual(themes.imported()[0]["version"], "1.1")

    def test_bad_hash_installs_nothing(self):
        ev = self._wait(catalogo.Download(dict(self.entry, sha256="0" * 64)).start())
        self.assertEqual(ev[0], "error")
        self.assertIn("no coincide", ev[1])
        self.assertEqual(themes.imported(), [])

    def test_official_claim_must_match_signature(self):
        ev = self._wait(catalogo.Download(dict(self.entry, origen="oficial")).start())
        self.assertEqual(ev[0], "error")
        self.assertIn("firma", ev[1])
        self.assertEqual(themes.imported(), [])

    def test_creator_claim_needs_official_signature(self):
        # «creador» exige la firma oficial: un archivo firmado por un autor cualquiera se rechaza
        ev = self._wait(catalogo.Download(dict(self.entry, origen="creador", creador="Kenji")).start())
        self.assertEqual(ev[0], "error")
        self.assertIn("firma", ev[1])
        self.assertEqual(themes.imported(), [])

    def test_entries_accept_creator(self):
        cat = {"temas": [dict(self.entry, origen="creador", creador="Kenji"), dict(self.entry, origen="otro")]}
        self.assertEqual([e["origen"] for e in catalogo.entries(cat)], ["creador"])

    def test_resume_after_cut(self):
        _Srv.cut = len(self.data) // 2
        dl = catalogo.Download(self.entry)
        with mock.patch.object(catalogo, "RETRIES", (0.1, 0.1, 0.1)):
            dl.start()
            ev = self._wait(dl)
        self.assertEqual(ev[0], "done", ev)
        self.assertEqual(_Srv.ranges, [len(self.data) // 2])         # continuó donde quedó
        self.assertEqual(len(themes.imported()), 1)

    def test_cancel(self):
        dl = catalogo.Download(self.entry)
        dl.cancel()
        ev = self._wait(dl.start())
        self.assertEqual(ev[0], "cancelled")
        self.assertEqual(themes.imported(), [])

    def test_gives_up_after_retries(self):
        with mock.patch.dict(os.environ, {"NUMPADMACROS_TEMAS_URL": "http://127.0.0.1:9/catalogo.json"}), \
                mock.patch.object(catalogo, "RETRIES", (0.05, 0.05, 0.05)):
            dl = catalogo.Download(self.entry).start()
            retries = []
            while True:
                ev = dl.events.get(timeout=20)
                if ev[0] == "retry":
                    retries.append(ev[1])
                if ev[0] in ("done", "error", "cancelled"):
                    break
        self.assertEqual(retries, [1, 2, 3])
        self.assertEqual(ev[0], "error")
        self.assertIn("conexión", ev[1])
        self.assertEqual(themes.imported(), [])


class RedesCreadorTest(unittest.TestCase):
    """Redes sociales de la ficha de un creador: solo https a los dominios oficiales de cada red."""
    VALIDAS = (("twitch", "https://www.twitch.tv/aquamanchileno"), ("twitch", "https://twitch.tv/x"),
               ("youtube", "https://www.youtube.com/@AquamanChileno"), ("youtube", "https://youtu.be/abc"),
               ("tiktok", "https://www.tiktok.com/@aquamanchileno"), ("kick", "https://kick.com/x"),
               ("instagram", "https://www.instagram.com/x/"), ("x", "https://x.com/x"),
               ("x", "https://twitter.com/x"), ("facebook", "https://www.facebook.com/x"),
               ("discord", "https://discord.gg/abc"), ("discord", "https://discord.com/invite/abc"))
    INVALIDAS = (("twitch", "http://www.twitch.tv/x"),                    # sin https
                 ("twitch", "https://twitch.tv.evil.com/x"),              # subdominio engañoso
                 ("twitch", "https://eviltwitch.tv/x"),                   # termina igual pero no es subdominio
                 ("twitch", "https://evil.com/twitch.tv"),                # el dominio solo en la ruta
                 ("twitch", "https://www.youtube.com/x"),                 # dominio de otra red
                 ("twitch", "https://user:pw@twitch.tv/x"),               # credenciales
                 ("twitch", "https://twitch.tv@evil.com/x"),              # el truco del @
                 ("twitch", "https://twitch.tv:8443/x"),                  # puerto
                 ("twitch", "https://twitch.tv\\@evil.com/"),             # barra invertida
                 ("twitch", "https://twitch.tv./x"),                      # punto final
                 ("twitch", "https://twitch.tv/ x"),                      # espacio
                 ("twitch", "https://twitсh.tv/x"),                       # letra cirílica parecida
                 ("twitch", "javascript:alert(1)"), ("twitch", "file:///etc/passwd"),
                 ("twitch", "//twitch.tv/x"), ("twitch", ""), ("twitch", None), ("twitch", 5),
                 ("myspace", "https://myspace.com/x"),                    # red desconocida
                 (None, "https://twitch.tv/x"))

    def test_urls(self):
        for red, url in self.VALIDAS:
            self.assertTrue(catalogo.red_url_valida(red, url), (red, url))
        for red, url in self.INVALIDAS:
            self.assertFalse(catalogo.red_url_valida(red, url), (red, url))

    def test_creator_info_descarta_lo_invalido(self):
        e = {"creador_info": {"nombre": " Ana ", "bio": "x " * 400, "redes": [
            {"red": "twitch", "url": "https://twitch.tv/ana"},
            {"red": "twitch", "url": "https://twitch.tv/otra"},          # repetida
            {"red": "kick", "url": "https://kick.com.evil.com/ana"},     # engañosa
            {"red": "youtube", "url": "javascript:alert(1)"}, "basura", {"red": "x"}]}}
        info = catalogo.creator_info(e)
        self.assertEqual(info["nombre"], "Ana")
        self.assertEqual([n["red"] for n in info["redes"]], ["twitch"])
        self.assertEqual(info["redes"][0]["nombre"], "Twitch")
        self.assertLessEqual(len(info["bio"]), catalogo.BIO_MAX)

    def test_creator_info_sin_datos(self):
        for e in (None, {}, {"creador_info": None}, {"creador_info": []}, {"creador_info": "x"}):
            self.assertIsNone(catalogo.creator_info(e))
        info = catalogo.creator_info({"creador_info": {"nombre": 5, "bio": None, "redes": "no"}})
        self.assertEqual(info, {"nombre": "", "bio": "", "redes": [], "avatar": None})


class ArmadorCreadorTest(unittest.TestCase):
    """El armador del repositorio de temas rechaza un creador.json inválido y publica el válido."""
    @classmethod
    def setUpClass(cls):
        import importlib.util
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        # la librería de temas junto a la app (carpeta «Librería de Temas» o el nombre del repositorio)
        path = next((p for p in (os.path.join(base, d, "tools", "armar_catalogo.py")
                                 for d in ("Librería de Temas", "NumpadMacros-Temas")) if os.path.isfile(p)), "")
        if not path:
            raise unittest.SkipTest("no está la librería de temas (NumpadMacros-Temas) junto a la app")
        spec = importlib.util.spec_from_file_location("armar_catalogo", path)
        cls.armar = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.armar)

    def _leer(self, datos):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "creadores", "ana"))
            with open(os.path.join(d, "creadores", "ana", "creador.json"), "w", encoding="utf-8") as f:
                f.write(datos if isinstance(datos, str) else json.dumps(datos))
            errores = []
            res = self.armar.leer_creador(os.path.join(d, "creadores", "ana"), "creadores/ana", errores)
        return res, errores

    def test_valido(self):
        res, err = self._leer({"nombre": "Ana", "bio": "Hola   mundo", "redes": [
            {"red": "twitch", "url": "https://www.twitch.tv/ana"}]})
        self.assertEqual(err, [])
        self.assertEqual(res, {"nombre": "Ana", "bio": "Hola mundo",
                               "redes": [{"red": "twitch", "url": "https://www.twitch.tv/ana"}]})

    def test_rechaza(self):
        base = {"nombre": "Ana", "bio": "x"}
        malos = [{**base, "redes": [{"red": "twitch", "url": "http://twitch.tv/ana"}]},
                 {**base, "redes": [{"red": "twitch", "url": "https://twitch.tv.evil.com/ana"}]},
                 {**base, "redes": [{"red": "twitch", "url": "https://u:p@twitch.tv/ana"}]},
                 {**base, "redes": [{"red": "twitch", "url": "https://twitch.tv:99/ana"}]},
                 {**base, "redes": [{"red": "twitch", "url": "javascript:alert(1)"}]},
                 {**base, "redes": [{"red": "myspace", "url": "https://myspace.com/ana"}]},
                 {**base, "redes": [{"red": "twitch", "url": "https://twitch.tv/a"},
                                    {"red": "twitch", "url": "https://twitch.tv/b"}]},
                 {**base, "bio": "x" * 301, "redes": []},
                 {"bio": "x", "redes": []}, [], "{no es json"]
        for datos in malos:
            res, err = self._leer(datos)
            self.assertIsNone(res, datos)
            self.assertTrue(err, datos)
        self.assertEqual(self._leer({**base, "bio": "x" * 300, "redes": []})[1], [])

    def _avatar(self, datos, nombre="avatar.png"):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "creadores", "ana"))
            carpeta = os.path.join(d, "creadores", "ana")
            if datos is not None:
                with open(os.path.join(carpeta, nombre), "wb") as f:
                    f.write(datos)
            with open(os.path.join(carpeta, "creador.json"), "w", encoding="utf-8") as f:
                json.dump({"nombre": "Ana", "avatar": nombre}, f)
            errores = []
            res = self.armar.leer_creador(carpeta, "creadores/ana", errores)
        return res, errores

    def test_avatar_valido_se_publica_con_huella(self):
        datos = _png()
        res, err = self._avatar(datos)
        self.assertEqual(err, [])
        self.assertEqual(res["avatar"], {"archivo": "creadores/ana/avatar.png",
                                         "sha256": hashlib.sha256(datos).hexdigest(), "tamano": len(datos)})
        self.assertIsNotNone(catalogo.avatar_valido(res["avatar"]))        # la app lo acepta

    def test_avatar_invalido_se_rechaza(self):
        malos = [(b"esto no es una imagen", "avatar.png"), (_png(512, ruido=True), "avatar.png"),
                 (_png(32), "avatar.png"), (_png(600), "avatar.png"), (_png(), "avatar.jpg"),
                 (None, "avatar.png"), (_png(), "../avatar.png"), (_png(), "avatar.svg")]
        for datos, nombre in malos:
            res, err = self._avatar(datos, nombre)
            self.assertIsNone(res, nombre)
            self.assertTrue(err, nombre)

    def test_avatar_no_cuadrado_se_rechaza(self):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (400, 200), "#123456").save(buf, "PNG")
        res, err = self._avatar(buf.getvalue())
        self.assertIsNone(res)
        self.assertIn("cuadrada", err[0])

    def test_avatar_jpeg_valido(self):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (200, 190), "#123456").save(buf, "JPEG", quality=88)
        res, err = self._avatar(buf.getvalue(), "foto.jpg")
        self.assertEqual(err, [])
        self.assertEqual(res["avatar"]["archivo"], "creadores/ana/foto.jpg")

    def test_coinciden_los_dominios_con_la_app(self):
        """El armador y la app aceptan y rechazan lo mismo."""
        for red, url in RedesCreadorTest.VALIDAS + RedesCreadorTest.INVALIDAS:
            if red not in self.armar.REDES:
                continue
            self.assertEqual(self.armar.url_red_error(red, url) is None, catalogo.red_url_valida(red, url),
                             (red, url))
        for red in catalogo.REDES:
            self.assertEqual(catalogo.REDES[red][1], self.armar.REDES[red])


def _png(lado=256, ruido=False):
    """Un PNG de verdad (con ruido si se quiere que pese) para las pruebas de la foto."""
    import io
    from PIL import Image
    im = Image.frombytes("RGB", (lado, lado), os.urandom(lado * lado * 3)) if ruido else Image.new("RGB", (lado, lado), "#3366aa")
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


class AvatarCreadorTest(unittest.TestCase):
    """La foto del creador: el catálogo no es de fiar, así que huella, tamaño y forma se comprueban."""
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.cfg = os.path.join(self.dir.name, "cfg")
        self.cat = os.path.join(self.dir.name, "cat")
        os.makedirs(os.path.join(self.cat, "creadores", "ana"))
        with open(os.path.join(self.cat, "catalogo.json"), "w") as f:
            f.write("{}")
        self.env = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.cfg, "NUMPADMACROS_TEMAS_URL": self.cat})
        self.env.start()
        self.addCleanup(self.env.stop)
        aislar_config(self, self.cfg)

    def _publicar(self, datos, sha=None, tam=None):
        with open(os.path.join(self.cat, "creadores", "ana", "avatar.png"), "wb") as f:
            f.write(datos)
        return {"archivo": "creadores/ana/avatar.png", "sha256": sha or hashlib.sha256(datos).hexdigest(),
                "tamano": tam if tam is not None else len(datos)}

    def test_foto_correcta_se_guarda_en_cache_y_se_reutiliza_sin_red(self):
        av = catalogo.avatar_valido(self._publicar(_png()))
        path = catalogo.avatar_get(av)
        self.assertTrue(path.startswith(os.path.join(self.cfg, "NumpadMacros", catalogo.AVATAR_CACHE)))
        self.assertTrue(os.path.basename(path).startswith(av["sha256"]))
        os.remove(os.path.join(self.cat, "creadores", "ana", "avatar.png"))      # sin «red»
        self.assertEqual(catalogo.avatar_get(av), path)

    def test_huella_incorrecta_no_se_usa(self):
        av = catalogo.avatar_valido(self._publicar(_png(), sha="ab" * 32))
        with self.assertRaises(ValueError):
            catalogo.avatar_get(av)
        self.assertFalse(os.path.exists(catalogo.avatar_path(av["sha256"])))

    def test_cache_alterada_se_vuelve_a_bajar(self):
        av = catalogo.avatar_valido(self._publicar(_png()))
        path = catalogo.avatar_get(av)
        with open(path, "wb") as f:
            f.write(b"basura")
        self.assertEqual(catalogo.avatar_get(av), path)
        with open(path, "rb") as f:
            self.assertEqual(hashlib.sha256(f.read()).hexdigest(), av["sha256"])

    def test_archivo_demasiado_grande_se_rechaza(self):
        datos = _png(512, ruido=True)
        self.assertGreater(len(datos), catalogo.AVATAR_MAX)
        # el catálogo miente sobre el tamaño: no se baja más de lo permitido ni se acepta
        self.assertIsNone(catalogo.avatar_valido(self._publicar(datos)))
        av = {"archivo": "creadores/ana/avatar.png", "sha256": hashlib.sha256(datos).hexdigest(), "tamano": 1000}
        with self.assertRaises(ValueError):
            catalogo.avatar_get(av)

    def test_no_imagen_o_medidas_malas(self):
        for datos in (b"no soy una imagen" * 50, _png(32), _png(600)):
            av = catalogo.avatar_valido(self._publicar(datos))
            with self.assertRaises(ValueError):
                catalogo.avatar_get(av)

    def test_entrada_del_catalogo_rara_se_ignora(self):
        sha = "ab" * 32
        malos = [None, "x", {}, {"archivo": "http://evil.com/a.png", "sha256": sha, "tamano": 10},
                 {"archivo": "//evil.com/a.png", "sha256": sha, "tamano": 10},
                 {"archivo": "/etc/passwd.png", "sha256": sha, "tamano": 10},
                 {"archivo": "../a.png", "sha256": sha, "tamano": 10},
                 {"archivo": "a.png", "sha256": "xyz", "tamano": 10},
                 {"archivo": "a.png", "sha256": sha, "tamano": 10 ** 9},
                 {"archivo": "a.png", "sha256": sha, "tamano": True},
                 {"archivo": "a.svg", "sha256": sha, "tamano": 10}]
        for av in malos:
            self.assertIsNone(catalogo.avatar_valido(av), av)
        self.assertIsNotNone(catalogo.avatar_valido({"archivo": "creadores/ana/a.png", "sha256": sha, "tamano": 10}))
        info = catalogo.creator_info({"creador_info": {"nombre": "Ana", "avatar": malos[1]}})
        self.assertIsNone(info["avatar"])

    def test_circulo_recortado(self):
        from npm import themes_tab
        import tkinter as tk
        av = catalogo.avatar_valido(self._publicar(_png()))
        path = catalogo.avatar_get(av)
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("sin pantalla")
        self.addCleanup(root.destroy)
        img = themes_tab.avatar_circle(root, path, 26, "#8844ff", 1.5)
        self.assertEqual((img.width(), img.height()), (26, 26))
        self.assertTrue(img.transparency_get(0, 0))            # la esquina queda fuera del círculo
        self.assertFalse(img.transparency_get(13, 13))


class AbrirRedTest(unittest.TestCase):
    """El clic en una red abre el perfil solo si el enlace pasa la lista (sin tocar el navegador real)."""
    def test_clic(self):
        from npm import themes_tab
        with mock.patch.object(themes_tab.sysutil, "open_url") as abrir:
            themes_tab.ThemesTab._open_net(None, {"red": "twitch", "nombre": "Twitch", "url": "https://www.twitch.tv/x"})
            abrir.assert_called_once_with("https://www.twitch.tv/x")
            abrir.reset_mock()
            themes_tab.ThemesTab._open_net(None, {"red": "twitch", "nombre": "Twitch", "url": "https://twitch.tv.evil.com/x"})
            themes_tab.ThemesTab._open_net(None, {"red": "twitch", "nombre": "Twitch", "url": "javascript:alert(1)"})
            abrir.assert_not_called()


if __name__ == "__main__":
    unittest.main()
