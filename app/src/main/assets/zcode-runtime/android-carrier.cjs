// android-carrier.cjs — PRODUCTION model-visible Android tool carrier.
// Spawned by the ZCode Agent Core as an MCP stdio server (user-config
// mcp.servers, kill-switch compatible — measured 2026-09-28). Forwards every
// host-registered Android tool to the loopback bridge, which hands execution
// to the Android host's AndroidToolDispatcher and returns AndroidToolResult.
//
// Endpoint discovery (phase7-runbook §Tool surface §3): prefer
// <runtime>/carrier/endpoint.json {port, token} written by the bootstrap at
// boot (the MCP spawn path's env pass-through was never instrumented); fall
// back to BRIDGE_TOKEN / SPIKE_HTTP_PORT from env.
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const readline = require("node:readline");

function discoverEndpoint() {
  try {
    const f = JSON.parse(fs.readFileSync(path.join(__dirname, "carrier", "endpoint.json"), "utf8"));
    if (f && Number(f.port) > 0 && typeof f.token === "string") {
      return { port: Number(f.port), token: f.token };
    }
  } catch {}
  return { port: Number(process.env.SPIKE_HTTP_PORT || 8765), token: process.env.BRIDGE_TOKEN || "" };
}

const EP = discoverEndpoint();
const PORT = EP.port;
const TOKEN = EP.token;
const CALL_TIMEOUT_MS = Number(process.env.CARRIER_CALL_TIMEOUT_MS || 120000);

function bridge(method, path, body, signal) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : null;
    const req = http.request({
      host: "127.0.0.1", port: PORT, method, path: path + "?t=" + TOKEN,
      headers: {
        "X-Bridge-Token": TOKEN,
        ...(data ? { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(data) } : {}),
      },
      timeout: CALL_TIMEOUT_MS,
    }, (res) => {
      let buf = ""; let size = 0;
      res.on("data", (c) => { size += c.length;
        if (size > 2097152) req.destroy(new Error("carrier result too large")); else buf += c; });
      res.on("end", () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(buf || "{}") }); }
        catch { resolve({ status: res.statusCode, body: { raw: buf } }); }
      });
    });
    req.on("error", reject);
    const abort = () => req.destroy(new Error("carrier cancelled"));
    signal?.addEventListener("abort", abort, {once:true});
    req.on("close", () => signal?.removeEventListener("abort", abort));
    if (signal?.aborted) { abort(); return; }
    req.on("timeout", () => { req.destroy(new Error("carrier bridge timeout")); });
    if (data) req.write(data);
    req.end();
  });
}

// --- tool surface: mirror the host's AndroidToolDefinitions ---------------
async function hostTools() {
  try {
    const r = await bridge("GET", "/carrier/tools");
    if (r.status === 200 && Array.isArray(r.body.tools)) return r.body.tools;
  } catch {}
  return [];
}

function mcpToolFromDefinition(d) {
  // Phase 8 §1.1.2: the standard MCP annotation key is readOnlyHint (the old
  // `readOnly` key normalized to `{}` — line B E11/E11b). No destructiveHint
  // (flips upstream riskLevel while changing no enforcement), no idempotentHint;
  // concurrentSafe stays false so concurrent appends are never assumed safe.
  return {
    name: d.toolId || d.name,
    description: d.description || "",
    inputSchema: d.inputSchema || { type: "object", properties: {}, additionalProperties: false },
    annotations: { readOnlyHint: d.readOnly === true },
  };
}

// --- MCP stdio server (JSON-RPC 2.0) --------------------------------------
const rl = readline.createInterface({ input: process.stdin });
const runningCalls = new Map();
function send(o) { process.stdout.write(JSON.stringify(o) + "\n"); }

rl.on("line", (line) => {
  if (!line.trim()) return;
  let m; try { m = JSON.parse(line); } catch { return; }
  if (m.id === undefined) {
    if (m.method === "notifications/cancelled") runningCalls.get(m.params?.requestId)?.abort();
    return;
  }
  const reply = (result) => send({ jsonrpc: "2.0", id: m.id, result });
  const fail = (code, message) => send({ jsonrpc: "2.0", id: m.id, error: { code, message } });

  switch (m.method) {
    case "initialize":
      reply({
        protocolVersion: "2024-11-05",
        capabilities: { tools: {} },
        serverInfo: { name: "android-host-carrier", version: "1.1.0" },
      });
      break;
    case "notifications/initialized":
      break;
    case "tools/list":
      hostTools().then((defs) => reply({ tools: defs.map(mcpToolFromDefinition) }))
        .catch((e) => fail(-32603, "carrier: tools fetch failed: " + e));
      break;
    case "tools/call": {
      const name = m.params && m.params.name;
      const args = (m.params && m.params.arguments) || {};
      const started = Date.now();
      const controller = new AbortController();
      runningCalls.set(m.id, controller);
      bridge("POST", "/carrier/call", { toolId: name, arguments: args, meta: m.params._meta }, controller.signal)
        .then((r) => {
          const b = r.body || {};
          const isError = b.ok === false || r.status >= 400;
          // AndroidToolResult mapping: structuredContent/artifacts → text + structured.
          // artifacts (ArtifactRef[]) rides inside structuredContent — MCP has no
          // top-level field for it and structuredContent is free-form JSON.
          const structured = b.artifacts
            ? { ...(b.structuredContent || {}), artifacts: b.artifacts }
            : b.structuredContent;
          const text = typeof b.text === "string" ? b.text
            : JSON.stringify(structured ?? { ok: b.ok, error: b.error });
          reply({
            content: [{ type: "text", text }],
            isError,
            ...(structured ? { structuredContent: structured } : {}),
          });
        })
        .catch((e) => reply({
          content: [{ type: "text", text: "carrier error: " + e }],
          isError: true,
        }))
        .finally(() => runningCalls.delete(m.id));
      break;
    }
    default:
      fail(-32601, "Method not found: " + m.method);
  }
});

process.on("SIGTERM", () => { for (const controller of runningCalls.values()) controller.abort(); process.exit(0); });
send({ jsonrpc: "2.0", id: "boot", result: { carrier: "android-host", pid: process.pid, port: PORT } });
