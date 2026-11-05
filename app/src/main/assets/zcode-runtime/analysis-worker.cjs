// Fixed, versioned analysis script. Input is a bounded snapshot on stdin;
// this worker never opens workspace files or executes caller-supplied code.
const crypto = require('node:crypto');
let input = '', bytes = 0;
process.stdin.on('data', chunk => {
  bytes += chunk.length;
  if (bytes > 1500000) { process.stderr.write('snapshot too large'); process.exit(2); }
  input += chunk;
});
process.stdin.on('end', () => {
  try {
    const request = JSON.parse(input);
    const files = request.files.map(file => {
      const data = Buffer.from(file.content, 'base64');
      const result = {path:file.path, bytes:data.length,
        sha256:crypto.createHash('sha256').update(data).digest('hex'), content:file.content,
        encoding:'base64'};
      if (request.operation === 'parse_json') {
        try { result.value = JSON.parse(data.toString('utf8')); result.valid = true; }
        catch { result.valid = false; result.error = 'INVALID_JSON'; }
      }
      return result;
    });
    const ok = files.every(file => file.valid !== false);
    process.stdout.write(JSON.stringify({ok, operation:request.operation, files}));
    process.exitCode = ok ? 0 : 3;
  } catch {
    process.stderr.write('invalid analysis snapshot'); process.exitCode = 2;
  }
});
