package com.okumawsx.numpadmacros

import android.Manifest
import android.content.pm.PackageManager
import android.view.HapticFeedbackConstants
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.waitForUpOrCancellation
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.min
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import kotlin.math.log10

private val NUMPAD_ORDER = listOf("47", "48", "49", "4b", "4c", "4d", "4f", "50", "51", "52", "53", "4e", "45", "e0:35", "37", "4a", "e0:1c")

// ==================================================================== pestaña Botonera
/** true si el celular está acostado (horizontal). */
@Composable
fun isLandscape(): Boolean {
    val c = LocalConfiguration.current
    return c.screenWidthDp > c.screenHeightDp
}

/**
 * Grupo a dibujar. Las teclas virtuales («celular») se ordenan siempre en 5 columnas
 * (6 × 5 con el celular acostado), venga como venga del PC: 30 teclas = 5 × 6.
 */
fun shownGroup(vm: AppVm, land: Boolean): KeyGroup {
    val g = vm.state.group(vm.group)
    if (g.id != "celular") return g
    val cols = if (land) 6 else 5
    val order = g.keys.sortedWith(compareBy({ it.row }, { it.col }))
    val keys = order.mapIndexed { i, k -> k.copy(col = i % cols, row = i / cols, w = 1, h = 1) }
    return g.copy(cols = cols, rows = (keys.size + cols - 1) / cols, keys = keys)
}

@Composable
fun PadsTab(vm: AppVm) {
    if (isLandscape() && !(vm.st == St.Idle && vm.state.banks.isEmpty())) {
        PadsLandscape(vm)
        return
    }
    val online = vm.online
    Column(Modifier.fillMaxSize()) {
        if (!vm.fullscreen) {
            AppBar(vm) {
                if (online) IconBtn("full", "Pantalla completa", { vm.fullscreen = true })
            }
        }
        if (vm.st == St.Lost) LostBanner(vm)
        if (vm.updBanner) UpdateBanner(vm, Modifier.padding(start = 14.dp, end = 14.dp, bottom = 10.dp))
        if (vm.st == St.Idle && vm.state.banks.isEmpty()) {
            EmptyPads(vm)
            return@Column
        }
        if (vm.meter && online && !vm.fullscreen) Meter(vm.level)
        if (vm.editMode) EditNotice()
        BankRow(vm)
        if (vm.state.groups.size > 1) GroupRow(vm)
        Box(Modifier.weight(1f).fillMaxWidth().alpha(if (online) 1f else 0.35f)) {
            PadsArea(vm, shownGroup(vm, false), land = false)
        }
        if (vm.st == St.Lost) {
            Row(Modifier.padding(14.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                NButton("Reintentar ahora", { vm.retryNow() }, Modifier.weight(1f), icon = "refresh")
                NButton("Cambiar PC", { vm.disconnect(); vm.tab = Tab.Conn }, kind = Kind.Ghost)
            }
        } else if (!vm.editMode) {
            if (vm.fullscreen) {
                Box(Modifier.padding(start = 14.dp, end = 14.dp, top = 12.dp, bottom = 14.dp)) {
                    NButton("Detener todo", { vm.stopAll() }, Modifier.fillMaxWidth(), Kind.Danger, "stop")
                }
            } else BottomControls(vm)
        } else Spacer(Modifier.height(12.dp))
        // espacio para la barra flotante, que pasa por encima del final de la pantalla
        Spacer(Modifier.height(LocalNavSpace.current))
    }
}

@Composable
private fun EditNotice(modifier: Modifier = Modifier.padding(start = 14.dp, end = 14.dp, bottom = 10.dp)) {
    Row(
        modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp))
            .background(C.accSoft).border(1.dp, C.accLine, RoundedCornerShape(12.dp)).padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        NIcon("edit", 16.dp, C.acc)
        Spacer(Modifier.width(8.dp))
        T("Toca un botón para cambiarlo. Se guarda en tu PC al instante.", 12.5.sp, C.text)
    }
}

/** Las teclas, según el diseño elegido en Ajustes. */
@Composable
private fun PadsArea(vm: AppVm, g: KeyGroup, land: Boolean) {
    val virt = g.id == "celular"
    when {
        vm.layout == "numpad" && g.rows <= 6 -> ShapeGrid(vm, g, center = land && !virt, gap = if (land) 7.dp else 8.dp)
        vm.layout == "numpad" -> ListGrid(vm, g, if (virt) g.cols else 4, if (land) 64.dp else 78.dp, onlyAssigned = false)
        vm.layout == "grandes" -> ListGrid(vm, g, if (land) 4 else 2, if (land) 110.dp else 150.dp, onlyAssigned = true)
        else -> ListGrid(vm, g, if (land) 6 else 4, if (land) 64.dp else 78.dp, onlyAssigned = false)
    }
}

// ---------------------------------------------------------------- celular acostado
@Composable
private fun PadsLandscape(vm: AppVm) {
    val online = vm.online
    Row(Modifier.fillMaxSize()) {
        if (!vm.fullscreen) SideBar(vm)
        Box(Modifier.weight(1f).fillMaxHeight()) {
            Column(Modifier.fillMaxSize().padding(top = if (vm.fullscreen) 40.dp else 10.dp, bottom = 10.dp)) {
                if (vm.st == St.Lost) LostBanner(vm)
                if (vm.updBanner && !vm.fullscreen) UpdateBanner(vm, Modifier.padding(start = 12.dp, end = 12.dp, bottom = 8.dp))
                if (vm.editMode) EditNotice(Modifier.padding(start = 12.dp, end = 12.dp, bottom = 8.dp))
                Box(Modifier.weight(1f).fillMaxWidth().alpha(if (online) 1f else 0.35f)) {
                    PadsArea(vm, shownGroup(vm, true), land = true)
                }
                if (vm.st == St.Lost) {
                    Row(Modifier.padding(start = 12.dp, end = 12.dp, top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        NButton("Reintentar ahora", { vm.retryNow() }, Modifier.weight(1f), icon = "refresh", height = 44.dp, fontSize = 14.sp)
                        NButton("Cambiar PC", { vm.disconnect(); vm.tab = Tab.Conn }, kind = Kind.Ghost, height = 44.dp, fontSize = 14.sp)
                    }
                }
            }
            if (vm.fullscreen) FullPill(vm, Modifier.align(Alignment.TopEnd).padding(top = 6.dp, end = 10.dp))
        }
    }
}

/** Barra lateral izquierda: estado, grupos, bancos, Detener, Editar, pantalla completa, volumen y menú. */
@Composable
private fun SideBar(vm: AppVm) {
    val online = vm.online
    val (txt, col) = statusLine(vm)
    Column(
        Modifier.width(210.dp).fillMaxHeight().background(C.panel.copy(alpha = if (C.glassOn) 0.72f else 1f)).padding(start = 10.dp, end = 10.dp, top = 10.dp, bottom = 6.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Logo(26.dp)
            Spacer(Modifier.width(8.dp))
            Column(Modifier.weight(1f)) {
                T("Numpad Macros", 13.sp, weight = FontWeight.ExtraBold, lines = 1)
                T("● " + txt, 10.5.sp, col, lines = 1)
            }
        }
        if (vm.meter && online) {
            val f = ((vm.level + 60f) / 60f).coerceIn(0f, 1f)
            Box(Modifier.fillMaxWidth().height(4.dp).clip(RoundedCornerShape(2.dp)).background(C.panel2)) {
                Box(Modifier.fillMaxHeight().fillMaxWidth(f).background(if (vm.level > -6f) C.warn else C.ok))
            }
        }
        if (vm.state.groups.size > 1) {
            val groups = vm.state.groups
            val sel = groups.indexOfFirst { it.id == vm.state.group(vm.group).id }.coerceAtLeast(0)
            SegRail(groups.map { it.name.substringBefore(" ") }, sel, { vm.group = groups[it].id }, height = 28.dp, fontSize = 11.sp)
        }
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            vm.state.banks.forEachIndexed { i, b ->
                val on = i == vm.state.active
                Box(
                    Modifier.fillMaxWidth().heightIn(min = 34.dp).clip(CircleShape).background(if (on) C.acc else C.panel2.copy(alpha = if (C.glassOn) 0.55f else 1f))
                        .border(1.dp, if (on) Color.Transparent else C.text.copy(alpha = if (C.glassOn) 0.11f else 0.3f), CircleShape)
                        .clickable(role = Role.Button) { vm.selectBank(i) }.padding(horizontal = 10.dp),
                    contentAlignment = Alignment.CenterStart,
                ) { T("${i + 1} · ${b.name}", 12.5.sp, if (on) C.accDark else C.text, if (on) FontWeight.ExtraBold else FontWeight.SemiBold, lines = 1) }
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(
                Modifier.weight(1f).height(38.dp).clip(CircleShape).background(C.badSoft).border(1.dp, C.badLine, CircleShape)
                    .clickable(role = Role.Button) { vm.stopAll() },
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.Center,
            ) {
                NIcon("stop", 14.dp, C.badText)
                Spacer(Modifier.width(5.dp))
                T("Detener", 12.5.sp, C.badText, FontWeight.ExtraBold)
            }
            if (online) {
                if (vm.editMode) IconBtn("check", "Listo", { vm.editMode = false }, C.ok, C.onOk, 38.dp)
                else IconBtn("edit", "Editar", { vm.editMode = true; vm.refresh() }, C.accSoft, C.acc, 38.dp)
                IconBtn("full", "Pantalla completa", { vm.fullscreen = true; vm.editMode = false }, C.panel2, C.text, 38.dp)
            }
        }
        Column {
            Row {
                T("Volumen", 10.5.sp, C.muted, modifier = Modifier.weight(1f))
                T("${Math.round(vm.volume * 100)} %", 10.5.sp, C.acc, FontWeight.Bold)
            }
            NSlider(vm.volume / 2f, { vm.setVol((it * 2f * 20).let { r -> Math.round(r) / 20f }) }, { vm.volDone() })
        }
        Box(Modifier.fillMaxWidth().height(1.dp).background(C.line))
        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            for ((tab, icon, name) in listOf(Triple(Tab.Pads, "grid", "Botonera"), Triple(Tab.Conn, "link", "Conexión"), Triple(Tab.Settings, "gear", "Ajustes"))) {
                val on = vm.tab == tab
                Box(
                    Modifier.weight(1f).height(40.dp).clip(RoundedCornerShape(10.dp)).background(if (on) C.accSoft else Color.Transparent)
                        .clickable(role = Role.Tab) { vm.tab = tab }.semantics { contentDescription = name },
                    contentAlignment = Alignment.Center,
                ) { NIcon(icon, 19.dp, if (on) C.acc else C.muted) }
            }
        }
    }
}

/** Pantalla completa acostada: solo las teclas y una píldora arriba a la derecha. */
@Composable
private fun FullPill(vm: AppVm, modifier: Modifier) {
    val (txt, col) = statusLine(vm)
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
        Row(
            Modifier.height(30.dp).pillSurface(elevation = 6.dp)
                .clickable(role = Role.Button) { if (vm.state.banks.isNotEmpty()) vm.selectBank((vm.state.active + 1) % vm.state.banks.size) }
                .semantics { contentDescription = "Banco ${vm.state.banks.getOrNull(vm.state.active)?.name ?: ""}. Toca para pasar al siguiente" }
                .padding(horizontal = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            T(vm.state.banks.getOrNull(vm.state.active)?.name ?: "", 11.sp, C.acc, FontWeight.ExtraBold, lines = 1)
            Spacer(Modifier.width(6.dp))
            T(if (vm.latency >= 0 && vm.online) "● ${vm.latency} ms" else "● " + txt.take(12), 11.sp, col, lines = 1)
        }
        Box(
            Modifier.size(30.dp).clip(CircleShape).background(C.badSoft).border(1.dp, C.badLine, CircleShape)
                .clickable(role = Role.Button) { vm.stopAll() }.semantics { contentDescription = "Detener todo" },
            contentAlignment = Alignment.Center,
        ) { NIcon("stop", 13.dp, C.badText) }
        Box(
            Modifier.size(30.dp).pillSurface(elevation = 6.dp)
                .clickable(role = Role.Button) { vm.fullscreen = false }.semantics { contentDescription = "Salir de pantalla completa" },
            contentAlignment = Alignment.Center,
        ) { NIcon("full", 13.dp, C.text) }
    }
}

@Composable
private fun EmptyPads(vm: AppVm) {
    Column(Modifier.fillMaxSize().padding(26.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        Box(Modifier.size(90.dp).clip(CircleShape).background(C.panel2), contentAlignment = Alignment.Center) { NIcon("pc", 44.dp, C.muted, 1.5f) }
        Spacer(Modifier.height(18.dp))
        T("Sin conexión con tu PC", 20.sp, weight = FontWeight.ExtraBold)
        Spacer(Modifier.height(8.dp))
        T("Conecta el celular para ver aquí tus bancos y botones.", 14.sp, C.muted, align = TextAlign.Center)
        Spacer(Modifier.height(22.dp))
        NButton("Conectar", { vm.tab = Tab.Conn }, icon = "link")
    }
}

@Composable
private fun LostBanner(vm: AppVm) {
    Row(
        Modifier.padding(start = 14.dp, end = 14.dp, bottom = 10.dp).fillMaxWidth().clip(RoundedCornerShape(14.dp))
            .background(C.accSoft).border(1.dp, C.accLine, RoundedCornerShape(14.dp)).padding(horizontal = 14.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        NIcon(if (vm.transport == "bt") "bt" else if (vm.transport == "usb") "usb" else "wifi", 22.dp, C.acc)
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            T("Se perdió la conexión con ${vm.pcName.ifBlank { "tu PC" }}", 13.sp, weight = FontWeight.Bold)
            T("¿El PC está encendido y con la app abierta?", 13.sp, C.muted)
        }
    }
}

@Composable
private fun Meter(level: Float) {
    Row(Modifier.padding(start = 18.dp, end = 18.dp, bottom = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        T("PC", 11.sp, C.muted)
        Spacer(Modifier.width(8.dp))
        val f = ((level + 60f) / 60f).coerceIn(0f, 1f)
        Box(Modifier.weight(1f).height(6.dp).clip(RoundedCornerShape(3.dp)).background(C.panel2)) {
            Box(Modifier.fillMaxHeight().fillMaxWidth(f).background(if (level > -6f) C.warn else C.ok))
        }
        Spacer(Modifier.width(8.dp))
        T(if (level > -59f) "${level.toInt()} dB".replace("-", "−") else "—", 11.sp, C.muted, modifier = Modifier.widthIn(min = 44.dp), align = TextAlign.End)
    }
}

@Composable
private fun BankRow(vm: AppVm) {
    Row(Modifier.fillMaxWidth().padding(start = 14.dp, end = 14.dp, bottom = 10.dp, top = if (vm.fullscreen) 14.dp else 0.dp), verticalAlignment = Alignment.CenterVertically) {
        Row(Modifier.weight(1f).horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            vm.state.banks.forEachIndexed { i, b ->
                Chip(b.name, i == vm.state.active, { vm.selectBank(i) }, height = 36.dp, solid = true)
            }
        }
        Spacer(Modifier.width(8.dp))
        if (vm.fullscreen) {
            val (txt, col) = statusLine(vm)
            Box(Modifier.size(8.dp).clip(CircleShape).background(col))
            Spacer(Modifier.width(5.dp))
            T(if (vm.latency >= 0 && vm.online) "${vm.latency} ms" else txt.take(14), 12.sp, col, lines = 1)
            Spacer(Modifier.width(8.dp))
            IconBtn("full", "Salir de pantalla completa", { vm.fullscreen = false })
        } else if (vm.online) {
            if (vm.editMode) {
                Row(
                    Modifier.height(36.dp).clip(RoundedCornerShape(18.dp)).background(C.ok).clickable(role = Role.Button) { vm.editMode = false }.padding(horizontal = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    NIcon("check", 15.dp, C.onOk, 2.4f)
                    Spacer(Modifier.width(6.dp))
                    T("Listo", 13.sp, C.onOk, FontWeight.ExtraBold)
                }
            } else {
                Row(
                    Modifier.height(36.dp).clip(RoundedCornerShape(18.dp)).border(1.dp, C.accLine, RoundedCornerShape(18.dp))
                        .clickable(role = Role.Button) { vm.editMode = true; vm.refresh() }.padding(horizontal = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    NIcon("edit", 15.dp, C.acc)
                    Spacer(Modifier.width(6.dp))
                    T("Editar", 13.sp, C.acc, FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
private fun GroupRow(vm: AppVm) {
    val groups = vm.state.groups
    val sel = groups.indexOfFirst { it.id == vm.state.group(vm.group).id }.coerceAtLeast(0)
    SegRail(groups.map { it.name }, sel, { vm.group = groups[it].id }, Modifier.padding(start = 14.dp, end = 14.dp, bottom = 10.dp))
}

/** Botonera con la forma real (virtuales, numpad, fila 1–0), según las posiciones que manda el PC. */
@Composable
private fun ShapeGrid(vm: AppVm, g: KeyGroup, center: Boolean = false, gap: Dp = 8.dp) {
    BoxWithConstraints(Modifier.fillMaxSize().padding(horizontal = if (center) 12.dp else 14.dp)) {
        val cwFit = (maxWidth - gap * (g.cols - 1)) / g.cols
        val chFit = (maxHeight - gap * (g.rows - 1)) / g.rows
        // acostado, el numpad se ajusta al alto y queda centrado
        val cw = if (center) min(cwFit, chFit * 1.15f) else cwFit
        val ch = if (center) chFit else min(chFit, cw * 1.25f)
        val left = if (center) ((maxWidth - (cw * g.cols + gap * (g.cols - 1))) / 2).coerceAtLeast(0.dp) else 0.dp
        for (k in g.keys) {
            Pad(
                vm, k,
                Modifier.offset(x = left + (cw + gap) * k.col, y = (ch + gap) * k.row)
                    .size(cw * k.w + gap * (k.w - 1), ch * k.h + gap * (k.h - 1)),
                big = false,
            )
        }
    }
}

@Composable
private fun ListGrid(vm: AppVm, g: KeyGroup, cols: Int, h: Dp, onlyAssigned: Boolean) {
    val order = if (g.id == "numpad") g.keys.sortedBy { k -> NUMPAD_ORDER.indexOf(k.id).let { if (it < 0) 99 else it } }
    else g.keys.sortedWith(compareBy({ it.row }, { it.col }))
    val assigned = order.filter { vm.state.resolve(it.id).first != null }
    val list = if (onlyAssigned && assigned.isNotEmpty() && !vm.editMode) assigned else order
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 14.dp), verticalArrangement = Arrangement.spacedBy(if (cols == 2) 10.dp else 8.dp)) {
        for (row in list.chunked(cols)) {
            Row(horizontalArrangement = Arrangement.spacedBy(if (cols == 2) 10.dp else 8.dp)) {
                for (k in row) Pad(vm, k, Modifier.weight(1f).height(h), big = cols == 2)
                repeat(cols - row.size) { Spacer(Modifier.weight(1f)) }
            }
        }
        Spacer(Modifier.height(4.dp))
    }
}

@Composable
private fun Pad(vm: AppVm, k: KeyPos, modifier: Modifier, big: Boolean) {
    val (act, isGlobal) = vm.state.resolve(k.id)
    val prog = vm.playing[k.id]
    var pressed by remember { mutableStateOf(false) }
    val view = LocalView.current
    // color propio de la tecla (null = «sin color»)
    val own = act?.let { C.keyColor(it.color) }
    val color = own ?: if (act != null) C.text else C.muted
    val shape = RoundedCornerShape(16.dp)
    val bg = when {
        pressed -> color.copy(alpha = 0.32f)
        prog != null -> color.copy(alpha = 0.18f)
        act != null -> C.padBg
        else -> C.padEmpty
    }
    val border = when {
        prog != null || pressed -> color
        own != null -> own.copy(alpha = 0.44f)
        act != null -> C.line
        vm.editMode -> C.line
        else -> C.padEmptyLine
    }
    val desc = "Tecla ${k.label}: " + (act?.label() ?: "sin acción") + if (isGlobal) " (Global)" else ""
    val gesture = if (vm.editMode) {
        Modifier.clickable(role = Role.Button) {
            vm.editing = EditTarget(if (isGlobal) "global" else vm.state.active, k.id, k.label)
        }
    } else {
        Modifier.pointerInput(k.id, vm.vibrate) {
            awaitEachGesture {
                awaitFirstDown(requireUnconsumed = false)
                pressed = true
                if (vm.vibrate) view.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                vm.press(k.id, true)
                waitForUpOrCancellation()
                pressed = false
                vm.press(k.id, false)
            }
        }
    }
    Box(
        modifier.clip(shape).background(bg).border(if (prog != null) 2.dp else 1.dp, border, shape)
            .semantics { contentDescription = desc }.then(gesture),
    ) {
        T(k.label, 11.sp, C.text.copy(alpha = 0.55f), modifier = Modifier.align(Alignment.TopStart).padding(start = 10.dp, top = 7.dp))
        if (act != null) {
            Box(Modifier.align(Alignment.TopEnd).padding(top = 7.dp, end = 8.dp)) { NIcon(act.icon(), 13.dp, color) }
            val name = act.label()
            T(
                name, if (big) 17.sp else if (name.length > 10) 11.5.sp else 13.sp, weight = FontWeight.Bold, align = TextAlign.Center,
                lines = if (big) 3 else 3, lh = if (big) 20.sp else 14.sp,
                modifier = Modifier.align(Alignment.Center).padding(horizontal = 6.dp, vertical = 18.dp),
            )
        } else if (vm.editMode) {
            Row(Modifier.align(Alignment.Center), verticalAlignment = Alignment.CenterVertically) {
                NIcon("plus", 14.dp, C.muted)
                Spacer(Modifier.width(4.dp))
                T("Asignar", 12.sp, C.muted)
            }
        }
        if (prog != null) {
            Box(Modifier.align(Alignment.BottomStart).fillMaxWidth(prog.coerceIn(0f, 1f)).height(4.dp).background(color))
        }
        if (isGlobal) {
            // las teclas Global (todos los bancos) llevan una «G»
            Box(
                Modifier.align(Alignment.BottomEnd).padding(end = 6.dp, bottom = 6.dp).size(18.dp).clip(RoundedCornerShape(5.dp))
                    .background(C.globalBg).border(1.dp, C.globalLine, RoundedCornerShape(5.dp)),
                contentAlignment = Alignment.Center,
            ) { T("G", 10.5.sp, C.globalText, FontWeight.ExtraBold) }
        } else if (vm.editMode && act != null) {
            Box(Modifier.align(Alignment.BottomEnd).padding(end = 8.dp, bottom = 6.dp)) { NIcon("edit", 14.dp, C.acc) }
        }
    }
}

@Composable
private fun BottomControls(vm: AppVm) {
    // Detener + volumen: una sola píldora flotante
    Row(
        Modifier.padding(start = 14.dp, end = 14.dp, top = 8.dp, bottom = 10.dp).fillMaxWidth().pillSurface(elevation = 8.dp)
            .padding(start = 7.dp, end = 16.dp, top = 7.dp, bottom = 7.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(
            Modifier.height(44.dp).clip(CircleShape).background(C.badSoft).border(1.dp, C.badLine, CircleShape)
                .clickable(role = Role.Button) { vm.stopAll() }.padding(horizontal = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            NIcon("stop", 16.dp, C.badText)
            Spacer(Modifier.width(6.dp))
            T("Detener", 14.sp, C.badText, FontWeight.ExtraBold)
        }
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Row {
                T("Volumen general", 12.sp, C.muted, modifier = Modifier.weight(1f))
                T(pctDb(vm.volume), 12.sp, C.acc, FontWeight.Bold)
            }
            NSlider(vm.volume / 2f, { vm.setVol((it * 2f * 20).let { r -> Math.round(r) / 20f }) }, { vm.volDone() })
        }
    }
}

// ==================================================================== hoja de edición
@Composable
fun EditSheet(vm: AppVm, ed: EditTarget) {
    val layerAct: Act? = if (ed.layer == "global") vm.state.global[ed.key] else vm.state.banks.getOrNull(ed.layer as Int)?.keys?.get(ed.key)
    val where = if (ed.layer == "global") "Global (todos los bancos)" else vm.state.banks.getOrNull(ed.layer as Int)?.name ?: ""
    var tab by remember(ed) { mutableStateOf(when (layerAct?.type) { "file", null -> 0; "keys" -> 1; else -> 2 }) }
    // sonido
    var lib by remember(ed) { mutableStateOf(layerAct?.lib ?: "") }
    var mode by remember(ed) { mutableStateOf(layerAct?.mode?.takeIf { layerAct.type == "file" } ?: "overlap") }
    var vol by remember(ed) { mutableStateOf((layerAct?.volume ?: 1.0).toFloat()) }
    var color by remember(ed) { mutableStateOf(layerAct?.color ?: -1) }
    var query by remember(ed) { mutableStateOf("") }
    // atajo
    val parts = (if (layerAct?.type == "keys") layerAct.combo else "").split("+").map { it.trim().lowercase() }.filter { it.isNotEmpty() }
    var mods by remember(ed) { mutableStateOf(parts.filter { it in listOf("ctrl", "shift", "alt", "win") }.toSet()) }
    var key by remember(ed) { mutableStateOf(parts.lastOrNull { it !in listOf("ctrl", "shift", "alt", "win") } ?: "f13") }
    // otro
    var other by remember(ed) { mutableStateOf(layerAct?.takeIf { it.type != "file" && it.type != "keys" }) }

    fun close() { vm.editing = null }
    val soundAct = { Act("file", vm.library.firstOrNull { it.lib == lib }?.title ?: layerAct?.title ?: "", mode, vol.toDouble(), lib, color) }

    Sheet("Tecla ${ed.label} · $where", "Se guarda en Numpad Macros de tu PC", ::close) {
        SegRail(listOf("Sonido", "Atajo", "Otro"), tab, { tab = it }, height = 36.dp, fontSize = 13.sp)
        when (tab) {
            0 -> {
                Field(query, { query = it }, "Buscar en la biblioteca del PC…", icon = "search")
                val items = vm.library.filter { query.isBlank() || it.title.contains(query.trim(), ignoreCase = true) }
                Column(Modifier.fillMaxWidth().heightIn(max = 230.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    if (vm.library.isEmpty()) T("La biblioteca del PC está vacía. Sube un sonido desde el celular.", 13.sp, C.muted)
                    for (it in items) {
                        val on = it.lib == lib
                        Row(
                            Modifier.fillMaxWidth().heightIn(min = 44.dp).clip(RoundedCornerShape(12.dp))
                                .background(if (on) C.accSoft else C.panel2).border(1.dp, if (on) C.acc else Color.Transparent, RoundedCornerShape(12.dp))
                                .clickable { lib = it.lib }.padding(horizontal = 12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            NIcon(if (on) "check" else "music", 16.dp, if (on) C.acc else C.muted)
                            Spacer(Modifier.width(10.dp))
                            T(it.title, 14.sp, weight = if (on) FontWeight.Bold else FontWeight.Medium, lines = 1, modifier = Modifier.weight(1f))
                            it.lufs?.let { l -> T("${"%.0f".format(l)} LUFS".replace("-", "−"), 11.5.sp, C.muted) }
                        }
                    }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    NButton("Subir del celular", { vm.openUpload(soundAct().copy(lib = "")) }, Modifier.weight(1f), Kind.Ghost, "up", 44.dp, 13.sp)
                    NButton("Escuchar en el PC", { if (lib.isNotBlank()) vm.preview(lib) }, Modifier.weight(1f), Kind.Ghost, "play", 44.dp, 13.sp, enabled = lib.isNotBlank())
                }
                T("AL PULSAR", 12.sp, C.muted, FontWeight.Bold)
                val modes = listOf("overlap" to "Superponer", "restart" to "Reiniciar", "toggle" to "Alternar", "hold" to "Mientras se mantiene")
                for (pair in modes.chunked(2)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        for ((id, n) in pair) Chip(n, mode == id, { mode = id }, Modifier.weight(1f))
                    }
                }
                Row {
                    T("VOLUMEN", 12.sp, C.muted, FontWeight.Bold, Modifier.weight(1f))
                    T(pctDb(vol), 12.sp, C.acc, FontWeight.Bold)
                }
                NSlider(vol / 2f, { vol = Math.round(it * 2f * 20) / 20f })
                Row(verticalAlignment = Alignment.CenterVertically) {
                    T("COLOR DEL BOTÓN", 12.sp, C.muted, FontWeight.Bold, Modifier.weight(1f))
                    T(C.keyColorName(color), 12.5.sp, C.keyColor(color) ?: C.muted, FontWeight.Bold)
                }
                ColorPicker(color) { color = it }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    NButton("Guardar", { vm.assign(ed.layer, ed.key, soundAct()); close() }, Modifier.weight(1f), enabled = lib.isNotBlank())
                    NButton("Quitar", { vm.assign(ed.layer, ed.key, null); close() }, kind = Kind.Danger)
                }
            }
            1 -> {
                T("TECLAS QUE SE MANTIENEN", 12.sp, C.muted, FontWeight.Bold)
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    for ((id, n) in listOf("ctrl" to "Ctrl", "shift" to "Shift", "alt" to "Alt", "win" to "Win")) {
                        Chip(n, id in mods, { mods = if (id in mods) mods - id else mods + id }, Modifier.weight(1f))
                    }
                }
                val groups = listOf(
                    "F13–F24 (no chocan con nada)" to (13..24).map { "f$it" },
                    "F1–F12" to (1..12).map { "f$it" },
                    "Letras" to ('a'..'z').map { it.toString() },
                    "Números" to ('0'..'9').map { it.toString() },
                )
                for ((title, keys) in groups) {
                    T(title.uppercase(), 12.sp, C.muted, FontWeight.Bold)
                    for (row in keys.chunked(6)) {
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            for (kk in row) Chip(kk.uppercase(), kk == key, { key = kk }, Modifier.weight(1f), height = 40.dp)
                            repeat(6 - row.size) { Spacer(Modifier.weight(1f)) }
                        }
                    }
                }
                val order = listOf("ctrl", "shift", "alt", "win")
                val combo = (order.filter { it in mods } + key).joinToString("+")
                Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(C.panel2).padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    T("El PC enviará", 12.sp, C.muted)
                    T(Act.comboText(combo), 26.sp, C.acc, FontWeight.ExtraBold, align = TextAlign.Center)
                    T("Asígnalo en OBS u otro programa pulsando este botón.", 12.sp, C.muted, align = TextAlign.Center)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    NButton("Guardar", { vm.assign(ed.layer, ed.key, Act("keys", combo = combo, color = layerAct?.color ?: -1)); close() }, Modifier.weight(1f))
                    NButton("Quitar", { vm.assign(ed.layer, ed.key, null); close() }, kind = Kind.Danger)
                }
            }
            else -> {
                val opts = mutableListOf<Pair<Act?, String>>(
                    null to "Sin acción",
                    Act("sound_stop") to "Detener todos los sonidos",
                    Act("bank_next") to "Pasar al banco siguiente",
                    Act("bank_prev") to "Volver al banco anterior",
                )
                vm.state.banks.forEachIndexed { i, b -> opts.add(Act("bank_go", bank = i + 1) to "Ir al banco «${b.name}»") }
                for ((a, n) in opts) {
                    val on = (a == null && other == null) || (a != null && other != null && a.type == other!!.type && (a.type != "bank_go" || a.bank == other!!.bank))
                    Row(
                        Modifier.fillMaxWidth().heightIn(min = 46.dp).clip(RoundedCornerShape(12.dp)).background(if (on) C.accSoft else C.panel2)
                            .border(1.dp, if (on) C.acc else Color.Transparent, RoundedCornerShape(12.dp)).clickable { other = a }.padding(horizontal = 12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        NIcon(if (on) "check" else (a?.icon() ?: "x"), 16.dp, if (on) C.acc else C.muted)
                        Spacer(Modifier.width(10.dp))
                        T(n, 14.sp, weight = if (on) FontWeight.Bold else FontWeight.Medium)
                    }
                }
                NButton("Guardar", { vm.assign(ed.layer, ed.key, other?.copy(color = layerAct?.color ?: -1)); close() }, Modifier.fillMaxWidth())
            }
        }
    }
}

/** Sin color + los 12 colores, en dos filas de 7 círculos grandes. */
@Composable
private fun ColorPicker(sel: Int, onPick: (Int) -> Unit) {
    val items = listOf(-1) + C.keyColorOrder
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        for (row in items.chunked(7)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                for (i in row) {
                    val on = i == sel || (i == -1 && C.keyColor(sel) == null)
                    val c = C.keyColor(i)
                    Box(
                        Modifier.size(40.dp).clip(CircleShape).border(3.dp, if (on) C.text else Color.Transparent, CircleShape)
                            .clickable(role = Role.RadioButton) { onPick(i) }
                            .semantics { contentDescription = C.keyColorName(i) + if (on) ", elegido" else "" },
                        contentAlignment = Alignment.Center,
                    ) {
                        if (c != null) Box(Modifier.size(30.dp).clip(CircleShape).background(c))
                        else Box(Modifier.size(30.dp).clip(CircleShape).border(2.dp, C.line, CircleShape), contentAlignment = Alignment.Center) { NIcon("x", 14.dp, C.muted) }
                    }
                }
                repeat(7 - row.size) { Spacer(Modifier.size(40.dp)) }
            }
        }
    }
}

// ==================================================================== subir un sonido
@Composable
fun UploadSheet(vm: AppVm, u: Upload) {
    val ctx = LocalContext.current
    val pick = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri -> if (uri != null) vm.pickedUri(uri) }
    val mic = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) vm.startRecording() else vm.toast = "Sin permiso de micrófono no se puede grabar." to true
    }
    val ed = vm.editing
    Sheet("Nuevo sonido", "Desde el celular a la biblioteca del PC", { vm.closeUpload() }) {
        when (u.phase) {
            "elegir" -> {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    BigTile("music", C.acc, "Elegir archivo", Modifier.weight(1f)) { pick.launch("audio/*") }
                    BigTile("mic", C.bad, "Grabar ahora", Modifier.weight(1f)) {
                        if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) vm.startRecording()
                        else mic.launch(Manifest.permission.RECORD_AUDIO)
                    }
                }
                InfoBox("Sirve cualquier audio: MP3, WAV, OGG, FLAC y OPUS se envían tal cual; otros (M4A, AAC, AMR…) se convierten a WAV en el celular. Hasta 50 MB; las grabaciones duran hasta 1 minuto.")
            }
            "grabando" -> {
                Column(Modifier.fillMaxWidth().padding(vertical = 20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    T("Grabando…", 18.sp, C.badText, FontWeight.ExtraBold)
                    Spacer(Modifier.height(8.dp))
                    T("0:%02d / 1:00".format(u.seconds), 34.sp, weight = FontWeight.ExtraBold)
                    Spacer(Modifier.height(20.dp))
                    Box(
                        Modifier.size(84.dp).clip(CircleShape).background(C.bad).clickable(role = Role.Button) { vm.stopRecording() }
                            .semantics { contentDescription = "Terminar de grabar" },
                        contentAlignment = Alignment.Center,
                    ) { Box(Modifier.size(28.dp).clip(RoundedCornerShape(6.dp)).background(Color.White)) }
                    Spacer(Modifier.height(10.dp))
                    T("Toca para terminar", 13.sp, C.muted)
                }
            }
            "convirtiendo" -> {
                Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(C.panel2).padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    T("Convirtiendo a WAV…", weight = FontWeight.Bold)
                    T("Tu PC no abre este formato, así que el celular lo convierte antes de enviarlo.", 12.5.sp, C.muted, lh = 18.sp)
                    Box(Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(3.dp)).background(C.bg)) {
                        Box(Modifier.fillMaxHeight().fillMaxWidth((u.received / 100f).coerceIn(0f, 1f)).background(C.acc))
                    }
                }
            }
            "listo", "enviando", "hecho" -> {
                Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(C.panel2).padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        NIcon(if (u.phase == "hecho") "check" else "music", 20.dp, if (u.phase == "hecho") C.ok else C.acc)
                        Spacer(Modifier.width(10.dp))
                        Column(Modifier.weight(1f)) {
                            T(u.name, weight = FontWeight.Bold, lines = 1)
                            T(sizeText(u.size), 12.sp, C.muted)
                        }
                    }
                    if (u.phase != "listo") {
                        val f = if (u.size > 0) (u.received.toFloat() / u.size).coerceIn(0f, 1f) else 0f
                        Box(Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(3.dp)).background(C.bg)) {
                            Box(Modifier.fillMaxHeight().fillMaxWidth(if (u.phase == "hecho") 1f else f).background(if (u.phase == "hecho") C.ok else C.acc))
                        }
                        T(if (u.phase == "hecho") "Listo: quedó en la biblioteca de tu PC." else "Enviando al PC… ${(f * 100).toInt()} %", 12.sp, C.muted)
                    }
                }
                if (u.phase == "listo") {
                    T("NOMBRE EN LA BIBLIOTECA", 12.sp, C.muted, FontWeight.Bold)
                    Field(u.title, { vm.setUploadTitle(it) }, "Nombre del sonido", accent = true)
                    T(
                        if (ed != null && vm.uploadAssign != null) "Se guarda en la carpeta de sonidos del PC, se mide su volumen y queda asignado a la tecla ${ed.label}."
                        else "Se guarda en la carpeta de sonidos del PC y se mide su volumen.",
                        12.5.sp, C.muted, lh = 18.sp,
                    )
                    NButton(if (ed != null && vm.uploadAssign != null) "Guardar y asignar" else "Guardar en la biblioteca", { vm.sendUpload(vm.uploadAssign) }, Modifier.fillMaxWidth())
                    NButton("Elegir otro", { vm.upload = Upload() }, Modifier.fillMaxWidth(), Kind.Link)
                }
                if (u.phase == "hecho") {
                    NButton("Listo", {
                        vm.closeUpload()
                        if (vm.uploadAssign != null) vm.editing = null
                    }, Modifier.fillMaxWidth(), Kind.Ok, "check")
                }
            }
            else -> {
                Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(C.badSoft).border(1.dp, C.badLine, RoundedCornerShape(14.dp)).padding(14.dp)) {
                    T(u.msg.ifBlank { "Algo falló." }, 14.sp, C.badText, lh = 20.sp)
                }
                NButton("Intentar de nuevo", { vm.upload = Upload() }, Modifier.fillMaxWidth())
            }
        }
    }
}

@Composable
private fun BigTile(icon: String, color: Color, text: String, modifier: Modifier, onClick: () -> Unit) {
    Column(
        modifier.heightIn(min = 96.dp).clip(RoundedCornerShape(16.dp)).background(C.panel2).border(1.dp, C.line, RoundedCornerShape(16.dp))
            .clickable(role = Role.Button, onClick = onClick),
        horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center,
    ) {
        NIcon(icon, 26.dp, color)
        Spacer(Modifier.height(8.dp))
        T(text, weight = FontWeight.Bold)
    }
}

private fun sizeText(b: Long): String = when {
    b <= 0 -> ""
    b < 1024 * 1024 -> "${(b + 1023) / 1024} KB"
    else -> "%.1f MB".format(b / 1048576.0)
}

@Suppress("unused")
private fun db(v: Float) = 20 * log10(v.coerceAtLeast(0.0001f))
