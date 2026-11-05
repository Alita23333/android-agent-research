"""Create an allowlisted review snapshot; no device or upstream workspace operations."""
from pathlib import Path
import hashlib, json, re, shutil, zipfile

root = Path(__file__).resolve().parents[2]
handoff = root / 'docs/handoff'
destination = handoff / 'zcode-phase9-sync-input'
archive_path = handoff / 'zcode-phase9-sync-input.zip'
assert not destination.exists() and not archive_path.exists(), 'Existing handoff retained; choose a new package revision instead of overwriting it.'
identity = json.loads((handoff/'evidence/phase9/final/release-identity.json').read_text(encoding='utf-8'))
assert identity['apkSha256'] == '9AACC118DFA83372837FFB4764414CC88FF7F477AE776646C318EBE87DF03EF7'
selected = {}
def add(relative, category):
    path = root / relative
    assert path.is_file() and not path.is_symlink(), relative
    selected[relative] = category

for relative in [
    'docs/handoff/ZCODE_PHASE9_SYNC_TASK.md', 'docs/project/CURRENT_STATE.md',
    'docs/handoff/zcode-integration-status.md', 'docs/handoff/phase9-product-acceptance.md',
    'docs/handoff/dsha-context-for-phase9.md', 'docs/handoff/codex-status-for-zcode.md',
    'docs/research/dsha-reuse-assessment-2026-10-03.md',
    'docs/handoff/phase9-integration-plan.md', 'docs/handoff/runtime-payload-alignment-report.txt',
    'docs/handoff/runtime-payload-licenses.md', 'docs/handoff/evidence/phase9/README.md']:
    add(relative,'documentation')
for name in ['bootstrap.cjs','gateway.cjs','ui-tree.cjs','vision-pipeline.cjs','android-carrier.cjs',
             'web-search.cjs','workspace-files.cjs','runtime-manifest.json','payload-SHA256SUMS.txt',
             'contracts/config-disable-pack.json','contracts/hard-confirm-pack.json','contracts/journal.sql']:
    add('app/src/main/assets/zcode-runtime/'+name,'runtime-source-contract')
for path in (root/'app/src/main/java/dev/alita/androidagent/zcode').rglob('*.kt'):
    add(path.relative_to(root).as_posix(),'android-boundary-source')
for relative in [
    'app/src/main/java/dev/alita/androidagent/device/AgentAccessibilityService.kt',
    'app/src/main/java/dev/alita/androidagent/device/DeviceToolProvider.kt',
    'app/src/main/java/dev/alita/androidagent/MainActivity.kt',
    'app/src/main/java/dev/alita/androidagent/MainViewModel.kt',
    'app/src/main/java/dev/alita/androidagent/AgentApplication.kt',
    'app/src/main/java/dev/alita/androidagent/model/SecureSettings.kt',
    'app/src/main/AndroidManifest.xml','app/src/main/res/xml/accessibility_service_config.xml',
    'app/src/main/res/xml/data_extraction_rules.xml','app/build.gradle.kts','build.gradle.kts','settings.gradle.kts',
    'app/src/test/java/dev/alita/androidagent/Phase9VisionBoundaryTest.kt',
    'app/src/test/java/dev/alita/androidagent/ZCodeIntegrationContractTest.kt']:
    add(relative,'android-source-or-build-reference')
for relative in [
    'tools/phase9/vision-product-regression.cjs','tools/phase9/internal-boundary-regression.cjs',
    'tools/phase9/phase8-repair-regression.cjs','tools/phase9/carrier-cancellation-regression.cjs',
    'tools/phase8/ui-boundary-regression.cjs','tools/phase8/carrier-product-regression.cjs',
    'tools/phase8/carrier-artifacts-check.cjs','tools/phase8/gateway-unittest.cjs',
    'tools/phase8/web-search-unittest.cjs','tools/phase8/wws-unittest.cjs']:
    add(relative,'local-regression-source')
for relative in ['tools/phase9/device-boundaries.cjs','tools/phase9/accept-product.py',
                 'tools/phase9/run-device-suites.py','tools/zcode/bridge-acceptance.cjs']:
    add(relative,'device-script-review-only')
for name in ['build.log','phase8-repair.log','ui-boundary-regression.log','vision-regression.log',
             'internal-boundary.log','carrier-artifacts.log','carrier-cancellation.log']:
    add('docs/handoff/evidence/phase9/'+name,'measured-test-log')
for path in (handoff/'evidence/phase9/final').iterdir():
    if path.suffix in {'.json','.err','.log'}:
        add(path.relative_to(root).as_posix(),'final-measured-evidence')

def sha(data): return hashlib.sha256(data).hexdigest().upper()
immutable={p['path']:p['sha256'] for p in identity['payload']}
snapshot=[]
for relative,category in sorted(selected.items()):
    data=(root/relative).read_bytes()
    assert not re.search(rb'sk-[A-Za-z0-9_-]{16,}',data), 'Potential credential: '+relative
    assert not re.search(rb'data:image/[^;\s]+;base64,[A-Za-z0-9+/=]{80,}',data), 'Embedded pixels: '+relative
    assert b'-----BEGIN PRIVATE KEY-----' not in data and b'-----BEGIN RSA PRIVATE KEY-----' not in data, relative
    assert not any(part.lower() in {'personal_provider_config.json','bridge-token','vision_config.json','search_config.json'}
                   for part in Path(relative).parts), relative
    if relative.startswith('app/src/main/') and relative.removeprefix('app/src/main/') in immutable:
        assert sha(data)==immutable[relative.removeprefix('app/src/main/')], 'Accepted runtime source drift: '+relative
    if relative.endswith('.json'):
        def inspect(value):
            if isinstance(value,dict):
                for key,item in value.items():
                    if key.lower() in {'apikey','api_key','bridgetoken','bridge_token','accesstoken','refreshtoken','authorization'}:
                        assert not isinstance(item,str) or not item.strip(), 'Credential-valued JSON field: '+relative
                    inspect(item)
            elif isinstance(value,list):
                for item in value: inspect(item)
        inspect(json.loads(data.decode('utf-8-sig')))
    target=destination/relative; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
    snapshot.append({'path':relative,'category':category,'sha256':sha(data),'bytes':len(data)})

(destination/'SOURCE_SNAPSHOT.json').write_text(json.dumps({
    'date':'2026-10-03','baseline':'Phase9 receiving-product PASS','runtime':'0.16.9-runtime5',
    'acceptedApkSha256':identity['apkSha256'],'files':snapshot,
    'notIncluded':['APK','native binaries','Core bundle','personal provider config','keys/tokens','databases','live frames']},
    ensure_ascii=False,indent=2),encoding='utf-8')
(destination/'START_HERE.md').write_text('''# ZCode Phase 9 同步输入

请先阅读 `INPUT_PACKAGE.md`，运行只读包校验 `verify-input.py`，再完整阅读 `docs/handoff/ZCODE_PHASE9_SYNC_TASK.md` 并执行。

本包由用户交给隔离工作区后才构成可访问输入。当前任务是修复同步与合同/证据交付；不启动下一阶段生产能力，不操作产品验收设备DEVICE_ANDROID17。
''',encoding='utf-8')
(destination/'INPUT_PACKAGE.md').write_text('''# 输入包说明

日期：2026-10-03。包内任务书为 `docs/handoff/ZCODE_PHASE9_SYNC_TASK.md`。快照来自已验收 Phase9 产品；源码与实测证据保持产品相对路径，见 `SOURCE_SNAPSHOT.json`。

这是审阅/修复复用输入，不是完整产品仓库或可安装runtime。完整Core0.16.9 bundle、native载荷、builtin provider大文件及APK未包含；它们的hash见release-identity/payload清单。先核对你自己的同版本上游载荷，不合成替代品。`payload-SHA256SUMS.txt`是完整产品载荷身份记录，不能用它要求本最小输入包具有所有二进制文件。本输入包完整性以根目录`SHA256SUMS.txt`为准。

没有复制个人provider/vision/search配置、Key/bridge token、Keystore、用户数据库或live screenshot。代码里的fixture-only/lab常量只属于公开测试fixture。

## 可在离线源码快照上运行的测试

从本包根目录，使用可用Node24运行以下脚本；它们不操作Android手机：

- `tools/phase9/vision-product-regression.cjs`：实际pipeline与本地mock；测试监听127.0.0.1:18086，需端口空闲。Mock不能证明真实VLM准确性。
- `tools/phase9/internal-boundary-regression.cjs`：实际host函数的授权关联、no-journal/no-queue、取消/清理。
- `tools/phase9/phase8-repair-regression.cjs`：Gateway hash/rollback生命周期；独立临时目录。
- `tools/phase9/carrier-cancellation-regression.cjs`：actual MCP carrier cancellation与本地HTTP fixture。
- `tools/phase8/ui-boundary-regression.cjs`：raw/normalized映射与abandoned poll。
- `tools/phase8/carrier-product-regression.cjs`：actual carrier handler产物传递；本地临时HTTP端口。

Gateway/WWS/search独立测试源码也提供，但需在你自己的isolated fixture中配置SPIKE_ROOT、runtime依赖与Core bundle；不得指向生产journal/workspace。JVM/Kotlin源码只供适配和审阅，需放入你的完整Android宿主与其依赖才能编译。本包未宣称完整产品可独立构建。

## 只供审阅的真机脚本

`tools/phase9/device-boundaries.cjs`、`accept-product.py`、`run-device-suites.py`包含固定产品设备ID或产品环境路径；`tools/zcode/bridge-acceptance.cjs`由产品入口设置目标。**不要在上游直接运行这些脚本。** 为自己的宿主/已分配设备适配fixture后运行，并保存自己的结果；禁止误操作DEVICE_ANDROID17。One-time migration/closure scripts没有提供，不可在已验收runtime上重复应用迁移。

`docs/handoff/evidence/phase9/final/`是接收侧最终实测报告；你的报告必须区分“引用产品已有证据”和“上游自行重新验证”。父目录日志及README解释开发失败与故障修复，最终pass不得抹掉失败历史。

## 校验

在解压根目录运行 `python verify-input.py`（Python3标准库即可；只读，无网络/设备调用）。清单不包含自身hash；ZIP整体hash在用户随附的`.zip.sha256`文件中。原始源文件字节保持不变；辅助说明/快照元数据也纳入包清单。
''',encoding='utf-8')
(destination/'verify-input.py').write_text('''from pathlib import Path
import hashlib
root = Path(__file__).resolve().parent
expected = {}
for line in (root / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
    digest, relative = line.split(maxsplit=1)
    path = (root / relative).resolve()
    assert path.is_relative_to(root) and not Path(relative).is_absolute(), relative
    assert path.is_file() and not path.is_symlink(), relative
    assert hashlib.sha256(path.read_bytes()).hexdigest().upper() == digest.upper(), relative
    assert relative not in expected, relative
    expected[relative] = digest
actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()
          and p.name != 'SHA256SUMS.txt' and '__pycache__' not in p.parts}
assert actual == set(expected), 'Missing or unexpected input files'
print('PASS: ' + str(len(expected)) + ' files verified; no device or network operation')
''',encoding='utf-8')
files=sorted(p for p in destination.rglob('*') if p.is_file())
manifest=destination/'SHA256SUMS.txt'
manifest.write_text(''.join(sha(p.read_bytes())+'  '+p.relative_to(destination).as_posix()+'\n' for p in files),encoding='utf-8')
with zipfile.ZipFile(archive_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for path in sorted(p for p in destination.rglob('*') if p.is_file()):
        archive.write(path,destination.name+'/'+path.relative_to(destination).as_posix())
with zipfile.ZipFile(archive_path) as archive:
    assert archive.testzip() is None
    for path in destination.rglob('*'):
        if path.is_file(): assert archive.read(destination.name+'/'+path.relative_to(destination).as_posix())==path.read_bytes()
archive_hash=sha(archive_path.read_bytes())
(handoff/'zcode-phase9-sync-input.zip.sha256').write_text(archive_hash+'  '+archive_path.name+'\n',encoding='utf-8')
result={'sourceFiles':len(snapshot),'checksummedFiles':len(files),'zipEntries':len(files)+1,
        'zipBytes':archive_path.stat().st_size,'zipSha256':archive_hash,'manifestSha256':sha(manifest.read_bytes()),
        'deviceOperations':0,'upstreamWrites':0,'runtimeChanges':0}
(handoff/'zcode-phase9-sync-input-validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
