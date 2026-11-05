"""Named acceptance targets. Selection never depends on adb device enumeration order.

This module contains test-side device identities only; it is not a production capability
or permission registry. Deployment drivers pin their artifact explicitly with with_artifact().
"""
from dataclasses import dataclass, replace
import re
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class DeviceTarget:
    name: str
    serial: str
    sdk: int
    android: str
    model: str
    abi: str = "arm64-v8a"
    package: str = "dev.alita.androidagent"
    runtime_version: str = "0.16.9-runtime5"
    apk_sha256: str | None = None
    payload_sha256: str | None = None
    required_capabilities: tuple[str, ...] = ()

    def __post_init__(self):
        for value in [self.apk_sha256, self.payload_sha256]:
            if value is not None and not re.fullmatch(r"[A-Fa-f0-9]{64}", value):
                raise ValueError("Artifact identity must be an exact SHA-256")

    def with_artifact(self, apk_sha256: str, payload_sha256: str | None = None):
        """Bind this immutable target to a selected APK, never to an observed arbitrary APK."""
        return replace(self, apk_sha256=apk_sha256.upper(),
                       payload_sha256=None if payload_sha256 is None else payload_sha256.upper())

    def validate_properties(self, properties: Mapping[str, str]):
        expected = {
            "ro.build.version.sdk": str(self.sdk),
            "ro.build.version.release": self.android,
            "ro.product.model": self.model,
        }
        for key, value in expected.items():
            if properties.get(key, "").strip() != value:
                raise ValueError(f"{self.name}: unexpected {key}")
        abis = properties.get("ro.product.cpu.abilist", "").strip().split(",")
        if self.abi not in abis:
            raise ValueError(f"{self.name}: required ABI {self.abi} is unavailable")

    def validate_artifact(self, apk_sha256: str, payload_sha256: str | None = None):
        if self.apk_sha256 is None:
            raise ValueError("Pin the selected APK before validating a deployment")
        if apk_sha256.upper() != self.apk_sha256:
            raise ValueError(f"{self.name}: APK identity mismatch")
        if self.payload_sha256 is not None and (
            payload_sha256 is None or payload_sha256.upper() != self.payload_sha256
        ):
            raise ValueError(f"{self.name}: runtime payload identity mismatch")

    def adb_argv(self, adb: str, *arguments: str):
        return [adb, "-s", self.serial, *arguments]

    def instrumentation_args(self):
        return ["-e", "deviceTarget", self.name]

    def activity_args(self):
        return ["--es", "deviceTarget", self.name]


TARGETS = MappingProxyType({
    "android15-main": DeviceTarget("android15-main", "DEVICE_ANDROID15", 35, "15", "MODEL_ANDROID15"),
    "android17-compat": DeviceTarget("android17-compat", "DEVICE_ANDROID17", 37, "17", "MODEL_ANDROID17"),
})
DEFAULT_TARGET = "android15-main"


def resolve_device_target(name: str | None = None):
    selected = DEFAULT_TARGET if name is None else name
    try:
        return TARGETS[selected]
    except KeyError:
        raise ValueError(f"Unknown device target: {selected!r}") from None


# Compact alias for acceptance drivers.
get_target = resolve_device_target
