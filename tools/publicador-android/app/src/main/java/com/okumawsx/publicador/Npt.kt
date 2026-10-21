// SPDX-License-Identifier: LGPL-3.0-or-later
// Copyright (C) 2026 OkumaWsX
// «Crear tema .npt»: tema en JSON + clave de firma -> .npt v1 firmado (igual que npm/npt.py pack()).
package com.okumawsx.publicador

import org.bouncycastle.crypto.params.Ed25519PrivateKeyParameters
import org.bouncycastle.crypto.params.Ed25519PublicKeyParameters
import org.bouncycastle.crypto.signers.Ed25519Signer
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.zip.Deflater
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

object Npt {
    const val OFFICIAL_KEY = "d22a3b4117eb17f96229d2ee90240c0f5e324ac34f97783de09124765d6711ff"
    private val MAGIC = "NPT".toByteArray()
    private const val VERSION = 1
    private const val FLAG_SIGNED = 1
    val REQUIRED = listOf("bg", "panel", "panel2", "line", "text", "muted", "acc", "on_acc", "key", "key_set",
        "key_global", "ok", "bad", "warn")

    class NptError(msg: String) : Exception(msg)

    fun hex(s: String): ByteArray = ByteArray(s.length / 2) { s.substring(it * 2, it * 2 + 2).toInt(16).toByte() }
    fun toHex(b: ByteArray) = b.joinToString("") { "%02x".format(it) }

    private val K: ByteArray by lazy {
        MessageDigest.getInstance("SHA-256").digest("NumpadMacros/npt/1/".toByteArray() + hex(OFFICIAL_KEY).reversedArray())
    }

    private fun validHex(v: Any?) = v is String && Regex("^#[0-9a-fA-F]{6}$").matches(v)

    /** Revisa y limpia un tema (igual que check_theme). */
    fun checkTheme(t: JSONObject): JSONObject {
        val name = t.optString("name", "").trim().take(40)
        if (name.isEmpty()) throw NptError("El tema no tiene nombre")
        val colors = t.optJSONObject("colors") ?: throw NptError("El tema no tiene colores")
        val clean = JSONObject()
        for (k in colors.keys()) {
            val v = colors.opt(k)
            if (validHex(v)) clean.put(k, (v as String).lowercase())
        }
        val missing = REQUIRED.filter { !clean.has(it) }
        if (missing.isNotEmpty()) throw NptError("Al tema le faltan colores: " + missing.joinToString(", "))
        val out = JSONObject()
            .put("name", name)
            .put("author", t.optString("author", "").trim().take(40).ifEmpty { "Desconocido" })
            .put("version", (if (t.has("version")) t.get("version").toString() else "1.0").take(12))
            .put("colors", clean)
        t.optJSONObject("alpha")?.let { a ->
            try {
                val w = a.opt("window")?.toString()?.toDouble() ?: 1.0
                val i = a.opt("idle")?.toString()?.toDouble() ?: 1.0
                out.put("alpha", JSONObject().put("window", w.coerceIn(0.5, 1.0)).put("idle", i.coerceIn(0.3, 1.0)))
            } catch (_: NumberFormatException) {
            }
        }
        return out
    }

    /** Semilla Ed25519 de 32 bytes desde el archivo de clave (PEM PKCS#8 sin contraseña). */
    fun loadKey(raw: ByteArray): Ed25519PrivateKeyParameters {
        val text = raw.toString(Charsets.US_ASCII)
        if (text.contains("ENCRYPTED")) throw NptError("La clave está protegida con contraseña: usa la clave sin contraseña.")
        val b64 = Regex("-----BEGIN PRIVATE KEY-----(.*?)-----END PRIVATE KEY-----", RegexOption.DOT_MATCHES_ALL)
            .find(text)?.groupValues?.get(1)?.replace(Regex("\\s"), "")
            ?: throw NptError("El archivo no tiene una clave válida.")
        val der = try { java.util.Base64.getDecoder().decode(b64) } catch (e: Exception) {
            throw NptError("El archivo no tiene una clave válida.")
        }
        val prefix = hex("302e020100300506032b657004220420")
        if (der.size != 48 || !der.copyOfRange(0, 16).contentEquals(prefix)) {
            throw NptError("El archivo no tiene una clave Ed25519 válida.")
        }
        return Ed25519PrivateKeyParameters(der, 16)
    }

    fun publicHex(key: Ed25519PrivateKeyParameters) = toHex(key.generatePublicKey().encoded)
    fun isOfficial(key: Ed25519PrivateKeyParameters) = publicHex(key) == OFFICIAL_KEY

    private fun zlib(data: ByteArray): ByteArray {
        val d = Deflater(9)
        d.setInput(data)
        d.finish()
        val out = ByteArrayOutputStream()
        val buf = ByteArray(8192)
        while (!d.finished()) out.write(buf, 0, d.deflate(buf))
        d.end()
        return out.toByteArray()
    }

    /** Tema -> bytes .npt v1 (cifrado y firmado). */
    fun pack(theme: JSONObject, key: Ed25519PrivateKeyParameters?): ByteArray {
        val t = checkTheme(theme)
        val payload = zlib(t.toString().toByteArray(Charsets.UTF_8))
        val nonce = ByteArray(12).also { SecureRandom().nextBytes(it) }
        val head = MAGIC + byteArrayOf(VERSION.toByte(), (if (key != null) FLAG_SIGNED else 0).toByte()) + nonce
        val c = Cipher.getInstance("AES/GCM/NoPadding")
        c.init(Cipher.ENCRYPT_MODE, SecretKeySpec(K, "AES"), GCMParameterSpec(128, nonce))
        c.updateAAD(head)
        val ct = c.doFinal(payload)
        var body = head + ByteBuffer.allocate(4).putInt(ct.size).array() + ct
        if (key != null) {
            val s = Ed25519Signer()
            s.init(true, key)
            s.update(body, 0, body.size)
            body += s.generateSignature()
        }
        return body
    }

    /** Comprueba el archivo recién creado como lo hará la app: (nombre, oficial). */
    fun verify(data: ByteArray): Pair<String, Boolean> {
        if (data.size < 21 || !data.copyOfRange(0, 3).contentEquals(MAGIC) || data[3].toInt() != VERSION) {
            throw NptError("El archivo no es un tema .npt v1")
        }
        val flags = data[4].toInt()
        val nonce = data.copyOfRange(5, 17)
        val n = ByteBuffer.wrap(data, 17, 4).int
        val end = 21 + n
        var official = false
        if (flags and FLAG_SIGNED != 0) {
            val v = Ed25519Signer()
            v.init(false, Ed25519PublicKeyParameters(hex(OFFICIAL_KEY), 0))
            v.update(data, 0, end)
            official = v.verifySignature(data.copyOfRange(end, data.size))
        }
        val c = Cipher.getInstance("AES/GCM/NoPadding")
        c.init(Cipher.DECRYPT_MODE, SecretKeySpec(K, "AES"), GCMParameterSpec(128, nonce))
        c.updateAAD(data.copyOfRange(0, 17))
        val payload = c.doFinal(data.copyOfRange(21, end))
        val inf = java.util.zip.Inflater()
        inf.setInput(payload)
        val out = ByteArrayOutputStream()
        val buf = ByteArray(8192)
        while (!inf.finished()) {
            val k = inf.inflate(buf)
            if (k == 0 && (inf.needsInput() || inf.needsDictionary())) break
            out.write(buf, 0, k)
        }
        inf.end()
        return JSONObject(out.toString("UTF-8")).getString("name") to official
    }
}
