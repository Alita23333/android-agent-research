from pathlib import Path
p = Path(__file__).resolve().parents[2] / 'app/src/main/assets/zcode-runtime/bootstrap.cjs'
s = p.read_text(encoding='utf-8')
def replace(old, new):
    global s
    assert s.count(old) == 1, (old[:70], s.count(old))
    s = s.replace(old, new, 1)

replace('const visionPipeline = require("./vision-pipeline.cjs");', '''const visionPipeline = require("./vision-pipeline.cjs");
const SHOTS = path.join(RUNTIME, "vision", "shots");
function purgeVisionFrames() {
  try { for (const f of fs.readdirSync(SHOTS)) fs.unlinkSync(path.join(SHOTS, f)); } catch {}
}
purgeVisionFrames(); // process restart never resurrects live screen observations
function frameMetadata(id, session) {
  if (!/^shot_[a-f0-9]{32}$/.test(id || "")) return null;
  try {
    const rows = JSON.parse(fs.readFileSync(path.join(SHOTS, "index.json"), "utf8"));
    const row = rows.find(x => x.shotId === id && x.sessionId === session);
    if (!row || row.filename !== id + ".jpeg" || row.bytes > 153600) return null;
    return row;
  } catch { return null; }
}
function cancelCarrierPending(reason) {
  for (const [id, pending] of (state.carrierPending || new Map())) {
    clearTimeout(pending.timer);
    pending.resolve({status:200, body:{ok:false,error:{code:reason}}});
    state.carrierPending.delete(id);
  }
  state.carrierQueue = [];
  for (const controller of (state.visionControllers || new Set())) controller.abort();
  state.visionCache?.clear();
  purgeVisionFrames();
}''')
replace('''    const m = JSON.parse(msgStr);
    if (m && m.method''', '''    const m = JSON.parse(msgStr);
    const session = m.params?.sessionId;
    if (session && session !== state.activeSession) {
      cancelCarrierPending("SESSION_CHANGED"); state.activeSession = session;
    }
    if (/^session\\/(?:stop|cancel|delete|dispose)$/.test(m.method || "")) cancelCarrierPending("CANCELLED");
    if (m && m.method''')
replace('''child.on("exit", (code) => { state.childPid = null; log(`app-server exited code=${code}`); });''', '''child.on("exit", (code) => { cancelCarrierPending("RUNTIME_EXITED"); state.childPid = null; log(`app-server exited code=${code}`); });''')
a = s.index('    ui_see: (call) => {')
b = s.index('    ...Object.fromEntries(WS_TOOLS', a)
s = s[:a] + '''    ui_see: async (call) => {
      const sessionKey = call.meta?.sessionId || state.activeSession;
      if (!sessionKey) return {ok:false,error:{code:"SESSION_REQUIRED"}};
      const controller = new AbortController();
      (state.visionControllers = state.visionControllers || new Set()).add(controller);
      call.cancelSignal?.addEventListener("abort", () => controller.abort(), {once:true});
      if (call.cancelSignal?.aborted) controller.abort();
      const clock = setTimeout(() => controller.abort(), 29000);
      const internalCall = async (toolId, iargs) => {
        if (controller.signal.aborted) throw new Error("vision_cancelled");
        const permission = await gateway.handlePermission({
          requestId:"vision_" + require("node:crypto").randomUUID(), sessionId:sessionKey,
          toolName:"mcp__android-host__" + toolId, input:iargs,
        });
        if (permission.decision !== "allow" || controller.signal.aborted) throw new Error("vision_capture_denied");
        const wantId = "internal_" + require("node:crypto").randomUUID();
        state.carrierQueue = state.carrierQueue || []; state.carrierPending = state.carrierPending || new Map();
        return new Promise(resolve => {
          const finish = result => {
            clearTimeout(timer); controller.signal.removeEventListener("abort", abort);
            state.carrierPending.delete(wantId);
            state.carrierQueue = state.carrierQueue.filter(x => x.callId !== wantId);
            resolve(result.body?.structuredContent || result.body);
          };
          const abort = () => finish({body:{ok:false,error:{code:"vision_cancelled"}}});
          const timer = setTimeout(() => finish({body:{ok:false,error:{code:"internal_call_timeout"}}}), 20000);
          controller.signal.addEventListener("abort", abort, {once:true});
          state.carrierPending.set(wantId, {resolve:finish,timer,toolId,callArgs:iargs});
          state.carrierQueue.push({toolId,arguments:iargs,callId:wantId,meta:{sessionId:sessionKey}});
        });
      };
      const renderFrame = async () => {
        const dump = await internalCall("ui_dump", {maxNodes:600});
        if (!dump || dump.ok === false) return null;
        return {generation:Number(String(dump.treeId).slice(1)),render:{nodes:dump.snapshot?.nodes || []},
          screenW:dump.snapshot?.screenW,screenH:dump.snapshot?.screenH};
      };
      const shotMeta = id => frameMetadata(id, sessionKey);
      const readShot = id => {
        const row = shotMeta(id); if (!row) return null;
        try {
          const f = path.join(SHOTS,row.filename);
          if (fs.lstatSync(f).isSymbolicLink() || fs.statSync(f).size !== row.bytes) return null;
          const bytes = fs.readFileSync(f);
          return require("node:crypto").createHash("sha256").update(bytes).digest("hex") === row.sha256 ? bytes : null;
        } catch { return null; }
      };
      state.visionCounts = state.visionCounts || new Map(); state.visionCache = state.visionCache || new Map();
      const now = Date.now();
      const hits = (state.visionCounts.get(sessionKey) || []).filter(t => now-t < 3600000);
      state.visionCounts.set(sessionKey,hits);
      try {
        return await visionPipeline.executeSee(call, {
          spikeRoot:ROOT, internalCall, renderFrame, readShot, shotMeta, sessionKey, signal:controller.signal, lab:LAB_VISION,
          sessionCount:() => hits.length,
          cacheGet:key => state.visionCache.get(key),
          cachePut:(key,value) => { if (state.visionCache.size >= 20) state.visionCache.delete(state.visionCache.keys().next().value); state.visionCache.set(key,value); },
          journal:row => { const id = gateway.journalNetworkRequest(row); if(row.result_code === "started") hits.push(Date.now()); return id; },
        });
      } finally { clearTimeout(clock); state.visionControllers.delete(controller); }
    },
''' + s[b:]
# A live worker checks this immediately before any Phase9 gesture/capture.
replace('''  if (url.pathname === "/carrier/next")''', '''  if (url.pathname === "/carrier/active") {
    send(200, {active:!!state.carrierPending?.has(url.searchParams.get("callId"))}); return;
  }
  if (url.pathname === "/vision/status") {
    const cfg = visionPipeline.loadVisionConfig(ROOT);
    send(200, {configured:!!cfg, provider:cfg?.providerId || null, model:cfg?.modelId || null,
      host:cfg ? new URL(cfg.baseUrl).hostname : null, route:"explicit-provider-text-result", lab:LAB_VISION}); return;
  }
  if (url.pathname === "/carrier/next")''')
# Authorization at the new entry points is explicit even for direct authenticated callers.
needle = '''  if (url.pathname === "/carrier/call" && req.method === "POST") {'''
a = s.index(needle); b = s.index('  if (url.pathname === "/sessions")', a)
block = s[a:b]
block = block.replace('req.on("end", () => {', 'req.on("end", async () => {', 1)
block = block.replace('''        const call = JSON.parse(body);''', '''        const call = JSON.parse(body);
        if (["ui_see","ui_tap","ui_screenshot"].includes(call.toolId)) {
          const controller = new AbortController();
          res.on("close", () => { if (!res.writableEnded) controller.abort(); });
          call.cancelSignal = controller.signal;
          const sessionId = state.activeSession || call.meta?.sessionId;
          if (!sessionId) return send(200,{ok:false,error:{code:"SESSION_REQUIRED"}});
          call.meta = {...call.meta,sessionId};
          const permission = await gateway.handlePermission({requestId:"carrier_" + require("node:crypto").randomUUID(),
            sessionId,toolName:"mcp__android-host__" + call.toolId,input:call.arguments || {}});
          if (permission.decision !== "allow" || controller.signal.aborted) return send(200,{ok:false,error:{code:"GATEWAY_DENIED"}});
        }''', 1)
block = block.replace('''            state.carrierPending.delete(call.callId);
            pend.resolve''', '''            state.carrierPending.delete(call.callId);
            state.carrierQueue = state.carrierQueue.filter(x => x.callId !== call.callId);
            pend.resolve''', 1)
block = block.replace('''          .then((r) => send(r.status, r.body));''', '''          .then((r) => send(r.status, r.body));
        res.on("close", () => {
          if (res.writableEnded) return;
          const pending = state.carrierPending.get(call.callId);
          if (pending) {clearTimeout(pending.timer); state.carrierPending.delete(call.callId);}
          state.carrierQueue = state.carrierQueue.filter(x => x.callId !== call.callId);
        });''', 1)
s = s[:a] + block + s[b:]
p.write_text(s, encoding='utf-8', newline='\n')
print('Carrier session/frame binding, cancellation and existing Gateway authorization installed.')
