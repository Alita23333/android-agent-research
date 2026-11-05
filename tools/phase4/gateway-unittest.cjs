// Phase 4 gateway unit test — runs ON DEVICE with the app-owned node against
// the real gateway.cjs module. Verifies classification, hard-confirm token
// enforcement, journal rows, and the deny/deferred paths deterministically
// (no model involved). Exit 0 = all checks pass.
const path = require("node:path");
const fs = require("node:fs");
const ROOT = process.env.SPIKE_ROOT || ".";
const { Gateway, classify, decide, HARD_CONFIRM_PACK } = require(path.join(ROOT, "runtime", "gateway.cjs"));

const g = new Gateway().init({ root: ROOT, workspace: path.join(ROOT, "workspace"), mode: "ask" });
let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log("PASS:", name, detail || ""); }
  else { fail++; console.log("FAIL:", name, detail || ""); }
}

// 1. classification
const ddCmd = { command: "dd if=/dev/zero of=/dev/block/mmcblk0test bs=1 count=1" };
check("classify dd -> CRITICAL", classify("Bash", ddCmd, "/w").risk === "CRITICAL");
check("classify mkfs -> CRITICAL", classify("Bash", { command: "mkfs.ext4 /dev/block/sda1" }, "/w").risk === "CRITICAL");
check("classify fastboot flash -> CRITICAL", classify("Bash", { command: "fastboot flash boot boot.img" }, "/w").risk === "CRITICAL");
check("classify factory reset -> CRITICAL", classify("Bash", { command: "echo wipe_data; recovery --wipe_data" }, "/w").risk === "CRITICAL");
check("classify echo -> PRIVILEGED", classify("Bash", { command: "echo hi" }, "/w").risk === "PRIVILEGED");
check("classify Write inside ws -> WRITE", classify("Write", { file_path: "/w/a.txt" }, "/w").risk === "WRITE");
check("classify Write outside ws -> PRIVILEGED", classify("Write", { file_path: "/etc/passwd" }, "/w").risk === "PRIVILEGED");
check("classify Read -> READ", classify("Read", { file_path: "/w/a.txt" }, "/w").risk === "READ");
check("classify CreateWorkflow -> DENIED_DEFERRED", classify("CreateWorkflow", {}, "/w").risk === "DENIED_DEFERRED");
check("classify unknown mcp -> PRIVILEGED", classify("mcp__x__y", {}, "/w").risk === "PRIVILEGED");

// 2. truth table
check("decide CRITICAL->hard_confirm all modes", ["ask","auto","full"].every(m => decide(m, "CRITICAL") === "hard_confirm"));
check("decide DENIED_DEFERRED->deny", decide("ask", "DENIED_DEFERRED") === "deny");
check("decide PRIVILEGED full->auto", decide("full", "PRIVILEGED") === "auto");
check("decide PRIVILEGED ask->ask", decide("ask", "PRIVILEGED") === "ask");
check("decide WRITE ask->ask auto/full->auto", decide("ask","WRITE")==="ask" && decide("auto","WRITE")==="auto" && decide("full","WRITE")==="auto");
check("decide READ->auto", decide("ask", "READ") === "auto");

// 3. hard-confirm token enforcement (no UI: use onAsk capture)
let asked = null;
g.onAsk = (key, info) => { asked = { key, info }; };
const p = g.handlePermission({ toolName: "Bash", input: ddCmd, sessionId: "unit-test", requestId: "req1" });
setTimeout(() => {
  check("hard-confirm asked via UI", !!asked && asked.info.hardConfirm === true, JSON.stringify(asked && asked.info.hits));
  // answer WITHOUT token -> refused -> deny to core + reject row
  const r1 = g.resolveAnswer(asked.key, { decision: "allow", source: "unit" });
  check("tokenless allow refused", r1.refused === true);
  p.then((decision) => {
    check("core got deny after tokenless", decision.decision === "deny");
    const rej = g.journalView(5).find(o => o.detail && o.detail.includes("token"));
    check("reject journaled", !!rej && rej.hard_confirm === 1);
    // 4. hard-confirm WITH token -> allow + journaled
    const p2 = g.handlePermission({ toolName: "Bash", input: ddCmd, sessionId: "unit-test", requestId: "req2" });
    setTimeout(() => {
      g.resolveAnswer(asked.key, { decision: "allow", confirmToken: asked.key, source: "unit" });
      p2.then((d2) => {
        check("tokened allow -> allow", d2.decision === "allow");
        const row = g.journalView(5).find(o => o.hard_confirm === 1 && o.decision === "allow");
        check("hard-confirm allow journaled with rule hits", !!row);
        console.log(`\nRESULT: PASS=${pass} FAIL=${fail}`);
        process.exit(fail === 0 ? 0 : 1);
      });
    }, 10);
  });
}, 10);

