"""Host-only target selection/identity checks; this file never runs adb."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from device_target import resolve_device_target


class DeviceTargetTest(unittest.TestCase):
    def test_default_is_explicit_android15_identity(self):
        target = resolve_device_target()
        self.assertEqual((target.name, target.serial, target.sdk), ("android15-main", "DEVICE_ANDROID15", 35))
        self.assertEqual(target.adb_argv("adb", "get-state"), ["adb", "-s", "DEVICE_ANDROID15", "get-state"])
        self.assertEqual(target.instrumentation_args(), ["-e", "deviceTarget", "android15-main"])

    def test_android17_must_be_named_and_unknown_targets_fail(self):
        self.assertEqual(resolve_device_target("android17-compat").serial, "DEVICE_ANDROID17")
        for name in ["", "DEVICE_ANDROID17", "first", "android15"]:
            with self.assertRaises(ValueError):
                resolve_device_target(name)

    def test_rejects_wrong_sdk_model_and_missing_arm64(self):
        target = resolve_device_target()
        properties = {"ro.build.version.sdk": "35", "ro.build.version.release": "15",
                      "ro.product.model": "MODEL_ANDROID15", "ro.product.cpu.abilist": "arm64-v8a,armeabi-v7a"}
        target.validate_properties(properties)
        for key, value in [("ro.build.version.sdk", "37"), ("ro.product.model", "MODEL_ANDROID17"),
                           ("ro.product.cpu.abilist", "armeabi-v7a")]:
            with self.assertRaises(ValueError):
                target.validate_properties({**properties, key: value})

    def test_artifact_identity_is_required_and_bound_independently(self):
        target = resolve_device_target()
        with self.assertRaises(ValueError):
            target.validate_artifact("a" * 64)
        bound = target.with_artifact("a" * 64, "b" * 64)
        bound.validate_artifact("A" * 64, "B" * 64)
        self.assertIsNone(target.apk_sha256)
        for actual, payload in [("c" * 64, "b" * 64), ("a" * 64, None)]:
            with self.assertRaises(ValueError):
                bound.validate_artifact(actual, payload)
        with self.assertRaises(ValueError):
            target.with_artifact("short")


if __name__ == "__main__":
    unittest.main()
