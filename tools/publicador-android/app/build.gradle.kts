plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// Misma firma que la app del celular: secretos ANDROID_KEYSTORE_* si existen; si no, la llave de
// desarrollo incluida (así cada APK nuevo se instala encima del anterior).
val releaseJks = file("release.jks")
val usingRelease = releaseJks.exists() && System.getenv("ANDROID_KEYSTORE_PASS") != null

android {
    namespace = "com.okumawsx.publicador"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.okumawsx.numpadmacros.publicador"
        minSdk = 26
        targetSdk = 35
        versionCode = 2
        versionName = "1.0.1"
    }

    signingConfigs {
        create("nm") {
            if (usingRelease) {
                storeFile = releaseJks
                storePassword = System.getenv("ANDROID_KEYSTORE_PASS")
                keyAlias = System.getenv("ANDROID_KEY_ALIAS") ?: "numpadmacros"
                keyPassword = System.getenv("ANDROID_KEY_PASS") ?: System.getenv("ANDROID_KEYSTORE_PASS")
            } else {
                storeFile = file("numpadmacros-dev.jks")
                storePassword = "numpadmacros-dev"
                keyAlias = "numpadmacros"
                keyPassword = "numpadmacros-dev"
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("nm")
        }
        debug {
            signingConfig = signingConfigs.getByName("nm")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    packaging {
        resources.excludes += setOf("META-INF/versions/9/OSGI-INF/MANIFEST.MF", "META-INF/DEPENDENCIES")
    }
    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

dependencies {
    val bom = platform("androidx.compose:compose-bom:2025.04.00")
    implementation(bom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.bouncycastle:bcprov-jdk18on:1.80")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
