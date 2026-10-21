package com.okumawsx.numpadmacros

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.graphics.luminance

/**
 * Colores de la app. Cambian con el tema elegido (Ajustes → Apariencia), por eso son estado:
 * al cambiar el tema, toda la interfaz se vuelve a dibujar sola.
 */
object C {
    var bg by mutableStateOf(Color(0xFF14161B))
    var panel by mutableStateOf(Color(0xFF1C1F26))
    var panel2 by mutableStateOf(Color(0xFF232730))
    var line by mutableStateOf(Color(0xFF2E333D))
    var text by mutableStateOf(Color(0xFFE9E9EC))
    var muted by mutableStateOf(Color(0xFF9AA0AB))
    var acc by mutableStateOf(Color(0xFFF2A33A))
    /** Texto sobre el acento (botones principales, chip activo). */
    var accDark by mutableStateOf(Color(0xFF1A1306))
    var accSoft by mutableStateOf(Color(0xFF3A2C14))
    var accLine by mutableStateOf(Color(0xFF7A5520))
    var ok by mutableStateOf(Color(0xFF4CC38A))
    var onOk by mutableStateOf(Color(0xFF06210F))
    var okSoft by mutableStateOf(Color(0xFF173528))
    var bad by mutableStateOf(Color(0xFFE5534B))
    var badSoft by mutableStateOf(Color(0xFF3A1A1A))
    var badLine by mutableStateOf(Color(0xFF7A2E2E))
    var badText by mutableStateOf(Color(0xFFFFB4AE))
    var warn by mutableStateOf(Color(0xFFE2B340))
    val blue = Color(0xFF6AA8FF)
    var globalBg by mutableStateOf(Color(0xFF241F36))
    var globalLine by mutableStateOf(Color(0xFF5B4A91))
    var globalText by mutableStateOf(Color(0xFFD9C9FF))
    var padBg by mutableStateOf(Color(0xFF1E222B))
    var padEmpty by mutableStateOf(Color(0xFF171A20))
    var padEmptyLine by mutableStateOf(Color(0xFF20242B))
    var light by mutableStateOf(false)
    /** Transparencias y desenfoque de las píldoras (se apagan con Alto contraste). */
    var glassOn by mutableStateOf(true)
    val scrim = Color(0x9E050608)

    /** Los 12 colores de los botones, en el mismo orden que el PC (`BUTTON_COLORS`); -1 = sin color. */
    val keyColors = listOf(
        Color(0xFFF2A33A), Color(0xFFE2C340), Color(0xFF9BD14A), Color(0xFF4CC38A), Color(0xFF3CC7C0), Color(0xFF6AA8FF),
        Color(0xFF4A6CF0), Color(0xFF9B7FE0), Color(0xFFE06FB8), Color(0xFFE5534B), Color(0xFFB07A4A), Color(0xFF8B909B),
    )
    val keyColorNames = listOf("Naranja", "Amarillo", "Lima", "Verde", "Turquesa", "Celeste", "Azul", "Morado", "Rosa", "Rojo", "Café", "Gris")
    val keyColorOrder = keyColors.indices.toList()
    fun keyColor(i: Int): Color? = keyColors.getOrNull(i)
    fun keyColorName(i: Int): String = keyColorNames.getOrNull(i) ?: "Sin color"

    /** Aplica una paleta (de un tema, de Alto contraste o de AMOLED). */
    fun apply(p: Map<String, Long>) {
        fun c(k: String): Color? = p[k]?.let { Color(it) }
        bg = c("bg")!!; panel = c("panel")!!; panel2 = c("panel2")!!; line = c("line")!!
        text = c("text")!!; muted = c("muted")!!; acc = c("acc")!!; accDark = c("on_acc")!!
        accSoft = c("acc_bg")!!; accLine = c("acc_dim")!!
        ok = c("ok")!!; onOk = c("on_ok") ?: Color(0xFF06210F); bad = c("bad")!!; warn = c("warn") ?: Color(0xFFE2B340)
        light = bg.luminance() > 0.5f
        okSoft = lerp(ok, panel, 0.8f)
        badSoft = c("bad_soft") ?: lerp(bad, panel, 0.82f)
        badLine = c("bad_line") ?: lerp(bad, panel, 0.5f)
        badText = c("bad_text") ?: if (light) bad else lerp(bad, Color.White, 0.5f)
        val key = c("key") ?: c("pad")!!
        padBg = key
        padEmpty = c("pad_empty") ?: lerp(key, bg, 0.55f)
        padEmptyLine = c("pad_empty_line") ?: lerp(line, bg, 0.45f)
        globalBg = c("key_global") ?: c("global_bg")!!
        globalLine = c("key_global_line") ?: c("global_line")!!
        globalText = c("key_global_text") ?: lerp(globalLine, Color.White, 0.6f)
    }
}

/** Temas aprobados (los mismos del escritorio) y las dos opciones solo del celular. */
object Themes {
    val list: Map<String, Map<String, Long>> = linkedMapOf(
        "Original" to mapOf("bg" to 0xFF14161B, "panel" to 0xFF1C1F26, "panel2" to 0xFF232730, "line" to 0xFF2E333D, "text" to 0xFFE9E9EC, "muted" to 0xFF8B909B, "on_acc" to 0xFF1A1306, "acc" to 0xFFF2A33A, "acc_dim" to 0xFF7A5520, "acc_bg" to 0xFF3A2C14, "key" to 0xFF262A33, "key_global" to 0xFF33294A, "key_global_line" to 0xFF7E5FC4, "key_global_text" to 0xFFD9C9FF, "ok" to 0xFF4CC38A, "on_ok" to 0xFF06210F, "bad" to 0xFFE5534B, "warn" to 0xFFE2B340),
        "Medianoche" to mapOf("bg" to 0xFF0B1220, "panel" to 0xFF111A2E, "panel2" to 0xFF18233B, "line" to 0xFF26334F, "text" to 0xFFE6EDF8, "muted" to 0xFF93A1BB, "on_acc" to 0xFF04121C, "acc" to 0xFF4CC2FF, "acc_dim" to 0xFF1E5F80, "acc_bg" to 0xFF0F2B3D, "key" to 0xFF1B2640, "key_global" to 0xFF2B2350, "key_global_line" to 0xFF8A74E0, "key_global_text" to 0xFFDED6FF, "ok" to 0xFF3FD29A, "on_ok" to 0xFF06210F, "bad" to 0xFFFF6B6B, "warn" to 0xFFF5C451),
        "Bosque" to mapOf("bg" to 0xFF0F1712, "panel" to 0xFF15201A, "panel2" to 0xFF1C2A22, "line" to 0xFF2A3B30, "text" to 0xFFE7F0E9, "muted" to 0xFF93A89A, "on_acc" to 0xFF102000, "acc" to 0xFFA6D94A, "acc_dim" to 0xFF56742A, "acc_bg" to 0xFF25331A, "key" to 0xFF1F2D25, "key_global" to 0xFF2F2A42, "key_global_line" to 0xFF8F7BD0, "key_global_text" to 0xFFE0D8FB, "ok" to 0xFF57D38C, "on_ok" to 0xFF06210F, "bad" to 0xFFFF6F61, "warn" to 0xFFF0C75E),
        "Vino" to mapOf("bg" to 0xFF1A0F13, "panel" to 0xFF24141A, "panel2" to 0xFF2E1A22, "line" to 0xFF43262F, "text" to 0xFFF6E9EC, "muted" to 0xFFB39AA2, "on_acc" to 0xFF241600, "acc" to 0xFFE8B54A, "acc_dim" to 0xFF7D5C1E, "acc_bg" to 0xFF3A2915, "key" to 0xFF33202A, "key_global" to 0xFF2C2448, "key_global_line" to 0xFF8E7AD6, "key_global_text" to 0xFFE2DAFE, "ok" to 0xFF5BD08F, "on_ok" to 0xFF06210F, "bad" to 0xFFFF6B70, "warn" to 0xFFF2C14E),
        "Grafito" to mapOf("bg" to 0xFF121212, "panel" to 0xFF1B1B1B, "panel2" to 0xFF242424, "line" to 0xFF333333, "text" to 0xFFECECEC, "muted" to 0xFF9A9A9A, "on_acc" to 0xFFFFFFFF, "acc" to 0xFF2860F0, "acc_dim" to 0xFF1D3F8F, "acc_bg" to 0xFF16213D, "key" to 0xFF2A2A2A, "key_global" to 0xFF312A45, "key_global_line" to 0xFF8D78D8, "key_global_text" to 0xFFDFD6FF, "ok" to 0xFF3CCF8E, "on_ok" to 0xFF06210F, "bad" to 0xFFFF5C5C, "warn" to 0xFFF3C13A),
        "Synthwave" to mapOf("bg" to 0xFF140D22, "panel" to 0xFF1D1331, "panel2" to 0xFF261A3F, "line" to 0xFF3A2A5A, "text" to 0xFFF3EAFF, "muted" to 0xFFA796C4, "on_acc" to 0xFF2A0016, "acc" to 0xFFFF4FA3, "acc_dim" to 0xFF8A2A5A, "acc_bg" to 0xFF3A1430, "key" to 0xFF2A1F45, "key_global" to 0xFF3A1F52, "key_global_line" to 0xFFB07CFF, "key_global_text" to 0xFFEAD9FF, "ok" to 0xFF43E5A8, "on_ok" to 0xFF06210F, "bad" to 0xFFFF5C7A, "warn" to 0xFFFFD166),
        "Océano" to mapOf("bg" to 0xFF0C1719, "panel" to 0xFF112124, "panel2" to 0xFF172B2F, "line" to 0xFF244045, "text" to 0xFFE4F2F2, "muted" to 0xFF8FB0B2, "on_acc" to 0xFF2A0D06, "acc" to 0xFFFF7A59, "acc_dim" to 0xFF8A3D2A, "acc_bg" to 0xFF3A1F18, "key" to 0xFF1A3034, "key_global" to 0xFF2A2748, "key_global_line" to 0xFF8B7FD9, "key_global_text" to 0xFFDDD8FF, "ok" to 0xFF4FD1A1, "on_ok" to 0xFF06210F, "bad" to 0xFFFF6363, "warn" to 0xFFF4C24F),
        "Claro" to mapOf("bg" to 0xFFEEF0F4, "panel" to 0xFFFFFFFF, "panel2" to 0xFFF3F4F7, "line" to 0xFFD5D9E0, "text" to 0xFF1B1E24, "muted" to 0xFF5D6470, "on_acc" to 0xFFFFFFFF, "acc" to 0xFFA85600, "acc_dim" to 0xFFE8B77A, "acc_bg" to 0xFFFFF1DD, "key" to 0xFFE8EAEF, "key_global" to 0xFFECE5FB, "key_global_line" to 0xFF7A5CC9, "key_global_text" to 0xFF3B2A72, "ok" to 0xFF16834F, "on_ok" to 0xFFFFFFFF, "bad" to 0xFFC62F28, "warn" to 0xFF8A6300),
        "Papel" to mapOf("bg" to 0xFFEFE6D6, "panel" to 0xFFF8F2E6, "panel2" to 0xFFEFE5D3, "line" to 0xFFD6C7AB, "text" to 0xFF2B2116, "muted" to 0xFF6B5B45, "on_acc" to 0xFFFFFFFF, "acc" to 0xFF8F4A1C, "acc_dim" to 0xFFCFA27E, "acc_bg" to 0xFFF2DFC9, "key" to 0xFFE7DCC6, "key_global" to 0xFFE6DCF0, "key_global_line" to 0xFF7A5C9E, "key_global_text" to 0xFF3A2752, "ok" to 0xFF2F7A46, "on_ok" to 0xFFFFFFFF, "bad" to 0xFFB23A2A, "warn" to 0xFF7D5A00),
        "Nórdico" to mapOf("bg" to 0xFF242933, "panel" to 0xFF2E3440, "panel2" to 0xFF3B4252, "line" to 0xFF4C566A, "text" to 0xFFECEFF4, "muted" to 0xFFAAB3C5, "on_acc" to 0xFF1B2430, "acc" to 0xFF88C0D0, "acc_dim" to 0xFF3F6470, "acc_bg" to 0xFF33414D, "key" to 0xFF3B4252, "key_global" to 0xFF4A3F5C, "key_global_line" to 0xFFB48EAD, "key_global_text" to 0xFFF3E6FF, "ok" to 0xFFA3BE8C, "on_ok" to 0xFF06210F, "bad" to 0xFFE0707A, "warn" to 0xFFEBCB8B),
        "Atardecer" to mapOf("bg" to 0xFF1C1316, "panel" to 0xFF26191D, "panel2" to 0xFF311F25, "line" to 0xFF4A2E35, "text" to 0xFFFBECE6, "muted" to 0xFFC2A39D, "on_acc" to 0xFF2B1000, "acc" to 0xFFFF8A3D, "acc_dim" to 0xFF8C4A1E, "acc_bg" to 0xFF3D2216, "key" to 0xFF36232A, "key_global" to 0xFF2C2547, "key_global_line" to 0xFF9D86E6, "key_global_text" to 0xFFE4DCFF, "ok" to 0xFF5FD39A, "on_ok" to 0xFF06210F, "bad" to 0xFFFF6B6B, "warn" to 0xFFFFCB57),
    )
    val altoContraste: Map<String, Long> = mapOf("bg" to 0xFF000000, "panel" to 0xFF0A0A0A, "panel2" to 0xFF161616, "line" to 0xFF7A7A7A, "text" to 0xFFFFFFFF, "muted" to 0xFFD0D0D0, "on_acc" to 0xFF000000, "acc" to 0xFFFFD400, "acc_hover" to 0xFFFFE14D, "acc_dim" to 0xFF6B5800, "acc_bg" to 0xFF2B2400, "key" to 0xFF1C1C1C, "key_set" to 0xFF002B4D, "key_set_line" to 0xFF4DB8FF, "key_set_text" to 0xFFFFFFFF, "key_global" to 0xFF2A0F4A, "key_global_line" to 0xFFC08CFF, "key_global_text" to 0xFFFFFFFF, "ok" to 0xFF3DFF8A, "bad" to 0xFFFF5050, "warn" to 0xFFFFD400, "on_ok" to 0xFF06210F)
    val amoled: Map<String, Long> = mapOf("bg" to 0xFF000000, "panel" to 0xFF000000, "panel2" to 0xFF0F0F10, "line" to 0xFF262628, "text" to 0xFFF2F2F2, "muted" to 0xFFA3A3A8, "acc" to 0xFFF2A33A, "on_acc" to 0xFF1A1306, "acc_bg" to 0xFF1F1608, "acc_dim" to 0xFF6B4A1C, "ok" to 0xFF4CC38A, "on_ok" to 0xFF06210F, "bad" to 0xFFFF5C52, "warn" to 0xFFE2B340, "global_bg" to 0xFF150F26, "global_line" to 0xFF7E5FC4, "pad" to 0xFF0D0D0F, "pad_empty" to 0xFF000000, "pad_empty_line" to 0xFF1C1C1F, "bad_soft" to 0xFF1F0807, "bad_line" to 0xFF5C1D1A, "bad_text" to 0xFFFF9D96, "num" to 0xFF8A8A90)

    /** especial: "" (ninguno), "contraste" o "amoled". */
    fun apply(name: String, especial: String, propio: Map<String, Long>? = null) {
        C.glassOn = especial != "contraste"
        C.apply(
            when (especial) {
                "contraste" -> altoContraste
                "amoled" -> amoled
                else -> propio ?: list[name] ?: list.getValue("Original")
            },
        )
    }

    /** Lee los colores de un mensaje "tema" del PC (texto "#rrggbb"). Si faltan los básicos, null. */
    fun fromJson(o: org.json.JSONObject?): Map<String, Long>? {
        if (o == null) return null
        val out = HashMap<String, Long>()
        for (k in o.keys()) {
            val v = o.optString(k).trim().removePrefix("#")
            if (v.length == 6) v.toLongOrNull(16)?.let { out[k] = 0xFF000000L or it }
        }
        val need = listOf("bg", "panel", "panel2", "line", "text", "muted", "acc", "on_acc", "acc_bg", "acc_dim", "ok", "bad", "key", "key_global", "key_global_line")
        return if (need.all { it in out }) out else null
    }
}
