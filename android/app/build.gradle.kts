plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// Firma: si GitHub tiene los secretos ANDROID_KEYSTORE_B64 / ANDROID_KEYSTORE_PASS,
// el workflow deja el archivo en app/release.jks y se usa ese. Si no, se usa la llave
// de desarrollo incluida (numpadmacros-dev.jks, contraseña "numpadmacros-dev", solo
// para pruebas): así cada APK compilado tiene la misma firma y se instala encima del anterior.
val releaseJks = file("release.jks")
val usingRelease = releaseJks.exists() && System.getenv("ANDROID_KEYSTORE_PASS") != null

android {
    namespace = "com.okumawsx.numpadmacros"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.okumawsx.numpadmacros"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
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
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")
}
