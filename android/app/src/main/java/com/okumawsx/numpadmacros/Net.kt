package com.okumawsx.numpadmacros

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothSocket
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStream
import java.io.InputStreamReader
import java.io.OutputStream
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.Inet4Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.net.Socket
import java.net.SocketTimeoutException
import java.security.MessageDigest
import java.util.UUID
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

const val TCP_PORT = 47800
const val UDP_PORT = 47801
const val BT_CHANNEL = 22
val BT_UUID: UUID = UUID.fromString("8f3c6a52-5e0b-4c6e-9b7b-1d2a9f0e7a12")

/** Un canal de ida y vuelta con mensajes JSON de una línea (TCP o Bluetooth). */
abstract class Link(input: InputStream, private val output: OutputStream) {
    abstract val transport: String
    abstract val where: String
    private val reader = BufferedReader(InputStreamReader(input, Charsets.UTF_8), 64 * 1024)
    private val lock = Any()

    /** Lee un mensaje; null cuando la conexión se cerró. */
    fun read(): JSONObject? {
        while (true) {
            val line = reader.readLine() ?: return null
            if (line.isBlank()) continue
            return try {
                JSONObject(line)
            } catch (e: Exception) {
                continue
            }
        }
    }

    fun send(o: JSONObject) {
        val bytes = (o.toString() + "\n").toByteArray(Charsets.UTF_8)
        synchronized(lock) {
            output.write(bytes)
            output.flush()
        }
    }

    abstract fun close()
}

class TcpLink(private val socket: Socket, override val transport: String) :
    Link(socket.getInputStream(), socket.getOutputStream()) {
    override val where: String = socket.inetAddress?.hostAddress ?: ""
    override fun close() {
        try { socket.close() } catch (_: Exception) {}
    }

    companion object {
        fun open(host: String, port: Int, transport: String, timeoutMs: Int = 3500): TcpLink {
            val s = Socket()
            s.tcpNoDelay = true
            s.keepAlive = true
            s.connect(InetSocketAddress(host, port), timeoutMs)
            return TcpLink(s, transport)
        }
    }
}

class BtLink(private val socket: BluetoothSocket) : Link(socket.inputStream, socket.outputStream) {
    override val transport = "bt"
    override val where: String = socket.remoteDevice?.address ?: ""
    override fun close() {
        try { socket.close() } catch (_: Exception) {}
    }

    companion object {
        /**
         * Conecta por RFCOMM: primero por el UUID del servicio; si el PC no lo publica
         * (pasa en algunos Linux), por el canal fijo 22.
         */
        @SuppressLint("MissingPermission")
        fun open(adapter: BluetoothAdapter, address: String): BtLink {
            try { adapter.cancelDiscovery() } catch (_: Exception) {}
            val dev: BluetoothDevice = adapter.getRemoteDevice(address)
            val tries = listOf<() -> BluetoothSocket>(
                { dev.createRfcommSocketToServiceRecord(BT_UUID) },
                { dev.createInsecureRfcommSocketToServiceRecord(BT_UUID) },
                { dev.javaClass.getMethod("createRfcommSocket", Int::class.javaPrimitiveType).invoke(dev, BT_CHANNEL) as BluetoothSocket },
                { dev.javaClass.getMethod("createInsecureRfcommSocket", Int::class.javaPrimitiveType).invoke(dev, BT_CHANNEL) as BluetoothSocket },
            )
            var last: Exception? = null
            for (make in tries) {
                var s: BluetoothSocket? = null
                try {
                    s = make()
                    s.connect()
                    return BtLink(s)
                } catch (e: Exception) {
                    last = e
                    try { s?.close() } catch (_: Exception) {}
                }
            }
            throw last ?: IllegalStateException("No se pudo conectar por Bluetooth")
        }
    }
}

object Discovery {
    private data class Iface(val name: String, val addr: Inet4Address, val prefix: Int, val broadcast: InetAddress?)

    private fun ifaces(): List<Iface> {
        val out = mutableListOf<Iface>()
        try {
            for (ni in NetworkInterface.getNetworkInterfaces()?.toList() ?: emptyList()) {
                if (!ni.isUp || ni.isLoopback) continue
                for (ia in ni.interfaceAddresses) {
                    val a = ia.address as? Inet4Address ?: continue
                    out.add(Iface(ni.name ?: "", a, ia.networkPrefixLength.toInt(), ia.broadcast))
                }
            }
        } catch (_: Exception) {}
        return out
    }

    fun isUsbName(name: String) = name.startsWith("rndis") || name.startsWith("usb") || name.startsWith("ncm")

    private fun toInt(a: InetAddress): Int {
        val b = a.address
        return ((b[0].toInt() and 255) shl 24) or ((b[1].toInt() and 255) shl 16) or ((b[2].toInt() and 255) shl 8) or (b[3].toInt() and 255)
    }

    /** Por qué camino llega el celular a esa IP: "usb" o "wifi". */
    fun transportFor(host: String): String {
        val ip = try { InetAddress.getByName(host) } catch (_: Exception) { return "wifi" }
        if (ip !is Inet4Address) return "wifi"
        for (f in ifaces()) {
            val mask = if (f.prefix <= 0) 0 else (-1 shl (32 - f.prefix))
            if ((toInt(ip) and mask) == (toInt(f.addr) and mask)) return if (isUsbName(f.name)) "usb" else "wifi"
        }
        return "wifi"
    }

    fun hasUsbNetwork(): Boolean = ifaces().any { isUsbName(it.name) }

    /** Pregunta por la red quién tiene Numpad Macros abierto. Bloquea ~timeoutMs. */
    fun scan(timeoutMs: Long = 1600): List<Found> {
        val found = LinkedHashMap<String, Found>()
        var sock: DatagramSocket? = null
        try {
            sock = DatagramSocket(null as java.net.SocketAddress?)
            sock.reuseAddress = true
            sock.broadcast = true
            sock.bind(InetSocketAddress(0))
            val msg = JSONObject().put("t", "descubrir").put("v", 1).toString().toByteArray(Charsets.UTF_8)
            val targets = LinkedHashSet<InetAddress>()
            for (f in ifaces()) f.broadcast?.let { targets.add(it) }
            targets.add(InetAddress.getByName("255.255.255.255"))
            val end = System.currentTimeMillis() + timeoutMs
            var nextSend = 0L
            var sends = 0
            val buf = ByteArray(4096)
            while (System.currentTimeMillis() < end) {
                val now = System.currentTimeMillis()
                if (sends < 3 && now >= nextSend) {
                    for (t in targets) {
                        try { sock.send(DatagramPacket(msg, msg.size, t, UDP_PORT)) } catch (_: Exception) {}
                    }
                    sends++
                    nextSend = now + 450
                }
                sock.soTimeout = 150
                try {
                    val p = DatagramPacket(buf, buf.size)
                    sock.receive(p)
                    val o = JSONObject(String(p.data, 0, p.length, Charsets.UTF_8))
                    if (o.optString("t") != "pc") continue
                    val host = p.address.hostAddress ?: continue
                    val id = o.optString("id", host)
                    val f = Found(id, o.optString("name", host), host, o.optInt("port", TCP_PORT),
                        o.optString("app", ""), o.optString("os", ""), transportFor(host))
                    // Si un mismo PC responde por USB y por Wi-Fi, se muestran los dos caminos
                    found["$id|${f.transport}"] = f
                } catch (_: SocketTimeoutException) {
                } catch (_: Exception) {
                }
            }
        } catch (_: Exception) {
        } finally {
            try { sock?.close() } catch (_: Exception) {}
        }
        return found.values.sortedWith(compareBy({ if (it.transport == "usb") 0 else 1 }, { it.name.lowercase() }))
    }
}

object Crypto {
    fun hex(b: ByteArray) = b.joinToString("") { String.format("%02x", it.toInt() and 255) }

    /** HMAC-SHA256: clave = token (texto hex, UTF-8), mensaje = nonce (texto hex, UTF-8). */
    fun proof(token: String, nonce: String): String {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(token.toByteArray(Charsets.UTF_8), "HmacSHA256"))
        return hex(mac.doFinal(nonce.toByteArray(Charsets.UTF_8)))
    }

    fun sha256(): MessageDigest = MessageDigest.getInstance("SHA-256")
}
