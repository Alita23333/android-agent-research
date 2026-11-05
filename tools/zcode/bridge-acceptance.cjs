const http = require("node:http");
const { execFileSync } = require("node:child_process");

const base = new URL(process.env.ZCODE_BRIDGE_URL || "http://127.0.0.1:18765");
const token = process.env.ZCODE_BRIDGE_TOKEN || (process.env.ANDROID_SERIAL ? execFileSync(
  process.env.ANDROID_ADB || "adb",
  ["-s", process.env.ANDROID_SERIAL, "exec-out", "run-as", "dev.alita.androidagent", "cat", "files/runtime/bridge-token"],
  { encoding: "utf8" },
).trim() : "");
if (!token) throw new Error("ZCODE_BRIDGE_TOKEN is required");

const events = [];
const waiters = new Set();
let sequence = 7000;

function request(method, pathname, body, timeoutMs = 30000) {
  return new Promise((resolve, reject) => {
    const bytes = body === undefined ? null : Buffer.from(JSON.stringify(body));
    const req = http.request({
      host: base.hostname,
      port: base.port,
      path: pathname,
      method,
      headers: {
        "X-Bridge-Token": token,
        ...(bytes ? { "Content-Type": "application/json", "Content-Length": bytes.length } : {}),
      },
    }, (res) => {
      let text = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => (text += chunk));
      res.on("end", () => {
        let value;
        try { value = JSON.parse(text || "{}"); } catch { value = { raw: text }; }
        if (res.statusCode >= 200 && res.statusCode < 300) resolve(value);
        else reject(new Error(`${method} ${pathname} -> ${res.statusCode}: ${JSON.stringify(value)}`));
      });
    });
    req.setTimeout(timeoutMs, () => req.destroy(new Error(`timeout: ${method} ${pathname}`)));
    req.on("error", reject);
    if (bytes) req.write(bytes);
    req.end();
  });
}

function killOrphanNodes(adb, serial) {
  try {
    execFileSync(adb, ["-s", serial, "shell", "run-as", "dev.alita.androidagent", "pkill", "-f", "libnode.so"]);
  } catch {
    // No matching orphan is the normal case. Production lifecycle is unchanged.
  }
}

function acceptEvent(event) {
  events.push({ at: Date.now(), ...event });
  if (events.length > 5000) events.splice(0, events.length - 5000);
  for (const waiter of [...waiters]) {
    if (waiter.predicate(event)) {
      waiters.delete(waiter);
      clearTimeout(waiter.timer);
      waiter.resolve(event);
    }
  }
  if (event.type === "permission") {
    request("POST", "/respond", {
      requestId: event.requestId,
      decision: event.hardConfirm ? "deny" : "allow",
    }).catch((error) => process.stderr.write(`permission response failed: ${error.message}\n`));
  }
}

function openEvents() {
  const req = http.request({
    host: base.hostname,
    port: base.port,
    path: `/events?t=${encodeURIComponent(token)}`,
    method: "GET",
    headers: { "X-Bridge-Token": token },
  });
  req.on("response", (res) => {
    let buffer = "";
    res.setEncoding("utf8");
    res.on("data", (chunk) => {
      buffer += chunk;
      while (buffer.includes("\n\n")) {
        const index = buffer.indexOf("\n\n");
        const block = buffer.slice(0, index);
        buffer = buffer.slice(index + 2);
        const data = block.split("\n").filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trim()).join("\n");
        if (!data) continue;
        try { acceptEvent(JSON.parse(data)); } catch {}
      }
    });
  });
  req.on("error", (error) => process.stderr.write(`SSE error: ${error.message}\n`));
  req.end();
  return req;
}

function waitFor(predicate, timeoutMs, label) {
  const existing = events.find((event) => predicate(event));
  if (existing) return Promise.resolve(existing);
  return new Promise((resolve, reject) => {
    const waiter = { predicate, resolve, timer: null };
    waiter.timer = setTimeout(() => {
      waiters.delete(waiter);
      reject(new Error(`timeout waiting for ${label}`));
    }, timeoutMs);
    waiters.add(waiter);
  });
}

async function rpc(method, params, timeoutMs = 90000) {
  const id = ++sequence;
  const pending = waitFor((event) => event.type === "rpc" && event.message && event.message.id === id, timeoutMs, method);
  await request("POST", "/rpc", { id, method, params });
  const event = await pending;
  if (event.message.error) throw new Error(`${method}: ${JSON.stringify(event.message.error)}`);
  return event.message.result;
}

async function main() {
  const sse = openEvents();
  await new Promise((resolve) => setTimeout(resolve, 300));
  const status = await request("GET", "/status");
  const workspace = "/data/user/0/dev.alita.androidagent/files/workspaces/default";
  const selection = { providerId: "deepseek", modelId: "deepseek-flash" };
  const scenario = process.argv[2] || "turn";
  if (scenario === "carrier-status") {
    let tools = [];
    const deadline = Date.now() + 30000;
    while (Date.now() < deadline) {
      try {
        tools = (await request("GET", "/carrier/tools")).tools || [];
        if (tools.length) break;
      } catch {}
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    process.stdout.write(JSON.stringify({
      phase: status.phase,
      tools: tools.map((tool) => ({ toolId: tool.toolId, readOnly: tool.readOnly, canonicalToolId: tool.metadata?.canonicalToolId })),
    }, null, 2) + "\n");
    sse.destroy();
    return;
  }
  if (scenario === "force-resume") {
    const sessionId = process.argv[3];
    if (!sessionId) throw new Error("force-resume requires a session id");
    const adb = process.env.ANDROID_ADB || "adb";
    const serial = process.env.ANDROID_SERIAL;
    execFileSync(adb, ["-s", serial, "shell", "am", "force-stop", "dev.alita.androidagent"]);
    await new Promise((resolve) => setTimeout(resolve, 1500));
    let unreachableAfterStop = false;
    try { await request("GET", "/status", undefined, 1500); } catch { unreachableAfterStop = true; }
    killOrphanNodes(adb, serial);
    execFileSync(adb, ["-s", serial, "shell", "su", "-c", "am start -n dev.alita.androidagent/.zcode.runtime.ZCodeActivity"]);
    let after;
    const deadline = Date.now() + 55000;
    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      try {
        const candidate = await request("GET", "/status", undefined, 2000);
        if (candidate.phase === "ready") { after = candidate; break; }
      } catch {}
    }
    if (!after) throw new Error("runtime did not relaunch after force-stop");
    const resumed = await request("GET", `/session/resume?id=${encodeURIComponent(sessionId)}`);
    const snapshot = await request("GET", `/session/read?id=${encodeURIComponent(sessionId)}`);
    process.stdout.write(JSON.stringify({
      unreachableAfterStop,
      relaunchedReady: after.phase === "ready",
      newRuntime: after.startedAt !== status.startedAt,
      resumed: !resumed.error,
      sessionId,
      persistedMessageCount: snapshot.snapshot?.messages?.length || 0,
      persistedAssistantMessages: (snapshot.snapshot?.messages || []).filter((m) => m.info?.role === "assistant" && m.info?.finish).length,
    }, null, 2) + "\n");
    sse.destroy();
    return;
  }
  if (scenario === "crash-restart") {
    const adb = process.env.ANDROID_ADB || "adb";
    const serial = process.env.ANDROID_SERIAL;
    const ps = execFileSync(adb, ["-s", serial, "shell", "su", "-c", "ps -A -o PID,PPID,NAME,ARGS"], { encoding: "utf8" });
    const line = ps.split(/\r?\n/).find((value) => value.includes("libnode.so") && value.includes("runtime/bootstrap.cjs"));
    if (!line) throw new Error("bootstrap Node process not found");
    const pid = line.trim().split(/\s+/)[0];
    execFileSync(adb, ["-s", serial, "shell", "su", "-c", `kill -9 ${pid}`]);
    let after;
    const deadline = Date.now() + 55000;
    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      try {
        const candidate = await request("GET", "/status", undefined, 2000);
        if (candidate.phase === "ready" && candidate.startedAt !== status.startedAt) { after = candidate; break; }
      } catch {}
    }
    if (!after) throw new Error("supervised runtime did not return to ready");
    process.stdout.write(JSON.stringify({
      killedBootstrapPid: Number(pid),
      beforeStartedAt: status.startedAt,
      afterStartedAt: after.startedAt,
      restarted: after.startedAt !== status.startedAt,
      phase: after.phase,
    }, null, 2) + "\n");
    sse.destroy();
    return;
  }
  if (scenario === "reconnect") {
    const sessionId = process.argv[3];
    if (!sessionId) throw new Error("reconnect requires a session id");
    const before = status;
    execFileSync(process.env.ANDROID_ADB || "adb", ["-s", process.env.ANDROID_SERIAL, "shell", "input", "keyevent", "HOME"]);
    await new Promise((resolve) => setTimeout(resolve, 1500));
    const backgrounded = await request("GET", "/status");
    execFileSync(process.env.ANDROID_ADB || "adb", ["-s", process.env.ANDROID_SERIAL, "shell", "su", "-c", "am", "start", "-n", "dev.alita.androidagent/.zcode.runtime.ZCodeActivity"]);
    await new Promise((resolve) => setTimeout(resolve, 1500));
    const after = await request("GET", "/status");
    const snapshot = await request("GET", `/session/read?id=${encodeURIComponent(sessionId)}`);
    process.stdout.write(JSON.stringify({
      beforePhase: before.phase,
      backgroundedPhase: backgrounded.phase,
      afterPhase: after.phase,
      sameRuntime: before.startedAt === after.startedAt,
      sessionReadable: (snapshot.snapshot?.messages?.length || 0) >= 3,
    }, null, 2) + "\n");
    sse.destroy();
    return;
  }
  if (scenario === "resume") {
    const sessionId = process.argv[3];
    if (!sessionId) throw new Error("resume requires a session id");
    const resumed = await request("GET", `/session/resume?id=${encodeURIComponent(sessionId)}`);
    const snapshot = await request("GET", `/session/read?id=${encodeURIComponent(sessionId)}`);
    process.stdout.write(JSON.stringify({
      status: { phase: status.phase, startedAt: status.startedAt },
      sessionId,
      resumed: !resumed.error,
      messageCount: snapshot.snapshot?.messages?.length || 0,
      persistedAssistantMessages: (snapshot.snapshot?.messages || []).filter((m) => m.info?.role === "assistant" && m.info?.finish).length,
    }, null, 2) + "\n");
    sse.destroy();
    return;
  }
  const connectivity = await rpc("provider/testModelConnectivity", { workspace: { workspacePath: workspace, workspaceKey: "default" }, selection }, 90000);
  const created = await rpc("session/create", {
    workspace: { workspacePath: workspace, workspaceKey: "default" },
    model: { ...selection, options: { reasoningLevel: "disabled" } },
    thoughtLevel: "disabled",
    ...(process.env.ZCODE_ACCEPTANCE_DENY_TOOLS ? {
      toolDenylist: (() => {
        const names = JSON.parse(process.env.ZCODE_ACCEPTANCE_DENY_TOOLS);
        if (!Array.isArray(names) || names.some(n => typeof n !== "string" || !/^[A-Za-z0-9_.-]+$/.test(n)))
          throw new Error("explicit acceptance deny names required");
        return names;
      })(),
    } : {}),
  });
  const sessionId = created.session.sessionId;
  if (scenario === "cancel") {
    const eventStart = events.length;
    await rpc("session/send", { sessionId, content: "Count slowly from 1 to 10000, writing every number on its own line." });
    await new Promise((resolve) => setTimeout(resolve, 200));
    await rpc("session/stop", { sessionId });
    await new Promise((resolve) => setTimeout(resolve, 1500));
    const snapshot = await request("GET", `/session/read?id=${encodeURIComponent(sessionId)}`);
    const serialized = JSON.stringify(snapshot);
    const rpcEvents = events.slice(eventStart).filter((event) => event.type === "rpc");
    process.stdout.write(JSON.stringify({
      status: { phase: status.phase },
      connectivity,
      sessionId,
      stopAccepted: true,
      cancelledEvidence: /cancel/i.test(serialized) || rpcEvents.some((event) => /cancel/i.test(JSON.stringify(event))),
      rpcEventCount: rpcEvents.length,
      messageCount: snapshot.snapshot?.messages?.length || 0,
    }, null, 2) + "\n");
    sse.destroy();
    return;
  }
  if (scenario === "device-tool" || scenario === "ui-tool" || scenario === "ui-find") {
    const isDevice = scenario === "device-tool";
    const isFind = scenario === "ui-find";
    const carrierTool = isDevice ? "mcp__android-host__device_info_identity"
      : (isFind ? "mcp__android-host__ui_find" : "mcp__android-host__ui_dump");
    const prompt = isDevice
      ? `Call ${carrierTool} exactly once. Then report the real device brand, model, ABI, and Android API returned by the tool.`
      : (isFind
        ? `Call ${carrierTool} exactly once with text "Increment". Then report the treeId, matched node id, role, label, and app package.`
        : `Call ${carrierTool} exactly once with detail compact and maxNodes 80. Then report the treeId, current app package, screen title, and emitted node count.`);
    const eventStart = events.length;
    const journalBefore = await request("GET", "/gateway/journal?limit=200");
    await rpc("session/send", { sessionId, content: prompt });
    let snapshot;
    let completed = false;
    const deadline = Date.now() + 120000;
    while (Date.now() < deadline) {
      snapshot = await request("GET", `/session/read?id=${encodeURIComponent(sessionId)}`);
      completed = (snapshot.snapshot?.messages || []).some((message) =>
        message.info?.role === "assistant" && message.info?.finish === "stop" && message.info?.semantics?.origin === "agent_runtime");
      const serialized = JSON.stringify(snapshot);
      const resultSeen = isDevice ? serialized.includes("MODEL_ANDROID17") : serialized.includes("treeId");
      if (completed && resultSeen) break;
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    if (!snapshot || !completed) throw new Error(`${scenario} did not complete`);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    const slice = events.slice(eventStart);
    const permissions = slice.filter((event) => event.type === "permission" && event.toolName === carrierTool);
    const expectedWireTool = isDevice ? "device_info_identity" : (isFind ? "ui_find" : "ui_dump");
    const carrierCalls = slice.filter((event) => event.type === "carrier-call" && (event.toolId === expectedWireTool || event.call?.toolId === expectedWireTool));
    const journalAfter = await request("GET", "/gateway/journal?limit=200");
    const beforeIds = new Set((journalBefore.operations || []).map((row) => row.id));
    const newRows = (journalAfter.operations || []).filter((row) => !beforeIds.has(row.id));
    const toolRows = newRows.filter((row) => String(row.tool || row.toolName || "").includes(carrierTool));
    const assistantText = (snapshot.snapshot?.messages || [])
      .filter((message) => message.info?.role === "assistant" && message.info?.semantics?.origin === "agent_runtime")
      .flatMap((message) => message.parts || [])
      .filter((part) => part.type === "text")
      .map((part) => part.text).join("\n");
    const serialized = JSON.stringify(snapshot);
    const outputs = (snapshot.snapshot?.messages || []).flatMap((m) => m.parts || [])
      .filter((p) => p.type === "tool" && p.tool === carrierTool).map((p) => p.state?.output || "");
    const physicalResultPresent = outputs.some((output) => isDevice
      ? output.includes("MODEL_ANDROID17")
      : output.includes('"treeId"') && output.includes('"performed": true') && output.includes('"verified": true'));
    if (!physicalResultPresent || carrierCalls.length !== 1 || !toolRows.length)
      throw new Error(`${scenario}: missing successful physical result, carrier event, or Gateway row`);
    process.stdout.write(JSON.stringify({
      status: { phase: status.phase },
      connectivity,
      sessionId,
      modelVisibleTool: carrierTool,
      permissionEvents: permissions.length,
      carrierCallEvents: carrierCalls.length,
      gatewayJournalRows: toolRows.map((row) => ({ id: row.id, tool: row.tool, risk: row.risk, decision: row.decision, approval_source: row.approval_source })),
      physicalResultPresent,
      finalAnswer: assistantText.slice(-1200),
    }, null, 2) + "\n");
    sse.destroy();
    return;
  }
  if (scenario === "ui-lab") {
    const prompt = process.argv.slice(3).join(" ");
    if (!prompt) throw new Error("ui-lab requires an explicit fixture-only prompt");
    const eventStart = events.length;
    const before = await request("GET", "/gateway/journal?limit=200");
    await rpc("session/send", { sessionId, content: prompt });
    let snapshot;
    let completed = false;
    const deadline = Date.now() + 120000;
    while (Date.now() < deadline) {
      snapshot = await request("GET", `/session/read?id=${encodeURIComponent(sessionId)}`);
      completed = (snapshot.snapshot?.messages || []).some((m) =>
        m.info?.role === "assistant" && m.info?.finish === "stop" && m.info?.semantics?.origin === "agent_runtime");
      if (completed) break;
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    if (!completed) throw new Error("ui-lab did not complete");
    const prior = new Set((before.operations || []).map((row) => row.id));
    const after = await request("GET", "/gateway/journal?limit=200");
    process.stdout.write(JSON.stringify({ sessionId, completed,
      carrierCalls: events.slice(eventStart).filter((e) => e.type === "carrier-call"),
      gatewayJournalRows: (after.operations || []).filter((r) => !prior.has(r.id)),
      messages: snapshot.snapshot?.messages,
    }, null, 2) + "\n");
    sse.destroy();
    return;
  }
  if (scenario === "workspace-tool") {
    const action = process.argv[3] || "create";
    const fixturePath = process.env.ZCODE_ACCEPTANCE_FILE || "phase8/model-visible.txt";
    const specs = {
      create: { tool: "workspace_file_create", args: { path: fixturePath, content: "created-by-zcode", create_parents: true } },
      overwrite: { tool: "workspace_file_overwrite", args: { path: fixturePath, content: "overwritten-by-zcode" } },
      append: { tool: "workspace_file_append", args: { path: fixturePath, content: "+append" } },
      delete: { tool: "workspace_file_delete", args: { path: fixturePath } },
    };
    const spec = specs[action];
    if (!spec) throw new Error("workspace-tool action must be create|overwrite|append|delete");
    const modelTool = `mcp__android-host__${spec.tool}`;
    const beforeJournal = await request("GET", "/gateway/journal?limit=500");
    const beforeWrites = await request("GET", "/gateway/writes?limit=500");
    const eventStart = events.length;
    await rpc("session/send", {
      sessionId,
      content: `Call ${modelTool} exactly once with these exact JSON arguments: ${JSON.stringify(spec.args)}. Do not call any other tool. Then briefly report the result.`,
    });
    let snapshot;
    let completed = false;
    const deadline = Date.now() + 120000;
    while (Date.now() < deadline) {
      snapshot = await request("GET", `/session/read?id=${encodeURIComponent(sessionId)}`);
      completed = (snapshot.snapshot?.messages || []).some((message) =>
        message.info?.role === "assistant" && message.info?.finish === "stop" && message.info?.semantics?.origin === "agent_runtime");
      const serialized = JSON.stringify(snapshot);
      if (completed && serialized.includes(spec.tool)) break;
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    if (!snapshot || !completed) throw new Error(`workspace ${action} did not complete`);
    await new Promise((resolve) => setTimeout(resolve, 500));
    const afterJournal = await request("GET", "/gateway/journal?limit=500");
    const afterWrites = await request("GET", "/gateway/writes?limit=500");
    const oldOpIds = new Set((beforeJournal.operations || []).map((row) => row.id));
    const oldTxnIds = new Set((beforeWrites.write_txns || []).map((row) => row.txn_id));
    const operations = (afterJournal.operations || []).filter((row) => !oldOpIds.has(row.id) && String(row.tool || "").includes(spec.tool));
    const txns = (afterWrites.write_txns || []).filter((row) => !oldTxnIds.has(row.txn_id) && row.tool === modelTool);
    const slice = events.slice(eventStart);
    const report = {
      status: { phase: status.phase }, connectivity, sessionId, action, modelTool,
      permissionEvents: slice.filter((event) => event.type === "permission" && event.toolName === modelTool).length,
      operations: operations.map((row) => ({ id: row.id, tool: row.tool, decision: row.decision, result: row.result, before_hash: row.before_hash, after_hash: row.after_hash, backup_path: row.backup_path, reversible: row.reversible })),
      txns: txns.map((row) => ({ txn_id: row.txn_id, state: row.state, route: row.route, mutation_kind: row.mutation_kind, target_rel: row.target_rel, before_hash: row.before_hash, after_hash: row.after_hash, backup_path: row.backup_path, reversible: row.reversible, error_code: row.error_code })),
      toolResultPresent: (snapshot.snapshot?.messages || []).flatMap((m) => m.parts || [])
        .some((p) => p.type === "tool" && p.tool === modelTool && p.state?.status === "completed"),
      finalAnswer: (snapshot.snapshot?.messages || []).flatMap((m) => m.parts || [])
        .filter((p) => p.type === "text").map((p) => p.text).join("\n").slice(-2000),
    };
    process.stdout.write(JSON.stringify(report, null, 2) + "\n");
    if (!report.toolResultPresent || operations.length < 1 || !txns.some((r) => r.state === "completed" && r.before_hash && r.after_hash))
      throw new Error(`workspace ${action} evidence incomplete or mutation not verified`);
    sse.destroy();
    return;
  }
  if (scenario === "web-search") {
    const carrierTool = "mcp__android-host__web_search";
    const query = process.argv.slice(3).join(" ") || "OpenAI official Codex documentation";
    const visibleTools = (await request("GET", "/carrier/tools")).tools || [];
    const searchStatus = await request("GET", "/search/status");
    const journalBefore = await request("GET", "/gateway/journal?limit=500");
    const networkBefore = await request("GET", "/gateway/network?limit=500");
    const eventStart = events.length;
    await rpc("session/send", {
      sessionId,
      content: `Call ${carrierTool} exactly once with query ${JSON.stringify(query)}. Use only its returned search results, then answer with at least one cited result URL. Do not use vendor-native browsing.`,
    });
    let snapshot;
    let completed = false;
    const deadline = Date.now() + 150000;
    while (Date.now() < deadline) {
      snapshot = await request("GET", `/session/read?id=${encodeURIComponent(sessionId)}`);
      completed = (snapshot.snapshot?.messages || []).some((message) =>
        message.info?.role === "assistant" && message.info?.finish === "stop" && message.info?.semantics?.origin === "agent_runtime");
      if (completed) break;
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    if (!snapshot || !completed) throw new Error("web-search did not complete");
    await new Promise((resolve) => setTimeout(resolve, 1000));
    const slice = events.slice(eventStart);
    const permissions = slice.filter((event) => event.type === "permission" && event.toolName === carrierTool);
    const carrierCalls = slice.filter((event) => event.type === "carrier-call" && (event.toolId === "web_search" || event.call?.toolId === "web_search"));
    const journalAfter = await request("GET", "/gateway/journal?limit=500");
    const networkAfter = await request("GET", "/gateway/network?limit=500");
    const oldOperationIds = new Set((journalBefore.operations || []).map((row) => row.id));
    const oldNetworkIds = new Set((networkBefore.network_requests || []).map((row) => row.id));
    const operations = (journalAfter.operations || []).filter((row) => !oldOperationIds.has(row.id));
    const networkRows = (networkAfter.network_requests || []).filter((row) => !oldNetworkIds.has(row.id));
    const assistantText = (snapshot.snapshot?.messages || [])
      .filter((message) => message.info?.role === "assistant" && message.info?.semantics?.origin === "agent_runtime")
      .flatMap((message) => message.parts || []).filter((part) => part.type === "text")
      .map((part) => part.text).join("\n");
    const searchToolParts = (snapshot.snapshot?.messages || [])
      .flatMap((message) => message.parts || [])
      .filter((part) => part.type === "tool" && part.tool === carrierTool && part.state?.status === "completed");
    const parsedSearchResults = searchToolParts.map((part) => {
      const output = part.state?.output;
      if (output && typeof output === "object") return output;
      if (typeof output !== "string") return null;
      for (const candidate of [output, output.split("\n\nStructured content:\n", 1)[0]]) {
        try { return JSON.parse(candidate); } catch {}
      }
      return null;
    }).filter(Boolean);
    const inlineDispatchEvidence = networkRows.some((row) => row.source === "web.search");
    const report = {
      status: { phase: status.phase }, connectivity, sessionId,
      modelVisible: visibleTools.some((tool) => tool.toolId === "web_search"),
      searchStatus,
      permissionEvents: permissions.length,
      carrierCallEvents: carrierCalls.length,
      inlineDispatchEvidence,
      gatewayOperations: operations.map((row) => ({ id: row.id, tool: row.tool, risk: row.risk, decision: row.decision, approval_source: row.approval_source })),
      networkRows: networkRows.map((row) => ({ id: row.id, source: row.source, backend_id: row.backend_id, host: row.host, status: row.status, bytes_in: row.bytes_in, result_code: row.result_code, query_sha256: row.query_sha256 })),
      toolResultPresent: parsedSearchResults.some((result) =>
        typeof result.backend === "string" && Array.isArray(result.results)),
      citedUrlPresent: /https?:\/\/[^\s)\]]+/.test(assistantText),
      finalAnswer: assistantText.slice(-2500),
    };
    process.stdout.write(JSON.stringify(report, null, 2) + "\n");
    if (!report.modelVisible || permissions.length !== 1 || carrierCalls.length !== 1 || !report.inlineDispatchEvidence || networkRows.length < 1 || !report.toolResultPresent || !report.citedUrlPresent) {
      throw new Error("web-search acceptance evidence incomplete");
    }
    sse.destroy();
    return;
  }
  const eventStart = events.length;
  await rpc("session/send", { sessionId, content: "Reply with exactly STREAM_ACCEPTANCE_OK and no other text." });
  let snapshot;
  let assistantCompleted = false;
  const deadline = Date.now() + 120000;
  while (Date.now() < deadline) {
    snapshot = await request("GET", `/session/read?id=${encodeURIComponent(sessionId)}`);
    assistantCompleted = (snapshot.snapshot?.messages || []).some((message) =>
      message.info?.role === "assistant" && message.info?.finish &&
      (message.parts || []).some((part) => part.type === "text" && part.text === "STREAM_ACCEPTANCE_OK"));
    if (assistantCompleted) break;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  if (!snapshot || !assistantCompleted) throw new Error("provider turn did not complete with the expected assistant marker");
  await new Promise((resolve) => setTimeout(resolve, 1000));
  const rpcEvents = events.slice(eventStart).filter((event) => event.type === "rpc");
  const turnEvents = events.slice(eventStart).filter((event) => event.type === "rpc" && event.message?.method === "session/event");
  const rpcMethods = rpcEvents.reduce((counts, event) => {
    const key = event.message?.method || (event.message?.id !== undefined ? "response" : "other");
    counts[key] = (counts[key] || 0) + 1;
    return counts;
  }, {});
  const report = {
    status: { phase: status.phase, nodeVersion: status.nodeVersion, arch: status.arch },
    connectivity,
    sessionId,
    rpcEventCount: rpcEvents.length,
    rpcMethods,
    sessionEventCount: turnEvents.length,
    streamed: (rpcMethods["state.updated"] || 0) > 1 || (rpcMethods["computer-use/operation-event"] || 0) > 1,
    finalMarkerPresent: assistantCompleted,
    snapshotMessageCount: snapshot.snapshot?.messages?.length,
  };
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  sse.destroy();
}

main().catch((error) => {
  process.stderr.write(error.stack + "\n");
  process.exit(1);
});
