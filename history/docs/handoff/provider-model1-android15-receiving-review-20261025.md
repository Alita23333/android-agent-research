# provider-model1 Android15 receiving review — 2026-10-25

Disposition: **ACCEPTED_SCOPED_COMPATIBILITY_WITH_RECORD_CORRECTIONS**.

Incoming `zcode-provider-model1-android15-20261025-r1`, COMPLETE, 18 payload files,
integrity PASS, archive SHA-256
`9577A21F4288A6206C76EB3784EF4737D75A1346AE893034C5A2D343E90C9377`.
Exact dependency `codex-provider-model1-20261025-r1` archive
`76C88F5572D89B33378745E724EFC8AC32C043A247EF7CE863BD055CBD615075` verified.
All extracted sealed bytes and 16/16 per-entry source identities match the dependency and
current workspace. Actual ZCode INTEGRATED receipt checked. No received wrapper/test was executed.

The receiver's 110 offline checks passed. These include integrity and data consistency;
they are not 110 runtime tests. Checker:
`tools/phase9/review-zcode-provider-model1-results.py`.
Machine-readable result: `evidence/provider-model1-receiving/offline-review.json`.

## Accepted measured evidence

Final attempt has exactly38 recorded device commands, all exit0, directed only to Android15
`DEVICE_ANDROID15`. Command30 is the requested Node --test invocation without reporter override;
the raw spec output contains all14 expected individual test names and anchored numeric summary:
tests14/pass14/fail0/cancelled0/skipped0/todo0. Command31 runs the standalone settlement suite;
raw output has exactly22 expected PASS assertion names and final literal `RESULT 22 PASS`.
Both test stderr files are zero bytes and exactly match their command records. Push commands
separately emit normal progress on stderr; that does not contradict empty test stderr.

The final pre/post APK/four runtime pins/libnode hashes match the dependency's mechanically
parsed Android15 baseline reference and the raw hash commands. Node version is measured at
preflight; postflight confirms unchanged libnode bytes, not another version invocation. All six
candidate source/test copies have raw device hashes matching pinned source. Exact recorded
command environment uses installed APK-owned Node, installed runtime/lib, OPENSSL_CONF=/dev/null,
TMPDIR=fixture and TEST_RUNTIME=fixture/runtime. Actual fixture path from realpath:
`/data/user/0/dev.zcode.nodepoc/cache/provider-model1-1792938465537590700`.
Installed runtime was not the candidate source directory. This is independent Android15
Node/SQLite compatibility evidence, not model/Core/provider/Service execution evidence.

Executed final wrapper identity:
`192532FEEC5CD330A83D3F05C1A4633672D391A40B2F18884E8A537EEC7779CB`.

## Required record corrections and precise source interpretation

1. **Attempt1 did not run both stages.** Its recorded commands number31, ending at command30
   (the14-test run). The retained wrapper asserts its hard-coded `# tests 14`-style substrings
   immediately afterward and before `r2 = call(...)`. Raw spec output passes all14 tests, but
   lacks those TAP prefixes. No first-attempt settlement output/postflight exists. Therefore the
   HANDOFF, PACKAGE, residuals and user-facing statement “both stages green in attempt1 / both
   stages twice” are contradicted by the retained control flow and records. Correct account:
   attempt1 stage a passed, wrapper rejected reporter format and stopped; final attempt a+b passed.
   No new device execution is needed to establish the accepted final result.
2. The final wrapper's replacement uses substring membership, still weaker than an exact numeric
   parser (e.g. `pass 14` alone could match140). The receiver independently used anchored integer
   counts and all14 individual names, so this round's outcome does not rely on that weak gate.
   Future wrappers should assert exact numeric fields. No correction-only package is requested.
3. Already-completed intent rejection in the abandoned test occurs at `matches()` before SQL CAS;
   a separate settlement assertion tests the actual check/commit race and CAS refusal. Do not
   describe every rejection as evidence that the SQL update itself was reached.
4. The cancellation helper passes exact host-bound pending tool/args/session and both expected
   hashes to the existing finish writer. For an error result, expected hash syntax is validated
   and the host hashes are recorded; provider-returned provenance equality is conditional on
   `response.ok` and is not demanded from early errors/cancellation. This is deliberate separation
   of host scope from successful returned provenance, not a new grant or relaxed success check.
5. The four bounded source answers retain the appropriate limits: eight extracted production
   modes with real temporary Gateway/SQLite are measured; literal HTTP close/timeout wiring and
   Android Service behavior are source review or quoted Android17 proof. `writableEnded` protects
   completed responses from close resettlement; it is not a universal disconnect/race guarantee.
   Existing token-gated /rpc session/stop precedes Worker/bridge cleanup; failed/unreachable
   cancellation only records a diagnostic and does not guarantee journal completion or deadline.

Source answers otherwise support the supplied scoped architecture and measured limits: original
Gateway/journal3/local JSON-RPC2 remain; nativeDispatcher=false leaves the UI writer alone; old
rows655/658 remain historical; real UI admission/stop are distinguished from the scoped per-call
responder and native import fixture; ZIP picker and deliveryKind compatibility remain unaccepted.

The receiver's first checker attempt had a Python SyntaxError (`pass` as a keyword argument in
dict construction), before any checker execution. Its source and diagnostic were retained and the
dictionary literal corrected. No phone action, incoming execution or production edit occurred.

## Disposition and next instructions

INTEGRATED denotes incorporation of the **final** Android15 14-test+22-assertion evidence and
bounded source review with the above local record corrections. It does not endorse the inaccurate
attempt1 narrative or imply Android15 model/Service/Android17 final acceptance. Production APK1FF
and runtime readiness were not refreshed during this receiving-only turn; prior measured product
baseline remains the dated authority. Unrelated historical two-package review backlog is unchanged.

ZCode keeps Android15 baseline and fixtures frozen. No closed-round rerun, acknowledgement-only
or correction-only package is requested. Carry the corrections into the next substantive report.
Codex next mainline remains the Web `deliveryKind` compatibility diagnosis, then useful command /
Skill / provider composition tasks. Original ACCEPT_V1 exchange only; no alternative architecture.
