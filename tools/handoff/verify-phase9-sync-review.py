"""Read-only upstream ZIP review; exports metadata only, never credentials."""
from pathlib import Path
import hashlib
import json
import re
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ZIP = ROOT.parent / 'AGENT ON ANDROID workflow/export/codex-phase9-sync-handoff.zip'
PREFIX = 'codex-phase9-sync-handoff/'
OUT = ROOT / 'docs/handoff/evidence/phase9-sync-review/integrity-review.json'

def sha(data):
    return hashlib.sha256(data).hexdigest().upper()

with zipfile.ZipFile(ZIP) as archive:
    assert archive.testzip() is None
    files = {i.filename[len(PREFIX):]: archive.read(i) for i in archive.infolist()
             if not i.is_dir() and i.filename.startswith(PREFIX)}
    manifest_results = []
    for name in ['SHA256SUMS.txt', 'runtime-payload/SHA256SUMS.txt']:
        base = name.rsplit('/', 1)[0] + '/' if '/' in name else ''
        covered, mismatches = set(), []
        for line in files[name].decode('utf-8-sig').splitlines():
            if not line.strip() or line.startswith('#'):
                continue
            digest, relative = line.split(None, 1)
            relative = relative.lstrip('*').replace('\\', '/')
            key = base + relative
            covered.add(key)
            if key not in files or sha(files[key]) != digest.upper():
                mismatches.append(key)
        manifest_results.append({'file': name, 'sha256': sha(files[name]),
            'entries': len(covered), 'mismatches': mismatches,
            'unlisted': sorted(k for k in files if k.startswith(base)
                               and k != name and k not in covered)})
    comparisons = []
    source_mirrors = []
    for name, data in files.items():
        if name.startswith('source/runtime/'):
            filename = name.rsplit('/', 1)[1]
            payload = 'runtime-payload/assets/zcode-runtime/' + filename
            shim = 'spike/poc-app/app/src/main/assets/runtime/' + filename
            same = files[payload] == files[shim] == data
            assert same, 'source/payload/test mirror mismatch: ' + filename
            source_mirrors.append({'file': filename, 'byte_equal': same, 'sha256': sha(data)})
    for name, data in files.items():
        if name.startswith('runtime-payload/assets/') or name.startswith('runtime-payload/jniLibs/'):
            relative = name.removeprefix('runtime-payload/')
            product = ROOT / 'app/src/main' / relative
            comparisons.append({'file': relative, 'sha256': sha(data),
                'product_exists': product.is_file(),
                'byte_equal': product.is_file() and product.read_bytes() == data})
    elves = []
    for name, data in files.items():
        if not name.startswith('runtime-payload/') or data[:4] != b'\x7fELF':
            continue
        assert data[4:6] == bytes([2, 1]), 'expected ELF64 little endian'
        phoff = struct.unpack_from('<Q', data, 32)[0]
        entsize, count = struct.unpack_from('<HH', data, 54)
        loads = []
        for i in range(count):
            entry = phoff + i * entsize
            typ, flags, offset, vaddr, paddr, size, memsize, align = struct.unpack_from('<IIQQQQQQ', data, entry)
            if typ == 1:
                loads.append({'offset': offset, 'vaddr': vaddr, 'alignment': align,
                    'static_16kb_ok': align >= 16384 and offset % 16384 == vaddr % 16384})
        elves.append({'file': name, 'sha256': sha(data), 'loads': loads,
            'static_16kb_ok': bool(loads) and all(s['static_16kb_ok'] for s in loads)})
    credential_name = 'runtime-payload/test-credentials/test-provider.json'
    value = json.loads(files[credential_name])['apiKey']
    credential = {'file': credential_name, 'api_key_nonempty': bool(value),
        'credential_like_prefix': bool(re.match(r'^(sk-|AIza|eyJ)', value)),
        'validity': 'NOT_TESTED', 'value_exported': False,
        'occurrence_file_count': sum(value.encode() in data for data in files.values()) if value else 0}
    product_manifest = json.loads((ROOT/'app/src/main/assets/zcode-runtime/runtime-manifest.json').read_text())
    upstream_manifest = json.loads(files['runtime-payload/assets/zcode-runtime/runtime-manifest.json'])
    changed_fields = [k for k in sorted(set(product_manifest) | set(upstream_manifest))
                      if product_manifest.get(k) != upstream_manifest.get(k)]
    result = {'kind': 'PHASE9_SYNC_READ_ONLY_REVIEW', 'date': '2026-10-03',
        'zip_bytes': ZIP.stat().st_size, 'zip_sha256': sha(ZIP.read_bytes()),
        'zip_crc_ok': True, 'file_count': len(files), 'manifests': manifest_results,
        'source_payload_test_mirrors': source_mirrors,
        'product_payload_comparisons': comparisons, 'static_elf_checks': elves,
        'credential_audit': credential, 'manifest_changed_fields': changed_fields,
        'full_upstream_kotlin_sources_provided': False,
        'upstream_device_drivers_provided': False,
        'product_apk_sha256': sha((ROOT/'docs/handoff/evidence/phase9/final/phase9-pass.apk').read_bytes()),
        'production_changes': 0, 'device_operations': 0, 'upstream_writes': 0}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'file_count': len(files), 'manifest_matches': [m['entries'] for m in manifest_results],
        'payload_equal': sum(c['byte_equal'] for c in comparisons), 'payload_compared': len(comparisons),
        'elf_static_16kb_pass': sum(e['static_16kb_ok'] for e in elves), 'elf_total': len(elves),
        'output': str(OUT)}, ensure_ascii=False))
