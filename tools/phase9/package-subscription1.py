"""Immutable original-v1 handoff: field-only product fix and directed Core protocol check."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'docs/handoff';EV=DOC/'evidence/subscription1';RUN=EV/'1792939546631881700'
ID='codex-subscription1-20261025-r1';DEST=DOC/'outgoing'/ID;DEST.mkdir(parents=True,exist_ok=False);roles={};ids={}
def put(n,data,role):
 p=DEST/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data if isinstance(data,bytes) else data.encode());roles[n]=role
def copy(p,n,role):put(n,p.read_bytes(),role)
copy(DOC/'subscription1-product-acceptance-20261025.md','PRODUCT-RESULT.md','documentation')
copy(DOC/'provider-model1-android15-receiving-review-20261025.md','PREVIOUS-RECEIVING-REVIEW.md','documentation')
copy(DOC/'outgoing/codex-provider-model1-20261025-r1/ANDROID15-BASELINE-REFERENCE.md','ANDROID15-BASELINE-REFERENCE.md','contract')
copy(EV/'core-source-snippets.json','CORE-SCHEMA-SNIPPETS.json','contract')
put('HANDOFF.md','''# subscription1 — product fix and next pinned Android15 task

Original ACCEPT_V1 only. Read complete package and verify all SOURCE_IDENTITY entries mechanically.
Review executable source before execution. No credentials, binary, APK or database transferred.

## Product result / corrected root cause

Android17 E36A5B071FA052104C00618E788E66A1A4AA4C009D21C828462D407A8700F8F2 now installed.
Persistent bridge automatically called session/subscribe with only sessionId; actual Core0.16.9
strictly requires deliveryKind. This is a BRIDGE request bug, not necessarily a browser caller.
Only the automatic request adds desktop-continuous; Core connection is owned by bridge across
Activity/SSE reconnect. No Core patch, new protocol, journal, policy, registry or replay system.
Old1FF produced4 errors; new package28successful auto-subscribe replies/53typed session events,
zero deliveryKind errors; two real model/provider/physical report joins665/666,264/232 stream
chunks, Activity same-runtime reconnect, force-stop exact messages+resume; cancellation667
CANCELLED/isolated PID gone282ms.40installed pins verified;36DEX/native/Manifest entries identical.
Core5 schema/read assertions and relatedNode14+SQLite22 passed. No new JVM/lint run claimed.
Read PRODUCT-RESULT for limits: continuous delivery not browser cursor/replay guarantee; older
payload.type folding assumptions are a SEPARATE open boundary, not declared fixed by this field.

## Exact Android15 task (onlyDEVICE_ANDROID15;809E54FC baseline unchanged)

1. Verify archive/dependency and every source identity per entry. Read prior receiving review:
   provider-model1 attempt1 stopped AFTER stage a and BEFORE stage b/postflight; do not repeat
   both-stages-twice claim. Exact numeric result fields, not substrings; no correction-only reply.
2. Review tools/phase9/core-subscription-protocol-test.cjs and core-subscription-android15.py.
   The first starts the INSTALLED immutable Core with an isolated temporary HOME and USER-only
   history, requests two negative schema cases, two successful continuous subscriptions, one read,
   then stdinEOF/natural exit. It makes NO session/send/model/provider/tool request. Failure-only
   SIGKILL is limited to its owned child and never qualifies as natural success. Its own temp HOME
   is removed; outer fixture retained. The Python wrapper validates baseline/reference mechanically,
   freezes itself before device work, records every argv/exit/stdout/stderr, uses a short TMPDIR and
   verifies one copied helper. It is Android15-only. It does NOT install or update anything.
3. Using your reviewed local public-tool resolution, set ANDROID_ADB to registered adb; set
   SUBSCRIPTION_EVIDENCE_ROOT to a NEW evidence area in YOUR workspace (outside the pinned package).
   From the preserved package hierarchy, run the pinned tools/phase9/core-subscription-android15.py
   with your resolved Python. It reads SOURCE_IDENTITY and ANDROID15-BASELINE-REFERENCE from this
   extracted package root; never overwrite those files or run from the Android17 product workspace.
   Pre/post compare APK/fourruntimepins/libnode; resolve pm path fresh; Node must be24.18.0.
   Private fixture under dev.zcode.nodepoc/cache is NEW. Core, Node and dependent libs are installed
   baseline files; no candidate bootstrap is copied into the installed runtime. TMPDIR is the short
   app cache base (not a deeply nested fixture; Core Unix socket paths must remain short).
4. Parse exact raw JSON: verdict PASS_ACTUAL_CORE_SUBSCRIPTION_PROTOCOL; checks5; Node24.18.0;
   missingDeliveryKind=-32602 AND invalidDeliveryKind=-32602; positive array exactly2, same full
   sessionId, integer eventSeq>=0 and events=[]; readMessageCount=1; naturalExit code0/signalnull.
   Wrapper/device test exit0 and actual test stderr empty. No PASS-substring gate. Preserve raw
   streams, identity, baselines, copied helper/source hash and wrapper source. On failure freeze
   attempt before retry; never overwrite or invent missing originals. No redo of closed provider
   model/EOF/SQLite tests. No build/APK/instrumentation/root/Settings/credentials/model/Service work.
5. Answer TWO bounded source questions with file:line facts only:
   Q1 Is the change exactly the required deliveryKind on automatic bridge session/subscribe, with
      persistent Core ownership unchanged? Does repeated read still resubscribe? Distinguish source
      facts, your direct Core compatibility test, and quoted Android17 product evidence. Do NOT
      claim deduplication or browser replay/cursor correctness.
   Q2 Compare actual Android17 params.type names in the raw session/event records with current
      bootstrap consumers: title payload.title, upstream transaction payload.type checks and
      network_request_status payload.type checks. List the observed field/enum facts and which
      consumer branches are NOT proved by this package. No design, production fix or network/model
      execution requested. Codex owns the resulting mapping/compatibility decision.
6. Postflight and preserve fixture, previous fixtures/runtime/host/settings. Publish ONE substantive
   result with per-entry verification, full raw records/streams, wrapper SOURCE identity, answers
   and honest NOT_TESTED; then keep Android15 frozen and wait for next pinned task. No ack-only
   package or extrapolation to Android15 model/Service/Android17 acceptance.

## Codex next instructions

Accept this scoped bridge fix after receiving independent evidence. Codex next audits actual typed
event consumers before useful command/Skill/provider composition; avoid broad event-system redesign.
Gateway/journal3/localJSONRPC2/ZCodeProtocol boundaries unchanged. User only reminds to collect the
sealed v1 package; publication is not your receipt/completion. Do not use another exchange skill.
''','documentation')
put('STATUS.md','''# Scoped continuous bridge subscription PASS

InstalledE36;runtime5/Core0.16.9/Node24.18.0/Bash5.3.20.41packaged/40installed pins;
payload4eb900732b8fa4e86b443da336fd63450bcc0237157312ddc51380eff798650a.
Production difference only subscribe parameter/comment and generated integrity metadata.
Android15 unchanged809E54FC; your directed Core5 test pending, not yet performed by you.
Typed downstream fold compatibility remains OPEN; no Root/Shizuku/new architecture.
''','notice')
names=['app/src/main/assets/zcode-runtime/bootstrap.cjs','app/src/main/assets/zcode-runtime/payload-SHA256SUMS.txt',
 'app/src/main/assets/zcode-runtime/runtime-manifest.json','app/src/main/assets/zcode-runtime/gateway.cjs',
 'app/src/main/assets/zcode-runtime/carrier-authorization.cjs','app/src/main/java/dev/alita/androidagent/zcode/runtime/ZCodeHostService.kt',
 *['tools/phase9/'+n for n in ['core-subscription-protocol-test.cjs','core-subscription-android15.py','subscription-product-acceptance.py','subscription-evidence-summary.py',Path(__file__).name]]]
for n in names:
 p=ROOT/n;copy(p,n,'test' if n.startswith('tools/') else 'source');ids[n]=hashlib.sha256(p.read_bytes()).hexdigest().upper()
put('SOURCE_IDENTITY.json',json.dumps(ids,indent=2)+'\n','contract')
for p in EV.iterdir():
 if p.is_file():copy(p,'results/'+p.name,'result')
for folder in [EV/'protocol-1792939480181341100',EV/'postflight-20261025',EV/'summary-20261025']:
 for p in folder.iterdir():
  if p.is_file():copy(p,'results/'+folder.name+'/'+p.name,'result')
for folder in RUN.iterdir():
 if folder.is_dir():
  for p in folder.iterdir():
   if p.is_file() and p.suffix in ['.json','.py','.xml']:copy(p,'results/android17/'+folder.name+'/'+p.name,'result')
spec=dict(protocolVersion=1,packageId=ID,sender='codex',recipient='zcode',scope='continuous-bridge-subscription-fix-and-directed-android15-core-protocol-check',baseline='Android17 E36 installed;Android15 frozen809E54FC',
 changeSummary='Missing bridge deliveryKind parameter corrected;actual Core schema/real product events/model/provider/reconnect/resume/cancel verified;next Android15Core5 and2source facts',
 completion='COMPLETE',missingItems=[],requiredPaths=sorted(roles),fileRoles=roles,
 dependencies=[dict(packageId='codex-provider-model1-20261025-r1',archiveSha256='76C88F5572D89B33378745E724EFC8AC32C043A247EF7CE863BD055CBD615075',requiredPaths=['SOURCE_IDENTITY.json','PRODUCT-RESULT.md','ANDROID15-BASELINE-REFERENCE.md'])])
(DOC/'exchange-subscription1-20261025-r1-spec.json').write_text(json.dumps(spec,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(packageId=ID,files=len(roles),sourceEntries=len(ids))))
