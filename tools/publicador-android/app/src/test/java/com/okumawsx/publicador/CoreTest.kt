// SPDX-License-Identifier: LGPL-3.0-or-later
// Copyright (C) 2026 OkumaWsX
package com.okumawsx.publicador

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class CoreTest {
    private fun zip(files: Map<String, String>): ByteArray {
        val out = ByteArrayOutputStream()
        ZipOutputStream(out).use { z ->
            for ((k, v) in files) {
                z.putNextEntry(ZipEntry(k))
                z.write(v.toByteArray())
                z.closeEntry()
            }
        }
        return out.toByteArray()
    }

    private val base = mapOf(
        "NumpadMacros-3.4.1-beta/npm/about.py" to "APP_ID = \"$APP_ID\"\n",
        "NumpadMacros-3.4.1-beta/npm/__init__.py" to "__version__ = \"3.4.1\"\n",
        "NumpadMacros-3.4.1-beta/installer/NumpadMacros.iss" to "AppId={{$APP_ID}\n",
        "NumpadMacros-3.4.1-beta/CHANGELOG.md" to "# Cambios\n\n## [Sin publicar]\n\n- Uno\r\n- Dos\n\n## [3.4.0] - 2026\n\n- Viejo\n",
        "NumpadMacros-3.4.1-beta/.gitignore" to "# x\n/build/\n*.log\n!keep.log\n",
        "NumpadMacros-3.4.1-beta/ENTREGA.txt" to "commit=" + "a".repeat(40) + "\n",
        "NumpadMacros-3.4.1-beta/npm/__pycache__/x.pyc" to "x",
        "NumpadMacros-3.4.1-beta/salida.log" to "x",
        "NumpadMacros-3.4.1-beta/build.sh" to "echo\r\n",
    )

    @Test fun readsPackage() {
        val p = Package.fromZip(zip(base), "NumpadMacros-codigo_3.4.1-beta.zip")
        assertTrue(p.isNumpadMacros())
        assertEquals(Ver(3, 4, 1), p.version())
        assertTrue(p.betaHint)
        assertEquals("a".repeat(40), p.baseCommit())
        assertEquals("- Uno\r\n- Dos", p.unreleased())
        val f = p.files()
        assertEquals(setOf("npm/about.py", "npm/__init__.py", "installer/NumpadMacros.iss", "CHANGELOG.md", ".gitignore", "build.sh"), f.keys)
        assertEquals("100755", f.getValue("build.sh").second)
        assertEquals("echo\n", f.getValue("build.sh").first.toString(Charsets.UTF_8))
        p.setUnreleased("- Tres\n")
        assertEquals("- Tres", p.unreleased())
        assertTrue(p.read("CHANGELOG.md").contains("## [3.4.0]"))
    }

    @Test fun rejectsOtherApp() {
        val other = base + ("NumpadMacros-3.4.1-beta/npm/about.py" to "APP_ID = \"OTRA\"\n")
        assertFalse(Package.fromZip(zip(other), "x.zip").isNumpadMacros())
        try {
            Package.fromZip(zip(mapOf("a.txt" to "x")), "x.zip")
            throw AssertionError("debió fallar")
        } catch (e: PubError) {
            assertTrue(e.message!!.contains("npm/about.py"))
        }
    }

    @Test fun globLikePython() {
        assertTrue(Glob.match("a/b/c.pyc", "*.pyc"))
        assertTrue(Glob.match("x.log", "*.log"))
        assertTrue(Glob.match("abc", "a[!x]c"))
        assertFalse(Glob.match("axc", "a[!x]c"))
        assertTrue(Glob.match("file.txt", "file.???"))
    }

    @Test fun versions() {
        assertEquals(Ver(3, 4, 1), Ver.parse("v3.4.1"))
        assertNull(Ver.parse("3.4"))
        assertTrue(Ver(3, 10, 0) > Ver(3, 9, 9))
        assertEquals("Mejora (funciones nuevas)", kindOf(Ver(3, 5, 0), Ver(3, 4, 9)))
        assertEquals("Corrección de errores", kindOf(Ver(3, 4, 2), Ver(3, 4, 1)))
        assertEquals("Primera versión publicada", kindOf(Ver(1, 0, 0), null))
        assertEquals("e69de29bb2d1d6434b8b29ae775ad8c2e48c5391", gitBlobSha(ByteArray(0)))
    }

    // tema creado por npm/npt.py (sin firma): mismo cifrado
    private val fromPython = "TlBUAQBHiyOwwFSAoSg93WEAAACf6BtQrxHzv6BDnlA4yRw5bnspBaEmmSh6/W4wt6DKLb1nCTgxd+tSwZ/CCykjMYAkbb0VrOmVl9jWoh7Gi9052XH3jcQDAA8vhAb8WQyCy1/AoE4OkZx3nvpgJzOXrO5iaLpxkX5DQn2xNuzI4IdGCIazNHkUV+nUEyqh6YhY+kTxDo1XBG9hDGuliMAQ0Ix27G22QSwWZCQfwcgi3rnK"
    private val testKey = "-----BEGIN PRIVATE KEY-----\nMC4CAQAwBQYDK2VwBCIEIAABAgMEBQYHCAkKCwwNDg8QERITFBUWFxgZGhscHR4f\n-----END PRIVATE KEY-----\n"

    @Test fun readsPythonTheme() {
        val (name, official) = Npt.verify(java.util.Base64.getDecoder().decode(fromPython))
        assertEquals("Prueba Android", name)
        assertFalse(official)
    }

    @Test fun packsTheme() {
        val key = Npt.loadKey(testKey.toByteArray())
        assertEquals("03a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8", Npt.publicHex(key))
        assertFalse(Npt.isOfficial(key))
        val colors = JSONObject()
        Npt.REQUIRED.forEach { colors.put(it, "#AABBCC") }
        val t = JSONObject().put("name", "  Mi tema ").put("colors", colors).put("alpha", JSONObject().put("window", 0.1))
        val data = Npt.pack(t, key)
        assertEquals(1, data[4].toInt())
        val (name, official) = Npt.verify(data)
        assertEquals("Mi tema", name)
        assertFalse(official)          // firmado, pero no con la clave oficial
        val clean = Npt.checkTheme(t)
        assertEquals(0.5, clean.getJSONObject("alpha").getDouble("window"), 0.0)
        assertEquals("Desconocido", clean.getString("author"))
        assertNotNull(clean.getJSONObject("colors").optString("bg"))
    }

    @Test fun missingColors() {
        try {
            Npt.checkTheme(JSONObject().put("name", "x").put("colors", JSONObject().put("bg", "#000000")))
            throw AssertionError("debió fallar")
        } catch (e: Npt.NptError) {
            assertTrue(e.message!!.startsWith("Al tema le faltan colores"))
        }
    }
}
