set -eu
am force-stop dev.alita.androidagent
am start -n dev.alita.androidagent/.zcode.runtime.ZCodeActivity
sleep 3
settings put secure enabled_accessibility_services com.miui.screenshot/.accessibility.ScreenshotAccessibilityService:com.omarea.vtools/.AccessibilitySceneMode:dev.alita.androidagent/dev.alita.androidagent.device.AgentAccessibilityService
settings put secure accessibility_enabled 1
