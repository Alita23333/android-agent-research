// Isolated catalog fixtures only. Run as the app UID with APK-owned Node.
// No model, plugin, hook, shell child, runtime mutation or second Skill registry.
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const crypto = require('node:crypto');
const CORE_SHA = 'b1df2ef3e5bd76c4af3ecb296bc003a10d3f13191a26610bd0ba940feadad529';
const app = process.argv[2];
if (!['dev.alita.androidagent', 'dev.zcode.nodepoc'].includes(app)) throw Error('explicit assigned app required');
const root = '/data/user/0/' + app;
const runtime = root + '/files/runtime';
const hash = (bytes) => crypto.createHash('sha256').update(bytes).digest('hex');
if (hash(fs.readFileSync(runtime + '/zcode.cjs')) !== CORE_SHA) throw Error('Core identity changed');
const token = fs.readFileSync(runtime + '/bridge-token', 'utf8').trim();
function request(route, body) {
  return new Promise((resolve, reject) => {
    const bytes = body === undefined ? null : Buffer.from(JSON.stringify(body));
    const req = http.request({ host: '127.0.0.1', port: 8765, path: route,
      method: bytes ? 'POST' : 'GET', headers: { 'X-Bridge-Token': token,
        ...(bytes ? { 'Content-Type': 'application/json', 'Content-Length': bytes.length } : {}) } }, (res) => {
      const chunks = []; let count = 0;
      res.on('data', (chunk) => { count += chunk.length; if (count > 1024 * 1024) req.destroy(Error('test response limit')); else chunks.push(chunk); });
      res.on('error', reject);
      res.on('end', () => { try { if (res.statusCode !== 200) throw Error('HTTP ' + res.statusCode); resolve(JSON.parse(Buffer.concat(chunks))); } catch (e) { reject(e); } });
    });
    req.setTimeout(30000, () => req.destroy(Error('test request deadline')));
    req.on('error', reject); req.end(bytes);
  });
}
async function main() {
  const status = await request('/status');
  if (status.phase !== 'ready' || !status.workspace) throw Error('existing runtime not ready');
  const base = fs.realpathSync(status.workspace);
  const appFiles = fs.realpathSync(root + '/files');
  if (!base.startsWith(appFiles + '/workspaces/')) throw Error('workspace outside designated app workspaces');
  const cfgFile = root + '/files/.zcode/cli/config.json';
  const before = fs.readFileSync(cfgFile); const cfg = JSON.parse(before);
  if (cfg.plugins?.enabled !== false || cfg.features?.memory !== false || cfg.memory?.extractionEnabled !== false) throw Error('kill switches changed');
  const run = Date.now().toString();
  const workspace = path.join(base, 'catalog-proof-' + run);
  fs.mkdirSync(workspace); // exclusive new nested test workspace; no existing fixture touched
  const skillRoot = path.join(workspace, '.agents/skills');
  const specs = [
    ['valid', `---\nname: valid-${run}\ndescription: Isolated catalog fixture only.\n---\nDo not execute this test skill.\n`],
    ['missing-description', `---\nname: missing-description-${run}\n---\nInvalid metadata fixture.\n`],
    ['unknown-metadata', `---\nname: unknown-${run}\ndescription: Isolated unknown metadata fixture only.\nx_future_field: preserved-test\n---\nDo not execute this test skill.\n`],
    ['android-dependency', `---\nname: dependency-${run}\ndescription: Isolated Android dependency metadata fixture only; not executable.\n---\nDo not execute this test skill.\n`],
  ];
  const inputs = [];
  for (const [dir, text] of specs) {
    const file = path.join(skillRoot, dir, 'SKILL.md');
    fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, text, { flag: 'wx' });
    inputs.push({ path: file, sha256: hash(Buffer.from(text)) });
  }
  const supplement = path.join(skillRoot, 'android-dependency/android.yaml');
  fs.writeFileSync(supplement, 'runtime: definitely-missing-fixture-runtime\nrequired_tools:\n  - absent_fixture.tool\n', { flag: 'wx' });
  inputs.push({ path: supplement, sha256: hash(fs.readFileSync(supplement)) });
  const response = await request('/rpc-wait', { method: 'skills/referenceCatalog', timeoutMs: 25000,
    params: { workspace: { workspacePath: workspace, workspaceKey: path.basename(workspace) } } });
  if (response.error || !response.result) throw Error('catalog RPC failed');
  const catalog = response.result; const names = new Set(catalog.skills.map((s) => s.name));
  const checks = {
    workspaceAuthority: catalog.authority === 'workspace',
    validSkillDiscovered: names.has('valid-' + run),
    missingDescriptionRejected: !names.has('missing-description-' + run),
    unknownMetadataDoesNotReject: names.has('unknown-' + run),
    androidSupplementNotEnforcedByCore: names.has('dependency-' + run),
    inputFilesUnchanged: inputs.every((i) => hash(fs.readFileSync(i.path)) === i.sha256),
    safetyConfigUnchanged: fs.readFileSync(cfgFile).equals(before),
  };
  const verdict = Object.values(checks).every(Boolean) ? 'PASS' : 'FAIL';
  const fixtureCatalog = { authority: catalog.authority,
    skills: catalog.skills.filter((s) => s.path.startsWith(skillRoot + '/')) };
  console.log(JSON.stringify({ verdict, scope: 'native Core catalog compatibility; no model or production Skill management acceptance',
    app, node: process.version, coreSha256: CORE_SHA, workspace, inputs, catalog: fixtureCatalog, checks,
    dependencyGap: 'Core catalog exposes Android-supplement dependency fixture as enabled. Host dependency admission is still needed before a product installer exposes imported skills.' }, null, 2));
  process.exitCode = verdict === 'PASS' ? 0 : 1;
}
main().catch((e) => { console.error(e.message); process.exitCode = 1; });
