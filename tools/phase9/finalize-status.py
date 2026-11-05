"""Publish canonical status only after final-artifact acceptance reports pass."""
from pathlib import Path
import json, hashlib, shutil
root=Path(__file__).resolve().parents[2]
out=root/'docs/handoff/evidence/phase9/final'
identity=json.loads((out/'release-identity.json').read_text(encoding='utf-8-sig'))
apk=root/'app/build/outputs/apk/debug/app-debug.apk'
assert hashlib.sha256(apk.read_bytes()).hexdigest().upper()==identity['installedApkSha256']
for stage,count in [('runtime',6),('visual',3),('previous',3),('workspace',5)]:
    report=json.loads((out/('summary-'+stage+'.json')).read_text(encoding='utf-8-sig'))
    assert len(report['checks'])==count and all(c['pass'] for c in report['checks']),stage
boundaries=json.loads((out/'device-boundaries.json').read_text(encoding='utf-8-sig'))
assert len(boundaries['checks'])==29 and all(c['pass'] for c in boundaries['checks'])
for p in out.glob('*.err'):
    stderr=p.read_text(encoding='utf-8-sig').strip()
    expected=(p.name=='activity-reconnect.err' and stderr=='Warning: Activity not started, its current task has been brought to the front')
    assert not stderr or expected,'Unexpected final stderr: '+p.name
assert all(int(s['failures'])==0 and int(s['errors'])==0 for s in identity['jvmTests'])
assert sum(int(s['tests']) for s in identity['jvmTests'])==30
assert identity['packagedPayloadMatches']==34 and identity['installedPayloadMatches']==33
assert 'BUILD SUCCESSFUL' in (out.parent/'build.log').read_text(encoding='utf-8-sig')
for log in ['phase8-repair.log','ui-boundary-regression.log','vision-regression.log',
            'carrier-cancellation.log','internal-boundary.log']:
    assert 'PASS' in (out.parent/log).read_text(encoding='utf-8-sig'),log
assert 'RESULT: PASS=9 FAIL=0' in (out.parent/'carrier-artifacts.log').read_text(encoding='utf-8-sig')
assert [s['pass'] for s in json.loads((out/'device-suites.json').read_text(encoding='utf-8-sig'))['suites']]==[44,22,57]
shutil.copy2(apk,out/'phase9-pass.apk')
report=root/'docs/handoff/phase9-product-acceptance.md'
text=report.read_text(encoding='utf-8')
replacements={
 '17A86A5F057301677B473EBDEE345BE8BBC11F7C31A514AB27AE9E0A7459AAA4':identity['apkSha256'],
 '24EC5A31E7F952F00CA9918BC00786D3AA4AB4C5891082B9EE4F7F973541B52E':identity['payloadManifestSha256'],
 '3646E5A412D1F1922C88D229E0412089E8A7537D3D39D8F684BB49E5D126237A':next(p['sha256'] for p in identity['payload'] if p['path'].endswith('/bootstrap.cjs'))}
for old,new in replacements.items():text=text.replace(old,new)
report.write_text(text,encoding='utf-8')
status=root/'docs/handoff/zcode-integration-status.md'
historic=status.read_text(encoding='utf-8')
marker='<!-- PHASE9_CURRENT_END -->'
if marker in historic:historic=historic.split(marker,1)[1].lstrip()
status.write_text(f'''# ZCode Integration Status — Phase 9 product acceptance

Current canonical status (2026-10-03): **Phase 9 receiving-product PASS** on `DEVICE_ANDROID17` (MODEL_ANDROID17, Android 17/API 37, ARM64). Tested and installed APK SHA-256: `{identity['apkSha256']}`. Runtime `0.16.9-runtime5`, unchanged ZCode Core 0.16.9 / APK-owned Node 24.18.0 / Bash 5.3.20, production Gateway with **journal schema 3**.

See [full Phase 9 acceptance and synchronization report](phase9-product-acceptance.md), [frozen release identity](evidence/phase9/final/release-identity.json), and `evidence/phase9/final/`. Historical Phase 7/8 sections below remain evidence of earlier baselines; their hold, pending or unstarted-workspace statements are not current instructions.

- Real screenshot, image-provider interpretation and coordinate tap: PASS through model-visible production MCP carrier, existing Gateway and native/INLINE routes. Existing test API verified with actual image input; independent explicit encrypted vision settings are configured.
- Final artifact: runtime/streaming/cancel/reconnect/crash/relaunch/persisted-session acceptance 6/6; physical boundaries and legacy UI 29/29; real new-tool model slices 3/3; real identity/UI/search 3/3; model workspace tools plus physical rollback 5/5.
- Build/lint PASS; JVM 30/0/0; phone Node regression WWS44/Gateway22/search57 with zero failures; carrier artifacts9/0; actual-source cancellation, vision, exact internal approval binding and three retained Phase8 repairs PASS.
- 34 packaged hashes verified; 33 immutable installed payload hashes verified; mutable host-owned personal-provider file follows the existing explicit exclusion. Exact consumed handoff manifests and product adaptation hashes are in the full report. No secret config or raw image bytes were exported.
- Three Phase8 repairs remain **STILL_PRODUCT_DIVERGENCE** versus the consumed upstream; source-level product adaptations close Phase9 secure capture, staleness, cleanup, egress, configuration, hard safety and trace binding. No Route C or competing architecture.
- Measured limit: this ROM removes Accessibility enablement on force-stop. Runtime/session recovery passes; screen control needs the system service re-enabled. Debug setup restored it explicitly; production does not use root to restore grants.
- Root/Shizuku/ADB production backends, PTY, optional Ubuntu ToolchainProvider, virtual display/input, MediaProjection and updater/watchdog remain deferred. DSHA remains a selective donor. Next upstream work is synchronization of these measured repairs and a corrected hash-pinned package/full regression, before a separately scoped capability phase.

{marker}

'''+historic,encoding='utf-8')
(root/'docs/project/CURRENT_STATE.md').write_text(f'''# Current product state

Updated: 2026-10-03. Canonical receiving-product acceptance: **Phase 9 PASS** on Android 17 device `DEVICE_ANDROID17` (MODEL_ANDROID17, API37, ARM64). No next production capability phase is started.

- Accepted runtime: `0.16.9-runtime5` receiving-product source merge; unmodified ZCode Core0.16.9, APK-owned Node24.18.0/Bash5.3.20. One production Gateway, journal schema **3**, existing workspace backups/rollback.
- Frozen and installed APK SHA: `{identity['apkSha256']}`. Recovery snapshots for Phase8 are retained; Phase9 accepted artifact is `docs/handoff/evidence/phase9/final/phase9-pass.apk`.
- Product architecture: Route A, ZCode owns Provider/Session/Context/Skill/Tool loop; MCP carrier and local JSON-RPC2.0 provider protocol stay separate. Native UI routes use the existing worker/Accessibility boundary; vision/search/workspace use existing INLINE seams.
- Accepted new capability: metadata-only screenshot, explicit HTTPS image-provider vision, verified coordinate tap/long press. Actual current test model `deepseek-flash` processed the physical image; configuration is independent, encrypted and private. Model-visible end-to-end traces are saved.
- Regression: runtime6/6, visual3/3, physical29/29, real previous tools3/3, workspace/rollback5/5; JVM30/0/0, lint/buildPASS; device WWS44/Gateway22/search57 and carrier artifacts9 all zero failures; source boundary/cancellation/cleanup/Phase8 repair tests pass.
- Safety: committed exact Gateway approval before native/internal dispatch; no journal => no execution; host policy ceiling; hard-confirm cannot be bypassed by benign labels or user mode; cancellation/purge and unverified/no-retry outcomes retained; rollback is a new operation. No runtime factory patch or second policy/journal/agent core.
- Source authority: Workflow Phase9 handoff + runtime5 payload, reconciled by `docs/handoff/dsha-context-for-phase9.md`. All three measured Phase8 repairs remain STILL_PRODUCT_DIVERGENCE and retained with executable regressions.
- Limits: window capture requires API34+; protected/black/IME/geometry/expired frames refuse. Force-stop on this ROM removes Accessibility grant; the user must re-enable it for screen control. General vision accuracy and positive long-list scrolling are not benchmarked.
- DSHA: selective donor, no fork/pivot. PTY/Ubuntu/Root/Shizuku/ADB/virtual display/input/MediaProjection/updater/watchdog remain deferred. Distribution licensing remains separate from technical acceptance.
- Next work: upstream synchronization of the measured product corrections and complete revised regression; do not add another architecture or silently start a new privileged capability phase.

Bootstrap: read this file, latest `docs/handoff/zcode-integration-status.md` and `docs/handoff/phase9-product-acceptance.md`; then the actual next handoff before implementation. Historical hold/blocked paragraphs do not override the current measured baseline.
''',encoding='utf-8')
coord=root/'docs/handoff/codex-status-for-zcode.md'
old=coord.read_text(encoding='utf-8')
if '<!-- PHASE9_COORDINATION_END -->' in old:old=old.split('<!-- PHASE9_COORDINATION_END -->',1)[1].lstrip()
coord.write_text('''# Current Codex product synchronization — Phase 9 PASS

Updated 2026-10-03. The authoritative current architecture, runtime integration, adapter/worker interfaces, production carrier findings, reusable Android components, measured limits and exact files to inspect are in [Phase 9 receiving-product report](phase9-product-acceptance.md) and [current integration status](zcode-integration-status.md). This is the synchronization output for ZCode; the M0 material below is historical.

ZCode should review and adopt the three retained Phase8 repairs and the Phase9 boundary corrections, then issue a source- and hash-pinned corrected handoff with full regressions. Product-side acceptance on `DEVICE_ANDROID17` is green, including actual image input using the existing multimodal test service. No second policy/journal/agent runtime or DSHA fork is requested. No other thread was messaged automatically.

<!-- PHASE9_COORDINATION_END -->

'''+old,encoding='utf-8')
print('Canonical Phase9 PASS published; installed/frozen APK '+identity['apkSha256'])
