// SPDX-License-Identifier: LGPL-3.0-or-later
// Copyright (C) 2026 OkumaWsX
// Una versión entregada (NumpadMacros-codigo_X.Y.Z.zip), leída en memoria.
// Es la misma lógica que tools/publicador/nucleo.py (clase Package) del Publicador de escritorio.
package com.okumawsx.publicador

import java.io.ByteArrayInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.util.zip.ZipInputStream

const val REPO = "OkumaWsX/NumpadMacros"
const val APP_ID = "8F3C6A52-5E0B-4C6E-9B7B-1D2A9F0E7A11"      // el mismo de npm/about.py y del instalador
const val WORKFLOW = "publicar.yml"
const val BRANCH = "main"
const val TOKEN_URL = "https://github.com/settings/personal-access-tokens/new?name=Publicador%20Numpad%20Macros" +
    "&description=Publicar%20versiones%20de%20Numpad%20Macros&expires_in=366" +
    "&contents=write&actions=write&workflows=write&metadata=read"

// Archivos que nunca se suben (además de lo que diga .gitignore)
val NEVER = listOf(
    ".git/*", "*/__pycache__/*", "__pycache__/*", "*.pyc", ".venv/*", "build/*", "dist/*",
    "dist-installer/*", "third_party/*", "interception.dll", "notas.md", "resumen.txt", ".DS_Store",
    "*/.DS_Store", "Thumbs.db", "ENTREGA.txt",
)

open class PubError(message: String, val step: Int = -1) : Exception(message)

// ============================================================================ versión
data class Ver(val a: Int, val b: Int, val c: Int) : Comparable<Ver> {
    override fun compareTo(other: Ver) = compareValuesBy(this, other, { it.a }, { it.b }, { it.c })
    override fun toString() = "$a.$b.$c"

    companion object {
        private val RE = Regex("""v?(\d+)\.(\d+)\.(\d+)""")
        fun parse(text: String?): Ver? {
            val m = RE.matchEntire((text ?: "").trim()) ?: return null
            return Ver(m.groupValues[1].toInt(), m.groupValues[2].toInt(), m.groupValues[3].toInt())
        }
    }
}

fun vstr(v: Ver?) = v?.toString() ?: "ninguna"

fun kindOf(new: Ver, old: Ver?): String = when {
    old == null -> "Primera versión publicada"
    new.a > old.a -> "Versión grande"
    new.b > old.b -> "Mejora (funciones nuevas)"
    else -> "Corrección de errores"
}

fun gitBlobSha(data: ByteArray): String {
    val md = MessageDigest.getInstance("SHA-1")
    md.update("blob ${data.size}\u0000".toByteArray())
    md.update(data)
    return md.digest().joinToString("") { "%02x".format(it) }
}

// ============================================================================ fnmatch (como Python)
object Glob {
    private val cache = HashMap<String, Regex>()

    fun match(name: String, pattern: String): Boolean =
        cache.getOrPut(pattern) { Regex(translate(pattern), RegexOption.DOT_MATCHES_ALL) }.matches(name)

    /** Igual que fnmatch.translate: * y ? también cruzan «/». */
    fun translate(pat: String): String {
        val sb = StringBuilder()
        var i = 0
        val n = pat.length
        while (i < n) {
            val c = pat[i]
            i++
            when (c) {
                '*' -> sb.append(".*")
                '?' -> sb.append(".")
                '[' -> {
                    var j = i
                    if (j < n && pat[j] == '!') j++
                    if (j < n && pat[j] == ']') j++
                    while (j < n && pat[j] != ']') j++
                    if (j >= n) {
                        sb.append("\\[")
                    } else {
                        var stuff = pat.substring(i, j).replace("\\", "\\\\")
                        i = j + 1
                        stuff = when {
                            stuff.startsWith("!") -> "^" + stuff.substring(1)
                            stuff.startsWith("^") -> "\\" + stuff
                            else -> stuff
                        }
                        sb.append("[").append(stuff).append("]")
                    }
                }
                else -> sb.append(Regex.escape(c.toString()))
            }
        }
        return sb.toString()
    }
}

// ============================================================================ zip
/** Rutas del zip con permiso de ejecución (bits Unix en el directorio central). */
fun zipExecBits(data: ByteArray): Set<String> {
    val out = HashSet<String>()
    val buf = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN)
    var eocd = -1
    var i = data.size - 22
    val stop = maxOf(0, data.size - 22 - 65535)
    while (i >= stop) {
        if (buf.getInt(i) == 0x06054b50) { eocd = i; break }
        i--
    }
    if (eocd < 0) return out
    val count = buf.getShort(eocd + 10).toInt() and 0xffff
    var p = buf.getInt(eocd + 16)
    repeat(count) {
        if (p < 0 || p + 46 > data.size || buf.getInt(p) != 0x02014b50) return out
        val nameLen = buf.getShort(p + 28).toInt() and 0xffff
        val extraLen = buf.getShort(p + 30).toInt() and 0xffff
        val commentLen = buf.getShort(p + 32).toInt() and 0xffff
        val ext = buf.getInt(p + 38)
        val name = String(data, p + 46, nameLen, Charsets.UTF_8).replace('\\', '/')
        if (((ext ushr 16) and 0b001_001_001) != 0) out.add(name)
        p += 46 + nameLen + extraLen + commentLen
    }
    return out
}

/** Una entrega: desde un .zip ([fromZip]) o desde la carpeta del proyecto ([Package] con sus archivos). */
class Package(raw: Map<String, ByteArray>, rawExec: Set<String>, sourceName: String, val fromZip: Boolean) {
    private val all = LinkedHashMap<String, ByteArray>()    // ruta (sin la carpeta raíz) -> contenido
    private val exec = HashSet<String>()
    val betaHint: Boolean
    var patterns: List<String> = emptyList()
        private set

    companion object {
        fun fromZip(zipBytes: ByteArray, sourceName: String): Package {
            val raw = LinkedHashMap<String, ByteArray>()
            try {
                ZipInputStream(ByteArrayInputStream(zipBytes)).use { z ->
                    while (true) {
                        val e = z.nextEntry ?: break
                        val name = e.name.replace('\\', '/')
                        if (name.startsWith("/") || name.split("/").contains("..")) {
                            throw PubError("El zip trae rutas no válidas.")
                        }
                        if (!e.isDirectory) raw[name] = z.readBytes()
                    }
                }
            } catch (e: PubError) {
                throw e
            } catch (e: Exception) {
                throw PubError("Elige el .zip con el código (NumpadMacros-codigo_X.Y.Z.zip).")
            }
            if (raw.isEmpty()) throw PubError("Elige el .zip con el código (NumpadMacros-codigo_X.Y.Z.zip).")
            return Package(raw, zipExecBits(zipBytes), sourceName, true)
        }
    }

    init {
        val about = raw.keys.filter {
            it.endsWith("npm/about.py") && (it == "npm/about.py" || it.endsWith("/npm/about.py")) &&
                it.split("/").none { p -> p == ".git" || p == "__pycache__" || p == "node_modules" }
        }.minByOrNull { it.length }
            ?: throw PubError("Este archivo no es Numpad Macros: no encontré su código (npm/about.py).")
        val prefix = about.removeSuffix("npm/about.py")          // "" o "NumpadMacros-3.4.1-beta/"
        for ((k, v) in raw) {
            if (!k.startsWith(prefix)) continue
            val rel = k.substring(prefix.length)
            all[rel] = v
            if (k in rawExec) exec.add(rel)
        }
        // «-beta» en el nombre del zip o de su carpeta: se sugiere publicar como beta
        betaHint = (sourceName + "/" + prefix).lowercase().contains("-beta")
    }

    fun has(rel: String) = all.containsKey(rel)
    fun read(rel: String): String = all[rel]?.toString(Charsets.UTF_8) ?: throw PubError("Falta $rel en el archivo.")
    private fun readOrNull(rel: String): String? = all[rel]?.toString(Charsets.UTF_8)

    // ---- comprobaciones
    /** Commit del que salió la entrega (ENTREGA.txt), o null. */
    fun baseCommit(): String? {
        val text = readOrNull("ENTREGA.txt") ?: return null
        return Regex("""^commit=([0-9a-f]{40})\s*$""", RegexOption.MULTILINE).find(text)?.groupValues?.get(1)
    }

    fun hasEntrega() = has("ENTREGA.txt")

    fun appId(): String? = readOrNull("npm/about.py")?.let {
        Regex("""APP_ID\s*=\s*"([^"]+)"""").find(it)?.groupValues?.get(1)
    }

    fun installerId(): String? = readOrNull("installer/NumpadMacros.iss")?.let {
        Regex("""AppId=\{\{([0-9A-Fa-f-]+)\}""").find(it)?.groupValues?.get(1)?.uppercase()
    }

    fun isNumpadMacros(): Boolean {
        val ids = setOfNotNull(appId(), installerId())
        return ids.isNotEmpty() && ids == setOf(APP_ID)
    }

    fun version(): Ver? = readOrNull("npm/__init__.py")?.let {
        Ver.parse(Regex("""__version__\s*=\s*"([^"]+)"""").find(it)?.groupValues?.get(1))
    }

    private val head = Regex("""^## \[Sin publicar\][^\n]*\n""", setOf(RegexOption.MULTILINE, RegexOption.IGNORE_CASE))
    private val next = Regex("""^## \[""", RegexOption.MULTILINE)

    /** Texto de la sección «## [Sin publicar]» del CHANGELOG. */
    fun unreleased(): String? {
        val text = readOrNull("CHANGELOG.md") ?: return null
        val m = head.find(text) ?: return null
        val rest = text.substring(m.range.last + 1)
        val n = next.find(rest)
        return rest.substring(0, n?.range?.first ?: rest.length).trim('\n')
    }

    fun setUnreleased(body: String) {
        val text = read("CHANGELOG.md")
        val m = head.find(text) ?: return
        val start = m.range.last + 1
        val rest = text.substring(start)
        val n = next.find(rest)
        val end = start + (n?.range?.first ?: rest.length)
        val new = text.substring(0, start) + body.trim('\n') + "\n\n" + text.substring(end)
        all["CHANGELOG.md"] = new.toByteArray(Charsets.UTF_8)
    }

    // ---- archivos
    fun ignored(rel: String, pats: List<String> = patterns): Boolean {
        val parts = rel.split("/")
        val base = parts.last()
        for (raw in NEVER + pats) {
            val p = raw.trimEnd('/')
            if (Glob.match(rel, p) || Glob.match(rel, "$p/*") ||
                parts.dropLast(1).any { Glob.match(it, p) } || Glob.match(base, p)) return true
        }
        return false
    }

    /** {ruta: (contenido, modo)} de todo lo que se sube. */
    fun files(): Map<String, Pair<ByteArray, String>> {
        val pats = ArrayList<String>()
        readOrNull(".gitignore")?.lineSequence()?.forEach { line0 ->
            val line = line0.trim()
            if (line.isNotEmpty() && !line.startsWith("#") && !line.startsWith("!")) pats.add(line.trimStart('/'))
        }
        patterns = pats
        val out = LinkedHashMap<String, Pair<ByteArray, String>>()
        for ((rel, data0) in all) {
            if (ignored(rel, pats)) continue
            var data = data0
            val probe = minOf(data.size, 8000)
            if ((0 until probe).none { data[it] == 0.toByte() }) {     // texto: GitHub guarda los finales como LF
                data = crlfToLf(data)
            }
            val execb = rel in exec || rel.endsWith(".sh")
            out[rel] = data to (if (execb) "100755" else "100644")
        }
        return out
    }

    private fun crlfToLf(d: ByteArray): ByteArray {
        val out = java.io.ByteArrayOutputStream(d.size)
        var i = 0
        while (i < d.size) {
            if (d[i] == '\r'.code.toByte() && i + 1 < d.size && d[i + 1] == '\n'.code.toByte()) { i++; continue }
            out.write(d[i].toInt())
            i++
        }
        return out.toByteArray()
    }
}
