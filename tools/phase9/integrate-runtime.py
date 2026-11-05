"""One-time source merge of the pinned runtime5 handoff onto Phase8 repairs."""
from pathlib import Path
import hashlib, json

ROOT = Path(__file__).resolve().parents[2]
EXPORT = ROOT.parent / 'AGENT ON ANDROID workflow' / 'export'
HANDOFF = EXPORT / 'codex-phase9-handoff'
PAYLOAD = EXPORT / 'codex-runtime-payload' / 'assets' / 'zcode-runtime'
OUT = ROOT / 'app/src/main/assets/zcode-runtime'
assert json.loads((OUT / 'runtime-manifest.json').read_text(encoding='utf-8'))['version'] == '0.16.9-runtime4', \
    'One-time runtime4 migration only. Integration is already applied; do not overwrite measured product repairs.'

def replace_once(text, old, new):
    assert text.count(old) == 1, (old[:80], text.count(old))
    return text.replace(old, new, 1)

def validate_package(package):
    for line in (package / 'SHA256SUMS.txt').read_text().splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64:
            continue
        rel = parts[1].lstrip('*')
        if rel.startswith('.mimosa/'):
            continue  # export-tool state; never part of the executable bundle
        assert hashlib.sha256((package / rel).read_bytes()).hexdigest().upper() == parts[0].upper(), rel

validate_package(HANDOFF)
validate_package(EXPORT / 'codex-runtime-payload')
gateway = (OUT / 'gateway.cjs').read_text(encoding='utf-8')
assert 'const beforeSize = ' in gateway and 'state: "verified", ref_op_id: opId' in gateway
gateway = replace_once(gateway, '  Write: "WRITE", Edit: "WRITE", ApplyPatch: "WRITE",', '''  // Phase 9 additive classes; decide() and hard-safety precedence unchanged.
  "mcp__android-host__ui_screenshot": "PRIVILEGED",
  "mcp__android-host__ui_see": "NETWORK",
  "mcp__android-host__ui_tap": "PRIVILEGED",
  Write: "WRITE", Edit: "WRITE", ApplyPatch: "WRITE",''')
gateway = replace_once(gateway, '(input.confirm || input.text)', '(input.confirm || input.text || input.label)')
(OUT / 'gateway.cjs').write_text(gateway, encoding='utf-8', newline='\n')

product = (OUT / 'bootstrap.cjs').read_text(encoding='utf-8')
up = (PAYLOAD / 'bootstrap.cjs').read_text(encoding='utf-8')
# Carry the two proven product handlers forward verbatim.
for start, end in [
    ('  if (url.pathname === "/carrier/next")', '  if (url.pathname === "/carrier/respond"'),
    ('  if (url.pathname === "/ui/render"', '  if (url.pathname === "/ui/selftest"'),
]:
    a, b = product.index(start), product.index(end, product.index(start))
    x, y = up.index(start), up.index(end, up.index(start))
    up = up[:x] + product[a:b] + up[y:]
(OUT / 'bootstrap.cjs').write_text(up, encoding='utf-8', newline='\n')
(OUT / 'vision-pipeline.cjs').write_bytes((PAYLOAD / 'vision-pipeline.cjs').read_bytes())
# Deliberately retain product ui-tree and the repaired Gateway; core/native are unchanged.
assert (OUT / 'zcode.cjs').read_bytes() == (PAYLOAD / 'zcode.cjs').read_bytes()
manifest = json.loads((PAYLOAD / 'runtime-manifest.json').read_text())
manifest['description'] = 'Route-A runtime5 receiving-product source merge; retains measured Phase8 repairs'
manifest['bridge']['endpoints'] += ['/gateway/writes', '/gateway/ui', '/ui/render', '/ui/status', '/vision/status']
manifest['bridge']['endpoints'] = sorted(set(manifest['bridge']['endpoints']))
manifest['bridgeEndpoints'] = manifest['bridge']['endpoints']
manifest['adaptations'] = ['Phase8 Gateway/hash/rollback', 'Phase8 abandoned poll cleanup', 'Phase8 emitted/raw node mapping', 'Phase9 contract closure at host boundaries']
(OUT / 'runtime-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Merged runtime5 source and retained all three Phase8 product repairs; hashes must be refreshed after boundary adaptations.')
