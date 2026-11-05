#!/usr/bin/env bash
# verify-phase8.sh — IMPLEMENTATION_PLAN Phase 8 acceptance (dual-track).
# Usage: bash verify-phase8.sh <adb-serial> [--try-enable] [SKIP_REGRESSION=1]
#
# Track 1 criterion: a text-only model can navigate representative standard
# Android settings screens (exercised here on the UiLab fixture + real
# Settings probes; the tree/actuation path is identical).
# Track 2 criterion: the workspace-write contract end-to-end (the eight
# product scaffold names map onto WW.* below; journal v3 additive migration;
# the /carrier/respond artifacts regression goes green).
set -u
SERIAL="${1:?usage: verify-phase8.sh <adb-serial> [--try-enable]}"
shift || true
TRY_ENABLE=0
for a in "$@"; do [ "$a" = "--try-enable" ] && TRY_ENABLE=1; done
PKG=dev.zcode.nodepoc
MAIN="$PKG/.MainActivity"
SETTINGS="$PKG/.SettingsActivity"
UILAB="$PKG/.UiLabActivity"
SVC_COMP="$PKG/.accessibility.ZcodeAccessibilityService"
ZCODE_SHA256="b1df2ef3e5bd76c4af3ecb296bc003a10d3f13191a26610bd0ba940feadad529"
WORK=$(cygpath -m "$(mktemp -d)" 2>/dev/null || mktemp -d)
ADB_CMD=$(powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:/DevTools/Resolve-Tool.ps1 -Name adb -Format Path | tr -d '\r')
export MSYS_NO_PATHCONV=1
adb() { "$ADB_CMD" -s "$SERIAL" "$@"; }
PASS=0; FAIL=0
check() { if [ "$2" = "0" ]; then PASS=$((PASS+1)); echo "PASS: $1 — $3"; else FAIL=$((FAIL+1)); echo "FAIL: $1 — $3"; fi; }
checkv() { if echo "$2" | grep -q '^OK'; then PASS=$((PASS+1)); echo "PASS: $1 — $2"; else FAIL=$((FAIL+1)); echo "FAIL: $1 — $2"; fi; }
TOKEN=""
bridge() { local sep="?"; case "$1" in *\?*) sep="&";; esac
  adb shell "curl -s --max-time 10 'http://127.0.0.1:8765$1${sep}t=$TOKEN'" 2>/dev/null | tr -d '\r'; }
wait_ready() { for _ in $(seq 1 30); do local s; s=$(bridge /status)
    if echo "$s" | grep -q '"phase":"ready"'; then return 0; fi; sleep 2; done; return 1; }
rpc_wait() { adb push "$1" /data/local/tmp/rpc8.json >/dev/null
  adb shell "curl -s --max-time ${2:-100} -X POST http://127.0.0.1:8765/rpc-wait -H 'X-Bridge-Token: $TOKEN' -H 'Content-Type: application/json' --data-binary @/data/local/tmp/rpc8.json" | tr -d '\r'; }
rpc_fire() { adb push "$1" /data/local/tmp/rpc8.json >/dev/null
  adb shell "curl -s --max-time 10 -X POST http://127.0.0.1:8765/rpc -H 'X-Bridge-Token: $TOKEN' -H 'Content-Type: application/json' --data-binary @/data/local/tmp/rpc8.json" >/dev/null; }
carrier_call() { echo "$1" > "$WORK/cc.json"; adb push "$WORK/cc.json" /data/local/tmp/cc8.json >/dev/null
  adb shell "curl -s --max-time 70 -X POST http://127.0.0.1:8765/carrier/call -H 'X-Bridge-Token: $TOKEN' -H 'Content-Type: application/json' --data-binary @/data/local/tmp/cc8.json" | tr -d '\r'; }
lab_count() { bridge "/labmocks/status" | python -c "import json,sys;d=json.load(sys.stdin);print(d['endpoints'].get('$1',{}).get('count',0))" 2>/dev/null; }
lab_body_find() { local ep="$1" sub="$2" c n r; c=$(lab_count "$ep")
  for ((n=c; n>=1 && n>c-12; n--)); do
    r=$(bridge "/labmocks/body?ep=$ep&n=$n" | python -c "import json,sys;print(json.load(sys.stdin).get('raw',''))" 2>/dev/null)
    if echo "$r" | grep -qF -- "$sub"; then echo "$r"; return 0; fi
  done; return 1; }
answer_perms() { local idle=0 ad="${1:-0}" ids id
  for _ in $(seq 1 60); do
    ids=$(bridge "/gateway/pending" | python -c "
import json,sys
try:
  d=json.load(sys.stdin); print(' '.join(p['requestId'] for p in d.get('pending',[])))
except Exception: print('')" 2>/dev/null)
    if [ -z "$(echo $ids | tr -d ' ')" ]; then idle=$((idle+1)); [ "$idle" -ge 3 ] && return 0
    else idle=0
      for id in $ids; do
        adb shell "curl -s --max-time 5 -X POST http://127.0.0.1:8765/respond -H 'X-Bridge-Token: $TOKEN' -H 'Content-Type: application/json' -d '{\"requestId\":\"$id\",\"decision\":\"allow\",\"alwaysDomain\":$ad}'" >/dev/null
      done
    fi
    sleep 0.8
  done; return 0; }
wait_final() { for _ in $(seq 1 30); do
    local r; r=$(bridge "/session/read?id=$1")
    if echo "$r" | grep -qF "$2"; then echo "$r"; return 0; fi; sleep 1.5
  done; bridge "/session/read?id=$1"; return 1; }
wsfile() { # wsfile <rel> — poll the ACTIVE workspace file (tool completion is
  # async w.r.t. the transcript needle, which can match the user message)
  for _ in $(seq 1 10); do
    local c; c=$(adb shell "run-as $PKG sh -c 'cat \"$WS/$1\" 2>/dev/null'" | tr -d '
')
    [ -n "$c" ] && { echo "$c"; return 0; }
    sleep 1.5
  done; echo ""; return 1; }
py() { python -c "$1"; }
kill_orphans() { adb shell am force-stop $PKG; sleep 2
  adb shell "run-as $PKG sh -c 'pkill -f libnode' >/dev/null 2>&1"; sleep 1; }
pull_journal() { local o="$1" ext
  for ext in "" "-wal" "-shm"; do
    adb shell "run-as $PKG sh -c 'base64 files/gateway/journal.sqlite$ext 2>/dev/null'" | tr -d '\r\n' > "$WORK/b64.tmp"
    [ -s "$WORK/b64.tmp" ] && base64 -d < "$WORK/b64.tmp" > "$WORK/$o.sqlite$ext" 2>/dev/null
    rm -f "$WORK/b64.tmp"
  done; }
devnode() { # devnode <script-rel-under-scripts> — run a node script ON DEVICE
  adb push "scripts/$1" /data/local/tmp/p8n.cjs >/dev/null
  adb shell "cat /data/local/tmp/p8n.cjs | run-as $PKG sh -c 'cat > files/p8n.cjs'"
  NODEDIR=$(adb shell pm path $PKG | head -1 | sed 's/package://; s/base.apk//; s#/$##' | tr -d '\r')
  adb shell "run-as $PKG sh -c 'cd files && LD_LIBRARY_PATH=\$PWD/runtime/lib OPENSSL_CONF=/dev/null HOME=\$PWD SPIKE_ROOT=\$PWD $NODEDIR/lib/arm64/libnode.so p8n.cjs'" 2>/dev/null | tr -d '\r'; }

echo "== 0. fresh start =="
kill_orphans
if adb shell "run-as $PKG sh -c 'ls files/gateway/journal.sqlite 2>/dev/null'" | tr -d '\r\n' | grep -q journal; then
  pull_journal j1
  PRECNT=$(py "
import sqlite3
try:
  c=sqlite3.connect('$WORK/j1.sqlite'); print(c.execute('select count(*) from operation').fetchone()[0])
except Exception as e: print('ERR '+str(e))" 2>/dev/null)
else PRECNT="no-journal"; fi
echo "pre-migration operation rows: $PRECNT"
adb shell "run-as $PKG sh -c 'touch files/labmocks.enabled files/labsearch.enabled; rm -f files/carrier.disabled'"
adb shell am start -n $MAIN >/dev/null; sleep 12
TOKEN=$(adb shell "run-as $PKG cat files/runtime/bridge-token" | tr -d '\r\n')
wait_ready; check "0.1 bridge ready" $? "$(bridge /status | head -c 80)"
WS=$(bridge /status | python -c "import json,sys;print(json.load(sys.stdin).get('workspace',''))" 2>/dev/null)

echo "== V0 precondition (V0.5 is the hard gate; exit 2 on failure) =="
SDK=$(adb shell getprop ro.build.version.sdk | tr -d '\r')
[ "$SDK" -ge 33 ]; check "V0.1 device SDK ≥ 33" $? "sdk=$SDK"
LOCALE=$(adb shell "getprop persist.sys.locale" | tr -d '\r'); [ -n "$LOCALE" ]; check "V0.2 locale recorded" $? "locale=$LOCALE"
adb shell "am start -a android.settings.SETTINGS" >/dev/null 2>&1; sleep 2
FOCUS0=$(adb shell "dumpsys window 2>/dev/null | grep -m1 mCurrentFocus" | tr -d '\r')
echo "$FOCUS0" | grep -q "com.android.settings"; check "V0.3 Settings launches (focus)" $? "${FOCUS0:0:80}"
adb shell "am force-stop com.android.settings" >/dev/null 2>&1; sleep 1
# HyperOS (measured): `dumpsys accessibility` does not list installed services
# by name — the package manager's registration is the declaration assertion
DECL=$(adb shell "dumpsys package $PKG 2>/dev/null | grep -c 'ZcodeAccessibilityService'" | tr -d '\r')
[ "$DECL" -ge 1 ]; check "V0.4 service declared (dumpsys package)" $? "matches=$DECL"
ENABLED_LIST=$(adb shell "settings get secure enabled_accessibility_services" | tr -d '\r')
A11Y_ON=$(adb shell "settings get secure accessibility_enabled" | tr -d '\r')
echo "$ENABLED_LIST" | grep -q "$SVC_COMP" && [ "$A11Y_ON" = "1" ]
V05=$?
if [ "$V05" != "0" ] && [ "$TRY_ENABLE" = "1" ]; then
  echo "  --try-enable: scripting enablement (preserving other services)"
  # A18 (measured on THIS device too): force-stop/debug-install CLEARS our
  # component from enabled_accessibility_services — so the put must come AFTER
  # the last force-stop (kill_orphans above), and nothing may force-stop the
  # app again after the put. The bridge is already up from section 0.
  adb shell "appops set $PKG android:access_restricted_settings allow" >/dev/null 2>&1
  CUR=$(adb shell "settings get secure enabled_accessibility_services" | tr -d '\r')
  BASE_LIST="${CUR%null}"; [ -z "$BASE_LIST" ] && BASE_LIST=""
  NEW_LIST="${BASE_LIST:+$BASE_LIST:}$SVC_COMP"
  adb shell "settings put secure enabled_accessibility_services '$NEW_LIST'" >/dev/null
  adb shell "settings put secure accessibility_enabled 1" >/dev/null
  sleep 3
  ENABLED_LIST=$(adb shell "settings get secure enabled_accessibility_services" | tr -d '\r')
  A11Y_ON=$(adb shell "settings get secure accessibility_enabled" | tr -d '\r')
  echo "$ENABLED_LIST" | grep -q "$SVC_COMP" && [ "$A11Y_ON" = "1" ]; V05=$?
  if [ "$V05" != "0" ]; then
    # retry once after a foreground round-trip (some ROMs bind on resume)
    adb shell am start -n $MAIN >/dev/null; sleep 6
    CUR=$(adb shell "settings get secure enabled_accessibility_services" | tr -d '\r')
    BASE_LIST="${CUR%null}"; [ -z "$BASE_LIST" ] && BASE_LIST=""
    NEW_LIST="${BASE_LIST:+$BASE_LIST:}$SVC_COMP"
    adb shell "settings put secure enabled_accessibility_services '$NEW_LIST'" >/dev/null
    sleep 3
    ENABLED_LIST=$(adb shell "settings get secure enabled_accessibility_services" | tr -d '\r')
    A11Y_ON=$(adb shell "settings get secure accessibility_enabled" | tr -d '\r')
    echo "$ENABLED_LIST" | grep -q "$SVC_COMP" && [ "$A11Y_ON" = "1" ]; V05=$?
  fi
fi
if [ "$V05" != "0" ]; then
  echo "FAIL: V0.5 accessibility service NOT enabled — enable it in Settings › Accessibility"
  echo "      (if greyed out: App info → ⋮ → Allow restricted settings), or rerun with --try-enable"
  echo "RESULT: PASS=$PASS FAIL=$((FAIL+1)) (blocked at V0.5; device state preserved)"
  exit 2
fi
check "V0.5 service enabled (hard gate)" 0 "list=${ENABLED_LIST:0:70}"
printf '%s\n%s\n' "$ENABLED_LIST" "$A11Y_ON" > "$WORK/baseline-a11y.txt"
for _ in $(seq 1 15); do
  CAP=$(bridge /capabilities 2>/dev/null)
  echo "$CAP" | grep -q '"ui.accessibility".*AVAILABLE' && break
  sleep 2
done
echo "$CAP" | grep -q '"ui.accessibility".*AVAILABLE'; check "V0.6 /capabilities ui.accessibility AVAILABLE" $? "$(echo "$CAP" | head -c 60)"

echo "== V1 visibility and dispatch surface =="
SHA=$(adb shell "run-as $PKG sh -c 'sha256sum files/runtime/zcode.cjs'" | tr -d '\r' | awk '{print $1}')
[ "$SHA" = "$ZCODE_SHA256" ]; check "V1.1 zcode.cjs sha unchanged (zero patch)" $? "${SHA:0:16}"
TOOLSJ=$(bridge /carrier/tools)
V12=$(echo "$TOOLSJ" | python -c "
import json,sys
d=json.load(sys.stdin)
ids=sorted((t.get('toolId') or t.get('name') or '') for t in d.get('tools',[]))
need=['ui_back','ui_click','ui_dump','ui_find','ui_long_press','ui_scroll','ui_type','ui_wait',
      'workspace_file_create','workspace_file_delete','workspace_file_append','workspace_file_overwrite']
missing=[n for n in need if n not in ids]
print('OK %d tools (all 12 host tools present)'%len(ids) if not missing else 'ERR missing=%s'%missing)" 2>/dev/null)
checkv "V1.2 /carrier/tools carries the 8 ui_* + 4 workspace_file_* tools" "$V12"
V13=$(echo "$TOOLSJ" | python -c "
import json,sys
d=json.load(sys.stdin)
ui=[t for t in d.get('tools',[]) if (t.get('toolId') or t.get('name','')).startswith('ui_')]
ro={ (t.get('toolId') or t.get('name')): t.get('readOnly') for t in ui }
expect_read={'ui_dump','ui_find','ui_wait'}
ok=all((v is True) == (k in expect_read) for k,v in ro.items())
print('OK readOnly map correct (%d tools)'%len(ro) if ok and len(ro)==8 else 'ERR %s'%ro)" 2>/dev/null)
checkv "V1.3 readOnly flags (dump/find/wait true; actuation false)" "$V13"
STJ=$(bridge /status)
V14=$(echo "$STJ" | python -c "
import json,sys
d=json.load(sys.stdin)
c=d.get('carrier')
fields=['workerPolls','workerCallsAnswered','inlineCalls','lastCallId','lastCallTool','workerRegistered','queueDepth']
ok=c and all(f in c for f in fields) and 'carrierQueue' not in d
print('OK seven counters; queue args suppressed (A17)' if ok else 'ERR %s'%json.dumps(c))" 2>/dev/null)
checkv "V1.4 /status.carrier seven-field projection (A17)" "$V14"

echo "== V2 semantic tree (UiLab fixture) =="
adb shell am start -n $UILAB >/dev/null; sleep 3
D1=$(carrier_call '{"toolId":"ui_dump","arguments":{"detail":"compact"}}')
V21=$(echo "$D1" | python -c "
import json,sys
d=json.load(sys.stdin)
sc=d.get('structuredContent') or {}
t=d.get('text','')
hdr=all(h in t for h in ['Snapshot: g','App: ','Screen: ','Win: #'])
print('OK treeId=%s nodes=%d'%(sc.get('treeId'), len(sc.get('nodes',[]))) if hdr and sc.get('treeId') else 'ERR '+t[:120])" 2>/dev/null)
checkv "V2.1 dump header set + envelope" "$V21"
V22=$(echo "$D1" | python -c "
import json,sys;d=json.load(sys.stdin);t=d.get('structuredContent',{}).get('treeId','')
print('OK starts at g1' if t=='g1' else 'ERR treeId=%s (must be g1, A19)'%t)" 2>/dev/null)
checkv "V2.2 generation starts at g1 (g0 sentinel, A19)" "$V22"
D1T=$(echo "$D1" | python -c "import json,sys;print(json.load(sys.stdin).get('text',''))" 2>/dev/null)
echo "$D1T" | grep -qi "increment"; check "V2.3 tree contains the Increment button (case-insensitive)" $? "$(echo "$D1T" | grep -im1 increment | head -c 60)"
echo "$D1T" | grep -q "Lab switch"; check "V2.4 tree contains the switch node" $? ""
V25=$(echo "$D1T" | python -c "
import sys
t=sys.stdin.read()
print('OK bytes=%d <= 20480'%len(t.encode()) if len(t.encode())<=20480 else 'ERR bytes=%d'%len(t.encode()))" 2>/dev/null)
checkv "V2.5 rendered text within the 20 KiB budget" "$V25"
D2=$(carrier_call '{"toolId":"ui_dump","arguments":{}}')
V26=$(echo "$D2" | python -c "
import json,sys
a=json.load(sys.stdin).get('structuredContent',{})
print('OK idempotent (same treeId)' if a.get('treeId')=='g1' else 'ERR treeId=%s'%a.get('treeId'))" 2>/dev/null)
checkv "V2.6 identical tree reuses the generation" "$V26"
DC=$(carrier_call '{"toolId":"ui_dump","arguments":{"maxNodes":400}}')
V27=$(echo "$DC" | python -c "
import json,sys
d=json.load(sys.stdin); sc=d.get('structuredContent') or {}
n=len(sc.get('nodes',[]))
print('OK clamped=true nodes=%d'%n if sc.get('clamped') is True and n<=300 else 'ERR clamped=%s nodes=%d'%(sc.get('clamped'),n))" 2>/dev/null)
checkv "V2.7 maxNodes=400 accept-and-clamp to 300 (A14/V2.3b)" "$V27"
DF=$(carrier_call '{"toolId":"ui_find","arguments":{"text":"Increment"}}')
V28=$(echo "$DF" | python -c "
import json,sys
d=json.load(sys.stdin); sc=d.get('structuredContent') or {}
m=sc.get('matches') if 'matches' in sc else d.get('matches')
print('OK found node %s'%(sc.get('nodeId') or (m and m[0].get('id'))) if d.get('ok') else 'ERR '+json.dumps(d)[:140])" 2>/dev/null)
checkv "V2.8 ui_find matches by text" "$V28"
DZ=$(carrier_call '{"toolId":"ui_find","arguments":{"text":"ZZZNOSUCH"}}')
V29=$(echo "$DZ" | python -c "
import json,sys
d=json.load(sys.stdin); sc=d.get('structuredContent') or {}
e=(d.get('error') or sc.get('error') or {})
sn=(sc.get('snapshot') or {}).get('nodes', [])
print('OK ui_not_found + snapshot(%d nodes)'%len(sn) if e.get('code')=='ui_not_found' and sn else 'ERR '+json.dumps(d)[:140])" 2>/dev/null)
checkv "V2.9 zero-match ui_find → ui_not_found + snapshot (A15/V2.4b)" "$V29"

echo "== V3 action + verification matrix (UiLab) =="
C1=$(carrier_call '{"toolId":"ui_click","arguments":{"text":"Increment","timeoutMs":5000}}')
V31=$(echo "$C1" | python -c "
import json,sys
d=json.load(sys.stdin); sc=d.get('structuredContent') or {}
print('OK performed=%s verified=%s method=%s'%(sc.get('performed'),sc.get('verified'),sc.get('method')) if d.get('ok') and sc.get('verified') else 'ERR '+json.dumps(d)[:160])" 2>/dev/null)
checkv "V3.1 ui_click Increment (selector path)" "$V31"
sleep 1
D3=$(carrier_call '{"toolId":"ui_dump","arguments":{}}')
V32=$(echo "$D3" | python -c "
import json,sys
t=json.load(sys.stdin).get('text','')
print('OK counter advanced' if 'count=1' in t else 'ERR no count=1 in tree: '+[l for l in t.split(chr(10)) if 'count' in l][:1].__str__())" 2>/dev/null)
checkv "V3.2 click verified in the tree (count=1)" "$V32"
T1=$(carrier_call '{"toolId":"ui_type","arguments":{"role":"Edit","text":"hello phase8"}}')
V33=$(echo "$T1" | python -c "
import json,sys
d=json.load(sys.stdin); sc=d.get('structuredContent') or {}
print('OK verified=%s observed=%r'%(sc.get('verified'),sc.get('observed')) if d.get('ok') else 'ERR '+json.dumps(d)[:160])" 2>/dev/null)
checkv "V3.3 ui_type into the Edit node (SET_TEXT)" "$V33"
B1=$(carrier_call '{"toolId":"ui_back","arguments":{}}')
V34=$(echo "$B1" | python -c "
import json,sys
d=json.load(sys.stdin); sc=d.get('structuredContent') or {}
print('OK verified=%s evidence=%s'%(sc.get('verified'),sc.get('evidence')) if d.get('ok') else 'ERR '+json.dumps(d)[:160])" 2>/dev/null)
checkv "V3.4 ui_back leaves the screen (window change)" "$V34"

echo "== V4 stale + failure surface =="
S1=$(carrier_call '{"toolId":"ui_click","arguments":{"treeId":"g0","nodeId":"#1"}}')
V41=$(echo "$S1" | python -c "
import json,sys
d=json.load(sys.stdin); e=(d.get('error') or (d.get('structuredContent') or {}).get('error') or {})
print('OK deterministic g0 refusal' if e.get('code')=='ui_stale_node' else 'ERR '+json.dumps(d)[:160])" 2>/dev/null)
checkv "V4.1 treeId g0 → ui_stale_node (A19/V5.3)" "$V41"
UIS=$(bridge /ui/status)
V42=$(echo "$UIS" | python -c "
import json,sys
d=json.load(sys.stdin)
print('OK worker registered, lab=%s'%d.get('lab') if d.get('workerRegistered') else 'ERR '+json.dumps(d))" 2>/dev/null)
checkv "V4.2 /ui/status workerRegistered" "$V42"

echo "== V5 gateway + ui_action journal =="
cat > "$WORK/cr5.json" <<EOF
{"method":"session/create","params":{"workspace":{"workspacePath":"$WS","workspaceKey":"$(basename "$WS")"},"thoughtLevel":"high"},"timeoutMs":30000}
EOF
RPC5=$(rpc_wait "$WORK/cr5.json")
SID5=$(echo "$RPC5" | python -c "import json,sys;print(json.load(sys.stdin).get('result',{}).get('session',{}).get('sessionId',''))" 2>/dev/null)
adb shell am start -n $UILAB >/dev/null; sleep 3
cat > "$WORK/s5c.json" <<EOF
{"id":809,"method":"session/send","params":{"sessionId":"$SID5","content":"USE:raw:mcp__android-host__ui_click:{\"text\":\"Increment\"}"}}
EOF
rpc_fire "$WORK/s5c.json"
answer_perms 0 >/dev/null
sleep 3
J=$(bridge "/gateway/journal?limit=200")
V51=$(echo "$J" | python -c "
import json,sys
d=json.load(sys.stdin)
rows=[o for o in d.get('operations',[]) if (o.get('tool') or '').endswith('__ui_click') and o.get('risk')=='PRIVILEGED']
print('OK %d ui_click PRIVILEGED rows'%len(rows) if rows else 'ERR no ui_click rows')" 2>/dev/null)
checkv "V5.1 ui_click classified PRIVILEGED in the journal" "$V51"
UIJ=$(bridge "/gateway/ui?limit=50")
V52=$(echo "$UIJ" | python -c "
import json,sys
d=json.load(sys.stdin)
rows=d.get('ui_actions',[])
clk=[r for r in rows if (r.get('action') or '')=='click' and r.get('result')=='ok']
print('OK %d ui_action rows (%d ok clicks)'%(len(rows),len(clk)) if clk else 'ERR '+json.dumps(rows[:1])[:160])" 2>/dev/null)
checkv "V5.2 ui_action rows via /gateway/ui (op_id claim)" "$V52"
echo "== WW track 2: workspace-write end-to-end (model path) =="
adb shell "run-as $PKG sh -c 'mkdir -p \"$WS/p8w\"'" >/dev/null
WSKEY=$(basename "$WS")
cat > "$WORK/cr.json" <<EOF
{"method":"session/create","params":{"workspace":{"workspacePath":"$WS","workspaceKey":"$WSKEY"},"thoughtLevel":"high"},"timeoutMs":30000}
EOF
RPC1=$(rpc_wait "$WORK/cr.json")
SID=$(echo "$RPC1" | python -c "import json,sys;print(json.load(sys.stdin).get('result',{}).get('session',{}).get('sessionId',''))" 2>/dev/null)
[ -n "$SID" ]; check "WW.0 session created" $? "sid=$SID"
adb shell "run-as $PKG sh -c 'rm -f \"$WS/p8w/a.txt\" 2>/dev/null; true'" >/dev/null

cat > "$WORK/s1.json" <<EOF
{"id":801,"method":"session/send","params":{"sessionId":"$SID","content":"USE:raw:mcp__android-host__workspace_file_create:{\"path\":\"p8w/a.txt\",\"content\":\"phase8 create\",\"create_parents\":true}"}}
EOF
rpc_fire "$WORK/s1.json"; answer_perms 0 >/dev/null; sleep 3
F1=$(wsfile "p8w/a.txt")
[ "$F1" = "phase8 create" ]; check "WW.c1 model-path create: file on disk in the ACTIVE workspace" $? "content=${F1:0:40}"
VW1=$(bridge "/gateway/writes?limit=20" | python -c "
import json,sys
d=json.load(sys.stdin)
rows=[t for t in d.get('write_txns',[]) if (t.get('target_rel') or '')=='p8w/a.txt']
comp=[t for t in rows if t.get('state')=='completed' and t.get('mutation_kind')=='create']
print('OK write_txn completed create (%d rows)'%len(rows) if comp else 'ERR '+json.dumps(rows[:1])[:160])" 2>/dev/null)
checkv "WW.c1 write_txn lifecycle (intent->completed)" "$VW1"

cat > "$WORK/s2.json" <<EOF
{"id":802,"method":"session/send","params":{"sessionId":"$SID","content":"USE:raw:mcp__android-host__workspace_file_overwrite:{\"path\":\"p8w/a.txt\",\"content\":\"phase8 overwrite\"}"}}
EOF
rpc_fire "$WORK/s2.json"; answer_perms 0 >/dev/null; sleep 3
F2=$(wsfile "p8w/a.txt")
[ "$F2" = "phase8 overwrite" ]; check "WW.c2 overwrite (upsert + backup)" $? "content=${F2:0:40}"
VW2=$(bridge "/gateway/writes?limit=20" | python -c "
import json,sys
d=json.load(sys.stdin)
rows=[t for t in d.get('write_txns',[]) if (t.get('target_rel') or '')=='p8w/a.txt' and t.get('state')=='completed' and t.get('mutation_kind')=='overwrite']
print('OK reversible=%s backup=%s'%(bool(rows and rows[0].get('backup_path')), bool(rows and rows[0].get('backup_sha256'))) if rows else 'ERR no overwrite txn')" 2>/dev/null)
checkv "WW.c2 pre-image backup recorded (R1/inline T2)" "$VW2"

OPID=""
for _ in $(seq 1 10); do
  OPID=$(bridge "/gateway/journal?limit=50" | python -c "
import json,sys
d=json.load(sys.stdin)
rows=[o for o in d.get('operations',[]) if (o.get('tool') or '').endswith('__workspace_file_overwrite') and o.get('result')=='ok']
print(rows[0]['id'] if rows else '')" 2>/dev/null)
  [ -n "$OPID" ] && break
  sleep 2
done
# NB: the inner double quotes MUST be backslash-escaped — unescaped, they
# close the outer quoting and the device receives a malformed body {id":N}
RB=$(adb shell "curl -s --max-time 20 -X POST http://127.0.0.1:8765/gateway/rollback -H 'X-Bridge-Token: $TOKEN' -H 'Content-Type: application/json' -d '{\"id\":$OPID}'" | tr -d '\r')
echo "DEBUG-RB: OPID=[$OPID] RB=[$RB]"
VW3=$(echo "$RB" | python -c "
import json,sys
d=json.load(sys.stdin)
print('OK rollback op %s'%d.get('operation') if d.get('ok') else 'ERR '+json.dumps(d)[:160])" 2>/dev/null)
checkv "WW.r rollback protocol (§4 eleven steps)" "$VW3"
F4=$(wsfile "p8w/a.txt")
[ "$F4" = "phase8 create" ]; check "WW.r rollback restored the pre-image" $? "content=$F4"

cat > "$WORK/s3.json" <<EOF
{"id":803,"method":"session/send","params":{"sessionId":"$SID","content":"USE:raw:mcp__android-host__workspace_file_append:{\"path\":\"p8w/a.txt\",\"content\":\"+append\"}"}}
EOF
rpc_fire "$WORK/s3.json"; answer_perms 0 >/dev/null; sleep 3
F3=$(wsfile "p8w/a.txt")
[ "$F3" = "phase8 create+append" ]; check "WW.c3 append semantics" $? "content=$F3"

cat > "$WORK/s5.json" <<EOF
{"id":805,"method":"session/send","params":{"sessionId":"$SID","content":"USE:raw:mcp__android-host__workspace_file_create:{\"path\":\"../../escape.txt\",\"content\":\"no\"}"}}
EOF
JBEF=$(bridge "/gateway/journal?limit=400" | python -c "import json,sys;print(len(json.load(sys.stdin).get('operations',[])))" 2>/dev/null)
rpc_fire "$WORK/s5.json"; answer_perms 0 >/dev/null; sleep 5
ESC=$(adb shell "run-as $PKG sh -c 'ls files/escape.txt 2>/dev/null'" | tr -d '
')
JAFT=$(bridge "/gateway/journal?limit=400" | python -c "import json,sys;print(len(json.load(sys.stdin).get('operations',[])))" 2>/dev/null)
[ -z "$ESC" ]; check "WW.t traversal refused, nothing written outside" $? "escape.txt absent; journal $JBEF->$JAFT"

cat > "$WORK/s6.json" <<EOF
{"id":806,"method":"session/send","params":{"sessionId":"$SID","content":"USE:raw:mcp__android-host__workspace_file_delete:{\"path\":\"p8w/a.txt\"}"}}
EOF
rpc_fire "$WORK/s6.json"; answer_perms 0 >/dev/null; sleep 4
GONE=$(adb shell "run-as $PKG sh -c 'ls \"$WS/p8w/a.txt\" 2>/dev/null'" | tr -d '
')
[ -z "$GONE" ]; check "WW.d delete" $? ""

GONE=$(adb shell "run-as $PKG sh -c 'ls files/workspaces/verify8/p8w/a.txt 2>/dev/null'" | tr -d '\r')
[ -z "$GONE" ]; check "WW.d delete" $? ""
echo "== WW migration + on-device unit suites =="
pull_journal j2
VWM=$(py "
import sqlite3
try:
  c=sqlite3.connect('$WORK/j2.sqlite')
  uv=c.execute('pragma user_version').fetchone()[0]
  n=c.execute('select count(*) from operation').fetchone()[0]
  wt=c.execute('select count(*) from write_txn').fetchone()[0]
  ua=c.execute('select count(*) from ui_action').fetchone()[0]
  pre=$([ "$PRECNT" = "no-journal" ] && echo 0 || echo "$PRECNT")
  print('OK user_version=%s operation=%d (pre=%d preserved) write_txn=%d ui_action=%d'%(uv,n,pre,wt,ua) if uv==3 and n>=pre else 'ERR uv=%s n=%s pre=%s'%(uv,n,pre))
except Exception as e: print('ERR '+str(e))" 2>/dev/null)
checkv "WW.m journal v3 additive migration (rows preserved)" "$VWM"
U1=$(devnode wws-unittest.cjs 2>/dev/null | tail -1)
echo "$U1" | grep -q "FAIL=0"; check "WW.u on-device wws-unittest (lifecycle suite)" $? "$U1"
U2=$(devnode web-search-unittest.cjs 2>/dev/null | tail -1)
echo "$U2" | grep -q "FAIL=0"; check "WW.ws on-device web-search-unittest (phase7 regression)" $? "$U2"
U3=$(devnode carrier-artifacts-check.cjs 2>/dev/null | tail -1)
echo "$U3" | grep -q "FAIL=0"; check "WW.a carrier artifacts regression GREEN (receiving-product fix)" $? "$U3"
U4=$(devnode gateway-unittest.cjs 2>/dev/null | tail -1)
echo "$U4" | grep -q "FAIL=0"; check "WW.g on-device gateway-unittest (phase4 suite)" $? "$U4"

echo "== V7 cleanup (restore device posture) =="
adb shell "run-as $PKG sh -c 'rm -f files/labmocks.enabled files/labsearch.enabled files/uilab.enabled'"
adb shell "run-as $PKG sh -c 'rm -rf \"$WS/p8w\"'"
BASE_LIST=$(sed -n 1p "$WORK/baseline-a11y.txt"); BASE_ON=$(sed -n 2p "$WORK/baseline-a11y.txt")
if [ "$BASE_LIST" = "null" ]; then adb shell "settings delete secure enabled_accessibility_services" >/dev/null
else adb shell "settings put secure enabled_accessibility_services \"$BASE_LIST\"" >/dev/null; fi
adb shell "settings put secure accessibility_enabled $BASE_ON" >/dev/null
echo "a11y posture restored (list kept our component only while running)"

if [ "${SKIP_REGRESSION:-0}" != "1" ]; then
  echo "== R regression: phase 4/5/6/7 suites =="
  # refresh the phase-4 unit script the older suite shells out to (its on-device
  # copy predates the canonical-containment classify fix and fails 1 check)
  adb push scripts/gateway-unittest.cjs /data/local/tmp/gu8.cjs >/dev/null
  adb shell "cat /data/local/tmp/gu8.cjs | run-as $PKG sh -c 'cat > files/gu.cjs'"
  for s in verify-phase4.sh verify-phase5.sh verify-phase6.sh verify-phase7.sh; do
    OUT=$(bash "scripts/$s" "$SERIAL" 2>&1 | tail -2)
    echo "$OUT" | grep -q "FAIL=0"; check "R $s" $? "$(echo "$OUT" | grep RESULT | head -1)"
  done
fi

echo ""
echo "RESULT: PASS=$PASS FAIL=$FAIL"
[ "$FAIL" = "0" ] && exit 0 || exit 1
