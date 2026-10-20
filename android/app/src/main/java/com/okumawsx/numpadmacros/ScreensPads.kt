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
@Composable
fun PadsTab(vm: AppVm) {
    val online = vm.online
    Column(Modifier.fillMaxSize()) {
        if (!vm.fullscreen) {
            AppBar(vm) {
                if (online) IconBtn("full", "Pantalla completa", { vm.fullscreen = true })
            }
        }
        if (vm.st == St.Lost) LostBanner(vm)
        if (vm.st == St.Idle && vm.state.banks.isEmpty()) {
            EmptyPads(vm)
            return@Column
        }
        if (vm.meter && online && !vm.fullscreen) Meter(vm.level)
        if (vm.editMode) {
            Row(
                Modifier.padding(start = 14.dp, end = 14.dp, bottom = 10.dp).fillMaxWidth().clip(RoundedCornerShape(12.dp))
                    .background(C.accSoft).border(1.dp, C.accLine, RoundedCornerShape(12.dp)).padding(horizontal = 12.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                NIcon("edit", 16.dp, C.acc)
                Spacer(Modifier.width(8.dp))
                T("Toca un botón para cambiarlo. Se guarda en tu PC al instante.", 12.5.sp, Color(0xFFF2D3A3))
            }
        }
        BankRow(vm)
        if (vm.state.groups.size > 1) GroupRow(vm)
        Box(Modifier.weight(1f).fillMaxWidth().alpha(if (online) 1f else 0.35f)) {
            val g = vm.state.group(vm.group)
            when {
                vm.layout == "numpad" && g.rows <= 6 -> ShapeGrid(vm, g)
                vm.layout == "numpad" -> ListGrid(vm, g, 4, 78.dp, onlyAssigned = false)
                vm.layout == "grandes" -> ListGrid(vm, g, 2, 150.dp, onlyAssigned = true)
                else -> ListGrid(vm, g, 4, 78.dp, onlyAssigned = false)
            }
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
            T("¿El PC está encendido y con la app abierta?", 13.sp, Color(0xFFE6C48C))
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
            Box(Modifier.fillMaxHeight().fillMaxWidth(f).background(if (level > -6f) Color(0xFFE2B340) else C.ok))
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
                Chip(b.name, i == vm.state.active, { vm.selectBank(i) }, height = 36.dp, round = 18.dp)
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
                    NIcon("check", 15.dp, Color(0xFF06210F), 2.4f)
                    Spacer(Modifier.width(6.dp))
                    T("Listo", 13.sp, Color(0xFF06210F), FontWeight.ExtraBold)
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
    Row(
        Modifier.padding(start = 14.dp, end = 14.dp, bottom = 10.dp).fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(C.panel).padding(3.dp),
        horizontalArrangement = Arrangement.spacedBy(3.dp),
    ) {
        for (g in vm.state.groups) {
            val on = g.id == vm.state.group(vm.group).id
            Box(
                Modifier.weight(1f).height(34.dp).clip(RoundedCornerShape(10.dp)).background(if (on) C.panel2 else Color.Transparent)
                    .clickable(role = Role.Tab) { vm.group = g.id },
                contentAlignment = Alignment.Center,
            ) { T(g.name, 12.5.sp, if (on) C.text else C.muted, if (on) FontWeight.Bold else FontWeight.Medium, lines = 1) }
        }
    }
}

/** Botonera con la forma real (virtuales, numpad, fila 1–0), según las posiciones que manda el PC. */
@Composable
private fun ShapeGrid(vm: AppVm, g: KeyGroup) {
    BoxWithConstraints(Modifier.fillMaxSize().padding(horizontal = 14.dp)) {
        val gap = 8.dp
        val cw = (maxWidth - gap * (g.cols - 1)) / g.cols
        val chFit = (maxHeight - gap * (g.rows - 1)) / g.rows
        val ch = min(chFit, cw * 1.25f)
        val totalH = ch * g.rows + gap * (g.rows - 1)
        val top = ((maxHeight - totalH) / 2).coerceAtLeast(0.dp) * 0f
        for (k in g.keys) {
            Pad(
                vm, k,
                Modifier.offset(x = (cw + gap) * k.col, y = top + (ch + gap) * k.row)
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
    val color = when {
        isGlobal -> C.purple
        act != null -> C.keyColor(act.color)
        else -> C.muted
    }
    val shape = RoundedCornerShape(16.dp)
    val bg = when {
        pressed -> color.copy(alpha = 0.32f)
        prog != null -> color.copy(alpha = 0.18f)
        isGlobal -> C.globalBg
        act != null -> C.padBg
        else -> C.padEmpty
    }
    val border = when {
        prog != null || pressed -> color
        isGlobal -> C.globalLine
        act != null -> color.copy(alpha = 0.44f)
        vm.editMode -> Color(0xFF4A505C)
        else -> C.padEmptyLine
    }
    val desc = "Tecla ${k.label}: " + (act?.label() ?: "sin acción")
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
        T(k.label, 11.sp, Color(0x8CE9E9EC), modifier = Modifier.align(Alignment.TopStart).padding(start = 10.dp, top = 7.dp))
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
        if (vm.editMode) {
            Box(Modifier.align(Alignment.BottomEnd).padding(end = 8.dp, bottom = 6.dp)) {
                if (isGlobal) T("Global", 10.sp, Color(0xFFA99BE0)) else if (act != null) NIcon("edit", 14.dp, C.acc)
            }
        }
    }
}

@Composable
private fun BottomControls(vm: AppVm) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
        Row(
            Modifier.height(48.dp).clip(RoundedCornerShape(14.dp)).background(C.badSoft).border(1.dp, C.badLine, RoundedCornerShape(14.dp))
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
    var color by remember(ed) { mutableStateOf(layerAct?.color ?: 0) }
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
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            listOf("Sonido", "Atajo", "Otro").forEachIndexed { i, n -> Chip(n, tab == i, { tab = i }) }
        }
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
                T("COLOR EN EL CELULAR", 12.sp, C.muted, FontWeight.Bold)
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    C.keyColors.forEachIndexed { i, c ->
                        Box(
                            Modifier.size(36.dp).clip(CircleShape).background(c).border(3.dp, if (i == color) C.text else Color.Transparent, CircleShape)
                                .clickable(role = Role.RadioButton) { color = i }.semantics { contentDescription = "Color ${i + 1}" },
                        )
                    }
                }
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
                            for (kk in row) Chip(kk.uppercase(), kk == key, { key = kk }, Modifier.weight(1f), height = 40.dp, round = 10.dp)
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
                    NButton("Guardar", { vm.assign(ed.layer, ed.key, Act("keys", combo = combo)); close() }, Modifier.weight(1f))
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
                NButton("Guardar", { vm.assign(ed.layer, ed.key, other); close() }, Modifier.fillMaxWidth())
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
