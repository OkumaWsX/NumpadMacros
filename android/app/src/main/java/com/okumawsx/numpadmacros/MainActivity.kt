package com.okumawsx.numpadmacros

import android.content.Intent
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import kotlinx.coroutines.delay

class MainActivity : ComponentActivity() {
    private val vm: AppVm by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
        )
        super.onCreate(savedInstanceState)
        handleIntent(intent)
        setContent {
            MaterialTheme(colorScheme = darkColorScheme(primary = C.acc, background = C.bg, surface = C.panel)) {
                Root(vm)
            }
            // Íconos de la barra de estado oscuros en los temas claros (Claro, Papel)
            val light = C.light
            LaunchedEffect(light) {
                val c = WindowCompat.getInsetsController(window, window.decorView)
                c.isAppearanceLightStatusBars = light
                c.isAppearanceLightNavigationBars = light
            }
            // Pantalla siempre encendida y pantalla completa
            val keep = vm.keepOn && vm.st == St.Online && vm.screen == Screen.Main && vm.tab == Tab.Pads
            LaunchedEffect(keep) {
                if (keep) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            }
            val full = vm.fullscreen && vm.screen == Screen.Main && vm.tab == Tab.Pads
            LaunchedEffect(full) {
                val c = WindowCompat.getInsetsController(window, window.decorView)
                if (full) {
                    c.systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
                    c.hide(WindowInsetsCompat.Type.systemBars())
                } else c.show(WindowInsetsCompat.Type.systemBars())
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    private fun handleIntent(i: Intent?) {
        val data = i?.data ?: return
        if (data.scheme == "nmacros") vm.handleQr(data.toString())
    }
}

@Composable
fun Root(vm: AppVm) {
    val scan = androidx.activity.compose.rememberLauncherForActivityResult(ScanContract()) { r -> if (r.contents != null) vm.handleQr(r.contents) }
    val onQr = {
        scan.launch(
            ScanOptions().setDesiredBarcodeFormats(ScanOptions.QR_CODE)
                .setPrompt("Apunta al código QR de la pestaña Dispositivos en tu PC")
                .setBeepEnabled(false).setOrientationLocked(false),
        )
    }
    Box(Modifier.fillMaxSize().background(C.bg).systemBarsPadding().imePadding()) {
        when (vm.screen) {
            Screen.Welcome -> WelcomeScreen(vm)
            Screen.Pin -> PinScreen(vm)
            Screen.Usb -> UsbScreen(vm)
            Screen.Bt -> BtScreen(vm)
            Screen.Connected -> ConnectedScreen(vm)
            Screen.SavedPcs -> SavedPcsScreen(vm)
            Screen.About -> AboutScreen(vm)
            Screen.Main -> Column(Modifier.fillMaxSize()) {
                Box(Modifier.weight(1f)) {
                    when (vm.tab) {
                        Tab.Pads -> PadsTab(vm)
                        Tab.Conn -> Column {
                            AppBar(vm)
                            ConnTab(vm, onQr)
                        }
                        Tab.Settings -> Column {
                            AppBar(vm)
                            SettingsTab(vm)
                        }
                    }
                }
                // acostado, la botonera trae su propio menú en la barra lateral
                val sideMenu = isLandscape() && !(vm.st == St.Idle && vm.state.banks.isEmpty())
                if (!(vm.tab == Tab.Pads && (vm.fullscreen || sideMenu))) BottomNav(vm)
            }
        }
        vm.editing?.let { ed -> if (vm.screen == Screen.Main) EditSheet(vm, ed) }
        vm.upload?.let { u -> UploadSheet(vm, u) }
        vm.toast?.let { (text, bad) ->
            LaunchedEffect(text) {
                delay(3500)
                vm.toast = null
            }
            Box(Modifier.fillMaxSize().padding(bottom = 90.dp, start = 16.dp, end = 16.dp), contentAlignment = Alignment.BottomCenter) {
                Box(
                    Modifier.clip(RoundedCornerShape(14.dp)).background(if (bad) C.badSoft else C.panel2)
                        .border(1.dp, if (bad) C.badLine else C.line, RoundedCornerShape(14.dp))
                        .clickable { vm.toast = null }.padding(horizontal = 16.dp, vertical = 12.dp),
                ) { T(text, 13.5.sp, if (bad) C.badText else C.text) }
            }
        }
    }
    val consumes = vm.upload != null || vm.editing != null || (vm.screen != Screen.Main && vm.screen != Screen.Welcome) ||
        vm.fullscreen || vm.editMode || (vm.screen == Screen.Main && vm.tab != Tab.Pads)
    BackHandler(enabled = consumes) {
        when {
            vm.upload != null -> vm.closeUpload()
            vm.editing != null -> vm.editing = null
            vm.screen == Screen.Pin -> vm.cancelPin()
            vm.screen != Screen.Main && vm.screen != Screen.Welcome -> vm.screen = Screen.Main
            vm.fullscreen -> vm.fullscreen = false
            vm.editMode -> vm.editMode = false
            else -> vm.tab = Tab.Pads
        }
    }
}
