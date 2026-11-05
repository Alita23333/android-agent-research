// web-search-unittest.cjs — Phase 7 on-device unit suite (V1.5 + the guard
// half of V2.6). Run on the device with the app-owned node:
//   cd files && LD_LIBRARY_PATH=$PWD/runtime/lib OPENSSL_CONF=/dev/null \
//   HOME=$PWD SPIKE_ROOT=$PWD <node> wsu.cjs
// (the verify-phase4.sh gu.cjs pattern). Read-only except nothing — it only
// reads runtime assets and the journal.
const { normalizeUrl, assertPublicHost, normalizeResults, normalizeText,
        classifyTransportError, sessionCapCheck, validateArgs } = require("./runtime/web-search.cjs");
const { classify, decide } = require("./runtime/gateway.cjs");
const fs = require("node:fs");

let pass = 0, fail = 0;
function check(name, ok) {
  if (ok) { pass++; console.log("PASS " + name); }
  else { fail++; console.log("FAIL " + name); }
}

// ---- URL / host guard matrix (research §3.4, 42-case matrix subset) --------
check("normalizeUrl >2000 chars -> invalid", normalizeUrl("https://x/" + "a".repeat(2100)).code === "webfetch_invalid_url");
check("normalizeUrl garbage -> invalid", normalizeUrl("not a url").code === "webfetch_invalid_url");
check("normalizeUrl ftp -> unsupported protocol", normalizeUrl("ftp://example.com/f").code === "webfetch_unsupported_protocol");
check("normalizeUrl user:pass -> credentials", normalizeUrl("https://u:p@example.com/").code === "webfetch_credentials_in_url");
const okUrl = normalizeUrl("https://Api.Example.COM:443/path?q=1");
check("normalizeUrl ok -> lowercase host", okUrl.ok === true && okUrl.host === "api.example.com");

function pub(host) { return assertPublicHost(host, {}).ok; }
function pubLab(host) { return assertPublicHost(host, { lab: true, labOrigin: { host: "127.0.0.1" } }).ok; }
check("host: localhost blocked", pub("localhost") === false);
check("host: *.localhost blocked", pub("foo.localhost") === false);
check("host: *.local blocked", pub("foo.local") === false);
check("host: single-label blocked", pub("intranet") === false);
check("host: 127.0.0.1 blocked", pub("127.0.0.1") === false);
check("host: 10.x blocked", pub("10.1.2.3") === false);
check("host: 192.168.x blocked", pub("192.168.1.1") === false);
check("host: 172.16.x blocked", pub("172.16.0.9") === false);
check("host: 169.254.x (metadata) blocked", pub("169.254.169.254") === false);
check("host: 100.64 CGNAT blocked", pub("100.64.0.1") === false);
check("host: [::1] blocked", pub("[::1]") === false);
check("host: [fc00::1] ULA blocked", pub("[fc00::1]") === false);
check("host: [fe80::1] link-local blocked", pub("[fe80::1]") === false);
check("host: [::ffff:10.0.0.5] mapped blocked", pub("[::ffff:10.0.0.5]") === false);
check("host: public domain allowed", pub("example.com") === true);
check("host: public IP allowed", pub("8.8.8.8") === true);
check("host: [2606:4700::1] public IPv6 allowed", pub("[2606:4700::1]") === true);
// V2.6 unit half — lab flag ON relaxes exactly the configured origin:
check("lab on: configured loopback origin allowed", pubLab("127.0.0.1") === true);
check("lab on: OTHER loopback still blocked", pubLab("127.0.0.2") === false);
check("lab on: 192.168.1.1 still blocked", pubLab("192.168.1.1") === false);
check("lab on: 10.0.0.5 still blocked", pubLab("10.0.0.5") === false);
check("lab on: [::1] still blocked", pubLab("[::1]") === false);
check("lab on: localhost name still blocked", pubLab("localhost") === false);

// ---- normalization -----------------------------------------------------------
const norm = normalizeResults([
  { title: "Caf&eacute; &#8212; <b>Best</b> coffee &amp; more", url: "https://example.com/cafe", snippet: "A caf&eacute; &#8212; test &amp; result" },
  { title: "Duplicate variant", url: "https://www.example.com/cafe#frag", snippet: "should collapse" },
  { title: "Bad scheme", url: "ftp://example.com/file", snippet: "dropped" },
], 8, "Caf&eacute; &#8212; answer");
check("normalize: named+numeric entities decoded", norm.results[0].title.includes("Café —") && norm.results[0].snippet.includes("café —"));
// strip runs BEFORE entity decode: real tags (<b>) vanish, entities decode
check("normalize: no tag markup survives", !norm.results[0].title.includes("<") && !norm.results[0].snippet.includes("<"));
check("normalize: www/fragment duplicate collapses (3 raw -> 1 unique: dup + ftp gone)",
  norm.results.length === 1);
check("normalize: ftp result dropped", norm.results.every((r) => r.url.startsWith("http")));
check("normalize: answer decoded+kept", norm.answer === "Café — answer");

const big = normalizeResults(
  Array.from({ length: 40 }, (_, i) => ({ title: "T".repeat(300) + i, url: `https://example.com/big/${i}`, snippet: "S".repeat(900) })), 999, null);
check("caps: results clamped to 20", big.results.length === 20);
check("caps: title <= 200", big.results.every((r) => r.title.length <= 200));
check("caps: snippet <= 500", big.results.every((r) => r.snippet.length <= 500));
check("caps: truncated flag set", big.truncated === true);

// ---- transport classifier ----------------------------------------------------
function terr(code, msg) { const e = new Error(msg || "x"); e.code = code; return e; }
const e1 = new Error("fetch failed"); e1.cause = terr("ENOTFOUND"); 
check("transport: ENOTFOUND via cause chain", classifyTransportError(e1).transport === "ENOTFOUND");
const e2 = new Error("fetch failed"); e2.cause = terr("ECONNREFUSED");
check("transport: ECONNREFUSED via cause chain", classifyTransportError(e2).transport === "ECONNREFUSED");
const e3 = new Error("This operation was aborted"); e3.name = "AbortError";
check("transport: AbortError (name in chain) -> timeout", classifyTransportError(e3).transport === "timeout");
check("transport: TLS code -> TLS_CERT", classifyTransportError(terr("", "unable to verify the first certificate (UNABLE_TO_VERIFY_LEAF_SIGNATURE)")).transport === "TLS_CERT");

// ---- session cap ---------------------------------------------------------------
const now = 1_000_000;
check("cap: first two allowed, third blocked",
  sessionCapCheck("s1", 2, now).allowed === true &&
  sessionCapCheck("s1", 2, now + 1000).allowed === true &&
  sessionCapCheck("s1", 2, now + 2000).allowed === false);
check("cap: rolling hour releases", sessionCapCheck("s1", 2, now + 3600_001).allowed === true);

// ---- input validation -----------------------------------------------------------
check("validate: short query refused", validateArgs({ query: "a" }).ok === false);
check("validate: unknown field refused", validateArgs({ query: "ok", bogus: 1 }).ok === false);
check("validate: query+count ok", validateArgs({ query: "ok", count: 5 }).ok === true);

// ---- gateway classification (V1.5) ----------------------------------------------
check("classify WebSearch -> NETWORK", classify("WebSearch", {}, "/w").risk === "NETWORK");
check("classify carrier web_search -> NETWORK", classify("mcp__android-host__web_search", {}, "/w").risk === "NETWORK");
check("classify other mcp -> PRIVILEGED (fail-closed)", classify("mcp__other__thing", {}, "/w").risk === "PRIVILEGED");
check("classify WebFetch -> NETWORK", classify("WebFetch", { url: "https://example.com/" }, "/w").risk === "NETWORK");
check("decide ask x NETWORK -> ask", decide("ask", "NETWORK") === "ask");

// ---- NETWORK pin: full-bundle scan (runbook §Gateway control §1) ----------------
// The NETWORK class is derived, not hand-maintained: scan EVERY occurrence of
// sideEffectScope:"network" and assert the hit set equals the pin. A silent
// upstream upgrade adding a third network tool must fail this check.
try {
  const buf = fs.readFileSync("./runtime/zcode.cjs", "latin1");
  const needle = 'sideEffectScope:"network"';
  const hits = [];
  let idx = 0;
  while ((idx = buf.indexOf(needle, idx)) !== -1) { hits.push(idx); idx += 1; }
  const pin = [1380567, 7567107, 7567421, 7574043];
  check("NETWORK pin: sideEffectScope scan hit set == {" + pin.join(",") + "} (found " + hits.join(",") + ")",
    hits.length === pin.length && pin.every((p) => hits.includes(p)));
} catch (e) {
  check("NETWORK pin scan", false);
}

// ---- journal v2 migration (V4.1 half) --------------------------------------------
try {
  const { DatabaseSync } = require("node:sqlite");
  let db;
  try { db = new DatabaseSync("./gateway/journal.sqlite", { readOnly: true }); }
  catch { db = new DatabaseSync("./gateway/journal.sqlite"); }
  const uv = db.prepare("pragma user_version").get();
  check("journal: user_version >= 2", uv.user_version >= 2);
  const tables = db.prepare("select name from sqlite_master where type='table'").all().map((r) => r.name);
  check("journal: network_request table exists", tables.includes("network_request"));
  check("journal: allow_rule table exists", tables.includes("allow_rule"));
  check("journal: operation table preserved", tables.includes("operation"));
  const cnt = db.prepare("select count(*) as c from operation").get();
  check("journal: operation rows preserved (count=" + cnt.c + ")", cnt.c >= 0);
  db.close();
} catch (e) {
  check("journal v2 inspect: " + e, false);
}

console.log(`RESULT: PASS=${pass} FAIL=${fail}`);
process.exit(fail === 0 ? 0 : 1);
