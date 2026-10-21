package com.okumawsx.numpadmacros

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.draw.alpha
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun SettingsTab(vm: AppVm) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(start = 16.dp, end = 16.dp, bottom = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        T("Ajustes", 24.sp, weight = FontWeight.ExtraBold)
        val (status, color) = statusLine(vm)
        Row(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(C.panel).clickable { vm.screen = Screen.SavedPcs }.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            NIcon("pc", 26.dp, C.acc)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                T(vm.pcName.ifBlank { "Ningún PC" }, 15.sp, weight = FontWeight.Bold)
                T(if (vm.st == St.Online) "Conectado por ${transportName(vm.transport)}" + (if (vm.latency >= 0) " · ${vm.latency} ms" else "") else status, 12.5.sp, color)
            }
            T("Mis PCs", 13.sp, C.acc, FontWeight.Bold)
            NIcon("chev", 20.dp, C.muted)
        }
        SectionLabel("Apariencia")
        Appearance(vm)
        SectionLabel("Botonera")
        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(C.panel).padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            T("Diseño de los botones", 13.sp, C.muted)
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                for ((id, n) in listOf("numpad" to "Forma de numpad", "cuadricula" to "Cuadrícula", "grandes" to "Grandes")) {
                    Chip(n, vm.layout == id, { vm.setLayoutPref(id) }, Modifier.weight(1f))
                }
            }
        }
        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(C.panel).padding(horizontal = 12.dp, vertical = 2.dp)) {
            SetRow("Vibrar al tocar", "Confirma cada pulsación", vm.vibrate) { vm.setVibratePref(!vm.vibrate) }
            SetRow("Pantalla siempre encendida", "Mientras la botonera está abierta", vm.keepOn) { vm.setKeepOnPref(!vm.keepOn) }
            SetRow("Reconectar solo", "Al abrir la app vuelve al último PC", vm.autoReconnect) { vm.setAutoPref(!vm.autoReconnect) }
            SetRow("Mostrar medidor del PC", "Nivel de lo que suena", vm.meter) { vm.setMeterPref(!vm.meter) }
        }
        SectionLabel("Actualizaciones")
        UpdateSettings(vm) { t, sub, on, click -> SetRow(t, sub, on, click) }
        RowItem("info", "Acerca de y soporte", "Versión $APP_VERSION · OkumaWsX", { vm.screen = Screen.About }) { NIcon("chev", 20.dp, C.muted) }
        Spacer(Modifier.height(LocalNavSpace.current))
    }
}

@Composable
private fun Appearance(vm: AppVm) {
    val special = vm.especial
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(C.panel).padding(14.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if (special.isNotBlank()) {
            Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(C.accSoft).border(1.dp, C.accLine, RoundedCornerShape(12.dp)).padding(horizontal = 12.dp, vertical = 9.dp)) {
                T("${if (special == "amoled") "AMOLED / OLED" else "Alto contraste"} está activo. Desactívalo para elegir un tema.", 12.5.sp, C.acc)
            }
        }
        T("Tema · ${if (special == "amoled") "AMOLED / OLED" else if (special == "contraste") "Alto contraste" else vm.tema}", 13.sp, C.muted)
        val names = Themes.list.keys.toList()
        Column(Modifier.alpha(if (special.isNotBlank()) 0.38f else 1f), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            for (row in names.chunked(4)) {
                Row(Modifier.fillMaxWidth()) {
                    for (n in row) {
                        val c = Themes.list.getValue(n)
                        val on = n == vm.tema
                        Column(
                            Modifier.weight(1f).clip(RoundedCornerShape(12.dp))
                                .clickable(enabled = special.isBlank(), role = Role.RadioButton) { vm.setTemaPref(n) }
                                .semantics { contentDescription = "Tema $n" + if (on) ", elegido" else "" }
                                .padding(vertical = 4.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Box(Modifier.size(52.dp).clip(CircleShape).border(3.dp, if (on) C.acc else Color.Transparent, CircleShape), contentAlignment = Alignment.Center) {
                                Box(
                                    Modifier.size(40.dp).clip(CircleShape).background(Color(c.getValue("bg"))).border(1.dp, Color(c.getValue("line")), CircleShape),
                                    contentAlignment = Alignment.Center,
                                ) { Box(Modifier.size(16.dp).clip(CircleShape).background(Color(c.getValue("acc")))) }
                            }
                            Spacer(Modifier.height(4.dp))
                            T(n, 11.sp, if (on) C.text else C.muted, if (on) FontWeight.ExtraBold else FontWeight.Medium, lines = 1)
                        }
                    }
                    repeat(4 - row.size) { Spacer(Modifier.weight(1f)) }
                }
            }
        }
        Box(Modifier.fillMaxWidth().height(1.dp).background(C.line))
        for ((id, title, sub) in listOf(
            Triple("contraste", "Alto contraste", "Negro y amarillo, texto más fuerte"),
            Triple("amoled", "Pantalla AMOLED / OLED", "Negro puro: ahorra batería"),
        )) {
            val on = special == id
            Row(
                Modifier.fillMaxWidth().clickable(role = Role.Switch) { vm.setEspecialPref(if (on) "" else id) }.padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(
                    Modifier.size(30.dp).clip(CircleShape).background(Color.Black).border(1.dp, C.line, CircleShape),
                    contentAlignment = Alignment.Center,
                ) { Box(Modifier.size(12.dp).clip(CircleShape).background(if (id == "contraste") Color(0xFFFFD400) else Color(0xFFF2F2F2))) }
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    T(title, 14.5.sp, weight = FontWeight.Bold)
                    T(sub, 12.5.sp, C.muted)
                }
                Toggle(on)
            }
        }
        T("Si en el PC marcas «Usar también en el celular conectado», el tema del PC se aplica aquí solo. Alto contraste y AMOLED no se mandan al PC.", 12.sp, C.muted, lh = 17.sp)
    }
}

@Composable
private fun SetRow(title: String, sub: String, on: Boolean, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clickable(role = Role.Switch, onClick = onClick).padding(vertical = 12.dp, horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            T(title, 14.5.sp, weight = FontWeight.Bold)
            T(sub, 12.5.sp, C.muted)
        }
        Toggle(on)
    }
}

@Composable
fun SavedPcsScreen(vm: AppVm) {
    var sel by remember { mutableStateOf<String?>(null) }
    Column(Modifier.fillMaxSize()) {
        BackBar("Mis PCs") { vm.screen = Screen.Main }
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(start = 16.dp, end = 16.dp, bottom = 22.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (vm.pcs.isEmpty()) T("Todavía no vinculas ningún PC.", 14.sp, C.muted)
            for (p in vm.pcs) {
                val active = vm.st == St.Online && vm.pcName == p.name
                val ic = when (p.transport) { "bt" -> C.blue; "usb" -> C.ok; else -> C.acc }
                RowItem(
                    "pc", p.name, (if (active) "Conectado · " else "") + "${transportName(p.transport)} · último uso: ${ago(p.last)}",
                    { sel = if (sel == p.id) null else p.id }, ic, if (active) C.accSoft else C.panel2, if (active) C.accLine else C.line,
                ) {
                    if (active) T("Activo", 12.sp, C.ok, FontWeight.Bold) else NIcon("dots", 20.dp, C.muted)
                }
                if (sel == p.id) {
                    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(C.panel).padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        T(p.name, weight = FontWeight.Bold)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            NButton("Conectar", { vm.connectSaved(p); vm.screen = Screen.Main; vm.tab = Tab.Pads }, Modifier.weight(1f), Kind.Ghost, height = 44.dp, fontSize = 14.sp)
                            NButton("Olvidar", { vm.forget(p); sel = null }, Modifier.weight(1f), Kind.Danger, height = 44.dp, fontSize = 14.sp)
                        }
                        T("«Olvidar» borra la vinculación: la próxima vez tendrás que escribir el código.", 12.sp, C.muted)
                    }
                }
            }
            Spacer(Modifier.height(8.dp))
            NButton("Agregar otro PC", { vm.screen = Screen.Main; vm.tab = Tab.Conn }, Modifier.fillMaxWidth(), Kind.Ghost, "plus")
        }
    }
}

@Composable
fun AboutScreen(vm: AppVm) {
    val ctx = LocalContext.current
    fun open(url: String) {
        try { ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) } catch (_: Exception) {}
    }
    Column(Modifier.fillMaxSize()) {
        BackBar("Acerca de") { vm.screen = Screen.Main }
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(start = 18.dp, end = 18.dp, bottom = 22.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(Modifier.padding(top = 6.dp, bottom = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                Logo(64.dp)
                Spacer(Modifier.width(14.dp))
                Column {
                    T("Numpad Macros", 20.sp, weight = FontWeight.ExtraBold)
                    T("App para Android $APP_VERSION · por OkumaWsX", 13.sp, C.muted)
                }
            }
            RowItem("info", "Instagram", "@okumawsx", { open("https://instagram.com/okumawsx") }, Color(0xFFE1306C)) { NIcon("chev", 20.dp, C.muted) }
            RowItem("link", "Discord", "Comunidad y soporte", { open("https://discord.gg/hcutJcBx9") }, Color(0xFF8A94FF)) { NIcon("chev", 20.dp, C.muted) }
            RowItem("grid", "GitHub", "Código fuente y novedades", { open("https://github.com/OkumaWsX/NumpadMacros") }) { NIcon("chev", 20.dp, C.muted) }
            RowItem("refresh", "Buscar actualizaciones", "Revisa ahora si hay una versión nueva", { vm.checkUpdates(manual = true) }, C.ok) { NIcon("chev", 20.dp, C.muted) }
            Spacer(Modifier.height(8.dp))
            Row(
                Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(C.panel).border(1.dp, C.acc, RoundedCornerShape(18.dp)).padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    T("¿Te sirve la app?", weight = FontWeight.Bold)
                    T("Es gratis. Si quieres apoyarla, puedes donar.", 12.5.sp, C.muted)
                }
                Spacer(Modifier.width(10.dp))
                NButton("Donar", { open("https://ceneka.net/OkumaWsX") }, icon = "heart")
            }
            T("Software libre · LGPL-3.0", 12.sp, C.muted, align = TextAlign.Center, modifier = Modifier.fillMaxWidth())
        }
    }
}
