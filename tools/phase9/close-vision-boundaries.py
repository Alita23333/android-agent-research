"""Pinned upstream implementation, adapted at the existing product boundaries."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'app/src/main/assets/zcode-runtime'
p = ASSETS / 'vision-pipeline.cjs'
s = p.read_text(encoding='utf-8')
def replace(old, new):
    global s
    assert s.count(old) == 1, (old[:90], s.count(old))
    s = s.replace(old, new, 1)
replace('const crypto = require("node:crypto");', '''const crypto = require("node:crypto");
const { assertPublicEgressDestination } = require("./web-search.cjs");''')
replace('const VISION_SESSION_CAP = 30;', 'const VISION_SESSION_CAP = 20;')
replace('''    if (!c || c.enabled === false) return null;
    return c;''', '''    if (!c || c.enabled !== true || !c.providerId || !c.modelId || !c.apiKey || !c.baseUrl) return null;
    return c;''')
replace('''  const n = raw.map((v) => {
    const x = typeof v === "number" ? v : parseFloat(v);
    if (!Number.isFinite(x)) return NaN;
    return x <= 1.5 && x > 0 ? x * 1000 : x;   // a 0..1 hint scaled up
  });''', '''  const parsed = raw.map((v) => typeof v === "number" ? v :
    typeof v === "string" && /^-?\\d+(?:\\.\\d+)?$/.test(v.trim()) ? Number(v) : NaN);
  // A scale hint applies to the entire box, never independently to an edge.
  const fractional = parsed.some(x => x > 0 && x < 1) && parsed.every(x => x >= 0 && x <= 1);
  const n = parsed.map(x => fractional ? x * 1000 : x);''')
replace('''    if (!(node.clickable || node.editable || node.scrollable)) continue;''', '''    if (node.visible === false || !(node.clickable || node.editable || node.scrollable || node.longClickable || node.checkable)) continue;''')
a = s.index('function httpJson(')
b = s.index('// The lab vision mock', a)
s = s[:a] + '''async function httpJson(urlStr, body, headers, timeoutMs, options = {}) {
  const u = new URL(urlStr);
  const lab = options.lab === true && u.origin === "http://127.0.0.1:18086";
  if (u.username || u.password || u.hash || (!lab && u.protocol !== "https:")) throw new Error("vision_egress_refused");
  const check = await assertPublicEgressDestination(urlStr, lab ? { lab: true, labOrigin: u.origin } : {});
  if (!check.ok) throw new Error("vision_egress_refused");
  const addresses = check.resolved || [];
  if (options.signal?.aborted) throw new Error("vision_cancelled");
  // The audit intent must commit before request construction can emit bytes.
  options.beforeEgress?.();
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const req = (u.protocol === "https:" ? https : http).request({
      hostname: u.hostname, port: u.port || (u.protocol === "https:" ? 443 : 80),
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

''' + s[b:]
replace('''  // config first — acceptance criterion 2 (no provider ⇒ report, never hallucinate)''', '''  const allowed = new Set(Object.keys(UI_SEE_TOOL.inputSchema.properties));
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

  // config first — acceptance criterion 2 (no provider ⇒ report, never hallucinate)''')
replace('''  if (!shotMeta) { shotMeta = helpers.shotMeta(shotId) || { width: 1080, height: 2400, screenW, screenH, format: "jpeg" }; }''', '''  shotMeta = helpers.shotMeta(shotId);
  if (!shotMeta || !Number.isInteger(shotMeta.screenW) || !Number.isInteger(shotMeta.screenH) ||
      shotMeta.treeId !== treeId || shotMeta.screenW !== screenW || shotMeta.screenH !== screenH)
    return err("vision_stale_shot", "frame generation or geometry changed; capture again");
  if (bytes.length > 153600) return err("vision_image_too_large", "compressed frame exceeds budget");
  const cacheKey = crypto.createHash("sha256").update(JSON.stringify([shotId,args,cfg.providerId,cfg.modelId])).digest("hex");
  const cached = helpers.cacheGet?.(cacheKey);
  if (cached) return structuredClone(cached);''')
replace('''      { Authorization: "Bearer " + (cfg.apiKey || "") }, timeoutMs);''', '''      { Authorization: "Bearer " + cfg.apiKey }, Math.min(timeoutMs, Math.max(1, 28000 - (Date.now() - started))), {
        lab: helpers.lab === true, signal: helpers.signal,
        beforeEgress: () => helpers.journal({source:"ui.vision", session:helpers.sessionKey,
          backend_id:cfg.providerId, host:new URL(cfg.baseUrl).hostname, method:"POST", scheme:new URL(cfg.baseUrl).protocol,
          result_code:"started", notes:"shot=" + shotId}),
      });''')
replace('''    return err("vision_transport_error", String(e && e.message || e).slice(0, 160));''', '''    const code = ["vision_cancelled","vision_egress_refused","vision_response_too_large","vision_request_timeout"].includes(e?.message) ? e.message : "vision_transport_error";
    return err(code, "vision request failed (" + code + ")");''')
replace('''      "provider returned HTTP " + resp.status + ": " + resp.body.slice(0, 120));''', '''      "provider returned HTTP " + resp.status);''')
replace('''  for (const e of (parsed.elements || [])) {''', '''  if (parsed.elements !== undefined && !Array.isArray(parsed.elements)) return err("vision_bad_response", "elements must be an array");
  for (const e of (parsed.elements || [])) {''')
replace('''        : "ui_tap {x:" + corr.tap.x + ", y:" + corr.tap.y + "}",''', '''        : "ui_tap {shotId:\\"" + shotId + "\\", x:" + corr.tap.x + ", y:" + corr.tap.y + "}",''')
replace('''  return {
    ok: true, text,
    structuredContent:''', '''  const result = {
    ok: true, text,
    structuredContent:''')
replace('''  };
}

module.exports = {''', '''  };
  // Bound the entire structured result, including labels and candidate payloads.
  result.structuredContent.text = result.structuredContent.text.slice(0, 1600);
  while (Buffer.byteLength(JSON.stringify(result)) > VISION_MAX_TEXT_BYTES && result.structuredContent.elements.length) {
    result.structuredContent.elements.pop(); result.structuredContent.dropped++;
  }
  while (Buffer.byteLength(JSON.stringify(result)) > VISION_MAX_TEXT_BYTES && result.text.length) result.text = result.text.slice(0, -128);
  helpers.cachePut?.(cacheKey, structuredClone(result));
  return result;
}

module.exports = {''')
replace('''  UI_SEE_TOOL, executeSee, normalizeBbox, correlate, a11yFirstGate,''', '''  UI_SEE_TOOL, executeSee, normalizeBbox, correlate, a11yFirstGate, httpJson,''')
p.write_text(s, encoding='utf-8', newline='\n')
print('Closed vision egress, audit-intent, response-budget, frame-binding and argument boundaries.')
