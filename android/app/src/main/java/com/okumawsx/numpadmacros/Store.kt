package com.okumawsx.numpadmacros

import android.content.Context
import org.json.JSONArray
import java.util.UUID

/** Lo que el celular recuerda: PCs vinculados y ajustes. */
class Store(ctx: Context) {
    private val p = ctx.getSharedPreferences("numpadmacros", Context.MODE_PRIVATE)

    val deviceId: String
        get() {
            var id = p.getString("dev", null)
            if (id == null) {
                id = UUID.randomUUID().toString()
                p.edit().putString("dev", id).apply()
            }
            return id
        }

    fun pcs(): List<SavedPc> {
        val s = p.getString("pcs", "[]") ?: "[]"
        return try {
            val a = JSONArray(s)
            (0 until a.length()).mapNotNull { a.optJSONObject(it)?.let(SavedPc::from) }.sortedByDescending { it.last }
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun writePcs(list: List<SavedPc>) {
        val a = JSONArray()
        list.forEach { a.put(it.toJson()) }
        p.edit().putString("pcs", a.toString()).apply()
    }

    fun savePc(pc: SavedPc) = writePcs(pcs().filter { it.id != pc.id } + pc)
    fun forget(id: String) = writePcs(pcs().filter { it.id != id })
    fun pc(id: String) = pcs().firstOrNull { it.id == id }

    var lastPc: String
        get() = p.getString("last", "") ?: ""
        set(v) = p.edit().putString("last", v).apply()

    var welcomed: Boolean
        get() = p.getBoolean("welcomed", false)
        set(v) = p.edit().putBoolean("welcomed", v).apply()

    var layout: String
        get() = p.getString("layout", "numpad") ?: "numpad"
        set(v) = p.edit().putString("layout", v).apply()

    var vibrate: Boolean
        get() = p.getBoolean("vibrate", true)
        set(v) = p.edit().putBoolean("vibrate", v).apply()

    var keepOn: Boolean
        get() = p.getBoolean("keepOn", true)
        set(v) = p.edit().putBoolean("keepOn", v).apply()

    var autoReconnect: Boolean
        get() = p.getBoolean("autoRe", true)
        set(v) = p.edit().putBoolean("autoRe", v).apply()

    var meter: Boolean
        get() = p.getBoolean("meter", true)
        set(v) = p.edit().putBoolean("meter", v).apply()

    /** Tema elegido (nombre de la lista de temas). */
    var tema: String
        get() = p.getString("tema", "Original") ?: "Original"
        set(v) = p.edit().putString("tema", v).apply()

    /** Opción especial: "" (ninguna), "contraste" o "amoled". */
    var especial: String
        get() = p.getString("especial", "") ?: ""
        set(v) = p.edit().putString("especial", v).apply()

    /** Colores de un tema propio que mandó el PC (JSON), o "" si el tema es de la lista. */
    var temaPc: String
        get() = p.getString("temaPc", "") ?: ""
        set(v) = p.edit().putString("temaPc", v).apply()

    // ---------------------------------------------------------------- actualizaciones
    var updAuto: Boolean
        get() = p.getBoolean("updAuto", true)
        set(v) = p.edit().putBoolean("updAuto", v).apply()

    var updBeta: Boolean
        get() = p.getBoolean("updBeta", false)
        set(v) = p.edit().putBoolean("updBeta", v).apply()

    /** Cuándo se buscó por última vez (ms). */
    var updLast: Long
        get() = p.getLong("updLast", 0L)
        set(v) = p.edit().putLong("updLast", v).apply()

    /** Versión que el usuario dejó para después («Ahora no»): no se vuelve a avisar sola. */
    var updSkip: String
        get() = p.getString("updSkip", "") ?: ""
        set(v) = p.edit().putString("updSkip", v).apply()
}
