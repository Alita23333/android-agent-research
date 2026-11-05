// Execute the product's actual carrier HTTP handlers in an isolated test server.
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const vm = require('node:vm');
const { spawn } = require('node:child_process');
const source = fs.readFileSync(path.resolve(__dirname, '../../app/src/main/assets/zcode-runtime/bootstrap.cjs'), 'utf8');
const start = source.indexOf('if (url.pathname === "/carrier/register"');
const end = source.indexOf('if (url.pathname === "/sessions")', start);
if (start < 0 || end < 0) throw new Error('Product carrier handlers missing');
const run = new vm.Script(`(function () { ${source.slice(start, end)} })()`);
const state = {};
const server = http.createServer((req, res) => run.runInNewContext({
  req, res, state, url: new URL(req.url, 'http://localhost'),
  send: (status, value) => { res.writeHead(status, { 'content-type': 'application/json' }); res.end(JSON.stringify(value)); },
  hostTools: [], INLINE_DISPATCH: {}, broadcast: () => {}, log: () => {},
  setTimeout, clearTimeout, process,
}));
server.listen(0, '127.0.0.1', () => {
  const child = spawn(process.execPath, [path.join(__dirname, 'carrier-artifacts-check.cjs')], {
    env: { ...process.env, SPIKE_ROOT: path.join(__dirname, 'unused-fixture'),
      SPIKE_HTTP_PORT: String(server.address().port), BRIDGE_TOKEN: 'fixture' },
    stdio: 'inherit',
  });
  child.on('exit', code => server.close(() => { process.exitCode = code || 0; }));
});
