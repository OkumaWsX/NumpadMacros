// SPDX-License-Identifier: LGPL-3.0-or-later
// Copyright (C) 2026 OkumaWsX
// Estado de las pantallas del Publicador (el trabajo pesado va en hilos aparte).
package com.okumawsx.publicador

import android.app.Application
import android.net.Uri
import android.provider.DocumentsContract
import android.provider.OpenableColumns
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

enum class Screen { CONNECT, HOME, CHECKS, REVIEW, PUBLISHING, THEME }

data class Check(val name: String, val state: String = "pending", val detail: String = "")

class Vm(app: Application) : AndroidViewModel(app) {
    val store = Store(app)
    var screen by mutableStateOf(Screen.CONNECT)
    var busy by mutableStateOf(false)

    // conectar
    var connectMsg by mutableStateOf("")
    var connectBad by mutableStateOf(true)

    // inicio
    var user by mutableStateOf("")
    var lastPub by mutableStateOf<String?>(null)
    var releases by mutableStateOf<List<JSONObject>?>(null)
    var homeError by mutableStateOf("")

    // revisión
    val checks = mutableStateListOf<Check>()
    var reviewing by mutableStateOf("")
    var checkFail by mutableStateOf<String?>(null)
    var notes by mutableStateOf("")
    var notesError by mutableStateOf("")
    var beta by mutableStateOf(false)
    var important by mutableStateOf(false)
    var discord by mutableStateOf(true)

    // tema
    var themeJson by mutableStateOf<JSONObject?>(null)
    var themeName by mutableStateOf("")
    var themeMsg by mutableStateOf("")
    var themeBad by mutableStateOf(false)
    var themeKeyInfo by mutableStateOf("")
    var themeOut: ByteArray? = null

    val gh get() = Pub.gh
    val rv get() = Pub.rv

    init {
        val tok = store.token
        if (Pub.state.value?.running == true) {
            screen = Screen.PUBLISHING
        } else if (tok != null) {
            Pub.gh = GitHub(tok)
            showHome()
        }
        refreshKeyInfo()
    }

    private fun io(job: suspend () -> Unit) = viewModelScope.launch(Dispatchers.IO) { job() }
    private suspend fun ui(block: () -> Unit) = withContext(Dispatchers.Main) { block() }

    // ================================================================ conectar
    fun showConnect(error: String = "") {
        connectMsg = error
        connectBad = true
        screen = Screen.CONNECT
    }

    fun saveToken(text: String) {
        val tok = text.trim()
        if (tok.isEmpty()) { connectMsg = "Primero pega el token en el cuadro."; connectBad = true; return }
        if (!tok.startsWith("github_pat_") && !tok.startsWith("ghp_")) {
            connectMsg = "Eso no parece un token de GitHub: debe empezar con «github_pat_»."
            connectBad = true
            return
        }
        busy = true
        connectMsg = "Probando…"
        connectBad = false
        val g = GitHub(tok)
        io {
            try {
                g.checkAccess()
                g.whoami()
                store.token = tok
                ui { Pub.gh = g; busy = false; showHome() }
            } catch (e: Exception) {
                ui { busy = false; connectMsg = e.message ?: e.toString(); connectBad = true }
            }
        }
    }

    // ================================================================ inicio
    fun showHome() {
        if (Pub.state.value?.running == true) { screen = Screen.PUBLISHING; return }
        Pub.state.value = null
        Pub.pkg = null
        screen = Screen.HOME
        releases = null
        homeError = ""
        val g = gh ?: return showConnect()
        io {
            try {
                val who = g.whoami()
                val rels = g.releases(6)
                val last = g.lastPublished()
                ui { user = who; releases = rels; lastPub = vstr(last) }
            } catch (e: Exception) {
                val msg = e.message ?: e.toString()
                ui {
                    if (msg.contains("no acepta") || (e is HttpFail && e.status == 401)) showConnect(msg)
                    else homeError = msg
                }
            }
        }
    }

    // ================================================================ revisar
    private val names = listOf("Leer el archivo", "Es Numpad Macros", "La versión es más nueva",
        "Tiene novedades anotadas", "Comparar con lo publicado")

    private suspend fun mark(i: Int, state: String, detail: String = "") = ui {
        checks[i] = checks[i].copy(state = state, detail = if (detail.isNotEmpty()) detail else checks[i].detail)
    }

    fun openZip(uri: Uri) = startReview(displayName(uri) ?: "archivo.zip") {
        val bytes = getApplication<Application>().contentResolver.openInputStream(uri)?.use { it.readBytes() }
            ?: throw PubError("No pude leer el archivo.")
        Package.fromZip(bytes, displayName(uri) ?: "")
    }

    fun openFolder(tree: Uri) = startReview(treeName(tree)) {
        val (files, name) = readTree(tree)
        Package(files, emptySet(), name, false)
    }

    private fun startReview(label: String, load: () -> Package) {
        if (Pub.state.value?.running == true) { screen = Screen.PUBLISHING; return }
        val g = gh ?: return showConnect()
        checks.clear()
        names.forEach { checks.add(Check(it)) }
        checks[0] = checks[0].copy(state = "run")
        reviewing = label
        checkFail = null
        screen = Screen.CHECKS
        val rv = Review()
        io {
            var step = 0
            try {
                val pkg = load()
                Pub.pkg = pkg
                mark(0, "ok", label)
                step = 1; mark(1, "run")
                if (!pkg.isNumpadMacros()) throw PubError("No es Numpad Macros: el identificador de la app no coincide. " +
                    "Así se evita publicar por error otra aplicación encima de esta.")
                mark(1, "ok", "Mismo identificador de app: se instala encima, no como una app distinta.")
                step = 2; mark(2, "run")
                rv.version = pkg.version()
                rv.published = g.lastPublished()
                val v = rv.version ?: throw PubError("No encontré el número de versión en npm/__init__.py.")
                val p = rv.published
                if (p != null && v <= p) throw PubError("La versión $v no es más nueva que la publicada ($p). " +
                    "Puede que hayas elegido una entrega anterior.")
                rv.kind = kindOf(v, p)
                mark(2, "ok", "$v es mayor que ${vstr(p)}")
                step = 3; mark(3, "run")
                rv.notes = pkg.unreleased() ?: ""
                if (!hasNoteLines(rv.notes)) throw PubError("La sección «Sin publicar» del CHANGELOG está vacía. " +
                    "Pídeme que anote los cambios (no hay nada que mostrar a los usuarios).")
                mark(3, "ok", "${noteLines(rv.notes)} cambios anotados en el CHANGELOG")
                step = 4; mark(4, "run")
                checkNotStale(pkg, g)
                compare(pkg, g, rv)
                val total = rv.added.size + rv.changed.size + rv.deleted.size
                mark(4, "ok", if (total > 0) "$total archivos cambiados" else "El código ya está en GitHub (solo falta publicar)")
                Pub.rv = rv
                kotlinx.coroutines.delay(400)
                ui {
                    notes = rv.notes
                    notesError = ""
                    beta = pkg.betaHint
                    important = false
                    discord = store.discord
                    screen = Screen.REVIEW
                }
            } catch (e: Exception) {
                mark(step, "bad")
                ui { checkFail = e.message ?: e.toString() }
            }
        }
    }

    private fun displayName(uri: Uri): String? = try {
        getApplication<Application>().contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
            ?.use { c -> if (c.moveToFirst()) c.getString(0) else null }
    } catch (e: Exception) {
        uri.lastPathSegment
    }

    private fun treeName(tree: Uri) = DocumentsContract.getTreeDocumentId(tree).substringAfterLast(':').substringAfterLast('/')
        .ifEmpty { "carpeta" }

    /** Todos los archivos de una carpeta elegida (sin .git, cachés ni dependencias). */
    private fun readTree(tree: Uri): Pair<Map<String, ByteArray>, String> {
        val cr = getApplication<Application>().contentResolver
        val out = LinkedHashMap<String, ByteArray>()
        val skip = setOf(".git", "__pycache__", "node_modules", ".gradle", ".venv", ".idea")
        val skipRoot = setOf("build", "dist", "dist-installer", "third_party")
        fun walk(docId: String, prefix: String) {
            val kids = DocumentsContract.buildChildDocumentsUriUsingTree(tree, docId)
            cr.query(kids, arrayOf(DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                DocumentsContract.Document.COLUMN_DISPLAY_NAME, DocumentsContract.Document.COLUMN_MIME_TYPE),
                null, null, null)?.use { c ->
                while (c.moveToNext()) {
                    val id = c.getString(0)
                    val name = c.getString(1)
                    val dir = c.getString(2) == DocumentsContract.Document.MIME_TYPE_DIR
                    if (dir) {
                        if (name in skip || (prefix.isEmpty() && name in skipRoot)) continue
                        walk(id, "$prefix$name/")
                    } else {
                        val u = DocumentsContract.buildDocumentUriUsingTree(tree, id)
                        cr.openInputStream(u)?.use { out[prefix + name] = it.readBytes() }
                    }
                }
            }
        }
        walk(DocumentsContract.getTreeDocumentId(tree), "")
        if (out.isEmpty()) throw PubError("La carpeta está vacía o no se pudo leer.")
        return out to treeName(tree)
    }

    // ================================================================ publicar
    fun discordPreview(): String {
        var extra = if (beta) " (versión de prueba)" else ""
        if (important) extra += " · actualización importante"
        return "🎉 Numpad Macros ${rv?.version}$extra ya está disponible. Abre la app y pulsa «Actualizar», o descárgala en GitHub."
    }

    fun publish() {
        val rv = rv ?: return
        val pkg = Pub.pkg ?: return
        val text = notes.trim()
        if (!hasNoteLines(text)) {
            notesError = "Las notas necesitan al menos una línea que empiece con «- »."
            return
        }
        if (text != rv.notes.trim()) pkg.setUnreleased(text)
        store.discord = discord
        Pub.beta = beta
        Pub.important = important
        Pub.discord = discord
        PublishService.start(getApplication())
        screen = Screen.PUBLISHING
    }

    // ================================================================ tema .npt
    fun refreshKeyInfo() {
        val k = store.themeKey
        themeKeyInfo = if (k == null) "" else try {
            val key = Npt.loadKey(k)
            if (Npt.isOfficial(key)) "Clave oficial de OkumaWsX guardada en este teléfono."
            else "Clave guardada (no es la oficial: el tema no saldrá como oficial)."
        } catch (e: Exception) {
            "La clave guardada no es válida: ${e.message}"
        }
    }

    fun showTheme() {
        themeJson = null
        themeName = ""
        themeMsg = ""
        themeOut = null
        refreshKeyInfo()
        screen = Screen.THEME
    }

    fun pickThemeJson(uri: Uri) {
        themeOut = null
        try {
            val text = getApplication<Application>().contentResolver.openInputStream(uri)!!.use { it.readBytes() }
                .toString(Charsets.UTF_8)
            val t = Npt.checkTheme(JSONObject(text))
            themeJson = JSONObject(text)
            themeName = t.getString("name")
            themeMsg = "Tema «$themeName» de ${t.getString("author")} (versión ${t.getString("version")})."
            themeBad = false
        } catch (e: Exception) {
            themeJson = null
            themeName = ""
            themeMsg = "No se puede usar ese archivo: ${if (e is org.json.JSONException) "no es un tema en JSON" else e.message}"
            themeBad = true
        }
    }

    fun pickThemeKey(uri: Uri) {
        try {
            val raw = getApplication<Application>().contentResolver.openInputStream(uri)!!.use { it.readBytes() }
            Npt.loadKey(raw)
            store.themeKey = raw
            refreshKeyInfo()
            themeBad = false
        } catch (e: Exception) {
            themeMsg = e.message ?: e.toString()
            themeBad = true
        }
    }

    fun forgetThemeKey() {
        store.themeKey = null
        refreshKeyInfo()
    }

    /** Arma el .npt en memoria; luego la pantalla pide dónde guardarlo. */
    fun buildTheme(): Boolean {
        val t = themeJson ?: return false
        val raw = store.themeKey ?: run { themeMsg = "Primero elige tu clave de firma."; themeBad = true; return false }
        return try {
            val data = Npt.pack(t, Npt.loadKey(raw))
            Npt.verify(data)
            themeOut = data
            true
        } catch (e: Exception) {
            themeMsg = "No se pudo crear el tema: ${e.message}"
            themeBad = true
            false
        }
    }

    fun saveTheme(uri: Uri) {
        val data = themeOut ?: return
        try {
            getApplication<Application>().contentResolver.openOutputStream(uri, "wt")!!.use { it.write(data) }
            val (name, official) = Npt.verify(data)
            themeMsg = if (official) "Listo: «$name» quedó guardado como tema oficial (firmado)."
            else "Listo: «$name» quedó guardado (firmado, pero no con la clave oficial)."
            themeBad = false
        } catch (e: Exception) {
            themeMsg = "No se pudo guardar: ${e.message}"
            themeBad = true
        }
    }
}
