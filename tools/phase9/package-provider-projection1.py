"""Prepare substantive ACCEPT_V1 source/test/evidence delivery. Does not publish or execute."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT/'docs/handoff'
OUT = DOC/'evidence/provider-projection1'
s = json.loads((OUT/'acceptance-summary.json').read_text())
package_id = 'codex-provider-projection1-20261023-r1'
stage = DOC/'outgoing'/package_id
stage.mkdir(parents=True, exist_ok=False)
roles = {}


def put(name, data, role):
    target=stage/name; target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data if isinstance(data,bytes) else data.encode('utf-8')); roles[name]=role


def copy(source,name,role):
    put(name,source.read_bytes(),role)


report=f'''# provider-projection1 — Android17 Core / Gateway / isolated-provider transport

Date: 2026-10-23. Disposition **PASS_SCOPED_CORE_GATEWAY_PROVIDER_TRANSPORT**.

The production Node host now reads the existing Kotlin review file/catalog, verifies exact package
and Android declaration identities, and passes immutable per-session pins through the existing
carrier/Android Dispatcher boundary. No new registry, review schema, journal table, permission
matrix or Route C patch. Imported production startup enrollment and user review UI remain disabled.

## Measured chain

Separate test APK, real runtime5 / Core0.16.9 / APK-owned Node24.18.0, own UID/root/config/port8766.
Actual Kotlin ZIP import + explicit trusted fixture review writes provider-reviews.json. Description
contains Chinese, emoji, slash and </script>, so Android JSONObject.quote/hash compatibility is
proved against real Kotlin output, not solely the JS helper. Real Core session/create pins v1;
publish/review v2, register only v2 in the worker, create another actual Core session. Execute old
session -> v1; Core close/resume old -> v1; new session -> v2. Calls deliberately supply wrong
content/declaration metadata; host session routing replaces it with the reviewed exact pins.

Every call traverses HTTP carrier, existing Gateway prompt/operation, production Kotlin worker,
Android Dispatcher/session resolver, isolated JSON-RPC provider and host-created physical report.
The test explicitly answers the normal Gateway prompt; unknown provider remains PRIVILEGED+ask.
The three operations join uniquely by session/callId to physical reports and both hash fields.
UIDs are isolated app UIDs, distinct from the owner. No root or Android15 operation.

Final Android17 fixture: `{s['deviceRun']}`. Operations4/5/6; physical versions v1/v1/v2.
First complete device fixture1792732635982405900 also passed; final repeat follows manifest
productRevision/payload metadata refresh. Both source snapshots and APKs retained. No device failure
in these two runs. Windows first file-link test failed EPERM; original source/log retained, then
explicit Windows-only skip; actual Android file links still required and passed.

## Verification

- Android Node boundary36: 36pass/0fail/0skip, actual filesystem links and SQLite.
- Windows Node boundary36: 35pass/0fail/1skip (file-link privilege); not claimed zero-skip.
- Existing Gateway settlement regression22: PASS.
- JVM118: 0fail/0error/0skip. Product/test APK builds PASS.
- Lint: 0errors/28existing warnings; known !path analyzer exception present in raw log,
  completed report and BUILD SUCCESSFUL retained. Not a warning-free claim.
- All41 payload SHA rows verified against candidate APK, runtime assets/native bytes match the
  separate tested APK. Core/Gateway/journal.sql/native/production Manifest unchanged vs previous
  uninstalled candidate4B2343D3…; six expected asset modifications plus one new module.

## Frozen identities

- Installed production APK: `{s['installedProductSha256']}` (pre/post equal, not reinstalled).
- Uninstalled candidate: `{s['candidateSha256']}`.
- Separate test APK: `{s['testApkSha256']}`.
- runtime-manifest.json: `{s['runtimeManifestSha256']}`.
- payload-SHA256SUMS.txt: `{s['payloadManifestSha256']}`.
- Version remains 0.16.9-runtime5; productRevision=provider-projection1-session-routing-candidate.

## Limits and next work

This is test-originated HTTP transport with actual Core sessions and explicit test answers, **not
a model-issued tool call/final answer or production approval UI**. No production host restart,
force-stop resume, imported-provider in-flight cancellation/revocation, power-loss or final product
installation acceptance. Current production host readiness NOT_VERIFIED; no restart/readiness
request performed. Historical last probe unavailable remains historical, not a fresh observation.

Node adapter is read-only and does not enroll imported packages. Fixed tools remain on their
existing route. Stable canonical ID/profile can route an old declaration; removed/renamed/schema-
incompatible tools fail closed rather than being automatically re-exposed. Retirement/revocation
limits remain the existing resolver boundaries; do not claim cancellation of retained handles.

Codex next: explicit host review/admission UI/startup enrollment using existing stores, followed
by real model/Gateway/provider/artifact/cancellation/restart acceptance. ZCode next: pinned Android15
compatibility36 and four bounded source questions per attached task; no production implementation.

Local evidence: docs/handoff/evidence/provider-projection1/acceptance-summary.json, final fixture
{s['deviceRun']}/result.json, commands-and-exits.json, artifact-0/1/2.json and android-boundary-tests.log.
Exchange remains original ACCEPT_V1; no confirmation-only package.
'''
(DOC/'provider-projection1-android17-20261023.md').write_text(report,encoding='utf-8')
put('STATUS.md',report,'documentation')
copy(DOC/'provider-projection1-zcode-next-task-20261023.md','HANDOFF.md','documentation')
copy(DOC/'provider-review1-source-receiving-review-20261023.md','PREVIOUS-RECEIVING-REVIEW.md','documentation')
baseline=json.loads((DOC/'incoming-zcode-provider-package1-android15-20261018-r1/results/runtime-identity.json').read_text())['pre']
put('ANDROID15-BASELINE-REFERENCE.md','# Historical mechanically recorded Android15 baseline\n\n'
    'Reference from accepted provider-package1 result; not a fresh device read. Ignore historic apkPath: discover current pm path.\n'
    'Only preflight APK/runtime/node values are reproduced; withdrawn recorder classification not copied.\n\n```json\n'+
    json.dumps({k:v for k,v in baseline.items() if k!='apkPath'},indent=2)+'\n```\n','documentation')
put('BOUNDARY-CONTRACT.md','''# Existing-boundary projection contract

Read-only ProviderReviewBindings.selected/verify/resolve projects existing schema1 review metadata,
v2 content-addressed catalog and restricted APK_NODE/base64 data-transform profile. It writes nothing.
SkillSessionBindings snapshots exact reviewed id/version/contentHash/definitionHash/toolIds in the
same sessions-index.json row. No active-pointer fallback for old sessions. Kotlin remains writer.
Android JSONObject.quote escaping and Kotlin sorted canonical joining are persisted identity;
Node matches it rather than changing old hashes. Registration supplies visibility/profile only;
host session metadata supplies actual old-version identity. Declaration changes require exact
review record, same compatible public profile and current visible canonical ID.
Carrier overwrites caller content/declaration hashes, checks existing Gateway/session/epoch scope,
reverifies pin after approval, passes pins to Worker/Dispatcher, and checks success provenance in
existing CAS operation settlement. Gateway schema3/risk/authorization and JSON-RPC2.0 unchanged.
No import-time enrollment, arbitrary code loading in main process or sandbox-completeness promise.
''','contract')
put('RESIDUALS.md','''# Boundaries not yet accepted

No real model-issued imported-provider call/final answer. Explicit user review/admission UI/startup
enrollment not shipped. Production candidate uninstalled; product host readiness NOT_VERIFIED.
Actual Core close/resume is not full host/force-stop restart proof. Test answers Gateway via normal
HTTP endpoint; this is not production unattended approval. No in-flight revocation guarantee.
No power-loss/directory-fsync guarantee. Windows physical-file-link skip disclosed; Android executes it.
Production Core/Gateway/journal schema/native/Manifest unchanged. Runtime metadata and bounded host
adapter/Worker/auth settlement changed; source identity is not global security proof.
Android15 has not executed this package until ZCode reports it. No confirmation-only next package.
''','documentation')
put('SOURCE-LICENSING.md','''# Sources and payload scope

New adapter/tests/probe and boundary edits are project-owned source. Existing Gateway/bootstrap/
Skill code originates from validated Workflow handoffs plus accepted receiving-product repairs.
No new third-party dependency. Android JSONObject.quote compatibility was checked against local
Android SDK35 JSONStringer source; no SDK source is redistributed. Existing Node/Core licenses and
distribution restrictions remain unchanged. No binaries/APKs/runtime libraries/Core bundle/private
configuration/credentials/token/database/executor directory are shipped. Runtime SHA metadata is
reference identity only; this is not a complete installable runtime payload. Android15 test reuses
its installed exact Node/libs and copies only named source files into a private fixture.
''','notice')
sources=[ROOT/'app/src/main/java/dev/alita/androidagent/AgentApplication.kt',
    *[ROOT/'app/src/main/java/dev/alita/androidagent/tools'/name for name in ['LocalProviderCatalog.kt','ProviderReviewStore.kt','PinnedIsolatedProvider.kt']],
    *[ROOT/'app/src/main/java/dev/alita/androidagent/zcode/adapter'/name for name in ['AndroidToolContracts.kt','ReadOnlyToolDispatcher.kt','ZCodeToolMapping.kt']],
    *[ROOT/'app/src/main/java/dev/alita/androidagent/zcode/runtime'/name for name in ['ZCodeRuntimeBundle.kt','ZCodeCarrierWorker.kt']],
    ROOT/'app/src/main/AndroidManifest.xml',ROOT/'app/src/isolationTest/AndroidManifest.xml',
    ROOT/'app/src/isolationTest/java/dev/alita/androidagent/execution/isolation/ProjectionProbeActivity.kt',
    *[ROOT/'app/src/main/assets/zcode-runtime'/name for name in ['provider-review-bindings.cjs','skill-session-bindings.cjs','bootstrap.cjs','carrier-authorization.cjs','gateway.cjs','contracts/journal.sql','runtime-manifest.json','payload-SHA256SUMS.txt']],
    *[ROOT/'tools/phase9'/name for name in ['provider-projection-test.cjs','provider-projection-fixture.cjs','provider-session-bindings-test.cjs','provider-declaration-settlement-test.cjs',
        'provider-settlement-regression.cjs','provider-projection-device-acceptance.py','provider-projection-evidence-summary.py',Path(__file__).name]],
    ROOT/'app/src/test/java/dev/alita/androidagent/ProviderReviewStoreTest.kt']
identities={}
for file in sources:
    name=file.relative_to(ROOT).as_posix();identities[name]=hashlib.sha256(file.read_bytes()).hexdigest().upper()
    role='test' if name.startswith('tools/') or '/test/' in name or '/isolationTest/' in name else 'contract' if name.endswith(('.json','.sql','.txt')) else 'source'
    copy(file,name,role)
put('SOURCE_IDENTITY.json',json.dumps(identities,indent=2)+'\n','contract')
for name in ['acceptance-summary.json','boundary-tests.log','settlement-regression.log','build.log','probe-build.log','build-final.log','lint.log','lint-results-debug.txt','projection-first.log','projection-first.cjs']:
    copy(OUT/name,'results/'+name,'result' if name!='projection-first.cjs' else 'test')
for run in ['1792732635982405900',s['deviceRun']]:
    for name in ['result.json','identity.json','source-sha256.json','commands-and-exits.json','android-boundary-tests.log','artifact-0.json','artifact-1.json','artifact-2.json']:
        copy(OUT/run/name,'results/android17/'+run+'/'+name,'result')
    # Preserve exact historical metadata for first pass, do not pretend it used final pins.
    for name in ['runtime-manifest.json','payload-SHA256SUMS.txt']:
        copy(OUT/run/'source/app/src/main/assets/zcode-runtime'/name,'results/android17/'+run+'/source-metadata/'+name,'result')
for file in sorted((OUT/'unit-tests').glob('*.xml')): copy(file,'results/unit-tests/'+file.name,'result')
spec=dict(protocolVersion=1,packageId=package_id,sender='codex',recipient='zcode',
    scope='provider-projection-and-per-session-carrier-pins-scoped-product-proof-plus-android15-compatibility-execution',
    baseline='Installed Android17 C51 unchanged; uninstalled candidate5A30BEED; Android15 809E54FC remains frozen',
    changeSummary='Read-only actual Kotlin review/catalog projection, per-session worker pins and declaration settlement; actual Core/Gateway/isolated-provider v1-v1-v2; next Android15 boundary36 task',
    completion='COMPLETE',missingItems=[],requiredPaths=sorted(roles),fileRoles=roles,
    dependencies=[dict(packageId='codex-provider-review1-20261023-r1',archiveSha256='30F50D7A4DB2EE3D0EA0C49B00AD40F13EE364CB6243DB69320CC9B2ECE0F338',requiredPaths=['SOURCE_IDENTITY.json']),
        dict(packageId='zcode-provider-review1-source-review-20261023-r1',archiveSha256='050E1AD9393896F6FFF0FEE1169E3B8F0F8875164D5951CAFFF1ED87BE01DC65',requiredPaths=['SOURCE-REVIEW.md'])])
(DOC/'exchange-provider-projection1-20261023-r1-spec.json').write_text(json.dumps(spec,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(stage=str(stage),files=len(roles),sourceEntries=len(identities))))
