package com.okumawsx.numpadmacros

import android.content.Context
import org.json.JSONArray
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/**
 * Actualizaciones de la app del celular, igual que el escritorio (npm/updater.py):
 * 1. latest(): pregunta a GitHub por las Releases (sin mandar datos del usuario) y busca la
 *    que trae el APK más nuevo («NumpadMacros-Android-<versión>.apk»). Las betas solo si se piden.
 * 2. download(): baja el APK y lo compara con su huella en SHA256SUMS.txt de la misma Release.
 *    Si no coincide, o la Release no trae huella, se borra y no se instala nada.
 * 3. La instalación la hace Android (siempre pide confirmar); los PCs vinculados y los ajustes
 *    se conservan porque el APK nuevo va firmado con la misma llave.
 */
object Updater {
    private const val REPO = "OkumaWsX/NumpadMacros"
    private const val API = "https://api.github.com/repos/$REPO/releases?per_page=15"
    const val RELEASES_URL = "https://github.com/$REPO/releases"
    const val CHECK_EVERY_MS = 24L * 3600 * 1000
    private val APK = Regex("""^NumpadMacros-Android-(\d+(?:\.\d+){1,2})\.apk$""")

    data class Info(
        val version: String,
        val tag: String,
        val notes: List<String>,
        val releaseUrl: String,
        val apkName: String,
        val apkUrl: String,
        val size: Long,
        val sumsUrl: String?,
        val published: String,
        val beta: Boolean,
    )

    class UpdateError(msg: String) : Exception(msg)

    fun parse(v: String): List<Int> {
        val n = Regex("""\d+""").findAll(v.trimStart('v', 'V').substringBefore("-")).map { it.value.toInt() }.take(3).toMutableList()
        while (n.size < 3) n.add(0)
        return n
    }

    /** ¿a es más nueva que b? */
    fun newer(a: String, b: String): Boolean {
        val x = parse(a); val y = parse(b)
        for (i in 0 until 3) if (x[i] != y[i]) return x[i] > y[i]
        return false
    }

    private fun open(url: String, accept: String = "application/vnd.github+json"): HttpURLConnection {
        val c = URL(url).openConnection() as HttpURLConnection
        c.connectTimeout = 10_000
        c.readTimeout = 20_000
        c.instanceFollowRedirects = true
        c.setRequestProperty("User-Agent", "NumpadMacros-Android/$APP_VERSION")
        c.setRequestProperty("Accept", accept)
        return c
    }

    /** La Release con el APK más nuevo (con betas solo si beta = true), o null. */
    fun latest(beta: Boolean): Info? {
        val text = try {
            val c = open(API)
            if (c.responseCode != 200) throw UpdateError("GitHub respondió ${c.responseCode}.")
            c.inputStream.bufferedReader().use { it.readText() }
        } catch (e: UpdateError) {
            throw e
        } catch (e: Exception) {
            throw UpdateError("No pude consultar GitHub. ¿Hay internet?")
        }
        val arr = JSONArray(text)
        var best: Info? = null
        for (i in 0 until arr.length()) {
            val r = arr.optJSONObject(i) ?: continue
            val pre = r.optBoolean("prerelease")
            if (r.optBoolean("draft") || (pre && !beta)) continue
            val assets = r.optJSONArray("assets") ?: continue
            var apk: Triple<String, String, Long>? = null
            var version = ""
            var sums: String? = null
            for (j in 0 until assets.length()) {
                val a = assets.optJSONObject(j) ?: continue
                val name = a.optString("name")
                val url = a.optString("browser_download_url")
                if (name == "SHA256SUMS.txt") sums = url
                APK.find(name)?.let { m -> version = m.groupValues[1]; apk = Triple(name, url, a.optLong("size")) }
            }
            val found = apk ?: continue
            if (best != null && !newer(version, best.version)) continue
            best = Info(
                version = version,
                tag = r.optString("tag_name"),
                notes = notesFrom(r.optString("body")),
                releaseUrl = r.optString("html_url").ifBlank { RELEASES_URL },
                apkName = found.first, apkUrl = found.second, size = found.third,
                sumsUrl = sums,
                published = r.optString("published_at").take(10),
                beta = pre,
            )
        }
        return best
    }

    /** Las notas de la Release como viñetas; primero las que hablan del celular. */
    fun notesFrom(body: String): List<String> {
        val lines = body.lines().map { it.trim() }.filter { it.startsWith("- ") || it.startsWith("* ") }
            .map { it.drop(2).replace("**", "").replace("`", "").replace(Regex("""\[([^\]]+)]\([^)]+\)"""), "$1").trim() }
            .filter { it.isNotBlank() && !it.startsWith("<!--") }
        val phone = lines.filter { Regex("(?i)android|celular|móvil|movil|apk").containsMatchIn(it) }
        return (phone + (lines - phone.toSet())).take(8)
    }

    /** Baja el APK a la caché y comprueba su huella. progress(bajado, total). */
    fun download(ctx: Context, info: Info, progress: (Long, Long) -> Unit): File {
        val sumsUrl = info.sumsUrl ?: throw UpdateError("La versión no trae huella de seguridad (SHA256SUMS.txt): no se instala.")
        val expected = try {
            open(sumsUrl, "*/*").inputStream.bufferedReader().use { it.readText() }.lines()
                .map { it.trim().split(Regex("""\s+"""), limit = 2) }
                .firstOrNull { it.size == 2 && it[1].trimStart('*') == info.apkName }?.get(0)?.lowercase()
        } catch (e: Exception) {
            throw UpdateError("No pude bajar la huella de seguridad. ¿Hay internet?")
        } ?: throw UpdateError("La huella de seguridad no incluye ${info.apkName}: no se instala.")

        val dir = File(ctx.cacheDir, "actualizaciones").apply { mkdirs() }
        dir.listFiles()?.forEach { it.delete() }          // borra descargas viejas
        val out = File(dir, info.apkName)
        val md = MessageDigest.getInstance("SHA-256")
        try {
            val c = open(info.apkUrl, "application/octet-stream")
            if (c.responseCode != 200) throw UpdateError("GitHub respondió ${c.responseCode} al descargar.")
            val total = c.contentLengthLong.takeIf { it > 0 } ?: info.size
            c.inputStream.use { inp ->
                out.outputStream().use { o ->
                    val buf = ByteArray(64 * 1024)
                    var done = 0L
                    var last = 0L
                    while (true) {
                        if (Thread.currentThread().isInterrupted) throw InterruptedException()
                        val n = inp.read(buf)
                        if (n < 0) break
                        o.write(buf, 0, n)
                        md.update(buf, 0, n)
                        done += n
                        if (done - last > 128 * 1024 || done == total) { last = done; progress(done, total) }
                    }
                    progress(done, total)
                }
            }
        } catch (e: UpdateError) {
            out.delete(); throw e
        } catch (e: InterruptedException) {
            out.delete(); throw e
        } catch (e: Exception) {
            out.delete(); throw UpdateError("La descarga se cortó. Revisa tu conexión e inténtalo de nuevo.")
        }
        val got = md.digest().joinToString("") { "%02x".format(it) }
        if (got != expected) {
            out.delete()
            throw UpdateError("El archivo descargado no coincide con el publicado, así que no se instaló nada.")
        }
        // por si acaso: el APK tiene que ser de esta misma app
        val pkg = ctx.packageManager.getPackageArchiveInfo(out.path, 0)?.packageName
        if (pkg != null && pkg != ctx.packageName) {
            out.delete()
            throw UpdateError("El archivo descargado no es de Numpad Macros, así que no se instaló nada.")
        }
        return out
    }
}
