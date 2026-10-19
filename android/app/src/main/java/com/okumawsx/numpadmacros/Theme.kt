package com.okumawsx.numpadmacros

import androidx.compose.ui.graphics.Color

// Paleta del diseño aprobado (igual a la app de escritorio)
object C {
    val bg = Color(0xFF14161B)
    val panel = Color(0xFF1C1F26)
    val panel2 = Color(0xFF232730)
    val line = Color(0xFF2E333D)
    val text = Color(0xFFE9E9EC)
    val muted = Color(0xFF9AA0AB)
    val acc = Color(0xFFF2A33A)
    val accDark = Color(0xFF1A1306)
    val accSoft = Color(0xFF3A2C14)
    val accLine = Color(0xFF7A5520)
    val ok = Color(0xFF4CC38A)
    val okSoft = Color(0xFF173528)
    val bad = Color(0xFFE5534B)
    val badSoft = Color(0xFF3A1A1A)
    val badLine = Color(0xFF7A2E2E)
    val badText = Color(0xFFFFB4AE)
    val blue = Color(0xFF6AA8FF)
    val purple = Color(0xFF9B7FE0)
    val globalBg = Color(0xFF241F36)
    val globalLine = Color(0xFF5B4A91)
    val padBg = Color(0xFF1E222B)
    val padEmpty = Color(0xFF171A20)
    val padEmptyLine = Color(0xFF20242B)
    val scrim = Color(0x9E050608)

    // Colores que el usuario puede dar a cada botón (índice 0–5)
    val keyColors = listOf(acc, ok, blue, Color(0xFFC87CFF), bad, Color(0xFFE2B340))
    fun keyColor(i: Int) = keyColors[((i % keyColors.size) + keyColors.size) % keyColors.size]
}
