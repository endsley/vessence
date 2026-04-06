plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// Read version from single source of truth: vessence/version.json
val versionFile = file("${rootProject.projectDir}/../version.json")
val versionJson = groovy.json.JsonSlurper().parseText(versionFile.readText()) as Map<*, *>
val appVersionCode = (versionJson["version_code"] as Number).toInt()
val appVersionName = versionJson["version_name"] as String

android {
    namespace = "com.vessences.android"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.vessences.android"
        minSdk = 28
        targetSdk = 35
        versionCode = appVersionCode
        versionName = appVersionName

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    signingConfigs {
        create("release") {
            storeFile = file("${rootProject.projectDir}/vessence-release.jks")
            storePassword = "REDACTED_PASSWORD"
            keyAlias = "vessence"
            keyPassword = "REDACTED_PASSWORD"
        }
    }

    buildTypes {
        debug {
            signingConfig = signingConfigs.getByName("release")
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            signingConfig = signingConfigs.getByName("release")
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
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
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }

    // ── Vessence Tool Sources (Phase 7b) ──────────────────────────────
    // Each tool under ~/ambient/tools/<name>/android/src/ ships a self-contained
    // Kotlin package that belongs to Jane's tool layer, NOT the Android app
    // kernel. At build time, the `generateToolSources` task below copies those
    // sources into a generated directory that the Kotlin compiler picks up as
    // an additional source set. This lets a new tool drop into tools/<name>/
    // without editing anything in android/app/src/main/java.
    sourceSets {
        getByName("main") {
            java.srcDirs(
                "src/main/java",
                layout.buildDirectory.dir("generated/source/tools/main/java"),
            )
        }
    }
}

// ── Vessence Tool Source Generator ────────────────────────────────────
val toolsRoot = file("${System.getProperty("user.home")}/ambient/tools")
val generatedToolSourcesDir = layout.buildDirectory.dir("generated/source/tools/main/java")

tasks.register<Copy>("generateToolSources") {
    description = "Copy tool Kotlin sources from ~/ambient/tools/*/android/src/ into the generated source set."
    group = "build"
    onlyIf { toolsRoot.exists() }
    if (toolsRoot.exists()) {
        toolsRoot.listFiles()?.forEach { toolDir ->
            if (toolDir.isDirectory) {
                val toolAndroidSrc = file("${toolDir.absolutePath}/android/src")
                if (toolAndroidSrc.exists()) {
                    from(toolAndroidSrc) {
                        include("**/*.kt")
                    }
                }
            }
        }
    }
    into(generatedToolSourcesDir)
    doFirst {
        generatedToolSourcesDir.get().asFile.mkdirs()
        logger.lifecycle("generateToolSources: copying tool sources from $toolsRoot → ${generatedToolSourcesDir.get().asFile}")
    }
    doLast {
        val count = fileTree(generatedToolSourcesDir.get().asFile).matching { include("**/*.kt") }.files.size
        logger.lifecycle("generateToolSources: $count Kotlin file(s) generated")
    }
}

// Wire the generator as a dependency of Kotlin compilation so it runs on every build.
afterEvaluate {
    tasks.named("preBuild").configure {
        dependsOn("generateToolSources")
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.09.03")
    val lifecycleVersion = "2.8.6"

    implementation(composeBom)
    androidTestImplementation(composeBom)

    // Core
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-compose:1.9.2")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:$lifecycleVersion")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:$lifecycleVersion")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:$lifecycleVersion")

    // Compose UI
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.navigation:navigation-compose:2.8.1")

    // Networking
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    // Image loading
    implementation("io.coil-kt:coil-compose:2.7.0")

    // Google Sign-In (Credential Manager)
    implementation("androidx.credentials:credentials:1.3.0")
    implementation("androidx.credentials:credentials-play-services-auth:1.3.0")
    implementation("com.google.android.libraries.identity.googleid:googleid:1.1.1")

    // Media3 (ExoPlayer)
    implementation("androidx.media3:media3-exoplayer:1.4.1")
    implementation("androidx.media3:media3-datasource:1.4.1")
    implementation("androidx.media3:media3-session:1.4.1")
    implementation("androidx.media3:media3-ui:1.4.1")

    // Material (legacy, for some components)
    implementation("com.google.android.material:material:1.12.0")

    // Voice
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    // OpenWakeWord: lightweight ONNX-based wake word detection
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.20.0")

    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}

// ── Mandatory changelog check ──────────────────────────────────────────────
// Fails the build if CHANGELOG.md doesn't have an entry for the current version.
tasks.register("verifyChangelog") {
    doLast {
        val versionName = android.defaultConfig.versionName
            ?: throw GradleException("versionName not set")
        val changelogFile = file("${rootProject.projectDir}/../configs/CHANGELOG.md")
        if (!changelogFile.exists()) {
            throw GradleException(
                "CHANGELOG.md not found at ${changelogFile.absolutePath}. " +
                "Create it and add an entry for v$versionName before building."
            )
        }
        val content = changelogFile.readText()
        if (!content.contains("## v$versionName")) {
            throw GradleException(
                "No changelog entry found for v$versionName in CHANGELOG.md. " +
                "Add '## v$versionName' section before building."
            )
        }
        println("Changelog verified: v$versionName entry found.")
    }
}

// ── ONNX model integrity check ────────────────────────────────────────────
// Fails the build if any .onnx.data file exists in assets (Android can't load external data)
tasks.register("verifyOnnxModels") {
    doLast {
        val assetsDir = file("src/main/assets/openwakeword")
        if (assetsDir.exists()) {
            val dataFiles = assetsDir.listFiles()?.filter { it.name.endsWith(".data") } ?: emptyList()
            if (dataFiles.isNotEmpty()) {
                throw GradleException(
                    "ONNX external data files found in assets — Android cannot load these!\n" +
                    "Files: ${dataFiles.joinToString { it.name }}\n" +
                    "Fix: Run 'onnx.save_model(m, path, save_as_external_data=False)' to inline weights."
                )
            }
        }
        println("ONNX models verified: no external .data files.")
    }
}

tasks.named("preBuild") {
    dependsOn("verifyChangelog", "verifyOnnxModels")
}
