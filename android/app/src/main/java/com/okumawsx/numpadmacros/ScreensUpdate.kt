package com.okumawsx.numpadmacros

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Aviso arriba de la botonera: «Hay una versión nueva». */
@Composable
fun UpdateBanner(vm: AppVm, modifier: Modifier = Modifier) {
    val info = vm.updInfo ?: return
    Row(
        modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(C.accSoft).border(1.dp, C.accLine, RoundedCornerShape(18.dp))
            .padding(start = 14.dp, end = 6.dp, top = 8.dp, bottom = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        NIcon("up", 20.dp, C.acc)
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            T("Hay una versión nueva · ${info.version}", 13.sp, weight = FontWeight.ExtraBold, lines = 1)
            T(info.notes.firstOrNull() ?: "Toca «Ver» para las novedades", 12.sp, C.muted, lines = 1)
        }
        Spacer(Modifier.width(8.dp))
        Box(
            Modifier.height(36.dp).clip(CircleShape).background(C.acc).clickable(role = Role.Button) { vm.openUpdate() }.padding(horizontal = 16.dp),
            contentAlignment = Alignment.Center,
        ) { T("Ver", 13.sp, C.accDark, FontWeight.ExtraBold) }
        Box(
            Modifier.size(36.dp).clip(CircleShape).clickable(role = Role.Button) { vm.updateLater() }.semantics { contentDescription = "Ahora no" },
            contentAlignment = Alignment.Center,
        ) { NIcon("x", 16.dp, C.muted) }
    }
}

/** Hoja de actualización: buscando, al día, novedades, permiso, descarga, instalar o error. */
@Composable
fun UpdateSheet(vm: AppVm) {
    val info = vm.updInfo
    val title = when (vm.updPhase) {
        "buscando" -> "Buscar actualizaciones"
        "aldia" -> "Actualizaciones"
        "error" -> "Actualización"
        else -> "Versión nueva"
    }
    Sheet(title, "Tienes la $APP_VERSION · se descarga de GitHub", { vm.closeUpdate() }) {
        when (vm.updPhase) {
            "buscando" -> Row(
                Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(C.panel2).padding(18.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                CircularProgressIndicator(Modifier.size(22.dp), color = C.acc, trackColor = C.line, strokeWidth = 3.dp)
                Spacer(Modifier.width(12.dp))
                T("Buscando en GitHub…", 14.sp, weight = FontWeight.Bold)
            }

            "aldia" -> {
                Column(Modifier.fillMaxWidth().padding(top = 12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Box(Modifier.size(64.dp).clip(CircleShape).background(C.okSoft), contentAlignment = Alignment.Center) { NIcon("check", 32.dp, C.ok, 2.4f) }
                    Spacer(Modifier.height(10.dp))
                    T("Estás al día", 18.sp, weight = FontWeight.ExtraBold)
                    T("La $APP_VERSION es la última versión" + if (vm.updBeta) " (incluidas las betas)." else ".", 13.sp, C.muted, align = TextAlign.Center)
                }
                NButton("Cerrar", { vm.closeUpdate() }, Modifier.fillMaxWidth(), Kind.Ghost)
            }

            "nueva" -> if (info != null) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.clip(CircleShape).background(C.accSoft).padding(horizontal = 10.dp, vertical = 4.dp)) {
                        T("$APP_VERSION → ${info.version}", 12.sp, C.acc, FontWeight.ExtraBold)
                    }
                    Spacer(Modifier.width(10.dp))
                    T(listOfNotNull(sizeMb(info.size), info.published.takeIf { it.isNotBlank() }, if (info.beta) "beta" else null).joinToString(" · "), 12.sp, C.muted, lines = 1)
                }
                SectionLabel("Novedades")
                Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(C.panel2).padding(horizontal = 14.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (info.notes.isEmpty()) T("Esta versión no trae notas.", 13.5.sp, C.muted)
                    for (n in info.notes) Row {
                        T("•", 13.5.sp, C.acc)
                        Spacer(Modifier.width(8.dp))
                        T(n, 13.5.sp, lh = 19.sp)
                    }
                    T("Ver todo en GitHub", 13.sp, C.acc, FontWeight.Bold, Modifier.clip(RoundedCornerShape(8.dp)).clickable { vm.openReleasePage() }.padding(vertical = 4.dp))
                }
                InfoBox("Se instala encima de la que tienes: no pierdes tus PCs vinculados ni tus ajustes.")
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    NButton("Ahora no", { vm.updateLater() }, kind = Kind.Ghost, fontSize = 14.sp)
                    NButton("Actualizar", { vm.startUpdate() }, Modifier.weight(1f), icon = "up")
                }
            }

            "permiso" -> {
                Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(C.panel2).padding(14.dp)) {
                    NIcon("info", 24.dp, C.acc)
                    Spacer(Modifier.width(12.dp))
                    Column {
                        T("Falta un permiso (solo la primera vez)", 14.sp, weight = FontWeight.Bold)
                        T("Android te mostrará «Instalar apps desconocidas». Activa «Permitir de esta fuente» para Numpad Macros y vuelve aquí: la descarga empieza sola.", 13.sp, C.muted, lh = 18.sp)
                    }
                }
                NButton("Abrir ajustes de Android", { vm.openInstallPermission() }, Modifier.fillMaxWidth())
                NButton("Cancelar", { vm.closeUpdate() }, Modifier.fillMaxWidth(), Kind.Link)
            }

            "descarga" -> {
                val f = if (vm.updTotal > 0) (vm.updDone.toFloat() / vm.updTotal).coerceIn(0f, 1f) else 0f
                Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(C.panel2).padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Row {
                        T("Descargando ${info?.version ?: ""}…", 14.sp, weight = FontWeight.Bold, modifier = Modifier.weight(1f))
                        T("${sizeMb(vm.updDone) ?: "0 MB"} / ${sizeMb(vm.updTotal) ?: "?"}", 12.5.sp, C.muted)
                    }
                    Box(Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(3.dp)).background(C.bg)) {
                        Box(Modifier.fillMaxHeight().fillMaxWidth(f).background(C.acc))
                    }
                    T("Puedes cerrar esta hoja y seguir usando la botonera: la descarga sigue.", 12.sp, C.muted)
                }
                NButton("Cancelar descarga", { vm.cancelUpdate() }, Modifier.fillMaxWidth(), Kind.Ghost, fontSize = 14.sp)
            }

            "instalar" -> {
                Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(C.panel2).padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        NIcon("check", 18.dp, C.ok, 2.4f)
                        Spacer(Modifier.width(8.dp))
                        T("Descargada y comprobada", 14.sp, weight = FontWeight.ExtraBold)
                    }
                    T("La huella SHA256 coincide con la publicada en GitHub.", 12.5.sp, C.muted)
                }
                T("Android te pedirá confirmar. Cuando termine, toca «Abrir» para volver a la app.", 13.sp, C.muted, lh = 18.sp)
                NButton("Instalar", { vm.installUpdate() }, Modifier.fillMaxWidth(), icon = "check")
            }

            else -> {
                Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(C.badSoft).border(1.dp, C.badLine, RoundedCornerShape(14.dp)).padding(14.dp)) {
                    Column {
                        T("No se pudo actualizar", 14.sp, C.badText, FontWeight.ExtraBold)
                        T(vm.updError.ifBlank { "Algo falló." } + " Tu versión actual sigue igual.", 13.5.sp, C.badText, lh = 19.sp)
                    }
                }
                NButton("Intentar de nuevo", { if (vm.updInfo != null) vm.startUpdate() else vm.checkUpdates(manual = true) }, Modifier.fillMaxWidth(), icon = "refresh")
                NButton("Descargar desde GitHub en el navegador", { vm.openReleasePage() }, Modifier.fillMaxWidth(), Kind.Link)
            }
        }
    }
}

/** Sección «Actualizaciones» de Ajustes. */
@Composable
fun UpdateSettings(vm: AppVm, row: @Composable (String, String, Boolean, () -> Unit) -> Unit) {
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(C.panel).padding(start = 12.dp, end = 12.dp, top = 2.dp, bottom = 12.dp)) {
        row("Buscar actualizaciones solas", "Al abrir la app, como mucho una vez al día", vm.updAuto) { vm.setUpdAutoPref(!vm.updAuto) }
        row("Recibir versiones de prueba (beta)", "Llegan antes, pero pueden traer fallas", vm.updBeta) { vm.setUpdBetaPref(!vm.updBeta) }
        val info = vm.updInfo
        Row(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(C.panel2).padding(start = 12.dp, end = 8.dp, top = 10.dp, bottom = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(Modifier.size(10.dp).clip(CircleShape).background(if (info != null) C.acc else C.ok))
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                T(if (info != null) "Hay una versión nueva: ${info.version}" else "Versión $APP_VERSION", 13.5.sp, weight = FontWeight.Bold, lines = 1)
                T(if (info != null) "Toca «Ver» para las novedades" else "Revisado: ${ago(vm.updLast)}", 12.sp, C.muted, lines = 1)
            }
            NButton(
                if (info != null) "Ver" else "Buscar ahora",
                { if (info != null) vm.openUpdate() else vm.checkUpdates(manual = true) },
                kind = Kind.Ghost, height = 38.dp, fontSize = 13.sp,
            )
        }
    }
}

private fun sizeMb(b: Long): String? = if (b <= 0) null else "%.1f MB".format(b / 1048576.0)
