package com.okumawsx.numpadmacros

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Icono de trazo del diseño (24x24). */
@Composable
fun NIcon(name: String, size: Dp = 20.dp, color: Color = C.text, stroke: Float = 1.8f, label: String? = null) {
    val path = remember(name) { PathParser().parsePathString(IconPaths.all[name] ?: "").toPath() }
    val mod = if (label != null) Modifier.semantics { contentDescription = label } else Modifier
    Canvas(mod.size(size)) {
        val k = this.size.width / 24f
        scale(k, pivot = Offset.Zero) {
            drawPath(path, color, style = Stroke(width = stroke, cap = StrokeCap.Round, join = StrokeJoin.Round))
        }
    }
}

@Composable
fun T(
    text: String, size: TextUnit = 14.sp, color: Color = C.text, weight: FontWeight = FontWeight.Normal,
    modifier: Modifier = Modifier, align: TextAlign? = null, lines: Int = Int.MAX_VALUE, lh: TextUnit = TextUnit.Unspecified,
) {
    Text(
        text, modifier = modifier, color = color, fontSize = size, fontWeight = weight, textAlign = align,
        maxLines = lines, overflow = TextOverflow.Ellipsis, lineHeight = lh,
    )
}

enum class Kind { Primary, Ghost, Danger, Link, Ok }

@Composable
fun NButton(
    text: String, onClick: () -> Unit, modifier: Modifier = Modifier, kind: Kind = Kind.Primary,
    icon: String? = null, height: Dp = 50.dp, fontSize: TextUnit = 15.sp, enabled: Boolean = true,
) {
    val (bg, fg, border) = when (kind) {
        Kind.Primary -> Triple(C.acc, C.accDark, Color.Transparent)
        Kind.Ghost -> Triple(C.panel2, C.text, C.line)
        Kind.Danger -> Triple(Color.Transparent, C.badText, C.badLine)
        Kind.Link -> Triple(Color.Transparent, C.acc, Color.Transparent)
        Kind.Ok -> Triple(C.ok, Color(0xFF06210F), Color.Transparent)
    }
    val shape = RoundedCornerShape(14.dp)
    Row(
        modifier
            .heightIn(min = height)
            .clip(shape)
            .background(if (enabled) bg else bg.copy(alpha = 0.4f))
            .border(1.dp, border, shape)
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick)
            .padding(horizontal = 16.dp),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) {
            NIcon(icon, 18.dp, fg)
            Spacer(Modifier.width(8.dp))
        }
        T(text, fontSize, fg, if (kind == Kind.Primary || kind == Kind.Ok) FontWeight.ExtraBold else FontWeight.SemiBold, lines = 1)
    }
}

@Composable
fun IconBtn(icon: String, label: String, onClick: () -> Unit, bg: Color = C.panel2, color: Color = C.text, size: Dp = 44.dp) {
    Box(
        Modifier.size(size).clip(RoundedCornerShape(14.dp)).background(bg)
            .clickable(role = Role.Button, onClick = onClick).semantics { contentDescription = label },
        contentAlignment = Alignment.Center,
    ) { NIcon(icon, 22.dp, color) }
}

@Composable
fun Chip(text: String, on: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier, height: Dp = 40.dp, round: Dp = 12.dp) {
    val shape = RoundedCornerShape(round)
    Box(
        modifier.heightIn(min = height).clip(shape)
            .background(if (on) C.acc else C.panel2)
            .border(1.dp, if (on) Color.Transparent else C.line, shape)
            .clickable(role = Role.Button, onClick = onClick)
            .padding(horizontal = 14.dp),
        contentAlignment = Alignment.Center,
    ) {
        T(text, 13.sp, if (on) C.accDark else C.text, if (on) FontWeight.ExtraBold else FontWeight.SemiBold, lines = 1)
    }
}

@Composable
fun Toggle(on: Boolean) {
    Box(
        Modifier.size(46.dp, 28.dp).clip(RoundedCornerShape(14.dp)).background(if (on) C.acc else Color(0xFF3A3F4A)),
    ) {
        Box(
            Modifier.align(if (on) Alignment.CenterEnd else Alignment.CenterStart).padding(3.dp)
                .size(22.dp).clip(CircleShape).background(if (on) C.accDark else C.text),
        )
    }
}

@Composable
fun SectionLabel(text: String) {
    T(text.uppercase(), 12.sp, C.muted, FontWeight.Bold, Modifier.padding(top = 6.dp))
}

@Composable
fun Logo(size: Dp = 32.dp) {
    val cell = size / 5
    Box(
        Modifier.size(size).clip(RoundedCornerShape(size / 4)).background(C.panel2),
        contentAlignment = Alignment.Center,
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(size / 16)) {
            for (r in 0 until 3) Row(horizontalArrangement = Arrangement.spacedBy(size / 16)) {
                for (c in 0 until 3) {
                    val i = r * 3 + c
                    Box(Modifier.size(cell).clip(RoundedCornerShape(2.dp)).background(if (i == 0 || i == 5 || i == 8) C.acc else Color(0xFF8B909B)))
                }
            }
        }
    }
}

/** Fila tocable con icono, título y subtítulo (lista de PCs, ajustes). */
@Composable
fun RowItem(
    icon: String, title: String, sub: String, onClick: () -> Unit,
    iconColor: Color = C.text, iconBg: Color = C.panel2, border: Color = C.line,
    right: @Composable (() -> Unit)? = null,
) {
    val shape = RoundedCornerShape(16.dp)
    Row(
        Modifier.fillMaxWidth().clip(shape).background(C.panel).border(1.dp, border, shape)
            .clickable(role = Role.Button, onClick = onClick).padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(42.dp).clip(RoundedCornerShape(12.dp)).background(iconBg), contentAlignment = Alignment.Center) {
            NIcon(icon, 22.dp, iconColor)
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            T(title, 15.sp, weight = FontWeight.Bold, lines = 1)
            T(sub, 12.5.sp, C.muted, lines = 2)
        }
        if (right != null) {
            Spacer(Modifier.width(8.dp))
            right()
        }
    }
}

@Composable
fun InfoBox(text: String) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(C.panel2).padding(12.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        NIcon("info", 18.dp, C.muted)
        T(text, 12.5.sp, C.muted, lh = 18.sp)
    }
}

@Composable
fun BackBar(title: String, onBack: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(start = 12.dp, end = 12.dp, top = 12.dp, bottom = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        IconBtn("back", "Volver", onBack, bg = Color.Transparent)
        Spacer(Modifier.width(10.dp))
        T(title, 16.sp, weight = FontWeight.Bold)
    }
}

@Composable
fun Field(value: String, onChange: (String) -> Unit, placeholder: String, modifier: Modifier = Modifier, icon: String? = null, number: Boolean = false, accent: Boolean = false) {
    val shape = RoundedCornerShape(12.dp)
    Row(
        modifier.fillMaxWidth().heightIn(min = 46.dp).clip(shape).background(C.panel2)
            .border(1.dp, if (accent) C.acc else Color.Transparent, shape).padding(horizontal = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) {
            NIcon(icon, 18.dp, C.muted)
            Spacer(Modifier.width(8.dp))
        }
        Box(Modifier.weight(1f)) {
            if (value.isEmpty()) T(placeholder, 14.sp, C.muted, lines = 1)
            BasicTextField(
                value, onChange, singleLine = true,
                textStyle = TextStyle(color = C.text, fontSize = 15.sp),
                cursorBrush = SolidColor(C.acc),
                keyboardOptions = if (number) KeyboardOptions(keyboardType = KeyboardType.Uri) else KeyboardOptions.Default,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

/** Hoja inferior propia (como en el diseño): fondo oscurecido + panel con esquinas redondas. */
@Composable
fun Sheet(title: String, sub: String, onClose: () -> Unit, content: @Composable ColumnScope.() -> Unit) {
    Box(
        Modifier.fillMaxSize().background(C.scrim)
            .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null, onClick = onClose),
        contentAlignment = Alignment.BottomCenter,
    ) {
        Column(
            Modifier.fillMaxWidth().fillMaxHeight(0.88f)
                .clip(RoundedCornerShape(topStart = 26.dp, topEnd = 26.dp)).background(C.panel)
                .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null) {}
                .padding(start = 18.dp, end = 18.dp, top = 10.dp, bottom = 16.dp),
        ) {
            Box(Modifier.align(Alignment.CenterHorizontally).size(44.dp, 5.dp).clip(RoundedCornerShape(3.dp)).background(Color(0xFF3A3F4A)))
            Spacer(Modifier.height(12.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    T(title, 19.sp, weight = FontWeight.ExtraBold, lines = 1)
                    T(sub, 12.5.sp, C.muted, lines = 2)
                }
                IconBtn("x", "Cerrar", onClose)
            }
            Spacer(Modifier.height(12.dp))
            Column(
                Modifier.weight(1f).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp),
                content = content,
            )
        }
    }
}

/** Deslizador simple (0..1) dibujado como en el diseño. */
@Composable
fun NSlider(value: Float, onChange: (Float) -> Unit, onDone: () -> Unit = {}, modifier: Modifier = Modifier) {
    androidx.compose.material3.Slider(
        value = value.coerceIn(0f, 1f), onValueChange = onChange, onValueChangeFinished = onDone,
        modifier = modifier.fillMaxWidth().height(30.dp),
        colors = androidx.compose.material3.SliderDefaults.colors(
            thumbColor = C.acc, activeTrackColor = C.acc, inactiveTrackColor = C.panel2,
            activeTickColor = Color.Transparent, inactiveTickColor = Color.Transparent,
        ),
    )
}

fun pctDb(v: Float): String {
    val pct = Math.round(v * 100)
    val db = if (v <= 0.0001f) "−∞ dB" else String.format(java.util.Locale.US, "%+.1f dB", 20 * kotlin.math.log10(v.toDouble())).replace("-", "−")
    return "$pct % · ${if (pct == 100) "0.0 dB" else db}"
}
