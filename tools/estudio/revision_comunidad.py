"""Lector y revisor de temas .npt (modo «comunidad»). Solo biblioteca estándar.

    from npt import revisar, revisar_catalogo
    r = revisar(bytes_o_ruta)   # {"ok", "errores": [{"codigo", "mensaje", "que_hacer", ["espacio"]}], "avisos", "datos"}

Las reglas y los textos viven en reglas.json (las comparte npt.js). Formato .npt v2:
"NPT" 2 0 | clave pública (32) | nonce (12) | AES-256-GCM(zlib(contenido)) | firma Ed25519 (64).
Como Python no trae AES ni Ed25519, van implementados aquí (lentos pero correctos: ~2 s por MB).
"""
import hashlib
import hmac
import json
import os
import re
import struct
import unicodedata
import zlib

REGLAS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "reglas.json"), encoding="utf-8"))
LIM = REGLAS["limites"]
OFFICIAL_KEY = "d22a3b4117eb17f96229d2ee90240c0f5e324ac34f97783de09124765d6711ff"
_KEY = hashlib.sha256(b"NumpadMacros/npt/1/" + bytes.fromhex(OFFICIAL_KEY)[::-1]).digest()  # clave de contenido (no secreta)


# ============================================================ AES-256-GCM (descifrar)
def _aes_tablas():
    sb, p, q = [0] * 256, 1, 1
    while True:
        p = (p ^ (p << 1) ^ (0x1B if p & 0x80 else 0)) & 0xFF
        q ^= (q << 1) & 0xFF
        q ^= (q << 2) & 0xFF
        q ^= (q << 4) & 0xFF
        if q & 0x80:
            q ^= 0x09
        r = lambda v, n: ((v << n) | (v >> (8 - n))) & 0xFF
        sb[p] = q ^ r(q, 1) ^ r(q, 2) ^ r(q, 3) ^ r(q, 4) ^ 0x63
        if p == 1:
            break
    sb[0] = 0x63
    te = [[0] * 256 for _ in range(4)]
    for x in range(256):
        s = sb[x]
        s2 = (s << 1) ^ (0x1B if s & 0x80 else 0)
        w = ((s2 & 0xFF) << 24) | (s << 16) | (s << 8) | ((s2 ^ s) & 0xFF)
        for i in range(4):
            te[i][x] = w
            w = ((w >> 8) | (w << 24)) & 0xFFFFFFFF
    return sb, te


_SB, _TE = _aes_tablas()


def _aes_claves(key):
    w = list(struct.unpack(">8I", key))
    rc = 1
    for i in range(8, 60):
        t = w[i - 1]
        if i % 8 == 0:
            t = ((t << 8) | (t >> 24)) & 0xFFFFFFFF
            t = (_SB[t >> 24] << 24 | _SB[(t >> 16) & 255] << 16 | _SB[(t >> 8) & 255] << 8 | _SB[t & 255]) ^ (rc << 24)
            rc = (rc << 1) ^ (0x11B if rc & 0x80 else 0)
        elif i % 8 == 4:
            t = _SB[t >> 24] << 24 | _SB[(t >> 16) & 255] << 16 | _SB[(t >> 8) & 255] << 8 | _SB[t & 255]
        w.append(w[i - 8] ^ t)
    return w


_RK = _aes_claves(_KEY)


def _aes_bloque(s0, s1, s2, s3):
    t0, t1, t2, t3 = _TE
    sb, rk = _SB, _RK
    s0, s1, s2, s3 = s0 ^ rk[0], s1 ^ rk[1], s2 ^ rk[2], s3 ^ rk[3]
    for r in range(4, 56, 4):
        s0, s1, s2, s3 = (
            t0[s0 >> 24] ^ t1[(s1 >> 16) & 255] ^ t2[(s2 >> 8) & 255] ^ t3[s3 & 255] ^ rk[r],
            t0[s1 >> 24] ^ t1[(s2 >> 16) & 255] ^ t2[(s3 >> 8) & 255] ^ t3[s0 & 255] ^ rk[r + 1],
            t0[s2 >> 24] ^ t1[(s3 >> 16) & 255] ^ t2[(s0 >> 8) & 255] ^ t3[s1 & 255] ^ rk[r + 2],
            t0[s3 >> 24] ^ t1[(s0 >> 16) & 255] ^ t2[(s1 >> 8) & 255] ^ t3[s2 & 255] ^ rk[r + 3])
    return (sb[s0 >> 24] << 24 | sb[(s1 >> 16) & 255] << 16 | sb[(s2 >> 8) & 255] << 8 | sb[s3 & 255]) ^ rk[56], \
           (sb[s1 >> 24] << 24 | sb[(s2 >> 16) & 255] << 16 | sb[(s3 >> 8) & 255] << 8 | sb[s0 & 255]) ^ rk[57], \
           (sb[s2 >> 24] << 24 | sb[(s3 >> 16) & 255] << 16 | sb[(s0 >> 8) & 255] << 8 | sb[s1 & 255]) ^ rk[58], \
           (sb[s3 >> 24] << 24 | sb[(s0 >> 16) & 255] << 16 | sb[(s1 >> 8) & 255] << 8 | sb[s2 & 255]) ^ rk[59]


def _gmul(x, y):
    z, r = 0, 0xE1 << 120
    for i in range(128):
        if (y >> (127 - i)) & 1:
            z ^= x
        x = (x >> 1) ^ r if x & 1 else x >> 1
    return z


def _ghash_tabla(h):
    tab = []
    for i in range(16):
        col = [0] * 256
        for k in range(8):
            col[1 << k] = _gmul(h, 1 << (120 - 8 * i + k))
        for b in range(3, 256):
            col[b] = col[b & -b] ^ col[b ^ (b & -b)]
        tab.append(col)
    return tab


def _ghash(tab, *partes):
    y = 0
    for datos in partes:
        datos = datos + b"\0" * (-len(datos) % 16)
        for i in range(0, len(datos), 16):
            v = (y ^ int.from_bytes(datos[i:i + 16], "big")).to_bytes(16, "big")
            y = 0
            for j in range(16):
                y ^= tab[j][v[j]]
    return y


def aes_gcm_descifrar(nonce, cifrado, aad):
    """Descifra (12 bytes de nonce, etiqueta de 16 al final). ValueError si el sello no cuadra."""
    ct, tag = cifrado[:-16], cifrado[-16:]
    n = struct.unpack(">3I", nonce)
    h = _aes_bloque(0, 0, 0, 0)
    tab = _ghash_tabla(int.from_bytes(struct.pack(">4I", *h), "big"))
    y = _ghash(tab, aad, ct, struct.pack(">QQ", len(aad) * 8, len(ct) * 8))   # cada parte se rellena a 16 bytes
    e = _aes_bloque(n[0], n[1], n[2], 1)
    esperado = (y ^ int.from_bytes(struct.pack(">4I", *e), "big")).to_bytes(16, "big")
    if not hmac.compare_digest(esperado, tag):
        raise ValueError("sello")
    ks = bytearray()
    for c in range((len(ct) + 15) // 16):
        ks += struct.pack(">4I", *_aes_bloque(n[0], n[1], n[2], c + 2))
    return (int.from_bytes(ct, "big") ^ int.from_bytes(ks[:len(ct)], "big")).to_bytes(len(ct), "big")


# ============================================================ Ed25519 (verificar)
_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P


def _suma(p, q):
    a = (p[1] - p[0]) * (q[1] - q[0]) % _P
    b = (p[1] + p[0]) * (q[1] + q[0]) % _P
    c = 2 * p[3] * q[3] * _D % _P
    d = 2 * p[2] * q[2] % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return e * f % _P, g * h % _P, f * g % _P, e * h % _P


def _mult(s, p):
    q = (0, 1, 1, 0)
    while s:
        if s & 1:
            q = _suma(q, p)
        p = _suma(p, p)
        s >>= 1
    return q


def _decodificar(b):
    y = int.from_bytes(b, "little")
    signo, y = y >> 255, y & ((1 << 255) - 1)
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P:
        x = x * pow(2, (_P - 1) // 4, _P) % _P
    if (x * x - x2) % _P or (x == 0 and signo):
        return None
    if x & 1 != signo:
        x = _P - x
    return x, y, 1, x * y % _P


def _codificar(p):
    zi = pow(p[2], _P - 2, _P)
    x, y = p[0] * zi % _P, p[1] * zi % _P
    return (y | (x & 1) << 255).to_bytes(32, "little")


_BASE = _decodificar((4 * pow(5, _P - 2, _P) % _P).to_bytes(32, "little"))


def ed25519_verificar(pub, firma, mensaje):
    a = _decodificar(pub)
    s = int.from_bytes(firma[32:], "little")
    if a is None or s >= _L or _codificar(_mult(8, a)) == _codificar((0, 1, 1, 0)):   # clave débil
        return False
    h = int.from_bytes(hashlib.sha512(firma[:32] + pub + mensaje).digest(), "little") % _L
    p = _suma(_mult(s, _BASE), _mult(h, ((_P - a[0]) % _P, a[1], a[2], (_P - a[3]) % _P)))
    return _codificar(p) == firma[:32]


# ============================================================ utilidades
def huella(pub_hex):
    h = hashlib.sha256(bytes.fromhex(pub_hex)).hexdigest()[:32].upper()
    g = [h[i:i + 4] for i in range(0, 32, 4)]
    return " ".join(g[:4]) + " · " + " ".join(g[4:])


def slug(s):
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _normalizar(nombre):
    r = REGLAS["reservado"]
    s = unicodedata.normalize("NFKD", nombre or "").lower().translate(str.maketrans(r["parecidas_de"], r["parecidas_a"]))
    return re.sub(r"[^a-z0-9]", "", s.translate(str.maketrans(r["numeros_de"], r["numeros_a"])))


def es_nombre_reservado(nombre):
    return _normalizar(REGLAS["reservado"]["nombre"]) in _normalizar(nombre)


def _plantilla(txt, datos):
    return re.sub(r"\{(\w+)\}", lambda m: str(datos.get(m.group(1), m.group(0))), txt)


def _limpio(s, n=40):
    """Texto de un archivo ajeno dentro de un mensaje: sin @ < > ni controles, y recortado."""
    s = re.sub(r"[@<>\x00-\x1f\x7f]", "", str(s))
    return s if len(s) <= n else s[:n] + "…"


def _item(tabla, codigo, **kw):
    for k in ("campo", "version", "nombre", "autor", "registrado", "otro"):
        if k in kw:
            kw[k] = _limpio(kw[k])
    if "detalle" in kw:
        kw["detalle"] = _limpio(kw["detalle"], 200)
    msg, que = REGLAS[tabla][codigo]
    kw["reexportar"] = REGLAS["reexportar"]
    out = {"codigo": codigo, "mensaje": _plantilla(msg, kw), "que_hacer": _plantilla(que, kw)}
    if "espacio" in kw:
        out["espacio"] = kw["espacio"]
    if "campo_id" in kw or codigo == "campo_extra":     # qué dato del tema (nombre, autor, descripcion…)
        out["campo"] = kw.get("campo_id", kw.get("campo"))
    return out


def _profundidad(v):
    return 1 + max((_profundidad(x) for x in (v.values() if isinstance(v, dict) else v)), default=0) \
        if isinstance(v, (dict, list)) else 0


def _es_int(v):
    return type(v) is int


def _hex(v):
    return isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v) is not None


# ============================================================ imágenes (PNG / APNG sin Pillow)
_CANALES = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def _inflar(datos, esperado):
    d = zlib.decompressobj()
    try:
        out = d.decompress(bytes(datos), esperado + 1)
        return d.eof and len(out) == esperado and not d.unused_data
    except zlib.error:
        return False


def revisar_png(data, slot, cuadros_declarados):
    """Lista de (codigo, detalle). Mira estructura, CRC y que los datos descompriman al tamaño del encabezado."""
    err, pos, bloques = [], 8, []
    permitidos = REGLAS["png"]["bloques_permitidos"]
    fin = False
    while pos + 12 <= len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        tipo = data[pos + 4:pos + 8]
        if pos + 12 + ln > len(data):
            break
        cuerpo = data[pos + 8:pos + 8 + ln]
        if struct.unpack(">I", data[pos + 8 + ln:pos + 12 + ln])[0] != zlib.crc32(tipo + cuerpo):
            return [("imagen_rota", "un bloque tiene la suma de control mal")]
        t = tipo.decode("latin-1")
        if t not in permitidos:
            if not any(c == "png_bloque_raro" and d == _limpio(t) for c, d in err):
                err.append(("png_bloque_raro", _limpio(t)))
        bloques.append((t, cuerpo))
        pos += 12 + ln
        if t == "IEND":
            fin = True
            break
    if not fin:
        return err + [("imagen_rota", "el PNG está incompleto")]
    if pos < len(data):
        err.append(("png_datos_extra", ""))
    if err or bloques[0][0] != "IHDR" or len(bloques[0][1]) != 13 or [b[0] for b in bloques].count("IHDR") != 1:
        return err or [("imagen_rota", "el encabezado no es el normal")]
    w, h, prof, ct, _c, _f, entrelazado = struct.unpack(">IIBBBBB", bloques[0][1])
    if ct not in _CANALES or prof not in (1, 2, 4, 8, 16) or entrelazado or not w or not h:
        return [("imagen_rota", "el encabezado no es el que escribe el Estudio")]
    mw, mh = REGLAS["ranuras"][slot]
    if w > mw or h > mh:
        return [("imagen_tamano", f"mide {w}×{h} y el máximo es {mw}×{mh}")]
    bits = _CANALES[ct] * prof

    def tam(fw, fh):
        return fh * (1 + (fw * bits + 7) // 8)

    tipos = [b[0] for b in bloques]
    actl = [b[1] for b in bloques if b[0] == "acTL"]
    if "IDAT" not in tipos or len(actl) > 1 or (actl and (len(actl[0]) != 8 or tipos.index("acTL") > tipos.index("IDAT"))):
        return [("imagen_rota", "los bloques están desordenados")]
    n = struct.unpack(">I", actl[0][:4])[0] if actl else 1
    if n < 1 or n != cuadros_declarados:
        return [("imagen_rota", f"el archivo declara {cuadros_declarados} cuadros y el PNG trae {n}")]
    if n > LIM["max_cuadros"] or w * h * n > LIM["max_pixeles"]:
        return [("imagen_tamano", f"tiene {n} cuadros")]
    if n > 1 and slot not in REGLAS["ranuras_animadas"]:
        return [("imagen_animada", "")]
    cuadros, actual, seq = [], None, 0       # cada cuadro animado: [ancho, alto, datos]
    for t, c in bloques:
        if t in ("fcTL", "fdAT"):
            if len(c) < (26 if t == "fcTL" else 4) or struct.unpack(">I", c[:4])[0] != seq:
                return [("imagen_rota", "los cuadros están desordenados")]
            seq += 1
        if t == "fcTL":
            fw, fh, fx, fy = struct.unpack(">IIII", c[4:20])
            if len(c) != 26 or not fw or not fh or fx + fw > w or fy + fh > h:
                return [("imagen_rota", "un cuadro está mal descrito o se sale de la imagen")]
            actual = [fw, fh, bytearray()]
            cuadros.append(actual)
        elif t == "fdAT" and actual:
            actual[2] += c[4:]
    if len(cuadros) != (n if actl else 0):
        return [("imagen_rota", "faltan cuadros")]
    en_idat = bool(cuadros) and tipos.index("fcTL") < tipos.index("IDAT")   # el primer cuadro va en IDAT
    ancho, alto = (cuadros[0][0], cuadros[0][1]) if en_idat else (w, h)
    if not _inflar(b"".join(c for t, c in bloques if t == "IDAT"), tam(ancho, alto)):
        return [("imagen_rota", "los datos no coinciden con el tamaño")]
    for fw, fh, datos in cuadros[1 if en_idat else 0:]:
        if not _inflar(datos, tam(fw, fh)):
            return [("imagen_rota", "los datos de un cuadro no coinciden con su tamaño")]
    return []


# ============================================================ contenido (JSON)
def _contenido(meta, ranuras):
    """Compara el JSON con lo que escribe el Estudio. Devuelve errores."""
    esq, out = REGLAS["esquema"], []
    falta = [k for k in esq["obligatorios"] if k not in meta]
    permitidos = esq["obligatorios"] + esq["opcionales"]
    if falta:
        out.append(_item("motivos", "campos_faltantes", detalle=", ".join(falta)))
    for k in meta:
        if k not in permitidos:
            out.append(_item("motivos", "campo_extra", campo=k))

    def malo(txt):
        out.append(_item("motivos", "campo_invalido", detalle=txt))

    def extras(d, validos, ruta):
        for k in d:
            if k not in validos:
                out.append(_item("motivos", "campo_extra", campo=f"{ruta}.{k}"))

    if "formato" in meta and not (_es_int(meta["formato"]) and meta["formato"] == 2):
        malo("«formato» debe ser 2.")
    for k, mx in (("nombre", LIM["max_nombre"]), ("autor", LIM["max_autor"]), ("version", LIM["max_version"]),
                  ("descripcion", LIM["max_descripcion"])):
        if k in meta and (not isinstance(meta[k], str) or len(meta[k]) > mx or (k == "nombre" and not meta[k].strip())):
            malo(f"«{k}» no es válido (hasta {mx} caracteres).")
    if "tipo" in meta and meta["tipo"] not in ("oscuro", "claro"):
        malo("«tipo» debe ser oscuro o claro.")
    if "creado" in meta and not isinstance(meta["creado"], str):
        malo("«creado» no es válido.")
    if "admite_transparencia" in meta and not isinstance(meta["admite_transparencia"], bool):
        malo("«admite_transparencia» no es válido.")
    if "pausar_animaciones" in meta and not isinstance(meta["pausar_animaciones"], bool):
        malo("«pausar_animaciones» no es válido.")
    col = meta.get("colores")
    if "colores" in meta:
        if not isinstance(col, dict):
            malo("«colores» no es válido.")
        else:
            extras(col, REGLAS["colores"], "colores")
            mal = [t for t in REGLAS["colores"] if not _hex(col.get(t))]
            if mal:
                malo("faltan colores o no son válidos: " + ", ".join(mal))
    alfa = meta.get("alfa")
    if "alfa" in meta:
        if not isinstance(alfa, dict):
            malo("«alfa» no es válido.")
        else:
            for k, v in alfa.items():
                if k not in REGLAS["colores"] or k == "bg" or not _es_int(v) or not 0 <= v <= 100:
                    malo(f"transparencia no válida en «{_limpio(k)}».")
    ven = meta.get("ventana")
    if "ventana" in meta:
        if not isinstance(ven, dict):
            malo("«ventana» no es válido.")
        else:
            extras(ven, esq["ventana"], "ventana")
            for k in esq["ventana"]:
                v = ven.get(k, 100)
                if not _es_int(v) or not LIM["opacidad_ventana_min"] <= v <= 100:
                    malo("la opacidad de la ventana debe estar entre 50 y 100.")
    fondo = meta.get("fondo")
    if "fondo" in meta:
        if not isinstance(fondo, dict):
            malo("«fondo» no es válido.")
        else:
            extras(fondo, esq["fondo"], "fondo")
            tipo = fondo.get("tipo", "degradado")
            if tipo not in ("solido", "degradado", "imagen"):
                malo("tipo de fondo desconocido.")
            if tipo == "degradado":
                st, (lo, hi) = fondo.get("colores"), REGLAS["degradado_colores"]
                if not isinstance(st, list) or not lo <= len(st) <= hi or not all(
                        isinstance(s, list) and len(s) == 2 and _hex(s[0]) and _es_int(s[1]) and 0 <= s[1] <= 100 for s in st):
                    malo("los colores del degradado no son válidos.")
                if fondo.get("desde", "tl") not in REGLAS["degradado_desde"]:
                    malo("el degradado empieza en un lugar desconocido.")
            if tipo == "imagen" and "fondo" not in ranuras:
                malo("el fondo de imagen necesita la imagen «fondo».")
            if not isinstance(fondo.get("una_pieza", False), bool) or not _es_int(fondo.get("tinte", 35)) \
                    or not 0 <= fondo.get("tinte", 35) <= LIM["tinte_max"]:
                malo("«una_pieza» o «tinte» no son válidos.")
    if "secciones" in meta:
        sec = meta["secciones"]
        if not isinstance(sec, dict):
            malo("«secciones» no es válido.")
        else:
            for k, s in sec.items():
                if k not in REGLAS["secciones"] or not isinstance(s, dict):
                    malo(f"sección desconocida: «{_limpio(k)}».")
                    continue
                extras(s, esq["seccion"], f"secciones.{k}")
                if not all(_es_int(s.get(p, 100)) and 0 <= s.get(p, 100) <= 100 for p in ("fondo", "contenido")) \
                        or not isinstance(s.get("realce", False), bool):
                    malo(f"valores no válidos en la sección «{_limpio(k)}».")
    return out


def _texto(campo, valor, out):
    if not isinstance(valor, str):
        return
    info, txt = REGLAS["campos"][campo], unicodedata.normalize("NFKC", valor)
    kw = dict(campo=info["campo"], donde=info["donde"], campo_id=campo)
    if re.search(REGLAS["texto"]["enlace"], txt, re.I):
        out.append(_item("motivos", "texto_enlace", **kw))
    if re.search(REGLAS["texto"]["mencion"], txt, re.I):
        out.append(_item("motivos", "texto_mencion", **kw))
    if any(lo <= ord(c) <= hi for c in valor for lo, hi in REGLAS["texto"]["invisibles"]):
        out.append(_item("motivos", "texto_invisible", **kw))


# ============================================================ API
def _leer(origen):
    if isinstance(origen, (bytes, bytearray, memoryview)):
        return bytes(origen)
    with open(origen, "rb") as f:
        return f.read(LIM["max_bytes"] + 1)


def revisar(origen):
    """Revisa un .npt (bytes o ruta) con las reglas de la comunidad. No lanza: todo va en el resultado."""
    errores, avisos, datos = [], [], {}
    res = {"ok": False, "errores": errores, "avisos": avisos, "datos": datos}
    try:
        data = _leer(origen)
    except OSError:
        errores.append(_item("motivos", "archivo_ilegible"))
        return res
    datos.update(tamano=len(data), sha256=hashlib.sha256(data).hexdigest())

    def parar(codigo, **kw):
        errores.append(_item("motivos", codigo, **kw))
        return res

    if len(data) > LIM["max_bytes"]:
        return parar("archivo_grande", kb=len(data) // 1024, max_kb=LIM["max_bytes"] // 1024)
    if data[:3] != b"NPT":
        return parar("proyecto_editable" if data.lstrip()[:1] == b"{" else "formato")
    if len(data) < 5 or data[3] != 2:
        return parar("version_formato")
    if len(data) < 5 + 32 + 12 + 16 + 64:
        return parar("danado")
    pub, nonce, cifrado, firma = data[5:37], data[37:49], data[49:-64], data[-64:]
    datos["firma_valida"] = ed25519_verificar(pub, firma, data[:-64])
    if not datos["firma_valida"]:
        return parar("danado")
    try:
        plano = aes_gcm_descifrar(nonce, cifrado, data[:37])
        d = zlib.decompressobj()
        raw = d.decompress(plano, LIM["max_descomprimido"])
        if d.unconsumed_tail:
            return parar("danado")
    except (ValueError, zlib.error):
        return parar("danado")
    try:
        if raw[:4] != b"NPTC":
            raise ValueError
        n = struct.unpack(">I", raw[4:8])[0]
        meta, blob = json.loads(raw[8:8 + n].decode("utf-8")), raw[8 + n:]
        if not isinstance(meta, dict):
            raise ValueError
        if _profundidad(meta) > LIM["max_profundidad"]:
            return parar("danado")
    except RecursionError:        # JSON anidado a propósito
        return parar("danado")
    except (ValueError, struct.error):
        return parar("contenido")

    oficial = pub.hex() == OFFICIAL_KEY
    datos.update(clave_publica=pub.hex(), huella=huella(pub.hex()), oficial=oficial)
    if oficial:
        errores.append(_item("motivos", "firma_oficial"))

    # imágenes: índice del contenido
    idx = meta.get("imagenes")
    if not isinstance(idx, dict):
        idx = {}
        if "imagenes" in meta:
            errores.append(_item("motivos", "campo_invalido", detalle="«imagenes» no es válido."))
    errores.extend(_contenido(meta, idx))
    tramos = []
    for slot, e in idx.items():
        if slot not in REGLAS["ranuras"]:
            errores.append(_item("motivos", "campo_invalido", detalle=f"espacio de imagen desconocido: «{_limpio(slot)}»."))
        elif not isinstance(e, dict) or not all(_es_int(e.get(k)) for k in ("inicio", "largo")):
            errores.append(_item("motivos", "campo_invalido", detalle=f"la imagen de «{_limpio(slot)}» no está bien descrita."))
        else:
            for k in e:
                if k not in REGLAS["esquema"]["imagen"]:
                    errores.append(_item("motivos", "campo_extra", campo=f"imagenes.{slot}.{k}"))
            tramos.append((e["inicio"], e["largo"], slot, e))
    pos = 0
    for ini, ln, _s, _e in sorted(tramos, key=lambda t: t[0]):
        if ini != pos or ln <= 0:
            pos = -1
            break
        pos += ln
    if tramos and pos != len(blob) or not tramos and blob:
        errores.append(_item("motivos", "bloques"))
    imagenes = {}
    for ini, ln, slot, e in sorted(tramos, key=lambda t: t[2]):
        img = blob[ini:ini + ln]
        if len(img) != ln:
            continue
        if e.get("formato") != "png" or img[:8] != b"\x89PNG\r\n\x1a\n":
            errores.append(_item("motivos", "no_png", espacio=slot))
            continue
        cuadros = e.get("cuadros", 1)
        for codigo, detalle in revisar_png(img, slot, cuadros if _es_int(cuadros) else 0):
            errores.append(_item("motivos", codigo, espacio=slot, detalle=detalle))
        w, h = struct.unpack(">II", img[16:24]) if len(img) >= 24 else (0, 0)
        imagenes[slot] = {"ancho": w, "alto": h, "cuadros": cuadros, "bytes": img}

    # textos y nombres
    for campo, clave in (("nombre", "nombre"), ("autor", "autor"), ("descripcion", "descripcion")):
        _texto(campo, meta.get(clave), errores)
    nombre, autor, version = meta.get("nombre"), meta.get("autor"), meta.get("version")
    for campo, valor in (("nombre", nombre), ("autor", autor)):
        if isinstance(valor, str) and not re.fullmatch(LIM["id_ok"], slug(valor)):
            errores.append(_item("motivos", "nombre_invalido", **REGLAS["campos"][campo], campo_id=campo))
    if isinstance(version, str) and not re.fullmatch(LIM["version_ok"], version, re.ASCII):
        errores.append(_item("motivos", "version_invalida", version=version))
    if isinstance(autor, str) and not oficial and es_nombre_reservado(autor):
        errores.append(_item("motivos", "nombre_reservado"))
    if imagenes:
        avisos.append(_item("avisos", "imagenes_a_mano"))

    colores = meta.get("colores")
    datos.update(nombre=nombre, autor=autor, version=version, descripcion=meta.get("descripcion"), tipo=meta.get("tipo"),
                 colores=colores if isinstance(colores, dict) else {}, imagenes=imagenes,
                 autor_slug=slug(autor) if isinstance(autor, str) else "",
                 tema_id=slug(nombre) if isinstance(nombre, str) else "",
                 # solo es fiable con ok=True: las mismas reglas de arriba ya revisaron su forma y sus límites
                 estilo={k: meta[k] for k in ("fondo", "secciones", "alfa", "ventana", "pausar_animaciones") if k in meta})
    res["ok"] = not errores
    return res


def revisar_catalogo(origen, publicados):
    """Como revisar() y además compara con los temas ya publicados.

    ``publicados``: lista de entradas de catalogo.json (id, nombre, version, sha256, huella_autor).
    Detecta: duplicado (mismo archivo), version_existe, nombre_repetido, nombre_ocupado (otra firma usa
    esa carpeta de autor) y nombre_cambiado (la misma firma ya está registrada con otro nombre).
    """
    res = revisar(origen)
    d = res["datos"]
    if "huella" not in d or not d.get("autor_slug"):
        return res
    nombre = str(d.get("nombre") or "")
    vistos, err = set(), res["errores"]
    for p in publicados:
        partes = str(p.get("id", "")).split("/")
        p_autor, p_tema = (partes[1] if len(partes) == 3 else ""), partes[-1]
        p_huella, otro = (p.get("huella_autor") or "").upper(), p.get("id", "")
        mismo_tema = p_autor == d["autor_slug"] and p_tema == d["tema_id"]
        if p.get("sha256") == d["sha256"]:
            err.append(_item("motivos", "duplicado", otro=otro))
        elif mismo_tema and p.get("version") == d["version"]:
            err.append(_item("motivos", "version_existe", version=d["version"], nombre=nombre))
        elif not mismo_tema and str(p.get("nombre", "")).lower() == nombre.lower():
            err.append(_item("motivos", "nombre_repetido", nombre=nombre, otro=otro))
        if p_autor == d["autor_slug"] and p_huella and p_huella != d["huella"] and "ocupado" not in vistos:
            vistos.add("ocupado")
            err.append(_item("motivos", "nombre_ocupado", autor=d["autor_slug"]))
        if p_huella == d["huella"] and p_autor and p_autor != d["autor_slug"] and "cambiado" not in vistos:
            vistos.add("cambiado")
            err.append(_item("motivos", "nombre_cambiado", registrado=p_autor, autor=d["autor_slug"]))
    res["ok"] = not err
    return res
