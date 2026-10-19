package com.okumawsx.numpadmacros

import android.annotation.SuppressLint
import android.app.Application
import android.bluetooth.BluetoothClass
import android.bluetooth.BluetoothManager
import android.content.Context
import android.net.Uri
import android.os.Build
import android.provider.OpenableColumns
import android.util.Base64
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.io.InputStream
import java.util.concurrent.ConcurrentHashMap

const val APP_VERSION = BuildConfig.VERSION_NAME
const val MAX_UPLOAD = 50L * 1024 * 1024
val AUDIO_EXT = listOf("mp3", "wav", "ogg", "flac", "opus", "aiff", "aif")

enum class Screen { Welcome, Main, Pin, Usb, Bt, Connected, SavedPcs, About }
enum class Tab { Pads, Conn, Settings }
enum class St { Idle, Connecting, Pin, Online, Lost }

data class BtDev(val name: String, val address: String, val computer: Boolean)

/** Estado de una subida de sonido desde el celular. */
data class Upload(
    val phase: String = "elegir",        // elegir, grabando, listo, enviando, hecho, error
    val name: String = "",               // nombre de archivo
    val title: String = "",              // nombre en la biblioteca
    val size: Long = 0,
    val received: Long = 0,
    val msg: String = "",
    val uri: Uri? = null,
    val file: File? = null,
    val seconds: Int = 0,
)

/** Qué tecla se está editando: capa (índice de banco o "global") y tecla. */
data class EditTarget(val layer: Any, val key: String, val label: String)

class AppVm(app: Application) : AndroidViewModel(app) {
    val store = Store(app)

    // ---------------------------------------------------------------- navegación
    var screen by mutableStateOf(if (store.welcomed) Screen.Main else Screen.Welcome)
    var tab by mutableStateOf(if (store.pcs().isEmpty()) Tab.Conn else Tab.Pads)

    // ---------------------------------------------------------------- conexión
    var st by mutableStateOf(St.Idle)
    var pcName by mutableStateOf("")
    var transport by mutableStateOf("wifi")
    var latency by mutableStateOf(-1)
    var lostAttempt by mutableStateOf(0)
    var error by mutableStateOf<String?>(null)
    var pinError by mutableStateOf<String?>(null)
    var toast by mutableStateOf<Pair<String, Boolean>?>(null)
    var firstLink by mutableStateOf(false)

    // ---------------------------------------------------------------- datos del PC
    var state by mutableStateOf(PcState())
    var library by mutableStateOf(listOf<LibItem>())
    var playing by mutableStateOf(mapOf<String, Float>())
    var level by mutableStateOf(-60f)
    var volume by mutableStateOf(1f)

    // ---------------------------------------------------------------- búsqueda
    var found by mutableStateOf(listOf<Found>())
    var scanning by mutableStateOf(false)
    var pcs by mutableStateOf(store.pcs())
    var btDevices by mutableStateOf(listOf<BtDev>())

    // ---------------------------------------------------------------- ajustes
    var layout by mutableStateOf(store.layout)
    var vibrate by mutableStateOf(store.vibrate)
    var keepOn by mutableStateOf(store.keepOn)
    var autoReconnect by mutableStateOf(store.autoReconnect)
    var meter by mutableStateOf(store.meter)

    // ---------------------------------------------------------------- edición
    var group by mutableStateOf("")          // "" = el primer grupo que mande el PC
    var editMode by mutableStateOf(false)
    var fullscreen by mutableStateOf(false)
    var editing by mutableStateOf<EditTarget?>(null)
    var upload by mutableStateOf<Upload?>(null)

    private var link: Link? = null
    private var outbox: Channel<JSONObject>? = null
    private var job: Job? = null
    private var gen = 0
    private var target: Target? = null
    private var stop = false               // la sesión terminó por una razón que no se reintenta
    private var awaitingCode = false
    private var pcId = ""
    private val pings = ConcurrentHashMap<Int, Long>()
    private var volJob: Job? = null
    private var uploadJob: Job? = null
    val recorder = Recorder(app)

    init {
        if (store.autoReconnect) {
            val last = store.pc(store.lastPc) ?: pcs.firstOrNull()
            if (last != null && last.token.isNotBlank()) start(last.target(), reconnect = true)
        }
    }

    val online get() = st == St.Online

    // ================================================================ conexión
    fun connect(t: Target) = start(t, reconnect = false)

    fun connectSaved(pc: SavedPc) = start(pc.target(), reconnect = false)

    fun connectFound(f: Found) {
        val saved = store.pc(f.id)
        val hosts = listOf(f.host) + (saved?.hosts ?: emptyList())
        connect(Target(f.id, f.name, hosts.distinct(), f.port, saved?.bt ?: "", f.transport))
    }

    fun retryNow() {
        val t = target ?: store.pc(store.lastPc)?.target() ?: return
        start(t, reconnect = true)
    }

    fun disconnect() {
        gen++
        job?.cancel()
        closeLink()
        st = St.Idle
        latency = -1
    }

    private fun closeLink() {
        val l = link
        link = null
        outbox?.close()
        outbox = null
        if (l != null) viewModelScope.launch(Dispatchers.IO) { l.close() }
    }

    private fun start(t: Target, reconnect: Boolean) {
        gen++
        val my = gen
        job?.cancel()
        closeLink()
        target = t
        error = null
        pinError = null
        stop = false
        awaitingCode = false
        pcName = t.name
        transport = t.transport
        st = if (reconnect) St.Lost else St.Connecting
        if (reconnect) lostAttempt = 1
        job = viewModelScope.launch(Dispatchers.IO) {
            var attempt = 0
            var retrying = reconnect
            while (isActive && gen == my) {
                val end = session(my)
                if (gen != my) return@launch
                if (stop) return@launch
                if (end == End.CLOSED_ONLINE) {
                    retrying = true
                    attempt = 0
                }
                if (!retrying || !store.autoReconnect && end != End.CLOSED_ONLINE) {
                    withContext(Dispatchers.Main) {
                        if (gen == my) {
                            st = if (end == End.CLOSED_ONLINE) St.Lost else St.Idle
                            if (end != End.CLOSED_ONLINE) error = "No pude conectar con ${target?.name?.ifBlank { "el PC" } ?: "el PC"}. ¿Está encendido y con Numpad Macros abierto?"
                        }
                    }
                    return@launch
                }
                if (!store.autoReconnect) {
                    withContext(Dispatchers.Main) { if (gen == my) { st = St.Lost; lostAttempt = 0 } }
                    return@launch
                }
                attempt++
                withContext(Dispatchers.Main) {
                    if (gen == my) {
                        st = St.Lost
                        lostAttempt = attempt
                    }
                }
                delay(minOf(5000L, 500L shl minOf(attempt - 1, 4)))
            }
        }
    }

    private enum class End { OPEN_FAILED, CLOSED_BEFORE, CLOSED_ONLINE }

    @SuppressLint("MissingPermission")
    private fun open(t: Target): Link {
        if (t.transport == "bt" && t.bt.isNotBlank()) {
            val bm = getApplication<Application>().getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
            val ad = bm.adapter ?: throw IllegalStateException("Este celular no tiene Bluetooth")
            return BtLink.open(ad, t.bt)
        }
        var last: Exception? = null
        for (h in t.hosts) {
            try {
                return TcpLink.open(h, t.port, Discovery.transportFor(h))
            } catch (e: Exception) {
                last = e
            }
        }
        // ¿Cambió la IP? Se busca el mismo PC en la red
        if (t.id.isNotBlank()) {
            for (f in Discovery.scan(1500).filter { it.id == t.id }) {
                try {
                    val l = TcpLink.open(f.host, f.port, f.transport)
                    target = t.copy(hosts = (listOf(f.host) + t.hosts).distinct(), port = f.port)
                    return l
                } catch (e: Exception) {
                    last = e
                }
            }
        }
        throw last ?: IllegalStateException("Sin dirección")
    }

    private suspend fun session(my: Int): End {
        val t = target ?: return End.OPEN_FAILED
        val l = try {
            open(t)
        } catch (e: Exception) {
            return End.OPEN_FAILED
        }
        val box = Channel<JSONObject>(Channel.UNLIMITED)
        var wasOnline = false
        withContext(Dispatchers.Main) {
            if (gen == my) {
                link = l
                outbox = box
                transport = l.transport
            }
        }
        if (gen != my) {
            l.close()
            return End.CLOSED_BEFORE
        }
        val scope = kotlinx.coroutines.CoroutineScope(Dispatchers.IO + Job())
        scope.launch {
            try {
                for (m in box) l.send(m)
            } catch (_: Exception) {
                l.close()
            }
        }
        scope.launch {
            var n = 0
            while (isActive) {
                delay(3000)
                if (st == St.Online) {
                    pings[n] = System.nanoTime()
                    box.trySend(JSONObject().put("t", "ping").put("n", n))
                    n++
                }
            }
        }
        try {
            l.send(
                JSONObject().put("t", "hola").put("v", 1).put("dev", store.deviceId)
                    .put("name", deviceName()).put("app", APP_VERSION),
            )
            while (true) {
                val m = l.read() ?: break
                withContext(Dispatchers.Main) {
                    if (gen == my) {
                        handle(m)
                        if (st == St.Online) wasOnline = true
                    }
                }
            }
        } catch (_: Exception) {
        }
        scope.coroutineContext[Job]?.cancel()
        box.close()
        l.close()
        withContext(Dispatchers.Main) {
            if (gen == my && link === l) {
                link = null
                outbox = null
                latency = -1
            }
        }
        return if (wasOnline) End.CLOSED_ONLINE else End.CLOSED_BEFORE
    }

    private fun deviceName(): String {
        val m = Build.MODEL ?: "Android"
        val b = Build.MANUFACTURER ?: ""
        return if (m.lowercase().startsWith(b.lowercase())) m else "${b.replaceFirstChar { it.uppercase() }} $m".trim()
    }

    private fun sendNow(o: JSONObject) {
        outbox?.trySend(o)
    }

    private fun handle(m: JSONObject) {
        when (m.optString("t")) {
            "reto" -> {
                val nonce = m.optString("nonce")
                pcId = m.optString("pc", target?.id ?: "")
                val name = m.optString("name", "")
                if (name.isNotBlank()) pcName = name
                target = target?.copy(id = pcId, name = pcName)
                val saved = store.pc(pcId)
                val code = target?.code
                if (m.optBoolean("known") && saved != null && saved.token.isNotBlank()) {
                    sendNow(JSONObject().put("t", "prueba").put("mac", Crypto.proof(saved.token, nonce)))
                } else if (code != null) {
                    awaitingCode = true
                    sendNow(JSONObject().put("t", "codigo").put("code", code))
                } else {
                    awaitingCode = true
                    st = St.Pin
                    screen = Screen.Pin
                }
            }
            "bienvenido" -> {
                awaitingCode = false
                val id = m.optString("pc", pcId).ifBlank { pcId }
                val name = m.optString("name", pcName).ifBlank { pcName }
                val token = m.optString("token", "")
                val saved = store.pc(id)
                val t = target ?: Target()
                val l = link
                val hosts = if (l is TcpLink) (listOf(l.where) + t.hosts + (saved?.hosts ?: emptyList())).filter { it.isNotBlank() }.distinct().take(6)
                else (t.hosts + (saved?.hosts ?: emptyList())).distinct()
                val bt = if (l is BtLink) l.where else (t.bt.ifBlank { saved?.bt ?: "" })
                val pc = SavedPc(id, name, token.ifBlank { saved?.token ?: "" }, hosts, t.port, bt, l?.transport ?: t.transport, System.currentTimeMillis())
                store.savePc(pc)
                store.lastPc = id
                pcs = store.pcs()
                target = pc.target()
                pcName = name
                st = St.Online
                lostAttempt = 0
                error = null
                pinError = null
                firstLink = token.isNotBlank()
                if (token.isNotBlank() || screen == Screen.Pin) screen = Screen.Connected
                else if (screen == Screen.Main && tab == Tab.Conn) tab = Tab.Pads
            }
            "rechazado" -> {
                stop = true
                when (m.optString("why")) {
                    "codigo" -> {
                        awaitingCode = true
                        target = target?.copy(code = null)
                        pinError = "Código incorrecto. Revisa el número en tu PC."
                        st = St.Pin
                        screen = Screen.Pin
                    }
                    "olvidado", "prueba" -> {
                        store.pc(pcId)?.let { store.savePc(it.copy(token = "")) }
                        pcs = store.pcs()
                        target = target?.copy(code = null)
                        pinError = "Tu PC ya no reconoce este celular: escribe el código de nuevo."
                        st = St.Pin
                        screen = Screen.Pin
                    }
                    "desactivado" -> {
                        st = St.Idle
                        error = "En tu PC está apagado «Permitir conexiones» (pestaña Dispositivos)."
                        if (screen != Screen.Main) screen = Screen.Main
                        tab = Tab.Conn
                    }
                    else -> {
                        st = St.Idle
                        error = "El PC rechazó la conexión."
                    }
                }
            }
            "estado" -> {
                state = PcState.from(m)
                if (volJob?.isActive != true) volume = state.volume.toFloat()
            }
            "biblioteca" -> library = parseLibrary(m)
            "sonando" -> {
                val k = m.optJSONObject("keys")
                val map = HashMap<String, Float>()
                if (k != null) for (key in k.keys()) map[key] = k.optDouble(key, 0.0).toFloat()
                playing = map
                level = m.optDouble("level", -60.0).toFloat().let { if (it.isNaN()) -60f else it }
            }
            "subida" -> onUploadMsg(m)
            "aviso" -> toast = m.optString("text") to m.optBoolean("bad")
            "pong" -> {
                val sent = pings.remove(m.optInt("n", -1))
                if (sent != null) latency = ((System.nanoTime() - sent) / 1_000_000).toInt()
            }
        }
    }

    // ================================================================ código de vinculación
    fun submitPin(code: String) {
        pinError = null
        val t = (target ?: return).copy(code = code)
        target = t
        if (link != null && awaitingCode) {
            sendNow(JSONObject().put("t", "codigo").put("code", code))
        } else {
            start(t, reconnect = false)
            st = St.Pin
        }
    }

    fun cancelPin() {
        disconnect()
        screen = Screen.Main
        tab = Tab.Conn
    }

    fun handleQr(text: String?): Boolean {
        if (text.isNullOrBlank()) return false
        val u = try { Uri.parse(text.trim()) } catch (_: Exception) { null }
        if (u == null || u.scheme != "nmacros" || u.host != "vincular") {
            toast = "Ese código QR no es de Numpad Macros." to true
            return false
        }
        val hosts = (u.getQueryParameter("h") ?: "").split(",").map { it.trim() }.filter { it.isNotEmpty() }
        if (hosts.isEmpty()) return false
        val port = u.getQueryParameter("p")?.toIntOrNull() ?: TCP_PORT
        val code = u.getQueryParameter("c")
        val name = u.getQueryParameter("n") ?: hosts.first()
        val id = u.getQueryParameter("id") ?: ""
        store.welcomed = true
        screen = Screen.Main
        tab = Tab.Conn
        connect(Target(id, name, hosts, port, store.pc(id)?.bt ?: "", Discovery.transportFor(hosts.first()), code))
        return true
    }

    fun connectManual(ip: String) {
        val clean = ip.trim()
        if (clean.isEmpty()) return
        val parts = clean.split(":")
        val port = parts.getOrNull(1)?.toIntOrNull() ?: TCP_PORT
        connect(Target("", parts[0], listOf(parts[0]), port, "", Discovery.transportFor(parts[0])))
    }

    // ================================================================ búsqueda
    fun scan() {
        if (scanning) return
        scanning = true
        viewModelScope.launch(Dispatchers.IO) {
            val r = Discovery.scan()
            withContext(Dispatchers.Main) {
                found = r
                scanning = false
            }
        }
    }

    @SuppressLint("MissingPermission")
    fun loadBonded() {
        try {
            val bm = getApplication<Application>().getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
            val ad = bm.adapter
            if (ad == null) {
                btDevices = emptyList()
                return
            }
            btDevices = ad.bondedDevices.map {
                val major = it.bluetoothClass?.majorDeviceClass ?: -1
                BtDev(it.name ?: it.address, it.address, major == BluetoothClass.Device.Major.COMPUTER)
            }.sortedWith(compareBy({ !it.computer }, { it.name.lowercase() }))
        } catch (_: SecurityException) {
            btDevices = emptyList()
        }
    }

    fun btEnabled(): Boolean = try {
        val bm = getApplication<Application>().getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
        bm.adapter?.isEnabled == true
    } catch (_: Exception) {
        false
    }

    fun connectBt(d: BtDev) {
        val saved = pcs.firstOrNull { it.bt.equals(d.address, ignoreCase = true) }
        connect(Target(saved?.id ?: "", saved?.name ?: d.name, saved?.hosts ?: emptyList(), saved?.port ?: TCP_PORT, d.address, "bt"))
    }

    fun forget(pc: SavedPc) {
        store.forget(pc.id)
        pcs = store.pcs()
        if (target?.id == pc.id) disconnect()
    }

    // ================================================================ botonera
    fun press(key: String, down: Boolean) {
        if (!online) return
        sendNow(JSONObject().put("t", "tecla").put("key", key).put("down", down))
    }

    fun selectBank(i: Int) {
        if (!online) return
        state = state.copy(active = i)
        sendNow(JSONObject().put("t", "banco").put("i", i))
    }

    fun stopAll() = sendNow(JSONObject().put("t", "detener"))

    fun setVol(v: Float) {
        volume = v
        if (volJob?.isActive == true) return
        volJob = viewModelScope.launch {
            delay(90)
            sendNow(JSONObject().put("t", "volumen").put("v", volume.toDouble()))
        }
    }

    fun volDone() {
        viewModelScope.launch {
            delay(120)
            sendNow(JSONObject().put("t", "volumen").put("v", volume.toDouble()))
        }
    }

    fun preview(lib: String) = sendNow(JSONObject().put("t", "escuchar").put("lib", lib))

    fun assign(layer: Any, key: String, act: Act?) {
        sendNow(
            JSONObject().put("t", "asignar").put("layer", layer).put("key", key)
                .put("act", act?.toJson() ?: JSONObject.NULL),
        )
        // se ve al instante; el PC confirma con un "estado" nuevo
        val a = act
        state = if (layer == "global") {
            state.copy(global = state.global.toMutableMap().apply { if (a == null) remove(key) else put(key, a) })
        } else {
            val i = layer as Int
            state.copy(banks = state.banks.mapIndexed { idx, b ->
                if (idx != i) b else b.copy(keys = b.keys.toMutableMap().apply { if (a == null) remove(key) else put(key, a) })
            })
        }
    }

    fun refresh() {
        sendNow(JSONObject().put("t", "pedir").put("what", "estado"))
        sendNow(JSONObject().put("t", "pedir").put("what", "biblioteca"))
    }

    // ================================================================ ajustes
    fun setLayoutPref(v: String) { layout = v; store.layout = v }

    /** Cuántos botones propios tiene el celular (se guarda en el PC). */
    fun setPhoneCount(n: Int) = sendNow(JSONObject().put("t", "botones").put("n", n))
    fun setVibratePref(v: Boolean) { vibrate = v; store.vibrate = v }
    fun setKeepOnPref(v: Boolean) { keepOn = v; store.keepOn = v }
    fun setAutoPref(v: Boolean) { autoReconnect = v; store.autoReconnect = v }
    fun setMeterPref(v: Boolean) { meter = v; store.meter = v }

    fun finishWelcome() {
        store.welcomed = true
        screen = Screen.Main
        tab = if (pcs.isEmpty()) Tab.Conn else Tab.Pads
    }

    // ================================================================ subir sonidos
    /** Acción con la que queda asignado el sonido subido (la arma la hoja de edición). */
    var uploadAssign: Act? = null

    fun openUpload(assign: Act?) {
        uploadAssign = assign
        upload = Upload()
    }

    fun closeUpload() {
        if (upload?.phase == "grabando") recorder.cancel()
        uploadJob?.cancel()
        upload = null
    }

    fun pickedUri(uri: Uri) {
        val cr = getApplication<Application>().contentResolver
        var name = "sonido"
        var size = -1L
        try {
            cr.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { c ->
                if (c.moveToFirst()) {
                    val ni = c.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    val si = c.getColumnIndex(OpenableColumns.SIZE)
                    if (ni >= 0) name = c.getString(ni) ?: name
                    if (si >= 0 && !c.isNull(si)) size = c.getLong(si)
                }
            }
        } catch (_: Exception) {}
        if (!name.contains('.')) {
            val ext = when (cr.getType(uri)) {
                "audio/mpeg" -> "mp3"; "audio/wav", "audio/x-wav" -> "wav"; "audio/ogg" -> "ogg"
                "audio/flac", "audio/x-flac" -> "flac"; "audio/opus" -> "opus"; else -> ""
            }
            if (ext.isNotEmpty()) name = "$name.$ext"
        }
        val ext = name.substringAfterLast('.', "").lowercase()
        val title = name.substringBeforeLast('.').replace('_', ' ').trim().replaceFirstChar { it.uppercase() }
        if (ext in AUDIO_EXT) {
            upload = if (size > MAX_UPLOAD) Upload(phase = "error", name = name, msg = "El archivo pesa más de 50 MB.")
            else Upload(phase = "listo", name = name, title = title, size = size, uri = uri)
            return
        }
        // Formato que el PC no abre (m4a, aac, 3gp, amr…): se convierte a WAV aquí
        val wavName = name.substringBeforeLast('.').ifBlank { "sonido" } + ".wav"
        upload = Upload(phase = "convirtiendo", name = wavName, title = title)
        uploadJob = viewModelScope.launch(Dispatchers.IO) {
            try {
                val f = File(getApplication<Application>().cacheDir, "convertido.wav")
                Decoder.toWav(getApplication(), uri, f) { p ->
                    viewModelScope.launch(Dispatchers.Main) { upload = upload?.copy(received = (p * 100).toLong(), size = 100) }
                }
                withContext(Dispatchers.Main) {
                    upload = if (f.length() > MAX_UPLOAD) Upload(phase = "error", name = wavName, msg = "Convertido a WAV pesa más de 50 MB. Prueba con un sonido más corto.")
                    else Upload(phase = "listo", name = wavName, title = title, size = f.length(), file = f)
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    upload = Upload(phase = "error", name = name, msg = "No pude convertir «$name» a un formato que tu PC entienda (${e.message ?: "error"}).")
                }
            }
        }
    }

    fun startRecording() {
        try {
            recorder.start()
            upload = Upload(phase = "grabando")
            viewModelScope.launch {
                while (upload?.phase == "grabando") {
                    delay(250)
                    upload = upload?.copy(seconds = recorder.seconds())
                    if (recorder.seconds() >= 60) stopRecording()
                }
            }
        } catch (e: Exception) {
            upload = Upload(phase = "error", msg = "No pude usar el micrófono: ${e.message ?: e}")
        }
    }

    fun stopRecording() {
        val f = recorder.stop()
        upload = if (f == null) Upload(phase = "error", msg = "La grabación quedó vacía.")
        else {
            val stamp = java.text.SimpleDateFormat("HHmmss", java.util.Locale.US).format(java.util.Date())
            Upload(phase = "listo", name = "grabacion-$stamp.wav", title = "Grabación " + stamp.substring(0, 2) + ":" + stamp.substring(2, 4), size = f.length(), file = f)
        }
    }

    fun setUploadTitle(t: String) {
        upload = upload?.copy(title = t)
    }

    /** Envía el archivo al PC en trozos; al terminar lo asigna a la tecla que se estaba editando. */
    fun sendUpload(assign: Act?) {
        val u = upload ?: return
        val l = link ?: run {
            upload = u.copy(phase = "error", msg = "No hay conexión con el PC.")
            return
        }
        val ed = editing
        upload = u.copy(phase = "enviando", received = 0)
        uploadJob = viewModelScope.launch(Dispatchers.IO) {
            try {
                val cr = getApplication<Application>().contentResolver
                val size = when {
                    u.file != null -> u.file.length()
                    u.size >= 0 -> u.size
                    else -> cr.openInputStream(u.uri!!)?.use { countBytes(it) } ?: 0L
                }
                if (size <= 0) throw IllegalStateException("El archivo está vacío")
                if (size > MAX_UPLOAD) throw IllegalStateException("El archivo pesa más de 50 MB")
                withContext(Dispatchers.Main) { upload = upload?.copy(size = size) }
                l.send(JSONObject().put("t", "subir_ini").put("name", u.name).put("size", size).put("title", u.title.ifBlank { u.name }))
                val md = Crypto.sha256()
                val input: InputStream = if (u.file != null) u.file.inputStream() else cr.openInputStream(u.uri!!)
                    ?: throw IllegalStateException("No pude abrir el archivo")
                input.use { inp ->
                    val buf = ByteArray(192 * 1024)
                    var seq = 0
                    while (isActive) {
                        var n = 0
                        while (n < buf.size) {
                            val r = inp.read(buf, n, buf.size - n)
                            if (r < 0) break
                            n += r
                        }
                        if (n <= 0) break
                        md.update(buf, 0, n)
                        l.send(JSONObject().put("t", "subir_parte").put("seq", seq++).put("data", Base64.encodeToString(buf, 0, n, Base64.NO_WRAP)))
                        if (upload?.phase == "error") return@launch
                        if (n < buf.size) break
                    }
                }
                val fin = JSONObject().put("t", "subir_fin").put("sha256", Crypto.hex(md.digest()))
                if (assign != null && ed != null) {
                    fin.put("assign", JSONObject().put("layer", ed.layer).put("key", ed.key).put("act", assign.toJson()))
                }
                l.send(fin)
            } catch (e: Exception) {
                withContext(Dispatchers.Main) { upload = upload?.copy(phase = "error", msg = e.message ?: "No se pudo enviar") }
            }
        }
    }

    private fun countBytes(i: InputStream): Long {
        val b = ByteArray(65536)
        var t = 0L
        while (true) {
            val r = i.read(b)
            if (r < 0) return t
            t += r
        }
    }

    private fun onUploadMsg(m: JSONObject) {
        val u = upload ?: return
        if (!m.optBoolean("ok", true)) {
            upload = u.copy(phase = "error", msg = m.optString("why", "El PC no aceptó el archivo."))
            return
        }
        if (m.optBoolean("fin")) {
            upload = u.copy(phase = "hecho", received = u.size, title = m.optString("title", u.title))
            toast = "«${m.optString("title", u.title)}» quedó en la biblioteca de tu PC." to false
            return
        }
        upload = u.copy(received = m.optLong("recibido", u.received))
    }

    override fun onCleared() {
        recorder.cancel()
        disconnect()
        super.onCleared()
    }
}
