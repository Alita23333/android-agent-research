package dev.alita.androidagent;

import android.os.Build;
import java.util.Arrays;

/** Test-source-set identity guard. Host adb serial selection is checked separately. */
public final class TestDeviceTarget {
    private TestDeviceTarget() {}
    public static final String ARGUMENT = "deviceTarget";
    public static final class Target {
        public final String name, model, release, abi;
        public final int sdk;
        private Target(String name, int sdk, String release, String model) {
            this.name = name; this.sdk = sdk; this.release = release; this.model = model;
            this.abi = "arm64-v8a";
        }
        private boolean matches() {
            return Build.VERSION.SDK_INT == sdk && release.equals(Build.VERSION.RELEASE)
                && model.equals(Build.MODEL) && Arrays.asList(Build.SUPPORTED_ABIS).contains(abi);
        }
    }
    private static final Target MAIN = new Target("android15-main", 35, "15", "MODEL_ANDROID15");
    private static final Target COMPAT = new Target("android17-compat", 37, "17", "MODEL_ANDROID17");

    /** Missing or unknown profile is rejected before any test fixture action. */
    public static Target require(String name) {
        final Target expected;
        if (MAIN.name.equals(name)) expected = MAIN;
        else if (COMPAT.name.equals(name)) expected = COMPAT;
        else throw new IllegalArgumentException("Explicit deviceTarget must name android15-main or android17-compat");
        if (!expected.matches()) throw new IllegalStateException("Unexpected device for " + expected.name);
        return expected;
    }

    /** Standalone read-only DocumentsProvider cannot load InstrumentationRegistry/Kotlin.
     * Its private ZIP generation is allowed only on the same exact known devices.
     * The instrumentation entry that consumes it still requires an explicit profile.
     */
    public static Target matchingKnownDevice() {
        if (MAIN.matches()) return MAIN;
        if (COMPAT.matches()) return COMPAT;
        return null;
    }
}
