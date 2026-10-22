// SPDX-License-Identifier: LGPL-3.0-or-later
// Copyright (C) 2026 OkumaWsX
// Pantallas del Publicador (mismo aspecto que el de escritorio: oscuro con acento naranja).
package com.okumawsx.publicador

import android.Manifest
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

object C {
    val bg = Color(0xFF14161B)
    val panel = Color(0xFF1C1F26)
    val panel2 = Color(0xFF232730)
    val line = Color(0xFF2E333D)
    val text = Color(0xFFE9E9EC)
    val muted = Color(0xFF8B909B)
    val soft = Color(0xFFB9BDC6)
    val accent = Color(0xFFF2A33A)
    val onAccent = Color(0xFF1A1306)
    val ok = Color(0xFF4CC38A)
    val bad = Color(0xFFE5534B)
    val warn = Color(0xFFE2B340)
    val discord = Color(0xFF313338)
}

const val APP_VERSION = "1.0.1"

@Composable
fun App(vm: Vm) {
    MaterialTheme(colorScheme = darkColorScheme(primary = C.accent, onPrimary = C.onAccent, background = C.bg,
        surface = C.panel, onSurface = C.text, onBackground = C.text)) {
        Column(Modifier.fillMaxSize().background(C.bg).safeDrawingPadding()) {
            Header(vm)
            Box(Modifier.weight(1f).fillMaxWidth()) {
                when (vm.screen) {
                    Screen.CONNECT -> ConnectScreen(vm)
                    Screen.HOME -> HomeScreen(vm)
                    Screen.CHECKS -> ChecksScreen(vm)
                    Screen.REVIEW -> ReviewScreen(vm)
                    Screen.PUBLISHING -> PublishingScreen(vm)
                    Screen.THEME -> ThemeScreen(vm)
                }
            }
        }
        val running = Pub.state.collectAsState().value?.running == true
        BackHandler(enabled = vm.screen != Screen.HOME && vm.screen != Screen.CONNECT && !running) { vm.showHome() }
    }
}

@Composable
private fun Header(vm: Vm) {
    Row(Modifier.fillMaxWidth().background(C.panel).padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(30.dp).clip(RoundedCornerShape(8.dp)).background(C.accent), contentAlignment = Alignment.Center) {
            Text("⬆", color = C.onAccent, fontWeight = FontWeight.Bold, fontSize = 16.sp)
        }
        Column(Modifier.padding(start = 10.dp).weight(1f)) {
            Text("Publicador · Numpad Macros", color = C.text, fontWeight = FontWeight.Bold, fontSize = 16.sp)
            if (vm.user.isNotEmpty() && vm.screen != Screen.CONNECT) {
                Text("● Conectado como ${vm.user}", color = C.ok, fontSize = 12.sp)
            }
        }
        if (vm.lastPub != null && vm.screen == Screen.HOME) {
            Column(horizontalAlignment = Alignment.End) {
                Text("Última publicada", color = C.muted, fontSize = 11.sp)
                Text(vm.lastPub ?: "", color = C.text, fontWeight = FontWeight.Bold, fontSize = 14.sp)
            }
        }
    }
    Box(Modifier.fillMaxWidth().height(1.dp).background(C.line))
}

// ---------------------------------------------------------------- piezas
@Composable
private fun Page(content: @Composable () -> Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) { content() }
}

@Composable
private fun Title(text: String, color: Color = C.text) =
    Text(text, color = color, fontSize = 21.sp, fontWeight = FontWeight.Bold, lineHeight = 26.sp)

@Composable
private fun Body(text: String, color: Color = C.text, size: Int = 14, bold: Boolean = false, modifier: Modifier = Modifier) =
    Text(text, color = color, fontSize = size.sp, lineHeight = (size + 6).sp,
        fontWeight = if (bold) FontWeight.Bold else FontWeight.Normal, modifier = modifier)

@Composable
private fun Accent(text: String, enabled: Boolean = true, modifier: Modifier = Modifier, onClick: () -> Unit) =
    Button(onClick = onClick, enabled = enabled, modifier = modifier.heightIn(min = 48.dp), shape = RoundedCornerShape(10.dp),
        colors = ButtonDefaults.buttonColors(containerColor = C.accent, contentColor = C.onAccent,
            disabledContainerColor = C.panel2, disabledContentColor = C.muted)) {
        Text(text, fontWeight = FontWeight.Bold, fontSize = 15.sp)
    }

@Composable
private fun Plain(text: String, modifier: Modifier = Modifier, onClick: () -> Unit) =
    OutlinedButton(onClick = onClick, modifier = modifier.heightIn(min = 48.dp), shape = RoundedCornerShape(10.dp),
        border = BorderStroke(1.dp, C.line), colors = ButtonDefaults.outlinedButtonColors(contentColor = C.text)) {
        Text(text, fontSize = 14.sp)
    }

@Composable
private fun Link(text: String, color: Color = C.accent, onClick: () -> Unit) =
    Text(text, color = color, fontSize = 14.sp, textDecoration = TextDecoration.Underline,
        modifier = Modifier.clickable(onClick = onClick).padding(vertical = 10.dp, horizontal = 2.dp))

@Composable
private fun FailBox(title: String, msg: String, content: @Composable () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(top = 16.dp).clip(RoundedCornerShape(10.dp)).background(Color(0xFF3A1A1A))
        .border(1.dp, Color(0xFF7A2E2E), RoundedCornerShape(10.dp)).padding(14.dp)) {
        Body(title, bold = true)
        Body(msg, color = Color(0xFFE3B5B5), modifier = Modifier.padding(top = 4.dp, bottom = 10.dp))
        content()
    }
}

@Composable
private fun StepRow(state: String, title: String, detail: String = "", right: String = "", frac: Float? = null) {
    val (icon, col) = when (state) {
        "run" -> "●" to C.accent
        "ok" -> "✓" to C.ok
        "bad" -> "✕" to C.bad
        else -> "·" to C.muted
    }
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
        Text(icon, color = col, fontWeight = FontWeight.Bold, fontSize = 16.sp, modifier = Modifier.width(26.dp))
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(title, color = if (state == "pending") C.muted else C.text, fontSize = 14.sp,
                    fontWeight = if (state == "run") FontWeight.Bold else FontWeight.Normal, modifier = Modifier.weight(1f))
                if (right.isNotEmpty()) Text(right, color = C.muted, fontSize = 12.sp, modifier = Modifier.padding(start = 8.dp))
            }
            if (detail.isNotEmpty()) Body(detail, color = C.muted, size = 13)
            if (frac != null) {
                LinearProgressIndicator(progress = { frac.coerceIn(0f, 1f) }, color = if (state == "bad") C.bad else C.accent,
                    trackColor = C.panel2, modifier = Modifier.fillMaxWidth().padding(top = 5.dp).height(5.dp).clip(RoundedCornerShape(3.dp)))
            }
        }
    }
}

private fun openUrl(ctx: Context, url: String) {
    try {
        ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    } catch (_: Exception) {
    }
}

// ---------------------------------------------------------------- conectar
@Composable
private fun ConnectScreen(vm: Vm) {
    val ctx = LocalContext.current
    var tok by remember { mutableStateOf("") }
    Page {
        Title("Conectar con GitHub (una sola vez)")
        Body("El Publicador necesita un «token»: una llave que le permite subir versiones a tu repositorio " +
            "NumpadMacros. Se guarda cifrada solo en este teléfono.", color = C.muted, modifier = Modifier.padding(top = 4.dp, bottom = 14.dp))
        listOf(
            "Pulsa «Crear el token en GitHub» (se abre el navegador, con tu sesión de GitHub).",
            "Nombre: «Publicador Numpad Macros». Expiración: 1 año.",
            "En «Repository access» elige «Only select repositories» → NumpadMacros.",
            "En «Permissions → Repository permissions» pon en «Read and write»: Actions, Contents y Workflows.",
            "Pulsa «Generate token», copia el texto que empieza con github_pat_ y pégalo abajo.",
        ).forEachIndexed { i, s -> Body("${i + 1}.  $s", modifier = Modifier.padding(vertical = 3.dp)) }
        Body("Puedes usar el mismo token que en el PC.", color = C.muted, size = 13, modifier = Modifier.padding(top = 6.dp))
        Plain("Crear el token en GitHub ↗", Modifier.padding(top = 12.dp)) { openUrl(ctx, TOKEN_URL) }
        OutlinedTextField(tok, { tok = it }, singleLine = true, label = { Text("Token (github_pat_…)") },
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            colors = fieldColors(), modifier = Modifier.fillMaxWidth().padding(top = 16.dp))
        Row(Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Plain("Pegar") {
                val cm = ctx.getSystemService(ClipboardManager::class.java)
                val t = cm.primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(ctx)?.toString()?.trim() ?: ""
                if (t.isNotEmpty()) { tok = t; vm.connectMsg = "Token pegado. Pulsa «Guardar y probar»."; vm.connectBad = false }
                else { vm.connectMsg = "El portapapeles está vacío: copia el token en GitHub primero."; vm.connectBad = true }
            }
            Accent("Guardar y probar", enabled = !vm.busy, modifier = Modifier.weight(1f)) { vm.saveToken(tok) }
        }
        if (vm.connectMsg.isNotEmpty()) Body(vm.connectMsg, color = if (vm.connectBad) C.bad else C.muted, modifier = Modifier.padding(top = 10.dp))
        if (vm.gh != null) Link("Volver sin cambiar el token", C.muted) { vm.showHome() }
    }
}

@Composable
private fun fieldColors() = OutlinedTextFieldDefaults.colors(focusedBorderColor = C.accent, unfocusedBorderColor = C.line,
    focusedTextColor = C.text, unfocusedTextColor = C.text, cursorColor = C.accent, focusedLabelColor = C.accent,
    unfocusedLabelColor = C.muted, focusedContainerColor = C.panel2, unfocusedContainerColor = C.panel2)

// ---------------------------------------------------------------- inicio
@Composable
private fun HomeScreen(vm: Vm) {
    val ctx = LocalContext.current
    val pickZip = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { it?.let(vm::openZip) }
    val pickDir = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { it?.let(vm::openFolder) }
    Page {
        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(Color(0xFF1A1D23))
            .border(2.dp, Color(0xFF3A3F4A), RoundedCornerShape(14.dp)).clickable { pickZip.launch(arrayOf("application/zip", "application/x-zip-compressed", "application/octet-stream")) }
            .padding(horizontal = 16.dp, vertical = 24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text("⬆", color = C.accent, fontSize = 34.sp, fontWeight = FontWeight.Bold)
            Body("Elige la versión nueva", bold = true, size = 18, modifier = Modifier.padding(top = 4.dp))
            Body("El archivo NumpadMacros-codigo_X.Y.Z.zip que te entrego (o la carpeta del proyecto). También puedes " +
                "«Compartir» el .zip con el Publicador desde Archivos, Drive o Telegram.", color = C.soft, size = 13,
                modifier = Modifier.padding(top = 6.dp))
            Body("No hace falta el .exe: el instalador se fabrica solo en GitHub.", color = C.muted, size = 12,
                modifier = Modifier.padding(top = 6.dp))
            Row(Modifier.padding(top = 14.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Accent("Elegir .zip…") { pickZip.launch(arrayOf("application/zip", "application/x-zip-compressed", "application/octet-stream")) }
                Plain("Elegir carpeta…") { pickDir.launch(null) }
            }
        }
        Body("Versiones publicadas", bold = true, size = 15, modifier = Modifier.padding(top = 20.dp, bottom = 6.dp))
        val rels = vm.releases
        when {
            vm.homeError.isNotEmpty() -> Body(vm.homeError, color = C.bad)
            rels == null -> Row(verticalAlignment = Alignment.CenterVertically) {
                CircularProgressIndicator(color = C.accent, strokeWidth = 2.dp, modifier = Modifier.size(16.dp))
                Body("Cargando…", color = C.muted, modifier = Modifier.padding(start = 8.dp))
            }
            rels.isEmpty() -> Body("Todavía no hay versiones publicadas: esta será la primera.", color = C.muted)
            else -> rels.forEach { rel ->
                Row(Modifier.fillMaxWidth().padding(vertical = 2.dp).clip(RoundedCornerShape(8.dp)).background(C.panel2)
                    .clickable { openUrl(ctx, rel.optString("html_url")) }.padding(horizontal = 12.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Text(rel.optString("tag_name") + if (rel.optBoolean("prerelease")) " · beta" else "", color = C.text,
                        fontWeight = FontWeight.Bold, fontSize = 14.sp, modifier = Modifier.weight(1f))
                    Text(rel.optString("published_at").take(10), color = C.muted, fontSize = 13.sp)
                    Text("  ↗", color = C.accent, fontSize = 14.sp)
                }
            }
        }
        Row(Modifier.fillMaxWidth().padding(top = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("Publicador $APP_VERSION", color = C.muted, fontSize = 12.sp, modifier = Modifier.weight(1f))
            Link("Crear tema .npt…") { vm.showTheme() }
            Spacer(Modifier.width(14.dp))
            Link("Cambiar token", C.muted) { vm.showConnect() }
        }
    }
}

// ---------------------------------------------------------------- revisión
@Composable
private fun ChecksScreen(vm: Vm) {
    Page {
        Title("Revisando ${vm.reviewing}…")
        Spacer(Modifier.height(12.dp))
        vm.checks.forEach { StepRow(it.state, it.name, it.detail) }
        vm.checkFail?.let { msg ->
            FailBox("No se puede publicar este archivo.", msg) { Plain("Elegir otro archivo") { vm.showHome() } }
        }
    }
}

@Composable
private fun ReviewScreen(vm: Vm) {
    val rv = vm.rv ?: return
    val ctx = LocalContext.current
    val askNotify = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { vm.publish() }
    Page {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(vstr(rv.published), color = C.muted, fontSize = 22.sp, fontWeight = FontWeight.Bold,
                modifier = Modifier.clip(RoundedCornerShape(8.dp)).background(C.panel2).padding(horizontal = 12.dp, vertical = 4.dp))
            Text("→", color = C.muted, fontSize = 22.sp, modifier = Modifier.padding(horizontal = 10.dp))
            Text(vstr(rv.version), color = C.accent, fontSize = 22.sp, fontWeight = FontWeight.Bold,
                modifier = Modifier.clip(RoundedCornerShape(8.dp)).background(Color(0xFF3A2C14))
                    .border(1.dp, Color(0xFF7A5520), RoundedCornerShape(8.dp)).padding(horizontal = 12.dp, vertical = 4.dp))
        }
        Body("Tipo detectado: ${rv.kind}", bold = true, modifier = Modifier.padding(top = 12.dp))
        Body("Se instalará encima de la que tienen los usuarios, como actualización de la misma app.", color = C.soft, size = 13)

        Body("Notas de la versión (salen del CHANGELOG; puedes corregirlas aquí)", bold = true, modifier = Modifier.padding(top = 18.dp))
        OutlinedTextField(vm.notes, { vm.notes = it; vm.notesError = "" }, colors = fieldColors(),
            textStyle = MaterialTheme.typography.bodyMedium.copy(color = C.text),
            modifier = Modifier.fillMaxWidth().heightIn(min = 160.dp, max = 360.dp).padding(top = 6.dp))
        if (vm.notesError.isNotEmpty()) Body(vm.notesError, color = C.bad, size = 13, modifier = Modifier.padding(top = 4.dp))
        val files = rv.added + rv.changed
        var summary = "Archivos: ${rv.changed.size} cambiados, ${rv.added.size} nuevos" +
            (if (rv.deleted.isNotEmpty()) ", ${rv.deleted.size} que se borran" else "") + "."
        if (files.isNotEmpty()) summary += " " + files.take(5).joinToString(", ") { it.substringAfterLast('/') } +
            if (files.size > 5) " y más." else "."
        if (files.isEmpty() && rv.deleted.isEmpty()) summary = "El código ya está en GitHub: solo se publica."
        Body(summary, color = C.muted, size = 13, modifier = Modifier.padding(top = 8.dp))
        if (rv.deleted.isNotEmpty()) Body("Se borran: " + rv.deleted.take(6).joinToString(", ") +
            if (rv.deleted.size > 6) " y más" else "", color = C.warn, size = 13)

        Body("Opciones", bold = true, modifier = Modifier.padding(top = 18.dp))
        Option("Versión de prueba (beta)", "Solo la reciben quienes activaron las betas", vm.beta) { vm.beta = it }
        Option("Importante", "Los usuarios no pueden omitirla", vm.important) { vm.important = it }
        Option("Anunciar en mi Discord", "Necesita el webhook configurado en GitHub", vm.discord) { vm.discord = it }
        if (vm.discord) {
            Column(Modifier.fillMaxWidth().padding(top = 8.dp).clip(RoundedCornerShape(8.dp)).background(C.discord).padding(12.dp)) {
                Body("Numpad Macros · bot", bold = true, size = 13)
                Body(vm.discordPreview(), size = 13)
            }
        }
        Accent("Aceptar y publicar ${vstr(rv.version)}", modifier = Modifier.fillMaxWidth().padding(top = 18.dp)) {
            if (Build.VERSION.SDK_INT >= 33) askNotify.launch(Manifest.permission.POST_NOTIFICATIONS) else vm.publish()
        }
        Plain("Cancelar", Modifier.fillMaxWidth().padding(top = 8.dp)) { vm.showHome() }
    }
}

@Composable
private fun Option(title: String, sub: String, value: Boolean, set: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().clickable { set(!value) }.padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Body(title)
            Body(sub, color = C.muted, size = 12)
        }
        Switch(value, set, colors = SwitchDefaults.colors(checkedThumbColor = C.onAccent, checkedTrackColor = C.accent,
            uncheckedTrackColor = C.panel2, uncheckedThumbColor = C.muted, uncheckedBorderColor = C.line))
    }
}

// ---------------------------------------------------------------- publicando
@Composable
private fun PublishingScreen(vm: Vm) {
    val st = Pub.state.collectAsState().value ?: return
    val ctx = LocalContext.current
    Page {
        if (st.done) {
            Title("✓  Numpad Macros ${st.version} publicada", C.ok)
            Body(if (st.beta) "Como beta: solo la reciben quienes activaron las versiones de prueba."
            else "Los usuarios verán el aviso la próxima vez que abran la app.", color = C.soft, modifier = Modifier.padding(top = 4.dp, bottom = 14.dp))
            st.assets?.let { assets ->
                Body("Archivos en la Release", bold = true)
                assets.forEach { (name, size) ->
                    Row(Modifier.fillMaxWidth().padding(vertical = 2.dp).clip(RoundedCornerShape(8.dp)).background(C.panel2)
                        .padding(horizontal = 12.dp, vertical = 9.dp)) {
                        Text(name, color = C.text, fontSize = 13.sp, modifier = Modifier.weight(1f))
                        Text(if (size > 100_000) "%.1f MB".format(size / 1e6) else "${maxOf(1, Math.round(size / 1e3))} KB",
                            color = C.muted, fontSize = 13.sp)
                    }
                }
            }
            if (st.discordFailed) Body("El anuncio en Discord no se pudo enviar (la versión sí quedó publicada). Revisa el " +
                "webhook y vuelve a anunciar desde GitHub: Actions → «Anunciar en Discord» → Run workflow.", color = C.warn,
                modifier = Modifier.padding(top = 12.dp))
            Row(Modifier.padding(top = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (st.releaseUrl.isNotEmpty()) Plain("Ver en GitHub ↗") { openUrl(ctx, st.releaseUrl) }
                Accent("Listo") { vm.showHome() }
            }
            return@Page
        }
        Title(st.title)
        if (st.sub.isNotEmpty()) Body(st.sub, color = C.muted, size = 13, modifier = Modifier.padding(top = 4.dp, bottom = 10.dp))
        st.rows.forEach { StepRow(it.state, it.label, right = it.right, frac = if (it.bar) (it.frac ?: 0f) else null) }
        st.failMsg?.let { msg ->
            FailBox("Se detuvo antes de terminar: los usuarios no recibieron nada nuevo.",
                "$msg Mándame una captura de esta pantalla (y del enlace) y lo arreglo; luego vuelves a elegir la versión corregida.") {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (st.failUrl.isNotEmpty()) Plain("Ver el detalle en GitHub ↗") { openUrl(ctx, st.failUrl) }
                    Plain("Volver al inicio") { vm.showHome() }
                }
            }
        }
    }
}

// ---------------------------------------------------------------- tema .npt
@Composable
private fun ThemeScreen(vm: Vm) {
    val pickJson = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { it?.let(vm::pickThemeJson) }
    val pickKey = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { it?.let(vm::pickThemeKey) }
    val save = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")) {
        it?.let(vm::saveTheme)
    }
    Page {
        Title("Crear tema .npt")
        Body("Convierte un tema en JSON en un archivo .npt firmado con tu clave, para que la app lo muestre como " +
            "tema oficial.", color = C.muted, modifier = Modifier.padding(top = 4.dp, bottom = 14.dp))
        StepRow(if (vm.themeJson != null) "ok" else "run", "1. El tema (JSON)", vm.themeName)
        Plain("Elegir el tema…", Modifier.padding(start = 26.dp)) { pickJson.launch(arrayOf("application/json", "text/*", "application/octet-stream")) }
        Spacer(Modifier.height(10.dp))
        StepRow(if (vm.themeKeyInfo.isNotEmpty()) "ok" else "pending", "2. Tu clave de firma (firma-temas-OkumaWsX.key)", vm.themeKeyInfo)
        Row(Modifier.padding(start = 26.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Plain(if (vm.themeKeyInfo.isEmpty()) "Elegir la clave…" else "Cambiar…") { pickKey.launch(arrayOf("*/*")) }
            if (vm.themeKeyInfo.isNotEmpty()) Link("Olvidar la clave", C.muted) { vm.forgetThemeKey() }
        }
        Body("La clave se guarda cifrada solo en este teléfono. Nunca la subas a GitHub.", color = C.muted, size = 12,
            modifier = Modifier.padding(start = 26.dp, top = 4.dp))
        Accent("Crear y guardar el .npt…", enabled = vm.themeJson != null && vm.themeKeyInfo.isNotEmpty(),
            modifier = Modifier.fillMaxWidth().padding(top = 18.dp)) {
            if (vm.buildTheme()) save.launch((vm.themeName.ifEmpty { "tema" }) + ".npt")
        }
        if (vm.themeMsg.isNotEmpty()) Body(vm.themeMsg, color = if (vm.themeBad) C.bad else C.ok, modifier = Modifier.padding(top = 12.dp))
        Plain("Volver", Modifier.fillMaxWidth().padding(top = 10.dp)) { vm.showHome() }
    }
}
