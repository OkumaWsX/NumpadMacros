package com.okumawsx.numpadmacros

import android.os.Build
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.BlurEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.TileMode
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.graphics.layer.GraphicsLayer
import androidx.compose.ui.graphics.layer.drawLayer
import androidx.compose.ui.graphics.rememberGraphicsLayer
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.positionInRoot
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/*
 * Vidrio esmerilado para las píldoras flotantes, sin librerías.
 *
 * La pantalla se dibuja en una capa (glassSource). Cada píldora (glass) vuelve a dibujar
 * esa capa desenfocada justo detrás de ella y le pone encima el color del tema translúcido.
 * El desenfoque usa el efecto nativo de Android 12+; en celulares más antiguos, y con
 * Alto contraste, la píldora queda solo translúcida (más opaca, para que se lea bien).
 */

class GlassState internal constructor(internal val source: GraphicsLayer, internal val blurred: GraphicsLayer) {
    internal var origin = Offset.Zero
    internal var size = IntSize.Zero
}

val LocalGlass = staticCompositionLocalOf<GlassState?> { null }

/** Espacio que hay que dejar al final de una pantalla para que la barra flotante no tape nada. */
val LocalNavSpace = compositionLocalOf { 0.dp }

@Composable
fun rememberGlass(): GlassState {
    val a = rememberGraphicsLayer()
    val b = rememberGraphicsLayer()
    return remember(a, b) { GlassState(a, b) }
}

/** Lo que va detrás de las píldoras (con su fondo incluido). */
fun Modifier.glassSource(g: GlassState): Modifier = this
    .onGloballyPositioned { g.origin = it.positionInRoot() }
    .drawWithContent {
        g.size = IntSize(size.width.toInt(), size.height.toInt())
        g.source.record { this@drawWithContent.drawContent() }
        drawLayer(g.source)
    }

val canBlur: Boolean get() = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S

/** Fondo de vidrio: desenfoque de lo que hay detrás + color del tema translúcido. */
@Composable
fun Modifier.glass(shape: Shape, tint: Color, radius: Dp = 22.dp): Modifier {
    val g = LocalGlass.current
    val pos = remember { object { var v = Offset.Zero } }
    val blur = g != null && canBlur && C.glassOn
    val color = when {
        !C.glassOn -> tint.copy(alpha = 1f)
        blur -> tint
        else -> tint.copy(alpha = maxOf(tint.alpha, 0.93f))
    }
    return this
        .onGloballyPositioned { pos.v = it.positionInRoot() }
        .clip(shape)
        .drawBehind {
            if (blur && g != null && g.size.width > 0) {
                val r = radius.toPx()
                g.blurred.renderEffect = BlurEffect(r, r, TileMode.Clamp)
                g.blurred.record(this, layoutDirection, g.size) { drawLayer(g.source) }
                translate(g.origin.x - pos.v.x, g.origin.y - pos.v.y) { drawLayer(g.blurred) }
            }
            drawRect(color)
        }
}

private val glassLine get() = C.text.copy(alpha = if (C.glassOn) 0.11f else 0.35f)
private val shadowColor get() = if (C.light) Color(0x38281E0A) else Color(0x99000000)

/** Superficie de píldora flotante: sombra suave, vidrio y borde fino. */
@Composable
fun Modifier.pillSurface(shape: Shape = CircleShape, elevation: Dp = 14.dp, tint: Color = C.panel.copy(alpha = 0.66f)): Modifier =
    this.shadow(elevation, shape, clip = false, ambientColor = shadowColor, spotColor = shadowColor)
        .glass(shape, tint)
        .border(1.dp, glassLine, shape)

/**
 * Riel de vidrio con opciones: la elegida se ve como una píldora clara encima
 * (selector de grupo, pestañas Sonido · Atajo · Otro).
 */
@Composable
fun SegRail(items: List<String>, selected: Int, onSelect: (Int) -> Unit, modifier: Modifier = Modifier, height: Dp = 34.dp, fontSize: TextUnit = 12.5.sp) {
    Row(
        modifier.fillMaxWidth().clip(CircleShape)
            .background(C.panel.copy(alpha = if (C.glassOn) 0.6f else 1f))
            .border(1.dp, glassLine, CircleShape).padding(3.dp),
        horizontalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        items.forEachIndexed { i, name ->
            val on = i == selected
            Box(
                Modifier.weight(1f).height(height)
                    .then(if (on) Modifier.shadow(4.dp, CircleShape, ambientColor = shadowColor, spotColor = shadowColor) else Modifier)
                    .clip(CircleShape)
                    .background(if (on) (if (C.glassOn) C.text.copy(alpha = 0.13f) else C.panel2) else Color.Transparent)
                    .then(if (on && !C.glassOn) Modifier.border(1.dp, C.acc, CircleShape) else Modifier)
                    .clickable(role = Role.Tab) { onSelect(i) }
                    .semantics { this.selected = on },
                contentAlignment = Alignment.Center,
            ) { T(name, fontSize, if (on) C.text else C.muted, if (on) FontWeight.ExtraBold else FontWeight.Medium, lines = 1) }
        }
    }
}
