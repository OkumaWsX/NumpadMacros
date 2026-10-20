package com.okumawsx.numpadmacros

import org.json.JSONArray
import org.json.JSONObject

/** Posición de una tecla en el dibujo del numpad: [id, etiqueta, col, fila, ancho, alto]. */
data class KeyPos(val id: String, val label: String, val col: Int, val row: Int, val w: Int, val h: Int)

/** Acción de una tecla, tal como la manda el PC. */
data class Act(
    val type: String,
    val title: String = "",
    val mode: String = "overlap",
    val volume: Double = 1.0,
    val lib: String = "",
    val color: Int = -1,
    val combo: String = "",
    val bank: Int = 1,
) {
    val isGlobalType get() = type in BANK_TYPES

    /** Texto corto para dibujar en el botón. */
    fun label(): String = when (type) {
        "file" -> title.ifBlank { "Sonido" }
        "keys" -> comboText(combo)
        "sound_stop" -> "Detener"
        "bank_next" -> "Banco ▸"
        "bank_prev" -> "◂ Banco"
        "bank_go" -> "→ Banco $bank"
        else -> ""
    }

    /** Nombre del icono de la esquina. */
    fun icon(): String = when (type) {
        "file" -> when (mode) {
            "restart" -> "refresh"
            "toggle" -> "play"
            "hold" -> "play"
            else -> "vol"
        }
        "keys" -> "kbd"
        "sound_stop" -> "stop"
        else -> "chev"
    }

    fun toJson(): JSONObject {
        val o = JSONObject().put("type", type)
        when (type) {
            "file" -> o.put("lib", lib).put("mode", mode).put("volume", volume)
            "keys" -> o.put("combo", combo)
            "bank_go" -> o.put("bank", bank)
        }
        // 0–11 = uno de los 12 colores; sin la clave = sin color
        if (color in 0..11) o.put("color", color)
        return o
    }

    companion object {
        val BANK_TYPES = setOf("bank_next", "bank_prev", "bank_go")

        fun from(o: JSONObject?): Act? {
            if (o == null) return null
            val type = o.optString("type", "none")
            if (type == "none" || type.isBlank()) return null
            return Act(
                type = type,
                title = o.optString("title", ""),
                mode = o.optString("mode", "overlap"),
                volume = o.optDouble("volume", 1.0).let { if (it.isNaN()) 1.0 else it },
                lib = o.optString("lib", ""),
                color = o.optInt("color", -1),
                combo = o.optString("combo", ""),
                bank = o.optInt("bank", 1),
            )
        }

        fun comboText(combo: String): String = combo.split("+").filter { it.isNotBlank() }.joinToString(" + ") { part ->
            when (part.lowercase()) {
                "ctrl" -> "Ctrl"; "shift" -> "Shift"; "alt" -> "Alt"; "win" -> "Win"
                else -> part.uppercase()
            }
        }
    }
}

data class Bank(val name: String, val keys: Map<String, Act>)

/** Grupo de teclas que se pueden lanzar desde el celular (virtuales, numpad, fila 1–0). */
data class KeyGroup(val id: String, val name: String, val cols: Int, val rows: Int, val keys: List<KeyPos>)

data class PcState(
    val active: Int = 0,
    val volume: Double = 1.0,
    val banks: List<Bank> = emptyList(),
    val global: Map<String, Act> = emptyMap(),
    val keys: List<KeyPos> = DEFAULT_KEYS,
    val groups: List<KeyGroup> = listOf(KeyGroup("numpad", "Numpad", 4, 5, DEFAULT_KEYS)),
    val paused: Boolean = false,
    /** Botones propios del celular: cuántos hay, si el PC está en «solo celular» y las cantidades posibles. */
    val phoneCount: Int = 24,
    val phoneOnly: Boolean = false,
    val phoneCounts: List<Int> = listOf(12, 24, 36, 48),
) {
    fun group(id: String): KeyGroup = groups.firstOrNull { it.id == id } ?: groups.first()

    /** Etiqueta de una tecla en cualquier grupo. */
    fun labelOf(id: String): String = groups.flatMap { it.keys }.firstOrNull { it.id == id }?.label ?: id

    /** Acción efectiva: primero la capa Global, luego el banco activo (igual que el PC). */
    fun resolve(id: String): Pair<Act?, Boolean> {
        global[id]?.let { return it to true }
        return banks.getOrNull(active)?.keys?.get(id) to false
    }

    fun countSounds() = (banks.flatMap { it.keys.values } + global.values).count { it.type == "file" }
    fun countKeys() = (banks.flatMap { it.keys.values } + global.values).count { it.type == "keys" }

    companion object {
        val DEFAULT_KEYS = listOf(
            KeyPos("45", "NumLk", 0, 0, 1, 1), KeyPos("e0:35", "/", 1, 0, 1, 1), KeyPos("37", "*", 2, 0, 1, 1),
            KeyPos("4a", "−", 3, 0, 1, 1), KeyPos("47", "7", 0, 1, 1, 1), KeyPos("48", "8", 1, 1, 1, 1),
            KeyPos("49", "9", 2, 1, 1, 1), KeyPos("4e", "+", 3, 1, 1, 2), KeyPos("4b", "4", 0, 2, 1, 1),
            KeyPos("4c", "5", 1, 2, 1, 1), KeyPos("4d", "6", 2, 2, 1, 1), KeyPos("4f", "1", 0, 3, 1, 1),
            KeyPos("50", "2", 1, 3, 1, 1), KeyPos("51", "3", 2, 3, 1, 1), KeyPos("e0:1c", "Enter", 3, 3, 1, 2),
            KeyPos("52", "0", 0, 4, 2, 1), KeyPos("53", ".", 2, 4, 1, 1),
        )

        private fun layer(o: JSONObject?): Map<String, Act> {
            val out = LinkedHashMap<String, Act>()
            if (o == null) return out
            for (k in o.keys()) Act.from(o.optJSONObject(k))?.let { out[k] = it }
            return out
        }

        private fun keyList(ka: JSONArray?): List<KeyPos> {
            val keys = mutableListOf<KeyPos>()
            if (ka == null) return keys
            for (i in 0 until ka.length()) {
                val k = ka.optJSONArray(i) ?: continue
                keys.add(KeyPos(k.optString(0), k.optString(1), k.optInt(2), k.optInt(3), k.optInt(4, 1).coerceAtLeast(1), k.optInt(5, 1).coerceAtLeast(1)))
            }
            return keys
        }

        fun from(o: JSONObject): PcState {
            val banks = mutableListOf<Bank>()
            val arr = o.optJSONArray("banks") ?: JSONArray()
            for (i in 0 until arr.length()) {
                val b = arr.optJSONObject(i) ?: continue
                banks.add(Bank(b.optString("name", "Banco ${i + 1}"), layer(b.optJSONObject("keys"))))
            }
            val keys = keyList(o.optJSONArray("keys")).ifEmpty { DEFAULT_KEYS }
            val groups = mutableListOf<KeyGroup>()
            o.optJSONArray("groups")?.let { ga ->
                for (i in 0 until ga.length()) {
                    val g = ga.optJSONObject(i) ?: continue
                    val gk = keyList(g.optJSONArray("keys"))
                    if (gk.isEmpty()) continue
                    val cols = g.optInt("cols", gk.maxOf { it.col + it.w }).coerceAtLeast(1)
                    val rows = g.optInt("rows", gk.maxOf { it.row + it.h }).coerceAtLeast(1)
                    groups.add(KeyGroup(g.optString("id", "g$i"), g.optString("name", "Teclas"), cols, rows, gk))
                }
            }
            // un PC viejo sin "groups": se muestra el numpad (en «solo celular» el PC no manda el numpad)
            if (groups.isEmpty()) groups.add(KeyGroup("numpad", "Numpad", 4, 5, keys))
            val ph = o.optJSONObject("phone")
            val counts = mutableListOf<Int>()
            ph?.optJSONArray("counts")?.let { a -> for (i in 0 until a.length()) counts.add(a.optInt(i)) }
            return PcState(
                active = o.optInt("active", 0),
                volume = o.optDouble("volume", 1.0).let { if (it.isNaN()) 1.0 else it },
                banks = banks,
                global = layer(o.optJSONObject("global")),
                keys = keys,
                groups = groups,
                paused = o.optBoolean("paused", false),
                phoneCount = ph?.optInt("count", 24) ?: 24,
                phoneOnly = ph?.optBoolean("only", false) ?: false,
                phoneCounts = counts.ifEmpty { listOf(12, 24, 36, 48) },
            )
        }
    }
}

data class LibItem(val lib: String, val title: String, val lufs: Double?)

fun parseLibrary(o: JSONObject): List<LibItem> {
    val out = mutableListOf<LibItem>()
    val arr = o.optJSONArray("items") ?: return out
    for (i in 0 until arr.length()) {
        val it = arr.optJSONObject(i) ?: continue
        val l = if (it.isNull("lufs")) null else it.optDouble("lufs").takeIf { d -> !d.isNaN() }
        out.add(LibItem(it.optString("lib"), it.optString("title"), l))
    }
    return out
}

/** PC encontrado por UDP en Wi-Fi o USB. */
data class Found(val id: String, val name: String, val host: String, val port: Int, val app: String, val os: String, val transport: String)

/** A dónde conectarse. transport: "wifi", "usb" o "bt". */
data class Target(
    val id: String = "",
    val name: String = "",
    val hosts: List<String> = emptyList(),
    val port: Int = 47800,
    val bt: String = "",
    val transport: String = "wifi",
    val code: String? = null,
)

/** PC guardado en el celular. */
data class SavedPc(
    val id: String,
    val name: String,
    val token: String,
    val hosts: List<String>,
    val port: Int,
    val bt: String,
    val transport: String,
    val last: Long,
) {
    fun toJson(): JSONObject = JSONObject().put("id", id).put("name", name).put("token", token)
        .put("hosts", JSONArray(hosts)).put("port", port).put("bt", bt).put("transport", transport).put("last", last)

    fun target(code: String? = null) = Target(id, name, hosts, port, bt, transport, code)

    companion object {
        fun from(o: JSONObject): SavedPc {
            val h = o.optJSONArray("hosts") ?: JSONArray()
            return SavedPc(
                o.optString("id"), o.optString("name"), o.optString("token"),
                (0 until h.length()).map { h.optString(it) }.filter { it.isNotBlank() },
                o.optInt("port", 47800), o.optString("bt"), o.optString("transport", "wifi"), o.optLong("last"),
            )
        }
    }
}

fun transportName(t: String) = when (t) {
    "usb" -> "Cable USB"
    "bt" -> "Bluetooth"
    else -> "Wi-Fi"
}

fun ago(ms: Long): String {
    if (ms <= 0) return "nunca"
    val d = (System.currentTimeMillis() - ms) / 1000
    return when {
        d < 90 -> "ahora"
        d < 3600 -> "hace ${d / 60} min"
        d < 86400 -> "hace ${d / 3600} h"
        d < 172800 -> "ayer"
        else -> "hace ${d / 86400} días"
    }
}
