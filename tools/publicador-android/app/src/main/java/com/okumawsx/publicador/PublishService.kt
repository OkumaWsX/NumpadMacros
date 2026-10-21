// SPDX-License-Identifier: LGPL-3.0-or-later
// Copyright (C) 2026 OkumaWsX
// Publicar sigue funcionando con la pantalla apagada o en otra app: sube el código, pone a trabajar al
// robot y sigue sus pasos, mostrando el avance en una notificación.
package com.okumawsx.publicador

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.update

data class Row(val id: String, val label: String, val state: String = "pending", val right: String = "",
               val frac: Float? = null, val bar: Boolean = false)

data class PubState(
    val version: Ver,
    val beta: Boolean,
    val rows: List<Row>,
    val title: String,
    val sub: String,
    val running: Boolean = true,
    val failMsg: String? = null,
    val failUrl: String = "",
    val done: Boolean = false,
    val releaseUrl: String = "",
    val assets: List<Pair<String, Long>>? = null,
    val discordFailed: Boolean = false,
)

/** Lo que se va a publicar (lo prepara la pantalla de revisión) y el avance (lo lee la interfaz). */
object Pub {
    var gh: GitHub? = null
    var pkg: Package? = null
    var rv: Review? = null
    var beta = false
    var important = false
    var discord = true
    val state = MutableStateFlow<PubState?>(null)

    fun row(id: String, st: String, right: String? = null, frac: Float? = null) = state.update { s ->
        s?.copy(rows = s.rows.map { if (it.id == id) it.copy(state = st, right = right ?: it.right, frac = frac ?: it.frac) else it })
    }
}

class PublishService : Service() {
    private var worker: Thread? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        channel(this)
        val n = note(this, "Publicando…", "Subiendo el código a GitHub")
        if (Build.VERSION.SDK_INT >= 29) startForeground(ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        else startForeground(ID, n)
        if (worker?.isAlive != true) {
            worker = Thread({ run() }, "publicar").also { it.start() }
        }
        return START_NOT_STICKY
    }

    private fun show(title: String, text: String) {
        getSystemService(NotificationManager::class.java).notify(ID, note(this, title, text))
    }

    private fun run() {
        val gh = Pub.gh!!
        val pkg = Pub.pkg!!
        val rv = Pub.rv!!
        val ver = rv.version!!
        try {
            Pub.row("up", "run")
            val sha = upload(pkg, gh, rv, ver) { msg ->
                Pub.row("up", "run", msg)
                show("Publicando $ver", msg)
            }
            Pub.row("up", "ok", if (sha != null) "listo" else "ya estaba subido")
            Pub.row("go", "run")
            show("Publicando $ver", "Poniendo a trabajar al robot")
            val since = startRobot(gh, ver, Pub.beta, Pub.important, Pub.discord)
            var run: org.json.JSONObject? = null
            for (i in 0 until 30) {
                run = findRun(gh, since)
                if (run != null) break
                Thread.sleep(3000)
            }
            if (run == null) throw PubError("El robot no arrancó. Revisa la pestaña Actions de tu repositorio.")
            Pub.row("go", "ok")
            follow(gh, run.getLong("id"), ver)
        } catch (e: Exception) {
            fail(e.message ?: e.toString(), "")
        } finally {
            Pub.state.update { it?.copy(running = false) }
            stopForeground(STOP_FOREGROUND_DETACH)
            stopSelf()
        }
    }

    private fun follow(gh: GitHub, runId: Long, ver: Ver) {
        val names = STAGES.associate { it.id to it.label }
        while (true) {
            val st = try {
                runStatus(gh, runId)
            } catch (e: Exception) {          // error de red pasajero: seguir intentando
                Thread.sleep(8000)
                continue
            }
            val map = mapOf("done" to "ok", "failed" to "bad", "running" to "run", "pending" to "pending")
            var now = ""
            for ((sid, v) in st.stages) {
                val (frac, state) = v
                val bar = sid in setOf("win", "lin", "mac")
                Pub.row(sid, map.getValue(state), if (bar && state == "running") "${(frac * 100).toInt()} %" else "", frac)
                if (state == "running" && now.isEmpty()) now = names[sid] ?: ""
            }
            if (st.discord == "success") Pub.row("dc", "ok")
            else if (st.discord == "failure") {
                Pub.row("dc", "bad", "falló: revisa el webhook")
                Pub.state.update { it?.copy(discordFailed = true) }
            }
            when (st.state) {
                "running" -> {
                    if (now.isNotEmpty()) show("Publicando $ver", now)
                    Thread.sleep(5000)
                }
                "success" -> {
                    val assets = try { releaseAssets(gh, ver) } catch (e: Exception) { null }
                    Pub.state.update { it?.copy(done = true, releaseUrl = assets?.first ?: "", assets = assets?.second) }
                    finalNote("✓ Numpad Macros $ver publicada",
                        if (Pub.beta) "Como beta: solo la reciben quienes activaron las versiones de prueba."
                        else "Los usuarios verán el aviso la próxima vez que abran la app.")
                    return
                }
                else -> {
                    fail("Falló: ${st.failed ?: "un paso del robot"}.", st.url)
                    return
                }
            }
        }
    }

    private fun fail(msg: String, url: String) {
        Pub.state.update { s ->
            s?.copy(title = "Publicación detenida", sub = "", failMsg = msg, failUrl = url,
                rows = s.rows.map { if (it.state == "run") it.copy(state = "bad") else it })
        }
        finalNote("Publicación detenida", msg)
    }

    private fun finalNote(title: String, text: String) {
        getSystemService(NotificationManager::class.java).notify(ID + 1, note(this, title, text, ongoing = false))
    }

    companion object {
        const val ID = 41
        private const val CH = "publicar"

        fun channel(ctx: Context) {
            ctx.getSystemService(NotificationManager::class.java).createNotificationChannel(
                NotificationChannel(CH, "Publicar versión", NotificationManager.IMPORTANCE_LOW))
        }

        fun note(ctx: Context, title: String, text: String, ongoing: Boolean = true): Notification {
            val open = PendingIntent.getActivity(ctx, 0, Intent(ctx, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            return Notification.Builder(ctx, CH)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle(title)
                .setContentText(text)
                .setStyle(Notification.BigTextStyle().bigText(text))
                .setOngoing(ongoing)
                .setAutoCancel(!ongoing)
                .setContentIntent(open)
                .build()
        }

        fun start(ctx: Context) {
            val v = Pub.rv!!.version!!
            val rows = mutableListOf(Row("up", "Subir el código a GitHub"), Row("go", "Poner a trabajar al robot"))
            STAGES.forEach { rows.add(Row(it.id, it.label, bar = it.id in setOf("win", "lin", "mac"))) }
            if (Pub.discord) rows.add(Row("dc", "Anunciar en Discord"))
            Pub.state.value = PubState(v, Pub.beta, rows, "Publicando $v…",
                "Primero se sube el código; después GitHub compila en sus servidores (unos 10–15 minutos). " +
                    "Puedes salir de la app o apagar la pantalla: GitHub te avisa por correo si algo falla.")
            ctx.startForegroundService(Intent(ctx, PublishService::class.java))
        }
    }
}
