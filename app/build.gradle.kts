plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "dev.alita.androidagent"
    compileSdk = 35

    defaultConfig {
        applicationId = "dev.alita.androidagent"
        minSdk = 31
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
        buildConfigField("boolean", "LEGACY_DIAGNOSTICS", "false")

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables.useSupportLibrary = true
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
        create("isolationTest") {
            initWith(getByName("debug"))
            applicationIdSuffix = ".isolationtest"
            matchingFallbacks += "debug"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true; buildConfig = true }
    packaging.jniLibs.useLegacyPackaging = true
    packaging.jniLibs.keepDebugSymbols += "**/*.so"
    sourceSets.getByName("main").assets.srcDir("build/isolated-runtime/assets")
    sourceSets.getByName("main").jniLibs.srcDir("build/isolated-runtime/jniLibs")
    testOptions.unitTests.isIncludeAndroidResources = true
    lint {
        // lifecycle-runtime 2.9 ships a detector compiled against a newer Kotlin
        // analysis API than AGP 8.7's lint runtime. Lint itself recommends
        // disabling this detector when it raises the linkage error.
        disable += "NullSafeMutableLiveData"
    }
    // The workspace path contains '!' which Kotlin treats as a JAR URL separator when
    // resolving the main classes JAR for tests. Compile the main sources into the test
    // fixture as a deterministic workaround; normal clones do not need a path change.
    sourceSets.getByName("test").java.srcDir("src/main/java")
    sourceSets.getByName("androidTest").java.srcDir("src/main/java")
    packaging.resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
}

val prepareIsolatedRuntime by tasks.registering(Exec::class) {
    inputs.file(rootProject.file("tools/phase9/prepare-product-isolation.py"))
    inputs.file("src/main/native/isolated_node.c")
    inputs.dir("src/main/assets/zcode-runtime/lib")
    inputs.file("src/main/jniLibs/arm64-v8a/libnode.so")
    inputs.file("src/main/assets/zcode-runtime/payload-SHA256SUMS.txt")
    outputs.dir(layout.buildDirectory.dir("isolated-runtime"))
    commandLine(providers.environmentVariable("ISOLATED_RUNTIME_PYTHON").orElse("python").get(),
        rootProject.file("tools/phase9/prepare-product-isolation.py").absolutePath)
}
tasks.named("preBuild").configure { dependsOn(prepareIsolatedRuntime) }

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.05.01")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.9.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.9.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    debugImplementation("androidx.compose.ui:ui-tooling")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.10.2")
    testImplementation("org.robolectric:robolectric:4.14.1")
    testImplementation("androidx.test:core-ktx:1.6.1")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.6.1")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
