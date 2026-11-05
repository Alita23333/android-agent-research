// Independent Android Local Tool Protocol provider. No MCP/ZCode messages,
// filesystem paths, shell commands, child processes, network or install hooks.
const crypto = require('node:crypto');
const { TextDecoder } = require('node:util');
const definition = {
  name: 'inspect', version: '1.0.0',
  description: 'Compute SHA-256, bytes and UTF-8 line count for explicit base64 data (at most 16 KiB). No file or command access. The Android host returns a verified digest report artifact.',
  inputSchema: { type: 'object', additionalProperties: false, required: ['base64'],
    properties: { base64: { type: 'string', maxLength: 21848 } } },
  capabilities: ['data-transform'], sideEffect: 'NONE', supportsCancellation: true,
};
let initialized = false;
function handle(message) {
  if (message.jsonrpc !== '2.0' || !Number.isSafeInteger(message.id)) throw Error('invalid request envelope');
  const params = message.params || {};
  if (message.method === 'initialize') {
    if (params.protocolVersion !== '1.0') return { protocolVersion: '1.0', tools: [] };
    initialized = true;
    return { protocolVersion: '1.0', tools: [definition] };
  }
  if (!initialized || message.method !== 'tools/call' || params.name !== 'inspect') throw Error('unsupported request');
  const args = params.arguments || {};
  const input = args.base64;
  if (Object.keys(args).some((k) => k !== 'base64') || typeof input !== 'string' || input.length > 21848 ||
      !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(input)) {
    return { ok: false, error: { code: 'INVALID_INPUT', message: 'Requires canonical base64 data only', retryable: false } };
  }
  const data = Buffer.from(input, 'base64');
  if (data.length > 16384 || data.toString('base64') !== input) return { ok: false,
    error: { code: 'INPUT_LIMIT', message: 'Explicit input exceeds 16 KiB or is not canonical', retryable: false } };
  let utf8 = true; let lineCount = null;
  try { const text = new TextDecoder('utf-8', { fatal: true }).decode(data); lineCount = text === '' ? 0 : text.split('\n').length - (text.endsWith('\n') ? 1 : 0); }
  catch { utf8 = false; }
  return { ok: true, data: { bytes: data.length, sha256: crypto.createHash('sha256').update(data).digest('hex'), utf8, lineCount } };
}
let pending = Buffer.alloc(0);
process.stdin.on('data', (chunk) => {
  pending = Buffer.concat([pending, chunk]);
  if (pending.length > 65536) { process.stderr.write('provider input limit\n'); process.exitCode = 2; process.stdin.destroy(); return; }
  let end;
  while ((end = pending.indexOf(10)) !== -1) {
    const line = pending.subarray(0, end); pending = pending.subarray(end + 1);
    let request;
    try {
      request = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(line));
      const result = handle(request);
      process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id: request.id, result }) + '\n');
    } catch {
      process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id: request?.id ?? null,
        error: { code: -32600, message: 'Invalid local request' } }) + '\n');
    }
  }
});
