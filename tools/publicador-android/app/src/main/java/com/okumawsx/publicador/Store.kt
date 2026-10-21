// SPDX-License-Identifier: LGPL-3.0-or-later
// Copyright (C) 2026 OkumaWsX
// Ajustes guardados solo en este teléfono. El token y la clave de firma de temas van cifrados con una
// llave del almacén seguro de Android (no sale del teléfono ni entra en las copias de seguridad).
package com.okumawsx.publicador

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class Store(ctx: Context) {
    private val prefs = ctx.getSharedPreferences("publicador", Context.MODE_PRIVATE)
    private val alias = "publicador-secretos"

    private fun key(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getKey(alias, null) as? SecretKey)?.let { return it }
        val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        gen.init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .build())
        return gen.generateKey()
    }

    private fun seal(data: ByteArray): String {
        val c = Cipher.getInstance("AES/GCM/NoPadding")
        c.init(Cipher.ENCRYPT_MODE, key())
        return Base64.encodeToString(c.iv + c.doFinal(data), Base64.NO_WRAP)
    }

    private fun open(text: String?): ByteArray? {
        if (text.isNullOrEmpty()) return null
        return try {
            val raw = Base64.decode(text, Base64.NO_WRAP)
            val c = Cipher.getInstance("AES/GCM/NoPadding")
            c.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, raw, 0, 12))
            c.doFinal(raw, 12, raw.size - 12)
        } catch (e: Exception) {
            null
        }
    }

    var token: String?
        get() = open(prefs.getString("token", null))?.toString(Charsets.UTF_8)
        set(v) = prefs.edit().apply { if (v == null) remove("token") else putString("token", seal(v.toByteArray())) }.apply()

    /** Contenido del archivo de clave de firma de temas (firma-temas-OkumaWsX.key). */
    var themeKey: ByteArray?
        get() = open(prefs.getString("theme_key", null))
        set(v) = prefs.edit().apply { if (v == null) remove("theme_key") else putString("theme_key", seal(v)) }.apply()

    var discord: Boolean
        get() = prefs.getBoolean("discord", true)
        set(v) = prefs.edit().putBoolean("discord", v).apply()
}
