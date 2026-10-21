package com.okumawsx.numpadmacros

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.delay

// ==================================================================== barra superior
@Composable
fun AppBar(vm: AppVm, right: @Composable (() -> Unit)? = null) {
    val (text, color) = statusLine(vm)
    Row(Modifier.fillMaxWidth().padding(start = 18.dp, end = 14.dp, top = 14.dp, bottom = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        Logo(34.dp)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            T("Numpad Macros", 17.sp, weight = FontWeight.ExtraBold)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(8.dp).clip(CircleShape).background(color))
                Spacer(Modifier.width(6.dp))
                T(text, 12.5.sp, color, lines = 1)
            }
        }
        right?.invoke()
    }
}

fun statusLine(vm: AppVm): Pair<String, Color> = when (vm.st) {
    St.Online -> buildString {
        append(transportName(vm.transport)); append(" · "); append(vm.pcName)
        if (vm.latency >= 0) append(" · ${vm.latency} ms")
        if (vm.state.paused) append(" · en pausa")
    } to (if (vm.state.paused) C.acc else C.ok)
    St.Connecting -> "Conectando con ${vm.pcName.ifBlank { "el PC" }}…" to C.muted
    St.Lost -> (if (vm.lostAttempt > 0) "Reconectando… intento ${vm.lostAttempt}" else "Sin conexión") to C.acc
    St.Pin -> "Esperando el código" to C.acc
    St.Idle -> "Sin conectar" to C.muted
}

@Composable
/** Alto que ocupa la barra flotante (para dejar espacio al final de cada pantalla). */
val NAV_SPACE = 84.dp

/** Barra inferior: una píldora de vidrio que flota sobre la pantalla. */
@Composable
fun BottomNav(vm: AppVm, modifier: Modifier = Modifier) {
    Row(
        modifier.padding(start = 16.dp, end = 16.dp, bottom = 12.dp).fillMaxWidth().pillSurface().padding(5.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        for ((tab, icon, name) in listOf(Triple(Tab.Pads, "grid", "Botonera"), Triple(Tab.Conn, "link", "Conexión"), Triple(Tab.Settings, "gear", "Ajustes"))) {
            val on = vm.tab == tab
            val col = if (on) C.acc else C.muted
            Column(
                Modifier.weight(1f).height(52.dp).clip(CircleShape)
                    .background(if (on) C.acc.copy(alpha = if (C.glassOn) 0.16f else 0.3f) else Color.Transparent)
                    .clickable(role = Role.Tab) { vm.tab = tab },
                horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center,
            ) {
                NIcon(icon, 20.dp, col)
                Spacer(Modifier.height(2.dp))
                T(name, 11.sp, col, if (on) FontWeight.Bold else FontWeight.Medium, lines = 1)
            }
        }
    }
}

// ==================================================================== bienvenida
@Composable
fun WelcomeScreen(vm: AppVm) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(start = 26.dp, end = 26.dp, top = 56.dp, bottom = 22.dp), verticalArrangement = Arrangement.spacedBy(22.dp)) {
        Logo(72.dp)
        Column {
            T("Tus sonidos,\ndesde el celular", 30.sp, weight = FontWeight.ExtraBold, lh = 35.sp)
            Spacer(Modifier.height(12.dp))
            T("Lanza los sonidos y atajos de Numpad Macros sin tocar el teclado. El sonido sale de tu PC, igual que con el numpad.", 15.sp, C.muted, lh = 22.sp)
        }
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            for ((i, c, t, d) in listOf(
                Quad("wifi", C.acc, "Wi-Fi", "En la misma red de tu casa"),
                Quad("bt", C.blue, "Bluetooth", "Sin Wi-Fi, a pocos metros"),
                Quad("usb", C.ok, "Cable USB", "La conexión más rápida"),
            )) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(40.dp).clip(RoundedCornerShape(12.dp)).background(C.panel2), contentAlignment = Alignment.Center) { NIcon(i, 20.dp, c) }
                    Spacer(Modifier.width(12.dp))
                    Column {
                        T(t, weight = FontWeight.Bold)
                        T(d, 12.5.sp, C.muted)
                    }
                }
            }
        }
        Spacer(Modifier.weight(1f))
        NButton("Empezar", { vm.finishWelcome() }, Modifier.fillMaxWidth())
        T("Necesitas Numpad Macros 3.3.1 o posterior en tu PC", 12.5.sp, C.muted, align = TextAlign.Center, modifier = Modifier.fillMaxWidth())
    }
}

data class Quad<A, B, C2, D>(val a: A, val b: B, val c: C2, val d: D)

// ==================================================================== pestaña Conexión
@Composable
fun ConnTab(vm: AppVm, onQr: () -> Unit) {
    var manual by remember { mutableStateOf(false) }
    var ip by remember { mutableStateOf("") }
    LaunchedEffect(Unit) {
        while (true) {
            if (vm.st != St.Online) vm.scan()
            delay(3500)
        }
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(start = 16.dp, end = 16.dp, bottom = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        if (vm.st == St.Online) {
            RowItem("pc", vm.pcName, "Conectado por ${transportName(vm.transport)}" + if (vm.latency >= 0) " · ${vm.latency} ms" else "", { vm.tab = Tab.Pads },
                C.ok, C.okSoft, C.ok) { NButton("Desconectar", { vm.disconnect() }, kind = Kind.Danger, height = 40.dp, fontSize = 13.sp) }
        }
        T("Conecta con tu PC", 24.sp, weight = FontWeight.ExtraBold)
        T("En tu PC abre Numpad Macros → pestaña «Dispositivos» y activa «Permitir conexiones».", 13.5.sp, C.muted, lh = 19.sp)
        vm.error?.let { e ->
            Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(C.badSoft).border(1.dp, C.badLine, RoundedCornerShape(14.dp)).padding(12.dp)) {
                T(e, 13.sp, C.badText, lh = 18.sp)
            }
        }
        if (vm.st == St.Connecting) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                NIcon("refresh", 14.dp, C.acc)
                Spacer(Modifier.width(8.dp))
                T("Conectando con ${vm.pcName.ifBlank { "el PC" }}…", 13.sp, C.acc)
            }
        }
        SectionLabel("Encontrados")
        val shown = vm.found
        if (shown.isEmpty()) {
            T("Todavía no aparece ningún PC.", 13.sp, C.muted)
        }
        for (f in shown) {
            val saved = vm.pcs.any { it.id == f.id && it.token.isNotBlank() }
            val isUsb = f.transport == "usb"
            RowItem(
                "pc", f.name, "${transportName(f.transport)} · Numpad Macros ${f.app}" + if (saved) " · vinculado" else "",
                { vm.connectFound(f) },
                if (isUsb) C.ok else C.acc, if (isUsb) C.okSoft else C.accSoft, if (isUsb) C.ok else C.accLine,
            ) { T("Conectar", 13.sp, C.acc, FontWeight.Bold) }
        }
        val offline = vm.pcs.filter { p -> shown.none { it.id == p.id } }
        if (offline.isNotEmpty()) {
            SectionLabel("Mis PCs")
            for (p in offline) {
                RowItem("pc", p.name, "${transportName(p.transport)} · último uso: ${ago(p.last)}", { vm.connectSaved(p) },
                    if (p.transport == "bt") C.blue else C.text) { T("Conectar", 13.sp, C.acc, FontWeight.Bold) }
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 2.dp)) {
            NIcon("refresh", 14.dp, C.muted)
            Spacer(Modifier.width(8.dp))
            T(if (vm.scanning) "Buscando en Wi-Fi y cable USB…" else "Se busca de nuevo cada pocos segundos", 12.5.sp, C.muted)
        }
        SectionLabel("Otras formas")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for ((icon, color, name, action) in listOf(
                Quad("qr", C.text, "Código QR", onQr),
                Quad("bt", C.blue, "Bluetooth", { vm.screen = Screen.Bt }),
                Quad("usb", C.ok, "Cable USB", { vm.screen = Screen.Usb }),
            )) {
                Column(
                    Modifier.weight(1f).heightIn(min = 92.dp).clip(RoundedCornerShape(16.dp)).background(C.panel)
                        .border(1.dp, C.line, RoundedCornerShape(16.dp)).clickable(role = Role.Button, onClick = action),
                    horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center,
                ) {
                    NIcon(icon, 26.dp, color)
                    Spacer(Modifier.height(8.dp))
                    T(name, 13.sp, weight = FontWeight.SemiBold)
                }
            }
        }
        if (!manual) {
            T("¿No aparece? Escribir la IP a mano", 13.sp, C.acc, FontWeight.SemiBold,
                Modifier.clip(RoundedCornerShape(8.dp)).clickable { manual = true }.padding(vertical = 10.dp))
        } else {
            T("La IP aparece en tu PC, en la pestaña «Dispositivos».", 12.5.sp, C.muted)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Field(ip, { ip = it }, "Ej.: 192.168.1.20", Modifier.weight(1f), number = true)
                NButton("Conectar", { vm.connectManual(ip) }, height = 46.dp, fontSize = 14.sp)
            }
        }
        Spacer(Modifier.height(LocalNavSpace.current))
    }
}

// ==================================================================== código de 4 números
@Composable
fun PinScreen(vm: AppVm) {
    var code by remember { mutableStateOf("") }
    LaunchedEffect(vm.pinError) { if (vm.pinError != null) code = "" }
    Column(Modifier.fillMaxSize()) {
        BackBar(vm.pcName.ifBlank { "Tu PC" }) { vm.cancelPin() }
        Column(Modifier.weight(1f).padding(start = 22.dp, end = 22.dp, bottom = 22.dp, top = 10.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
            Column {
                T("Escribe el código", 24.sp, weight = FontWeight.ExtraBold)
                Spacer(Modifier.height(6.dp))
                T("Son 4 números que aparecen en Numpad Macros → Dispositivos. Solo se pide la primera vez.", 13.5.sp, C.muted, lh = 19.sp)
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp, Alignment.CenterHorizontally)) {
                for (i in 0 until 4) {
                    val d = code.getOrNull(i)?.toString() ?: ""
                    Box(
                        Modifier.size(56.dp, 66.dp).clip(RoundedCornerShape(14.dp)).background(C.panel2)
                            .border(2.dp, if (i == code.length.coerceAtMost(3) && code.length < 4) C.acc else C.line, RoundedCornerShape(14.dp)),
                        contentAlignment = Alignment.Center,
                    ) { T(d, 30.sp, weight = FontWeight.ExtraBold) }
                }
            }
            vm.pinError?.let { T(it, 13.sp, C.badText, align = TextAlign.Center, modifier = Modifier.fillMaxWidth()) }
            if (code.length == 4 && vm.pinError == null) {
                T("Comprobando…", 13.sp, C.muted, align = TextAlign.Center, modifier = Modifier.fillMaxWidth())
            }
            Spacer(Modifier.weight(1f))
            val keys = listOf("1", "2", "3", "4", "5", "6", "7", "8", "9", "⌫", "0", "OK")
            for (r in 0 until 4) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    for (c in 0 until 3) {
                        val k = keys[r * 3 + c]
                        val ok = k == "OK"
                        Box(
                            Modifier.weight(1f).height(54.dp).clip(RoundedCornerShape(14.dp)).background(if (ok) C.acc else C.panel2)
                                .clickable(role = Role.Button) {
                                    when (k) {
                                        "⌫" -> code = code.dropLast(1)
                                        "OK" -> if (code.length == 4) vm.submitPin(code)
                                        else -> if (code.length < 4) {
                                            code += k
                                            if (code.length == 4) vm.submitPin(code)
                                        }
                                    }
                                },
                            contentAlignment = Alignment.Center,
                        ) { T(k, 22.sp, if (ok) C.accDark else C.text, FontWeight.Bold) }
                    }
                }
            }
        }
    }
}

// ==================================================================== cable USB
@Composable
fun UsbScreen(vm: AppVm) {
    val ctx = LocalContext.current
    Column(Modifier.fillMaxSize()) {
        BackBar("Cable USB") { vm.screen = Screen.Main }
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(start = 20.dp, end = 20.dp, bottom = 22.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Row(
                Modifier.fillMaxWidth().height(150.dp).clip(RoundedCornerShape(20.dp)).background(C.panel),
                horizontalArrangement = Arrangement.spacedBy(18.dp, Alignment.CenterHorizontally), verticalAlignment = Alignment.CenterVertically,
            ) {
                NIcon("phone", 54.dp, C.text, 1.4f)
                Box(Modifier.width(70.dp).height(3.dp).background(C.ok))
                NIcon("pc", 60.dp, C.text, 1.4f)
            }
            T("La conexión más rápida", 22.sp, weight = FontWeight.ExtraBold)
            val steps = listOf(
                "Conecta el celular al PC con el cable USB.",
                "En el aviso del celular toca «Cargando por USB» y elige «Compartir conexión por USB» (o «Anclaje USB»). También está en Ajustes → Conexión compartida.",
                "Vuelve aquí: tu PC aparece solo y conectas como por Wi-Fi.",
            )
            steps.forEachIndexed { i, s ->
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Box(Modifier.size(30.dp).clip(CircleShape).background(C.panel2), contentAlignment = Alignment.Center) {
                        T("${i + 1}", weight = FontWeight.ExtraBold, color = C.acc)
                    }
                    T(s, 14.sp, C.text, lh = 21.sp, modifier = Modifier.weight(1f))
                }
            }
            NButton("Abrir «Conexión compartida»", {
                val intents = listOf(
                    Intent().setClassName("com.android.settings", "com.android.settings.TetherSettings"),
                    Intent(Settings.ACTION_WIRELESS_SETTINGS),
                    Intent(Settings.ACTION_SETTINGS),
                )
                for (it in intents) {
                    try {
                        ctx.startActivity(it.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); break
                    } catch (_: Exception) {}
                }
            }, Modifier.fillMaxWidth(), Kind.Ghost, "gear")
            InfoBox("No usa tus datos móviles ni necesita el modo desarrollador. El celular carga mientras tanto.")
            Spacer(Modifier.weight(1f))
            NButton("Ya lo activé", {
                vm.scan()
                vm.screen = Screen.Main
                vm.tab = Tab.Conn
            }, Modifier.fillMaxWidth())
        }
    }
}

// ==================================================================== Bluetooth
@Composable
fun BtScreen(vm: AppVm) {
    val ctx = LocalContext.current
    val needPerm = Build.VERSION.SDK_INT >= 31
    var granted by remember {
        mutableStateOf(!needPerm || ContextCompat.checkSelfPermission(ctx, Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED)
    }
    val ask = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        granted = ok
        if (ok) vm.loadBonded()
    }
    LaunchedEffect(granted) {
        if (!granted && needPerm) ask.launch(Manifest.permission.BLUETOOTH_CONNECT)
        while (granted) {
            vm.loadBonded()
            delay(3000)
        }
    }
    Column(Modifier.fillMaxSize()) {
        BackBar("Bluetooth") { vm.screen = Screen.Main }
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(start = 18.dp, end = 18.dp, bottom = 22.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(
                Modifier.align(Alignment.CenterHorizontally).padding(top = 8.dp).size(150.dp).clip(CircleShape)
                    .background(Brush.radialGradient(listOf(Color(0xFF1F3350), Color(0xFF182436), Color(0xFF141C28)))),
                contentAlignment = Alignment.Center,
            ) { NIcon("bt", 54.dp, C.blue, 2f) }
            Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
                T("Elige tu PC", 20.sp, weight = FontWeight.ExtraBold)
                Spacer(Modifier.height(4.dp))
                T("Aparecen los equipos ya vinculados con este celular.", 13.sp, C.muted, align = TextAlign.Center)
            }
            when {
                !granted -> {
                    InfoBox("Para usar Bluetooth, Android pide el permiso «Dispositivos cercanos».")
                    NButton("Dar permiso", { ask.launch(Manifest.permission.BLUETOOTH_CONNECT) }, Modifier.fillMaxWidth())
                }
                !vm.btEnabled() -> {
                    InfoBox("El Bluetooth del celular está apagado.")
                    NButton("Encender Bluetooth", {
                        try { ctx.startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) } catch (_: Exception) {}
                    }, Modifier.fillMaxWidth())
                }
                else -> {
                    val pcs = vm.btDevices.filter { it.computer }
                    val others = vm.btDevices.filter { !it.computer }
                    if (vm.st == St.Connecting && vm.transport == "bt") {
                        T("Conectando con ${vm.pcName}…", 13.sp, C.acc)
                    }
                    vm.error?.let { T(it, 13.sp, C.badText, lh = 18.sp) }
                    SectionLabel("Computadores")
                    if (pcs.isEmpty()) T("Ninguno todavía.", 13.sp, C.muted)
                    for (d in pcs) {
                        RowItem("pc", d.name, "Vinculado · ${d.address}", { vm.connectBt(d) }, C.blue) {
                            T("Conectar", 13.sp, C.acc, FontWeight.Bold)
                        }
                    }
                    if (others.isNotEmpty()) {
                        SectionLabel("Otros equipos vinculados")
                        for (d in others) {
                            RowItem("bt", d.name, d.address, { vm.connectBt(d) }, C.muted) {
                                T("Probar", 13.sp, C.muted, FontWeight.Bold)
                            }
                        }
                    }
                    InfoBox("¿No aparece tu PC? Primero vincúlalos: en el PC activa el Bluetooth y en el celular ve a Ajustes → Bluetooth → Vincular nuevo dispositivo. Funciona hasta unos 10 m.")
                    NButton("Abrir ajustes de Bluetooth", {
                        try { ctx.startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) } catch (_: Exception) {}
                    }, Modifier.fillMaxWidth(), Kind.Ghost, "bt")
                }
            }
        }
    }
}

// ==================================================================== conectado
@Composable
fun ConnectedScreen(vm: AppVm) {
    Column(Modifier.fillMaxSize().padding(start = 26.dp, end = 26.dp, bottom = 26.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Spacer(Modifier.weight(0.6f))
        Box(Modifier.size(110.dp).clip(CircleShape).background(C.okSoft), contentAlignment = Alignment.Center) {
            NIcon("check", 56.dp, C.ok, 2.6f)
        }
        Spacer(Modifier.height(26.dp))
        T("¡Listo, conectado!", 26.sp, weight = FontWeight.ExtraBold)
        Spacer(Modifier.height(10.dp))
        T("${vm.pcName} por ${transportName(vm.transport)}" + (if (vm.latency >= 0) " · ${vm.latency} ms de demora." else ".") + "\nLa próxima vez se conecta solo.",
            15.sp, C.muted, align = TextAlign.Center, lh = 22.sp)
        Spacer(Modifier.height(22.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for (t in listOf("${vm.state.banks.size} bancos", "${vm.state.countSounds()} sonidos", "${vm.state.countKeys()} atajos")) {
                Box(Modifier.clip(RoundedCornerShape(14.dp)).background(C.panel2).padding(horizontal = 12.dp, vertical = 6.dp)) { T(t, 13.sp) }
            }
        }
        Spacer(Modifier.weight(1f))
        NButton("Ir a la botonera", {
            vm.screen = Screen.Main
            vm.tab = Tab.Pads
        }, Modifier.fillMaxWidth(), icon = "grid")
    }
}
