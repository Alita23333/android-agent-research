// carrier-artifacts-check.cjs — bridge-level regression test for the
// AndroidToolResult artifacts pass-through (receiving-product feedback
// 2026-09-29: runtime3 dropped `artifacts` in /carrier/respond, forcing every
// downstream product to carry a local boundary patch).
//
// What it proves, against a RUNNING bridge (device-side, APK-owned node):
//   1. /carrier/register exposes a worker tool through /carrier/tools;
//   2. /carrier/call for an Android-dispatcher tool queues for the worker
//      (inline host tools like web_search are NOT touched);
//   3. /carrier/next hands the pending call to the worker;
//   4. /carrier/respond carrying {text, structuredContent, artifacts} delivers
//      ALL THREE fields back on the original /carrier/call response — the
//      exact boundary the runtime3 bug dropped;
//   5. /carrier/register with [] unregisters (cleanup, no tool pollution).
//
// Run (same shape as verify-phase7.sh's web-search-unittest scheduling):
//   adb push scripts/carrier-artifacts-check.cjs /data/local/tmp/cac.cjs
//   adb shell "cat /data/local/tmp/cac.cjs | run-as $PKG sh -c 'cat > files/cac.cjs'"
//   adb shell "run-as $PKG sh -c 'cd files && LD_LIBRARY_PATH=\$PWD/runtime/lib \
//     OPENSSL_CONF=/dev/null HOME=\$PWD SPIKE_ROOT=\$PWD \
//     $NODEDIR/lib/arm64/libnode.so cac.cjs'"
// Exit 0 + "RESULT: PASS=n FAIL=0" is green. No zcode core / model involved.
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");

function discoverEndpoint() {
  try {
    const f = JSON.parse(fs.readFileSync(path.join(process.env.SPIKE_ROOT || process.cwd(), "runtime", "carrier", "endpoint.json"), "utf8"));
    if (f && Number(f.port) > 0 && typeof f.token === "string") {
      return { port: Number(f.port), token: f.token };
    }
  } catch {}
  return { port: Number(process.env.SPIKE_HTTP_PORT || 8765), token: process.env.BRIDGE_TOKEN || "" };
}

const EP = discoverEndpoint();
let PASS = 0, FAIL = 0;
function check(name, ok, detail) {
  if (ok) { PASS++; console.log("OK   " + name); }
  else { FAIL++; console.log("FAIL " + name + (detail ? " — " + detail : "")); }
}

function bridge(method, p, body) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : null;
    const req = http.request({
      host: "127.0.0.1", port: EP.port, method, path: p + "?t=" + EP.token,
      headers: {
        "X-Bridge-Token": EP.token,
        ...(data ? { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(data) } : {}),
      },
      timeout: 12000,
    }, (res) => {
      let buf = "";
      res.on("data", (c) => (buf += c));
      res.on("end", () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(buf || "{}") }); }
        catch { resolve({ status: res.statusCode, body: { raw: buf } }); }
      });
    });
    req.on("error", reject);
    req.on("timeout", () => { req.destroy(new Error("bridge request timeout")); });
    if (data) req.write(data);
    req.end();
  });
}

const HARD_DEADLINE = setTimeout(() => {
  console.log("RESULT: PASS=" + PASS + " FAIL=" + (FAIL + 1) + " (hard deadline — a bridge call never settled)");
  process.exit(1);
}, 15000);
HARD_DEADLINE.unref();

(async () => {
  // 1. register a probe tool
  const reg = await bridge("POST", "/carrier/register", {
    tools: [{ toolId: "artifacts_probe", description: "regression probe", readOnly: true }],
  });
  check("register probe tool", reg.status === 200 && reg.body.ok === true, JSON.stringify(reg.body).slice(0, 120));

  const tools = await bridge("GET", "/carrier/tools");
  const ids = (tools.body.tools || []).map((t) => t.toolId || t.name);
  check("probe visible in /carrier/tools", ids.includes("artifacts_probe"), "tools=" + JSON.stringify(ids));

  // 2-4. the round trip: call (queued for worker) -> next -> respond with artifacts
  const callP = bridge("POST", "/carrier/call", { toolId: "artifacts_probe", arguments: { x: 1 } })
    .catch((e) => ({ status: 0, body: { raw: String(e) } }));

  const next = await bridge("GET", "/carrier/next").catch((e) => ({ status: 0, body: { raw: String(e) } }));
  check("worker receives call via /carrier/next",
    next.status === 200 && next.body && next.body.toolId === "artifacts_probe" && typeof next.body.callId === "string",
    JSON.stringify(next.body).slice(0, 120));

  const ARTIFACTS = [{ id: "regression-probe", version: 1 }, { id: "second", version: 3 }];
  const resp = await bridge("POST", "/carrier/respond", {
    callId: next.body && next.body.callId, ok: true,
    text: "probe text", structuredContent: { probe: 1 }, artifacts: ARTIFACTS,
  }).catch((e) => ({ status: 0, body: { raw: String(e) } }));
  check("respond accepted", resp.status === 200 && resp.body.ok === true, JSON.stringify(resp.body).slice(0, 120));

  const call = await callP;
  const c = call.body || {};
  check("call response status/body ok", call.status === 200 && c.ok === true, JSON.stringify(c).slice(0, 160));
  check("call response text pass-through", c.text === "probe text", JSON.stringify(c.text));
  check("call response structuredContent pass-through", c.structuredContent && c.structuredContent.probe === 1, JSON.stringify(c.structuredContent));
  check("call response ARTIFACTS pass-through (the runtime3 bug)",
    Array.isArray(c.artifacts) && c.artifacts.length === 2 && c.artifacts[0].id === "regression-probe" && c.artifacts[1].version === 3,
    "artifacts=" + JSON.stringify(c.artifacts));

  // 5. cleanup — no tool pollution for the rest of the run
  const unreg = await bridge("POST", "/carrier/register", { tools: [] });
  const tools2 = await bridge("GET", "/carrier/tools");
  const ids2 = (tools2.body.tools || []).map((t) => t.toolId || t.name);
  check("unregister cleans up /carrier/tools", unreg.status === 200 && !ids2.includes("artifacts_probe"), "tools=" + JSON.stringify(ids2));

  console.log("RESULT: PASS=" + PASS + " FAIL=" + FAIL);
  process.exit(FAIL === 0 ? 0 : 1);
})().catch((e) => {
  console.log("RESULT: PASS=" + PASS + " FAIL=" + (FAIL + 1) + " (fatal: " + e + ")");
  process.exit(1);
});
