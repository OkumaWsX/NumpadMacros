package com.okumawsx.numpadmacros

import android.annotation.SuppressLint
import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.File
import java.io.RandomAccessFile

/** Graba del micrófono a un WAV (16 bits, mono, 48 kHz): el PC lo abre sin convertir nada. */
class Recorder(private val ctx: Context) {
    private val rate = 48000
    @Volatile private var running = false
    private var thread: Thread? = null
    private var file: File? = null
    @Volatile private var bytes = 0L

    fun seconds(): Int = (bytes / (rate * 2)).toInt()

    @SuppressLint("MissingPermission")
    fun start() {
        cancel()
        val min = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        if (min <= 0) throw IllegalStateException("micrófono no disponible")
        val rec = AudioRecord(MediaRecorder.AudioSource.MIC, rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, min * 4)
        if (rec.state != AudioRecord.STATE_INITIALIZED) {
            rec.release()
            throw IllegalStateException("no se pudo abrir el micrófono")
        }
        val f = File(ctx.cacheDir, "grabacion.wav")
        file = f
        bytes = 0
        running = true
        rec.startRecording()
        thread = Thread {
            RandomAccessFile(f, "rw").use { out ->
                out.setLength(0)
                out.write(ByteArray(44))
                val buf = ByteArray(min)
                while (running) {
                    val n = rec.read(buf, 0, buf.size)
                    if (n > 0) {
                        out.write(buf, 0, n)
                        bytes += n
                    }
                }
                try { rec.stop() } catch (_: Exception) {}
                rec.release()
                writeHeader(out, bytes)
            }
        }.also { it.start() }
    }

    /** Termina y devuelve el archivo (o null si no se grabó nada). */
    fun stop(): File? {
        running = false
        thread?.join(2000)
        thread = null
        val f = file
        return if (f != null && bytes > rate / 5) f else null
    }

    fun cancel() {
        running = false
        thread?.join(2000)
        thread = null
    }

    private fun writeHeader(out: RandomAccessFile, data: Long) {
        fun le32(v: Long) = byteArrayOf((v and 255).toByte(), ((v shr 8) and 255).toByte(), ((v shr 16) and 255).toByte(), ((v shr 24) and 255).toByte())
        fun le16(v: Int) = byteArrayOf((v and 255).toByte(), ((v shr 8) and 255).toByte())
        out.seek(0)
        out.write("RIFF".toByteArray())
        out.write(le32(36 + data))
        out.write("WAVE".toByteArray())
        out.write("fmt ".toByteArray())
        out.write(le32(16))
        out.write(le16(1))          // PCM
        out.write(le16(1))          // mono
        out.write(le32(rate.toLong()))
        out.write(le32(rate * 2L))  // bytes por segundo
        out.write(le16(2))
        out.write(le16(16))
        out.write("data".toByteArray())
        out.write(le32(data))
    }
}
