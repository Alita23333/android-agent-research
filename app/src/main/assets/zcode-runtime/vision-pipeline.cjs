// vision-pipeline.cjs — Phase 9 W3 (runbook §2.3/§4): the bridge-INLINE vision
// interpretation tool `ui_see`. Route A (gate G4): the frame goes ONLY to the
// user-configured vision provider, and the model receives normalized text +
// elements[] — never pixels. With no provider configured the tool REFUSES
// (acceptance criterion 2) rather than hallucinating.
//
// Shapes follow the runbook: request §4.2 (OpenAI-compatible chat/completions,
// image_url data-URL), prompt §4.3, normalizer §4.4 (tolerant in, strict out,
// slack-clamp-then-reject per A6b), budgets §4.8, error taxonomy §4.6/§9.
const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");
const https = require("node:https");
const crypto = require("node:crypto");
const { assertPublicHost, assertPublicEgressDestination } = require("./web-search.cjs");

const VISION_MAX_TEXT_BYTES = 8192;      // the model-facing text/elements budget
const VISION_TIMEOUT_DEFAULT_MS = 20000; // §5.5: capture ≤3s + request 20s inside the 30s upstream clock
const VISION_TIMEOUT_MAX_MS = 25000;     // hard clamp (accept-and-clamp above 20s)
const VISION_BBOX_SLACK = 50;            // normalized units (5% screen) — clamp inside, reject outside
const VISION_TOP_N = 3;                  // candidates when ambiguous
const VISION_SESSION_CAP = 20;           // per-session ui_see calls (search sessionCap precedent)

const UI_SEE_TOOL = {
  toolId: "ui_see",
  description: "Ask the configured vision provider about the current screen (custom-drawn or accessibility-poor UI). Pixels never go to the chat model; the answer is normalized text + element boxes with tap coordinates, correlated to accessibility nodes when they exist. Prefer ui_dump/ui_click when the tree has the element — ui_see refuses with ui_vision_not_needed when the tree already addresses the region (force:true overrides). If no vision provider is configured this tool reports that limitation.",
  readOnly: true,
  inputSchema: {
    type: "object", additionalProperties: false, required: ["question"],
    properties: {
      question: { type: "string", minLength: 2, maxLength: 500 },
      mode: { type: "string", enum: ["describe", "locate", "read_text"], default: "describe" },
      detail: { type: "string", enum: ["low", "high"], default: "high" },
      region: { type: "array", items: { type: "integer" }, minItems: 4, maxItems: 4,
        description: "[l,t,r,b] normalized 0..1000 — where you are asking about; enables the a11y-first refusal before any egress" },
      shotId: { type: "string", description: "interpret this live frame instead of capturing a new one" },
      force: { type: "boolean", default: false, description: "override the a11y-first refusal" },
      maxElements: { type: "integer", minimum: 1, maximum: 40, default: 40 },
      timeoutMs: { type: "integer", minimum: 1000, maximum: 30000, default: 20000 },
    },
  },
};

// §4.3 the prompt (verbatim runbook contract)
function visionPrompt(mode) {
  return "You are a screen-interpreter attached to an Android agent. Answer ONLY with a single JSON object, no prose, no markdown fences. Shape: {\"text\":\"<one short paragraph answering the question>\",\"elements\":[{\"label\":\"<short>\",\"bbox\":[l,t,r,b]}]}. bboxes are integers normalized to 0..1000 over the full image (l<t corner first). elements only when the question asks WHERE things are; at most 20. mode=" + mode + ".";
}

function loadVisionConfig(spikeRoot) {
  try {
    const f = path.join(spikeRoot, "runtime", "vision", "vision_config.json");
    const c = JSON.parse(fs.readFileSync(f, "utf8"));
    if (!c || c.enabled !== true || !c.providerId || !c.modelId || !c.apiKey || !c.baseUrl) return null;
    return c;
  } catch { return null; }
}

// §4.4 tolerant in, strict out: accept bbox with floats/strings/0-1 scale
// hints, clamp inside ±slack, reject outside. Returns {ok, bbox} or {ok:false, code}.
function normalizeBbox(raw) {
  if (!Array.isArray(raw) || raw.length !== 4) return { ok: false, code: "vision_bad_bbox" };
  const parsed = raw.map((v) => typeof v === "number" ? v :
    typeof v === "string" && /^-?\d+(?:\.\d+)?$/.test(v.trim()) ? Number(v) : NaN);
  // A scale hint applies to the entire box, never independently to an edge.
  const fractional = parsed.some(x => x > 0 && x < 1) && parsed.every(x => x >= 0 && x <= 1);
  const n = parsed.map(x => fractional ? x * 1000 : x);
  if (n.some((x) => !Number.isFinite(x))) return { ok: false, code: "vision_bad_bbox" };
  if (n[0] >= n[2] || n[1] >= n[3]) return { ok: false, code: "vision_bad_bbox" };
  const inside = n.every((x) => x >= -VISION_BBOX_SLACK && x <= 1000 + VISION_BBOX_SLACK);
  if (!inside) return { ok: false, code: "vision_bad_bbox", raw };
  const clamped = n.map((x) => Math.max(0, Math.min(1000, Math.round(x))));
  const clampUnits = Math.max(...n.map((x, i) => Math.abs(x - clamped[i])));
  return { ok: true, bbox: clamped, clamped: clampUnits > 0, clampUnits };
}

// §5.1/§5.2: bbox → display rect → node correlation. nodes = the CURRENT
// generation's rendered structured nodes (from /ui/render); screenW/H = the
// shot's recorded screen size.
function correlate(bbox, nodes, screenW, screenH) {
  const rect = [
    Math.round(bbox[0] / 1000 * screenW), Math.round(bbox[1] / 1000 * screenH),
    Math.round(bbox[2] / 1000 * screenW), Math.round(bbox[3] / 1000 * screenH),
  ];
  const cx = Math.round((rect[0] + rect[2]) / 2), cy = Math.round((rect[1] + rect[3]) / 2);
  let best = null, bestJ = 0; const cands = [];
  for (const node of (nodes || [])) {
    const b = node.bounds;
    if (!Array.isArray(b) || b.length !== 4) continue;
    const ix = Math.max(0, Math.min(rect[2], b[2]) - Math.max(rect[0], b[0]));
    const iy = Math.max(0, Math.min(rect[3], b[3]) - Math.max(rect[1], b[1]));
    const inter = ix * iy;
    if (inter <= 0) continue;
    const union = (rect[2] - rect[0]) * (rect[3] - rect[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter;
    const j = union > 0 ? inter / union : 0;
    if (j >= 0.5) {
      cands.push({ j, node });
      if (j > bestJ) { bestJ = j; best = node; }
    }
  }
  cands.sort((a, b2) => b2.j - a.j);
  const match = cands.length === 0 ? "none" : cands.length === 1 ? "unique" : "ambiguous";
  return {
    rect, tap: { x: cx, y: cy }, match,
    matched: best ? { nodeId: "#" + best.id, viewId: best.viewId || null, role: best.role,
      label: best.text || null, jaccard: Math.round(bestJ * 10000) / 10000, bounds: best.bounds } : null,
    candidates: cands.length > 1 ? cands.slice(0, VISION_TOP_N).map((c) => ({
      nodeId: "#" + c.node.id, role: c.node.role, label: c.node.text || null, jaccard: Math.round(c.j * 10000) / 10000 })) : null,
  };
}

// §5.6 the a11y-first soft gate: does the CURRENT tree already have a visible
// actionable node intersecting the region? Evaluable only with a region.
function a11yFirstGate(region, nodes, screenW, screenH) {
  if (!region) return { gate: "unevaluated" };
  const nb = normalizeBbox(region);
  if (!nb.ok) return { gate: "invalid" };
  const r = [
    nb.bbox[0] / 1000 * screenW, nb.bbox[1] / 1000 * screenH,
    nb.bbox[2] / 1000 * screenW, nb.bbox[3] / 1000 * screenH,
  ];
  for (const node of (nodes || [])) {
    const b = node.bounds;
    if (!Array.isArray(b) || b.length !== 4) continue;
    if (node.visible === false || !(node.clickable || node.editable || node.scrollable || node.longClickable || node.checkable)) continue;
    const ix = Math.max(0, Math.min(r[2], b[2]) - Math.max(r[0], b[0]));
    const iy = Math.max(0, Math.min(r[3], b[3]) - Math.max(r[1], b[1]));
    if (ix > 0 && iy > 0) return { gate: "refuse", hit: { nodeId: "#" + node.id, role: node.role, label: node.text || null } };
  }
  return { gate: "passed" };
}

async function httpJson(urlStr, body, headers, timeoutMs, options = {}) {
  const u = new URL(urlStr);
  const lab = options.lab === true && u.origin === "http://127.0.0.1:18086";
  if (u.username || u.password || u.hash || (!lab && u.protocol !== "https:")) throw new Error("vision_egress_refused");
  const guardOptions = lab ? {lab:true,labOrigin:{host:"127.0.0.1"}} : {};
  if (!assertPublicHost(u.hostname,guardOptions).ok) throw new Error("vision_egress_refused");
  const publicAddress = address => {
    const bare = address.replace(/^\[|\]$/g, "").toLowerCase();
    const mapped = bare.match(/^::ffff:([a-f0-9]{1,4}):([a-f0-9]{1,4})$/);
    if (mapped) {
      const hi = parseInt(mapped[1],16), lo = parseInt(mapped[2],16);
      return assertPublicHost([hi>>8,hi&255,lo>>8,lo&255].join("."),{}).ok;
    }
    if (bare.includes(":") && !/^[23][a-f0-9]{3}:/.test(bare)) return false;
    return assertPublicHost(bare,guardOptions).ok;
  };
  if (!lab && require("node:net").isIP(u.hostname.replace(/^\[|\]$/g,"")) && !publicAddress(u.hostname)) throw new Error("vision_egress_refused");
  const check = await assertPublicEgressDestination(u, guardOptions);
  if (!check.ok) throw new Error("vision_egress_refused");
  const addresses = check.resolved || [];
  if (addresses.some(x=>!publicAddress(typeof x === "string" ? x : x.address)) ||
      (!addresses.length && !require("node:net").isIP(u.hostname.replace(/^\[|\]$/g,"")))) throw new Error("vision_egress_refused");
  if (options.signal?.aborted) throw new Error("vision_cancelled");
  // The audit intent must commit before request construction can emit bytes.
  options.beforeEgress?.();
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const req = (u.protocol === "https:" ? https : http).request({
      hostname: u.hostname.replace(/^\[|\]$/g,""), port: u.port || (u.protocol === "https:" ? 443 : 80),
      path: u.pathname + u.search, method: "POST",
      // Pin the already-checked resolution; TLS still validates the original hostname.
      ...(addresses.length ? { lookup: (_host, opts, cb) => {
        const values = addresses.map(x => typeof x === "string" ? {address:x, family:x.includes(":") ? 6 : 4} : x);
        if (opts?.all) cb(null, values); else cb(null, values[0].address, values[0].family);
      }} : {}),
      headers: Object.assign({ "Content-Type": "application/json", "Content-Length": Buffer.byteLength(data) }, headers),
    }, res => {
      const chunks = []; let size = 0;
      res.on("error", reject);
      res.on("data", chunk => { size += chunk.length;
        if (size > 131072) req.destroy(new Error("vision_response_too_large")); else chunks.push(chunk); });
      res.on("end", () => resolve({status: res.statusCode, body: Buffer.concat(chunks).toString("utf8")}));
    });
    const timer = setTimeout(() => req.destroy(new Error("vision_request_timeout")), timeoutMs);
    const abort = () => req.destroy(new Error("vision_cancelled"));
    options.signal?.addEventListener("abort", abort, {once:true});
    req.on("close", () => { clearTimeout(timer); options.signal?.removeEventListener("abort", abort); });
    req.on("error", reject);
    req.end(data);
  });
}

// The lab vision mock (§ line D §2): a loopback server started by the bridge
// when files/labvision.enabled exists, on 18086, answering /v1/chat/completions
// with deterministic fixtures selected by the question text.
const LABVISION_PORT = 18086;
function startLabVision(root, log) {
  const server = http.createServer((req, res) => {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      state.count++;
      let q = "";
      try {
        const j = JSON.parse(body);
        for (const p of (j.messages?.[1]?.content || [])) if (p.type === "text") q = p.text;
      } catch {}
      const fixtures = {
        default: { text: "A settings screen; the Battery Saver toggle is on the right, currently off.",
          elements: [{ label: "Battery Saver toggle", bbox: [700, 100, 950, 180] }] },
        error: { __error: "vision_backend_error", status: 500 },
        latency: { __latency: 6000 },
        increment: { text: "A lab screen with an Increment button and a switch.",
          elements: [{ label: "Increment", bbox: [40, 75, 960, 135] }] },
      };
      let fx = fixtures.default;
      if (/increment/i.test(q)) fx = fixtures.increment;
      if (/errorcase/i.test(q)) fx = fixtures.error;
      if (/latencycase/i.test(q)) fx = fixtures.latency;
      state.lastQuestion = q; state.lastBody = body;
      const reply = () => res.end(JSON.stringify({
        choices: [{ message: { content: JSON.stringify({ text: fx.text, elements: (fx.elements || []) }) } }],
      }));
      if (fx.__latency) { setTimeout(reply, fx.__latency); return; }
      if (fx.__error) { res.statusCode = fx.status; res.end(JSON.stringify({ error: { message: fx.__error } })); return; }
      reply();
    });
  });
  const state = { count: 0, lastQuestion: "", lastBody: "" };
  server.on("error", (e) => { state.listenError = String(e); log?.("labvision listen failed (resolve-and-continue): " + String(e).slice(0, 80)); });
  return new Promise((resolve) => {
    try { server.listen(LABVISION_PORT, "127.0.0.1", () => resolve({ server, state })); }
    catch (e) { state.listenError = String(e); resolve({ server, state }); }
  });
}

// ---- the INLINE execution entry (bootstrap calls this) -----------------------
// helpers: { spikeRoot, internalCall(toolId,args), readShot(shotId), renderFrame(),
//            journal(row), sessionKey, sessionCount() }
async function executeSee(call, helpers) {
  const args = call.arguments || {};
  const started = Date.now();
  const err = (code, message, extra) => ({ ok: false, text: "ui_see failed: " + code,
    structuredContent: Object.assign({ ok: false, tool: "ui_see", action: "see", performed: false,
      verified: false, error: { code, message } }, extra || {}) });

  const allowed = new Set(Object.keys(UI_SEE_TOOL.inputSchema.properties));
  if (!args || typeof args !== "object" || Array.isArray(args) || Object.keys(args).some(k => !allowed.has(k)) ||
      typeof args.question !== "string" || args.question.length < 2 || args.question.length > 500 ||
      (args.region && (!Array.isArray(args.region) || args.region.length !== 4 || !args.region.every(Number.isInteger) || !normalizeBbox(args.region).ok)) ||
      (args.mode && !["describe","locate","read_text"].includes(args.mode)) ||
      (args.detail && !["low","high"].includes(args.detail)) ||
      (args.force !== undefined && typeof args.force !== "boolean") ||
      (args.maxElements !== undefined && (!Number.isInteger(args.maxElements) || args.maxElements < 1 || args.maxElements > 40)) ||
      (args.timeoutMs !== undefined && (!Number.isInteger(args.timeoutMs) || args.timeoutMs < 1000 || args.timeoutMs > 30000)) ||
      (args.shotId !== undefined && !/^shot_[a-f0-9]{32}$/.test(args.shotId))) return err("ui_invalid_input", "invalid vision arguments");
  if (helpers.signal?.aborted) return err("vision_cancelled", "request cancelled");

  // config first — acceptance criterion 2 (no provider ⇒ report, never hallucinate)
  const cfg = helpers.config || loadVisionConfig(helpers.spikeRoot);
  if (!cfg) return err("vision_unconfigured",
    "no vision provider is configured — open the app's Settings › Vision section; the accessibility tree (ui_dump) is the only available channel");
  if (cfg.apiType && cfg.apiType !== "openai-chat-completions") {
    return err("vision_provider_unsupported", "only the OpenAI-compatible vision path is implemented (apiType=" + cfg.apiType + ")");
  }

  // per-session cost cap (search precedent)
  if (!args.shotId && (helpers.sessionCount?.() ?? 0) >= VISION_SESSION_CAP) {
    return err("vision_session_cap", "per-session vision call cap reached (" + VISION_SESSION_CAP + ")");
  }

  // fresh tree for the gate + correlation (internal dump via the worker)
  let nodes = [], treeId = null, screenW = 1080, screenH = 2400, observationEpoch = null, rotation = null;
  try {
    const frame = await helpers.renderFrame();
    if (frame && frame.render) {
      nodes = frame.render.nodes || [];
      treeId = "g" + (frame.generation ?? 0);
      observationEpoch = frame.observationEpoch; rotation = frame.rotation;
      screenW = frame.screenW || screenW; screenH = frame.screenH || screenH;
    }
  } catch { /* tree unavailable — custom-drawn case; the gate simply cannot fire */ }

  // a11y-first soft gate (§5.6) — before any capture or egress when evaluable
  if (args.region && !args.force) {
    const g = a11yFirstGate(args.region, nodes, screenW, screenH);
    if (g.gate === "refuse") {
      return err("ui_vision_not_needed",
        "the accessibility tree already addresses that region — use ui_click with nodeId " + g.hit.nodeId + " (force:true to override)",
        { gate: "refuse", hit: g.hit, treeId });
    }
  }

  // frame: reuse shotId or one internal capture
  let shotId = args.shotId || null, shotMeta = null;
  if (!shotId) {
    const cap = await helpers.internalCall("ui_screenshot", { maxLongEdge: 1080 });
    if (!cap || cap.ok === false) return err("vision_capture_failed", (cap && cap.error && cap.error.code) || "capture failed");
    shotId = cap.shotId; shotMeta = cap;
  }
  const bytes = helpers.readShot(shotId);
  if (!bytes) return err("vision_shot_missing", "shot " + shotId + " is not in the live store (it may have been pruned) — re-capture");
  shotMeta = helpers.shotMeta(shotId);
  if (!shotMeta || !Number.isInteger(shotMeta.screenW) || !Number.isInteger(shotMeta.screenH) ||
      shotMeta.treeId !== treeId || shotMeta.screenW !== screenW || shotMeta.screenH !== screenH ||
      typeof observationEpoch !== "string" || !observationEpoch || shotMeta.observationEpoch !== observationEpoch ||
      !Number.isInteger(rotation) || shotMeta.rotation !== rotation)
    return err("vision_stale_shot", "frame generation or geometry changed; capture again");
  if (bytes.length > 153600) return err("vision_image_too_large", "compressed frame exceeds budget");
  const cacheKey = crypto.createHash("sha256").update(JSON.stringify([shotId,args,cfg])).digest("hex");
  const cached = helpers.cacheGet?.(cacheKey);
  if (cached) return structuredClone(cached);
  if ((helpers.sessionCount?.() ?? 0) >= VISION_SESSION_CAP) return err("vision_session_cap", "per-session hourly network budget reached");

  // timeout accept-and-clamp
  const wantTimeout = Number(args.timeoutMs) || VISION_TIMEOUT_DEFAULT_MS;
  const timeoutMs = Math.min(wantTimeout > VISION_TIMEOUT_DEFAULT_MS ? VISION_TIMEOUT_MAX_MS : wantTimeout, VISION_TIMEOUT_MAX_MS);
  const timeoutClamped = wantTimeout > VISION_TIMEOUT_DEFAULT_MS;

  // the VLM round trip
  const b64 = bytes.toString("base64");
  const reqBody = {
    model: cfg.modelId,
    messages: [
      { role: "system", content: visionPrompt(args.mode || "describe") },
      { role: "user", content: [
        { type: "text", text: String(args.question || "") },
        { type: "image_url", image_url: { url: "data:image/" + (shotMeta.format || "jpeg") + ";base64," + b64, detail: args.detail || "high" } },
      ] },
    ],
    max_tokens: 1200, temperature: 0,
  };
  const t0 = Date.now();
  let resp;
  try {
    resp = await httpJson(cfg.baseUrl.replace(/\/$/, "") + "/chat/completions", reqBody,
      { Authorization: "Bearer " + cfg.apiKey }, Math.min(timeoutMs, Math.max(1, 28000 - (Date.now() - started))), {
        lab: helpers.lab === true, signal: helpers.signal,
        beforeEgress: () => helpers.journal({source:"ui.vision", session:helpers.sessionKey,
          backend_id:cfg.providerId, host:new URL(cfg.baseUrl).hostname, method:"POST", scheme:new URL(cfg.baseUrl).protocol,
          result_code:"started", notes:"shot=" + shotId}),
      });
  } catch (e) {
    helpers.journal({ source: "ui.vision", backend_id: cfg.providerId, host: (() => { try { return new URL(cfg.baseUrl).hostname; } catch { return null; } })(),
      result_code: "vision_transport_error", notes: "err=" + String(e && e.message).slice(0, 80) + " shot=" + shotId });
    const code = ["vision_cancelled","vision_egress_refused","vision_response_too_large","vision_request_timeout"].includes(e?.message) ? e.message : "vision_transport_error";
    return err(code, "vision request failed (" + code + ")");
  }
  const elapsedReq = Date.now() - t0;
  if (helpers.signal?.aborted) return err("vision_cancelled", "request cancelled");
  helpers.journal({ source: "ui.vision", backend_id: cfg.providerId,
    host: (() => { try { return new URL(cfg.baseUrl).hostname; } catch { return null; } })(),
    status: resp.status, bytes_in: resp.body.length, duration_ms: elapsedReq, timeout_ms: timeoutMs,
    result_code: resp.status === 200 ? "ok" : "vision_http_" + resp.status,
    notes: "shot=" + shotId + ";tree=" + (treeId || "-") + ";img_b64=" + b64.length });
  if (resp.status !== 200) {
    return err(resp.status === 401 || resp.status === 403 ? "vision_auth_failed" : "vision_backend_error",
      "provider returned HTTP " + resp.status);
  }
  const fresh = await helpers.renderFrame();
  if (!fresh || "g" + fresh.generation !== treeId || fresh.screenW !== screenW || fresh.screenH !== screenH ||
      fresh.observationEpoch !== observationEpoch || fresh.rotation !== rotation)
    return err("vision_stale_shot", "screen changed during interpretation; inspect again");

  // parse + normalize (tolerant in, strict out)
  let content = "", parsed = null, dropped = 0;
  try {
    const j = JSON.parse(resp.body);
    content = j.choices?.[0]?.message?.content || "";
    const m = content.match(/\{[\s\S]*\}/);
    parsed = m ? JSON.parse(m[0]) : null;
  } catch { parsed = null; }
  if (!parsed || typeof parsed.text !== "string") {
    return err("vision_bad_response", "the provider answer did not contain the JSON contract: " + content.slice(0, 120));
  }
  const maxEls = Math.min(Number(args.maxElements) || 40, 40);
  const elements = [];
  if (parsed.elements !== undefined && !Array.isArray(parsed.elements)) return err("vision_bad_response", "elements must be an array");
  for (const e of (parsed.elements || [])) {
    if (elements.length >= maxEls) { dropped++; continue; }
    const nb = normalizeBbox(e && e.bbox);
    if (!nb.ok) { dropped++; continue; }
    const corr = correlate(nb.bbox, nodes, shotMeta.screenW, shotMeta.screenH);
    elements.push({
      label: String((e && e.label) || "").slice(0, 80),
      bbox: nb.bbox, rect: corr.rect, clamped: nb.clamped, clampUnits: nb.clampUnits,
      tap: corr.tap, match: corr.match, matched: corr.matched, candidates: corr.candidates,
      action_hint: corr.match === "unique"
        ? "ui_click {treeId:\"" + treeId + "\", nodeId:\"" + corr.matched.nodeId + "\"}"
        : "ui_tap {shotId:\"" + shotId + "\", x:" + corr.tap.x + ", y:" + corr.tap.y + "}",
    });
  }
  let text = "Q: " + args.question + "\nA: " + parsed.text;
  if (elements.length) text += "\nelements: " + elements.map((e) =>
    e.label + " " + e.match + (e.matched ? " " + e.matched.nodeId : "") + " tap(" + e.tap.x + "," + e.tap.y + ")").join("; ");
  if (Buffer.byteLength(text) > VISION_MAX_TEXT_BYTES) text = text.slice(0, VISION_MAX_TEXT_BYTES);

  const result = {
    ok: true, text,
    structuredContent: {
      ok: true, tool: "ui_see", action: "see",
      treeId, shotId, provider: cfg.providerId, model: cfg.modelId,
      mode: args.mode || "describe", detail: args.detail || "high",
      region: args.region || null,
      text: parsed.text, elements,
      ambiguous: elements.some((e) => e.match === "ambiguous"),
      reused: !!args.shotId, dropped, gate: args.region ? (args.force ? "forced" : "passed") : "unevaluated",
      timeoutClamped, elapsedMs: Date.now() - started, error: null,
    },
  };
  // Bound the entire structured result, including labels and candidate payloads.
  const utf8Slice = (value, budget) => { let out = "";
    for (const character of value) { if (Buffer.byteLength(out + character) > budget) break; out += character; } return out; };
  result.text = utf8Slice(result.text, 2800);
  result.structuredContent.text = utf8Slice(result.structuredContent.text, 2000);
  while (Buffer.byteLength(JSON.stringify(result)) > VISION_MAX_TEXT_BYTES && result.structuredContent.elements.length) {
    result.structuredContent.elements.pop(); result.structuredContent.dropped++;
  }
  while (Buffer.byteLength(JSON.stringify(result)) > VISION_MAX_TEXT_BYTES && result.text.length) result.text = result.text.slice(0, -128);
  helpers.cachePut?.(cacheKey, structuredClone(result));
  return result;
}

module.exports = {
  UI_SEE_TOOL, executeSee, normalizeBbox, correlate, a11yFirstGate, httpJson,
  loadVisionConfig, startLabVision, visionPrompt,
  VISION_MAX_TEXT_BYTES, VISION_TIMEOUT_DEFAULT_MS, VISION_TIMEOUT_MAX_MS,
  VISION_BBOX_SLACK, VISION_SESSION_CAP, LABVISION_PORT,
};
