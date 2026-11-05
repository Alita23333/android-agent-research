// Review-only fault injection over the supplied source. No runtime is launched,
// no production config is written, and no device/network operation occurs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../../docs/handoff/upstream-review/phase9-sync-97f7ef8a/codex-phase9-sync-handoff');
const source = fs.readFileSync(path.join(root, 'source/runtime/bootstrap.cjs'), 'utf8');
const start = source.indexOf('  try {\n    const cfgDir = path.join(ROOT, ".zcode", "cli");');
const end = source.indexOf('  // carrier endpoint discovery file', start);
assert.ok(start > 0 && end > start, 'exact source boot-hardening section must exist');
const logs = [];
const context = {
  ROOT: '/review-only', CARRIER_OFF: false, RUNTIME: '/review-only/runtime',
  process: { execPath: '/review-only/node' }, path,
  loadSearchConfig: () => null,
  log: line => logs.push(line),
  fs: {
    mkdirSync: () => {},
    readFileSync: () => '{"plugins":{"enabled":true}}',
    writeFileSync: () => { throw new Error('fixture config write failure'); },
  },
};
vm.runInNewContext(source.slice(start, end) + '\ncontinuedPastHardening = true;', context);
assert.equal(context.continuedPastHardening, true);
assert.ok(logs.some(line => line.includes('config-disable failed:')));
const permissionMethod = source.includes('m.method === "interaction/requestPermission"');
assert.equal(permissionMethod, true);
assert.equal(source.includes('m.method === "permission/request"'), false);
const existenceSwitch = source.includes('fs.existsSync(path.join(ROOT, "carrier.disabled"))');
assert.equal(existenceSwitch, true);
const { Gateway } = require(path.join(root, 'source/runtime/gateway.cjs'));
const arbitraryMethodAllowed = new Gateway().rpcGuard('review/unknown-method', {}).allowed;
assert.equal(arbitraryMethodAllowed, true); // deny-list ceiling, not an allow-list
const visionSource = fs.readFileSync(path.join(root, 'source/runtime/vision-pipeline.cjs'), 'utf8');
const loaderStart = visionSource.indexOf('function loadVisionConfig(');
const loaderEnd = visionSource.indexOf('// §4.4', loaderStart);
const loaderContext = {
  path, fs: { readFileSync: () => JSON.stringify({ enabled: true,
    providerId: 'fixture', modelId: 'fixture', apiKey: 'fixture-only',
    baseUrl: 'https://example.com/v1', unknownReviewField: true }) },
};
vm.runInNewContext(visionSource.slice(loaderStart, loaderEnd) +
  '\nloaded = loadVisionConfig("/review-only");', loaderContext);
assert.equal(loaderContext.loaded.unknownReviewField, true);
console.log(JSON.stringify({
  kind: 'REPRODUCED_EXISTING_CONTRACT_GAP',
  source: 'source/runtime/bootstrap.cjs',
  permissionMethod: 'interaction/requestPermission',
  carrierDisabledControl: 'existence check, not parseable positive-enable document',
  configWriteFailureStopsBoot: false,
  continuedPastHardening: context.continuedPastHardening,
  rpcUnknownMethodAllowed: arbitraryMethodAllowed,
  visionConfigUnknownFieldRejected: false,
  scope: 'isolated source section only; no full Core/device boot attempted',
}, null, 2));
