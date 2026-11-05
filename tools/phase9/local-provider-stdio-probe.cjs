// Protocol-only compatibility probe. No Core/model/Gateway registration or external writes.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawn } = require('node:child_process');
const file = path.resolve(process.argv[2] || '');
if (!/^\/data\/(?:user\/0|data)\/dev\.(?:alita\.androidagent|zcode\.nodepoc)\/cache\/local-provider-probe-[0-9]+\/provider\.cjs$/.test(file)) throw Error('isolated assigned-app provider fixture required');
if (process.version !== 'v24.18.0') throw Error('use accepted APK-owned Node24.18.0');
const child = spawn(process.execPath, [file], { cwd: path.dirname(file), stdio: ['pipe', 'pipe', 'pipe'] });
const pending = new Map(); const responses = []; let buffer = ''; let sequence = 0;
let stderr = ''; child.stderr.on('data', (d) => { stderr = (stderr + d.toString()).slice(-4096); });
function rejectAll(e) { for (const p of pending.values()) { clearTimeout(p.timer); p.reject(e); } pending.clear(); }
child.on('error', rejectAll); child.on('exit', () => rejectAll(Error('provider exited before reply')));
child.stdout.on('data', (d) => {
  buffer += d.toString();
  if (Buffer.byteLength(buffer) > 65536) { rejectAll(Error('probe output limit')); child.kill(); return; }
  for (;;) {
    const i = buffer.indexOf('\n'); if (i < 0) break;
    const text = buffer.slice(0, i); buffer = buffer.slice(i + 1);
    try {
      const reply = JSON.parse(text); const job = pending.get(reply.id);
      if (reply.jsonrpc !== '2.0' || !job) throw Error('invalid protocol reply');
      clearTimeout(job.timer); pending.delete(reply.id); responses.push(reply); job.resolve(reply);
    } catch (e) { rejectAll(e); child.kill(); }
  }
});
function rpc(method, params) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => { pending.delete(id); reject(Error('probe reply deadline')); child.kill(); }, 3000);
    pending.set(id, { resolve, reject, timer });
    child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
  });
}
const checks = []; const assert = (name, ok) => { if (!ok) throw Error(name); checks.push(name); };
async function main() {
  try {
    const init = await rpc('initialize', { protocolVersion: '1.0', client: { name: 'compatibility-probe', version: '1.0' } });
    const tool = init.result.tools[0];
    assert('initialize major1 exact data-transform declaration', init.result.protocolVersion === '1.0' && init.result.tools.length === 1 &&
      tool.name === 'inspect' && tool.sideEffect === 'NONE' && tool.supportsCancellation === true && JSON.stringify(tool.capabilities) === '["data-transform"]');
    const inspect = async (args) => (await rpc('tools/call', { name: 'inspect', arguments: args })).result;
    const text = Buffer.from('Android 上的独立工具\nsecond line\n');
    const binary = Buffer.from([0, 1, 127, 128, 255]);
    for (const [name, bytes, utf8, lines] of [['UTF8', text, true, 2], ['binary', binary, false, null]]) {
      const r = await inspect({ base64: bytes.toString('base64') });
      assert(name + ' hash/bytes/encoding', r.ok === true && r.data.bytes === bytes.length && r.data.sha256 === crypto.createHash('sha256').update(bytes).digest('hex') && r.data.utf8 === utf8 && r.data.lineCount === lines);
    }
    const bad = await inspect({ base64: '!!!!' }); assert('malformed base64 rejected', bad.ok === false && bad.error.code === 'INVALID_INPUT');
    const unknown = await inspect({ base64: '', command: 'id' }); assert('command property rejected', unknown.ok === false && unknown.error.code === 'INVALID_INPUT');
    const max = Buffer.alloc(16384, 65); const accepted = await inspect({ base64: max.toString('base64') });
    assert('exact 16KiB boundary accepted', accepted.ok === true && accepted.data.bytes === max.length && accepted.data.sha256 === crypto.createHash('sha256').update(max).digest('hex'));
    const large = await inspect({ base64: Buffer.alloc(16385).toString('base64') }); assert('over 16KiB rejected', large.ok === false && large.error.code === 'INPUT_LIMIT');
    const mcp = await rpc('tools/list', {}); assert('MCP method is not local-provider method', mcp.error?.code === -32600 && !mcp.result);
    console.log(JSON.stringify({ verdict: 'PASS', node: process.version,
      providerSha256: crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'), checks, responses, stderr,
      scope: 'independent Local Tool Protocol process only; no model or product Gateway/dispatcher proof' }, null, 2));
  } finally {
    rejectAll(Error('probe closing'));
    child.stdin.end(); child.kill();
    await new Promise((resolve) => {
      if (child.exitCode !== null || child.signalCode !== null) return resolve();
      const timer = setTimeout(() => { child.kill('SIGKILL'); resolve(); }, 500);
      child.once('exit', () => { clearTimeout(timer); resolve(); });
    });
  }
}
main().catch((e) => { console.error(e.message); process.exitCode = 1; });
