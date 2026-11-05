from pathlib import Path
import subprocess, shlex
root = Path(__file__).resolve().parents[2]
adb = r'C:\Android\Sdk\platform-tools\adb.exe'
serial = 'DEVICE_ANDROID17'
def command(*args):
    return subprocess.check_output([adb, '-s', serial, *args], text=True, encoding='utf-8').strip()
existing = command('shell','settings','get','secure','enabled_accessibility_services')
component = 'dev.alita.androidagent/dev.alita.androidagent.device.AgentAccessibilityService'
components = [x for x in existing.split(':') if x and x != 'null']
if component not in components: components.append(component)
script = root / 'tools/phase9/device-setup.sh'
script.write_text('set -eu\nam force-stop dev.alita.androidagent\nam start -n dev.alita.androidagent/.zcode.runtime.ZCodeActivity\nsleep 3\nsettings put secure enabled_accessibility_services ' + shlex.quote(':'.join(components)) + '\nsettings put secure accessibility_enabled 1\n', encoding='utf-8', newline='\n')
command('push',str(script),'/data/local/tmp/p9-mainline-setup.sh')
print(command('shell',"su -c 'sh /data/local/tmp/p9-mainline-setup.sh'"))
print(command('forward','tcp:18765','tcp:8765'))
print('Target setup complete; existing accessibility providers retained.')
