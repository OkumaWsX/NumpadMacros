// SPDX-License-Identifier: LGPL-3.0-or-later
// Copyright (C) 2026 OkumaWsX
// GitHub, revisar, subir y seguir al robot «Publicar versión».
// Misma lógica que tools/publicador/nucleo.py del Publicador de escritorio.
package com.okumawsx.publicador

import android.util.Base64
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.TimeUnit

const val API = "https://api.github.com"

class HttpFail(val status: Int, msg: String) : PubError("GitHub respondió $status: $msg")

class GitHub(token: String, val repo: String = REPO) {
    val token = token.trim()

    private val json = "application/json".toMediaType()

    fun call(method: String, path: String, body: Any? = null, ok: Set<Int> = setOf(200, 201, 204)): Any? {
        val url = if (path.startsWith("http")) path else API + path
        val rb = body?.toString()?.toRequestBody(json)
        val req = Request.Builder().url(url)
            .header("Authorization", "Bearer $token")
            .header("Accept", "application/vnd.github+json")
            .header("X-GitHub-Api-Version", "2022-11-28")
            .header("User-Agent", "NumpadMacros-Publicador-Android")
            .method(method, rb ?: if (method == "POST" || method == "PATCH") ByteArray(0).toRequestBody(json) else null)
            .build()
        val (status, raw) = try {
            client.newCall(req).execute().use { r -> r.code to (r.body?.string() ?: "") }
        } catch (e: IOException) {
            throw PubError("No pude conectar con GitHub (${e.message}). ¿Hay internet?")
        }
        if (status !in ok) {
            val msg = try { JSONObject(raw).optString("message", "") } catch (e: Exception) { raw.take(200) }
            throw HttpFail(status, msg)
        }
        if (raw.isBlank()) return null
        return if (raw.trimStart().startsWith("[")) JSONArray(raw) else JSONObject(raw)
    }

    fun obj(method: String, path: String, body: Any? = null) = call(method, path, body) as JSONObject
    fun arr(path: String) = call("GET", path) as JSONArray
    fun r(path: String) = "/repos/$repo$path"

    // ---- comprobaciones
    fun whoami(): String = obj("GET", "/user").optString("login", "?")

    /** Lanza PubError con una explicación si al token le faltan permisos. */
    fun checkAccess(): String {
        try {
            call("GET", r(""))
        } catch (e: HttpFail) {
            if (e.status == 401 || e.status == 403) throw PubError("GitHub no acepta el token (¿lo copiaste completo? ¿venció?).")
            if (e.status == 404) throw PubError("El token no tiene acceso al repositorio $repo. Al crearlo, en «Repository access» elige NumpadMacros.")
            throw e
        }
        try {
            call("GET", r("/actions/workflows/$WORKFLOW"))
        } catch (e: HttpFail) {
            if (e.status == 404) return "falta-robot"
            if (e.status == 401 || e.status == 403) throw PubError("Al token le falta el permiso «Actions: Read and write».")
            throw e
        }
        return "ok"
    }

    // ---- versiones publicadas
    fun releases(n: Int = 20): List<JSONObject> {
        val a = arr(r("/releases?per_page=$n"))
        return (0 until a.length()).map { a.getJSONObject(it) }.filter { !it.optBoolean("draft") }
    }

    fun lastPublished(): Ver? {
        var best: Ver? = null
        for (rel in releases()) {
            val v = Ver.parse(rel.optString("tag_name"))
            if (v != null && (best == null || v > best)) best = v
        }
        try {
            val tags = arr(r("/tags?per_page=50"))
            for (i in 0 until tags.length()) {
                val v = Ver.parse(tags.getJSONObject(i).optString("name"))
                if (v != null && (best == null || v > best)) best = v
            }
        } catch (_: HttpFail) {
        }
        return best
    }

    /** "ahead", "identical", "behind" o "diverged"; null si GitHub no conoce base. */
    fun compare(base: String, head: String = BRANCH): String? = try {
        obj("GET", r("/compare/$base...$head")).optString("status")
    } catch (e: HttpFail) {
        if (e.status == 404 || e.status == 422) null else throw e
    }

    // ---- árbol del repositorio
    fun head(): Pair<String, String> {
        val commit = obj("GET", r("/git/ref/heads/$BRANCH")).getJSONObject("object").getString("sha")
        val tree = obj("GET", r("/git/commits/$commit")).getJSONObject("tree").getString("sha")
        return commit to tree
    }

    fun remoteFiles(treeSha: String): Map<String, Pair<String, String>> {
        val data = obj("GET", r("/git/trees/$treeSha?recursive=1"))
        if (data.optBoolean("truncated")) throw PubError("El repositorio es demasiado grande para compararlo.")
        val t = data.getJSONArray("tree")
        val out = HashMap<String, Pair<String, String>>()
        for (i in 0 until t.length()) {
            val e = t.getJSONObject(i)
            if (e.optString("type") == "blob") out[e.getString("path")] = e.getString("sha") to e.getString("mode")
        }
        return out
    }

    companion object {
        val client: OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(90, TimeUnit.SECONDS)
            .writeTimeout(90, TimeUnit.SECONDS)
            .build()
    }
}

// ============================================================================ revisar
/** Resultado de revisar un paquete contra lo publicado. */
class Review {
    var version: Ver? = null
    var published: Ver? = null
    var kind = ""
    var notes = ""
    var added = listOf<String>()
    var changed = listOf<String>()
    var deleted = listOf<String>()
    var local: Map<String, Pair<ByteArray, String>> = emptyMap()
    var head = ""
    var tree = ""
    var remote: Map<String, Pair<String, String>> = emptyMap()
}

/** Evita subir una entrega más antigua que el código que ya está en GitHub (se desharían cambios posteriores). */
fun checkNotStale(pkg: Package, gh: GitHub) {
    val base = pkg.baseCommit()
    if (base == null) {
        if (pkg.fromZip) throw PubError(
            "Este archivo es una entrega antigua (no dice de qué versión del código salió). " +
                "Usa la entrega más reciente que te pasé.")
        return
    }
    val status = gh.compare(base)
    if (status == "ahead" || status == "diverged") throw PubError(
        "Este archivo es más antiguo que el código que ya está en GitHub: subirlo desharía cambios posteriores. " +
            "Usa la entrega más reciente (borra las anteriores para no confundirlas).")
}

fun compare(pkg: Package, gh: GitHub, rv: Review) {
    rv.local = pkg.files()
    val (h, t) = gh.head()
    rv.head = h
    rv.tree = t
    rv.remote = gh.remoteFiles(t)
    val added = ArrayList<String>()
    val changed = ArrayList<String>()
    for ((path, v) in rv.local) {
        val hit = rv.remote[path]
        if (hit == null) added.add(path)
        else if (hit.first != gitBlobSha(v.first) || hit.second != v.second) changed.add(path)
    }
    // lo que nunca se sube (ENTREGA.txt, compilados…) tampoco se borra de GitHub
    rv.deleted = rv.remote.keys.filter { it !in rv.local && !pkg.ignored(it) }.sorted()
    rv.added = added.sorted()
    rv.changed = changed.sorted()
}

fun hasNoteLines(text: String) = text.lines().any { it.trim().startsWith("-") || it.trim().startsWith("*") }
fun noteLines(text: String) = text.lines().count { it.trim().startsWith("-") || it.trim().startsWith("*") }

// ============================================================================ subir
/** Sube el código como un commit en main. Devuelve el sha (o null si no había cambios). */
fun upload(pkg: Package, gh: GitHub, rv: Review, version: Ver, progress: (String) -> Unit): String? {
    for (attempt in 0 until 2) {
        compare(pkg, gh, rv)
        val todo = rv.added + rv.changed
        if (todo.isEmpty() && rv.deleted.isEmpty()) return null
        val entries = JSONArray()
        todo.forEachIndexed { i, path ->
            val (data, mode) = rv.local.getValue(path)
            progress("Subiendo archivos (${i + 1} de ${todo.size})…")
            val blob = gh.obj("POST", gh.r("/git/blobs"), JSONObject()
                .put("content", Base64.encodeToString(data, Base64.NO_WRAP)).put("encoding", "base64"))
            entries.put(JSONObject().put("path", path).put("mode", mode).put("type", "blob").put("sha", blob.getString("sha")))
        }
        for (path in rv.deleted) {
            entries.put(JSONObject().put("path", path).put("mode", rv.remote.getValue(path).second)
                .put("type", "blob").put("sha", JSONObject.NULL))
        }
        progress("Guardando la versión en GitHub…")
        val tree = gh.obj("POST", gh.r("/git/trees"), JSONObject().put("base_tree", rv.tree).put("tree", entries))
        val commit = gh.obj("POST", gh.r("/git/commits"), JSONObject()
            .put("message", "Numpad Macros $version (desde el Publicador)")
            .put("tree", tree.getString("sha"))
            .put("parents", JSONArray().put(rv.head)))
        try {
            gh.call("PATCH", gh.r("/git/refs/heads/$BRANCH"),
                JSONObject().put("sha", commit.getString("sha")).put("force", false))
            return commit.getString("sha")
        } catch (e: HttpFail) {
            if (e.status == 422 && attempt == 0) continue        // main cambió mientras tanto: reintentar
            if ((e.status == 403 || e.status == 404) && todo.any { it.startsWith(".github/workflows/") }) {
                throw PubError("Al token le falta el permiso «Workflows: Read and write» (hace falta para subir los archivos del robot).")
            }
            throw e
        }
    }
    throw PubError("No se pudo guardar: el repositorio cambió mientras subía. Vuelve a intentarlo.")
}

// ============================================================================ robot
private fun isoUtc(ms: Long): String =
    SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }.format(Date(ms))

/** Inicia «Publicar versión». Devuelve la hora (UTC, ISO) del inicio. */
fun startRobot(gh: GitHub, version: Ver, beta: Boolean, important: Boolean, discord: Boolean): String {
    val started = isoUtc(System.currentTimeMillis() - 5000)
    fun yes(v: Boolean) = if (v) "true" else "false"     // GitHub recibe los sí/no como texto
    val body = JSONObject().put("ref", BRANCH).put("inputs", JSONObject()
        .put("tipo", "automatico").put("version", version.toString())
        .put("beta", yes(beta)).put("importante", yes(important)).put("discord", yes(discord)))
    for (i in 0 until 12) {        // recién subido, GitHub tarda unos segundos en ver el robot
        try {
            gh.call("POST", gh.r("/actions/workflows/$WORKFLOW/dispatches"), body)
            return started
        } catch (e: HttpFail) {
            if ((e.status == 404 || e.status == 422) && i < 11) {
                Thread.sleep(5000)
                continue
            }
            if (e.status == 403) throw PubError("Al token le falta el permiso «Actions: Read and write».")
            throw e
        }
    }
    return started
}

fun findRun(gh: GitHub, since: String): JSONObject? {
    val runs = gh.obj("GET", gh.r("/actions/workflows/$WORKFLOW/runs?event=workflow_dispatch&per_page=10"))
        .optJSONArray("workflow_runs") ?: return null
    for (i in 0 until runs.length()) {
        val run = runs.getJSONObject(i)
        if (run.optString("created_at") >= since) return run
    }
    return null
}

data class Stage(val id: String, val label: String, val keys: List<String>)

// Pasos que muestra el Publicador -> cómo reconocer el trabajo del robot
val STAGES = listOf(
    Stage("prep", "Revisar la versión y las novedades", listOf("preparar")),
    Stage("win", "Pruebas y compilar Windows (instalador + portátil)", listOf("windows")),
    Stage("lin", "Compilar Linux", listOf("ubuntu", "linux")),
    Stage("mac", "Compilar macOS", listOf("macos")),
    Stage("pub", "Crear la Release + huellas de seguridad", listOf("publicar")),
)

data class RunStatus(
    val state: String,                                  // running | success | failure
    val stages: Map<String, Pair<Float, String>>,       // id -> (fracción, done|failed|running|pending)
    val url: String,
    val failed: String?,
    val discord: String?,
)

fun runStatus(gh: GitHub, runId: Long): RunStatus {
    val run = gh.obj("GET", gh.r("/actions/runs/$runId"))
    val ja = gh.obj("GET", gh.r("/actions/runs/$runId/jobs?per_page=50")).optJSONArray("jobs") ?: JSONArray()
    val jobs = (0 until ja.length()).map { ja.getJSONObject(it) }
    val stages = LinkedHashMap<String, Pair<Float, String>>()
    var failed: String? = null
    var discord: String? = null
    fun stepsOf(j: JSONObject): List<JSONObject> {
        val s = j.optJSONArray("steps") ?: return emptyList()
        return (0 until s.length()).map { s.getJSONObject(it) }
    }
    for (st in STAGES) {
        val job = jobs.firstOrNull { j -> st.keys.any { j.optString("name").lowercase().contains(it) } }
        if (job == null) {
            stages[st.id] = 0f to "pending"
            continue
        }
        val steps = stepsOf(job)
        val done = steps.count { it.optString("status") == "completed" }
        val frac = if (steps.isNotEmpty()) done.toFloat() / steps.size
        else if (job.optString("status") == "completed") 1f else 0.05f
        val concl = job.optString("conclusion")
        val state = when {
            concl == "success" -> "done"
            concl in setOf("failure", "cancelled", "timed_out") -> "failed"
            job.optString("status") == "in_progress" -> "running"
            else -> "pending"
        }
        if (state == "failed" && failed == null) {
            val bad = steps.firstOrNull { it.optString("conclusion") == "failure" }?.optString("name") ?: ""
            failed = st.label + if (bad.isNotEmpty()) ": $bad" else ""
        }
        stages[st.id] = (if (state == "done") 1f else frac) to state
        if (st.id == "pub") {
            steps.firstOrNull { it.optString("name").lowercase().contains("discord") }?.let {
                discord = it.optString("conclusion").ifEmpty { null }
            }
        }
    }
    val concl = run.optString("conclusion")
    var state = if (run.optString("status") != "completed") "running" else if (concl == "success") "success" else "failure"
    // Si la Release se creó, la versión está publicada aunque haya fallado solo el anuncio
    val pub = jobs.firstOrNull { it.optString("name").lowercase().contains("publicar") }
    if (state == "failure" && pub != null && stepsOf(pub).any {
            it.optString("name").lowercase().contains("release") && it.optString("conclusion") == "success"
        }) {
        state = "success"
        stages["pub"] = 1f to "done"
        failed = null
    }
    return RunStatus(state, stages, run.optString("html_url"), failed, discord)
}

fun releaseAssets(gh: GitHub, version: Ver): Pair<String, List<Pair<String, Long>>> {
    val rel = gh.obj("GET", gh.r("/releases/tags/v$version"))
    val a = rel.optJSONArray("assets") ?: JSONArray()
    return rel.optString("html_url") to (0 until a.length()).map {
        val o = a.getJSONObject(it)
        o.getString("name") to o.optLong("size")
    }
}
