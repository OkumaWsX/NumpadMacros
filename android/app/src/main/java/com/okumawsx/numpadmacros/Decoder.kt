package com.okumawsx.numpadmacros

import android.content.Context
import android.media.AudioFormat
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.net.Uri
import java.io.File
import java.io.RandomAccessFile

/**
 * Convierte audio que el PC no sabe abrir (m4a, aac, 3gp, amr…) a WAV PCM de 16 bits,
 * con el mismo número de canales y frecuencia que entrega el decodificador.
 */
object Decoder {
    const val MAX_SECONDS = 600

    fun toWav(ctx: Context, uri: Uri, out: File, progress: (Float) -> Unit = {}): File {
        val ex = MediaExtractor()
        ex.setDataSource(ctx, uri, null)
        var track = -1
        var fmt: MediaFormat? = null
        for (i in 0 until ex.trackCount) {
            val f = ex.getTrackFormat(i)
            if ((f.getString(MediaFormat.KEY_MIME) ?: "").startsWith("audio/")) {
                track = i; fmt = f; break
            }
        }
        if (track < 0 || fmt == null) {
            ex.release()
            throw IllegalStateException("El archivo no tiene audio que se pueda leer.")
        }
        ex.selectTrack(track)
        val durUs = if (fmt.containsKey(MediaFormat.KEY_DURATION)) fmt.getLong(MediaFormat.KEY_DURATION) else 0L
        val codec = MediaCodec.createDecoderByType(fmt.getString(MediaFormat.KEY_MIME)!!)
        codec.configure(fmt, null, null, 0)
        codec.start()
        var rate = if (fmt.containsKey(MediaFormat.KEY_SAMPLE_RATE)) fmt.getInteger(MediaFormat.KEY_SAMPLE_RATE) else 44100
        var channels = if (fmt.containsKey(MediaFormat.KEY_CHANNEL_COUNT)) fmt.getInteger(MediaFormat.KEY_CHANNEL_COUNT) else 2
        var floatPcm = false
        var data = 0L
        val info = MediaCodec.BufferInfo()
        RandomAccessFile(out, "rw").use { raf ->
            raf.setLength(0)
            raf.write(ByteArray(44))
            var inputDone = false
            var outputDone = false
            var tmp = ByteArray(0)
            try {
                while (!outputDone) {
                    if (!inputDone) {
                        val ii = codec.dequeueInputBuffer(10_000)
                        if (ii >= 0) {
                            val buf = codec.getInputBuffer(ii)!!
                            val n = ex.readSampleData(buf, 0)
                            if (n < 0 || ex.sampleTime > MAX_SECONDS * 1_000_000L) {
                                codec.queueInputBuffer(ii, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                                inputDone = true
                            } else {
                                codec.queueInputBuffer(ii, 0, n, ex.sampleTime, 0)
                                if (durUs > 0) progress((ex.sampleTime.toFloat() / durUs).coerceIn(0f, 1f))
                                ex.advance()
                            }
                        }
                    }
                    val oi = codec.dequeueOutputBuffer(info, 10_000)
                    when {
                        oi == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> {
                            val of = codec.outputFormat
                            rate = of.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                            channels = of.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                            floatPcm = of.containsKey(MediaFormat.KEY_PCM_ENCODING) &&
                                of.getInteger(MediaFormat.KEY_PCM_ENCODING) == AudioFormat.ENCODING_PCM_FLOAT
                        }
                        oi >= 0 -> {
                            if (info.size > 0) {
                                val ob = codec.getOutputBuffer(oi)!!
                                ob.position(info.offset)
                                ob.limit(info.offset + info.size)
                                if (tmp.size < info.size) tmp = ByteArray(info.size)
                                ob.get(tmp, 0, info.size)
                                if (floatPcm) {
                                    val fb = java.nio.ByteBuffer.wrap(tmp, 0, info.size).order(java.nio.ByteOrder.nativeOrder()).asFloatBuffer()
                                    val pcm = ByteArray(fb.remaining() * 2)
                                    var j = 0
                                    while (fb.hasRemaining()) {
                                        val s = (fb.get().coerceIn(-1f, 1f) * 32767f).toInt()
                                        pcm[j++] = (s and 255).toByte(); pcm[j++] = ((s shr 8) and 255).toByte()
                                    }
                                    raf.write(pcm); data += pcm.size
                                } else {
                                    raf.write(tmp, 0, info.size); data += info.size
                                }
                            }
                            codec.releaseOutputBuffer(oi, false)
                            if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) outputDone = true
                            if (data > MAX_SECONDS.toLong() * rate * channels * 2) outputDone = true
                        }
                    }
                }
            } finally {
                try { codec.stop() } catch (_: Exception) {}
                codec.release()
                ex.release()
            }
            if (data <= 0) throw IllegalStateException("No se pudo convertir el audio.")
            wavHeader(raf, data, rate, channels)
        }
        return out
    }

    fun wavHeader(out: RandomAccessFile, data: Long, rate: Int, channels: Int) {
        fun le32(v: Long) = byteArrayOf((v and 255).toByte(), ((v shr 8) and 255).toByte(), ((v shr 16) and 255).toByte(), ((v shr 24) and 255).toByte())
        fun le16(v: Int) = byteArrayOf((v and 255).toByte(), ((v shr 8) and 255).toByte())
        out.seek(0)
        out.write("RIFF".toByteArray()); out.write(le32(36 + data)); out.write("WAVE".toByteArray())
        out.write("fmt ".toByteArray()); out.write(le32(16)); out.write(le16(1)); out.write(le16(channels))
        out.write(le32(rate.toLong())); out.write(le32(rate.toLong() * channels * 2)); out.write(le16(channels * 2)); out.write(le16(16))
        out.write("data".toByteArray()); out.write(le32(data))
    }
}
