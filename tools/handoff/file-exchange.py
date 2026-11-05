"""Versioned, immutable file handoff. No device/network/tool execution on receive."""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import shutil
import stat
import tempfile
import uuid
import zipfile

VERSION = 1
MAX_BYTES = 1024 * 1024 * 1024
ROLES = {'documentation', 'source', 'contract', 'test', 'result', 'runtime', 'notice'}
STATES = {'RECEIVED', 'ACCEPTED_FOR_REVIEW', 'NEEDS_REVISION', 'INTEGRATED'}

def digest(data):
    return hashlib.sha256(data).hexdigest().upper()

def stamp():
    return datetime.now(timezone.utc).isoformat()

def identifier(value):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,95}', value):
        raise ValueError('invalid package ID')
    return value

def safe_path(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError('unsafe path')
    p = PurePosixPath(value)
    if p.is_absolute() or str(p) != value or any(s in {'.', '..'} for s in p.parts):
        raise ValueError('unsafe path')
    for part in p.parts:
        if part.endswith((' ', '.')) or re.search(r'[<>"|?*\x00-\x1f]', part):
            raise ValueError('unsafe Windows path')
        if re.fullmatch(r'(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\..*)?', part, re.I):
            raise ValueError('reserved Windows path')
    return value

def audit(name, data):
    parts = PurePosixPath(name).parts
    if any(p.lower() in {'.mimosa', '.git', '.zcode', 'node_modules'} for p in parts):
        raise ValueError('executor/repository state forbidden: ' + name)
    if re.search(rb'sk-[A-Za-z0-9_-]{16,}', data):
        raise ValueError('potential API credential: ' + name)
    if re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', data):
        raise ValueError('private key forbidden: ' + name)
    if re.search(rb'data:image/[^;\s]+;base64,[A-Za-z0-9+/=]{80,}', data):
        raise ValueError('embedded image bytes forbidden: ' + name)
    if name.lower().endswith(('.db', '.sqlite', '.sqlite3', '.keystore', '.jks')):
        raise ValueError('private database/key store forbidden: ' + name)
    if name.lower().endswith('.json'):
        try:
            obj = json.loads(data)
        except (ValueError, UnicodeDecodeError):
            return
        def walk(item):
            if isinstance(item, dict):
                for key, value in item.items():
                    normalized = re.sub(r'[_-]', '', key.lower())
                    if normalized in {'apikey', 'accesstoken', 'bridgetoken', 'password', 'secret', 'privatekey'}:
                        if value not in ('', None, '__REQUIRED_AT_RUNTIME__'):
                            raise ValueError('non-placeholder secret field: ' + name)
                    walk(value)
            elif isinstance(item, list):
                for value in item:
                    walk(value)
        walk(obj)

def metadata_check(meta):
    if meta.get('protocolVersion') != VERSION:
        raise ValueError('incompatible protocol version')
    identifier(meta['packageId'])
    if (meta.get('sender'), meta.get('recipient')) not in {('codex', 'zcode'), ('zcode', 'codex')}:
        raise ValueError('invalid direction')
    for key in ['scope', 'baseline', 'changeSummary']:
        if not isinstance(meta.get(key), str) or not meta[key].strip():
            raise ValueError('missing metadata: ' + key)
    if meta.get('completion') not in {'COMPLETE', 'PARTIAL'}:
        raise ValueError('missing completion')
    if not isinstance(meta.get('missingItems'), list) or not isinstance(meta.get('requiredPaths'), list):
        raise ValueError('missing requiredPaths/missingItems')
    if meta['completion'] == 'COMPLETE' and meta['missingItems']:
        raise ValueError('COMPLETE cannot have missing items')
    for name in meta['requiredPaths']:
        safe_path(name)

def publish(exchange, source, spec):
    meta = json.loads(Path(spec).read_text(encoding='utf-8-sig'))
    metadata_check(meta)
    source = Path(source).resolve()
    files = {}
    for p in sorted(source.rglob('*')):
        if p.is_symlink() or p.is_junction():
            raise ValueError('source link forbidden')
        if not p.is_file():
            continue
        name = safe_path(p.relative_to(source).as_posix())
        if name in {'PACKAGE.json', 'SHA256SUMS.txt'}:
            raise ValueError('reserved metadata name')
        data = p.read_bytes()
        audit(name, data)
        files[name] = data
    if not files or len(files) > 10000 or sum(map(len, files.values())) > MAX_BYTES:
        raise ValueError('empty/oversize input')
    if len({n.casefold() for n in files}) != len(files):
        raise ValueError('case collision')
    missing = sorted(set(meta['requiredPaths']) - set(files))
    if missing and (meta['completion'] != 'PARTIAL' or not meta['missingItems']):
        raise ValueError('undeclared missing required paths')
    rolemap = meta.pop('fileRoles', {})
    if set(rolemap) != set(files) or any(v not in ROLES for v in rolemap.values()):
        raise ValueError('every actual file must have an explicit valid role')
    meta['createdAt'] = stamp()
    meta['payload'] = [{'path': n, 'sha256': digest(data), 'size': len(data), 'role': rolemap[n]}
                       for n, data in files.items()]
    package = (json.dumps(meta, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    audit('PACKAGE.json', package)
    files['PACKAGE.json'] = package
    sums = ''.join(f'{digest(data)}  {n}\n' for n, data in sorted(files.items())).encode()
    files['SHA256SUMS.txt'] = sums
    lane = Path(exchange).resolve() / f'{meta["sender"]}-to-{meta["recipient"]}'
    lane.mkdir(parents=True, exist_ok=True)
    destination = lane / meta['packageId']
    if destination.exists():
        raise ValueError('immutable package already exists; use a new ID')
    temporary = Path(tempfile.mkdtemp(prefix='_staging-', dir=lane))
    try:
        with zipfile.ZipFile(temporary/'bundle.zip', 'w', zipfile.ZIP_DEFLATED) as z:
            for n, data in sorted(files.items()):
                z.writestr(n, data)
        ready = {'protocolVersion': VERSION, 'packageId': meta['packageId'],
                 'sender': meta['sender'], 'recipient': meta['recipient'],
                 'archive': 'bundle.zip', 'archiveSha256': digest((temporary/'bundle.zip').read_bytes()),
                 'archiveBytes': (temporary/'bundle.zip').stat().st_size,
                 'packageManifestSha256': digest(package), 'shaManifestSha256': digest(sums)}
        (temporary/'READY.json').write_text(json.dumps(ready, indent=2)+'\n', encoding='utf-8')
        verify(temporary)  # verify before atomic publication
        temporary.rename(destination)
        return destination
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)  # exact locally-created staging dir only

def verify(directory):
    directory = Path(directory)
    if directory.is_symlink() or directory.is_junction():
        raise ValueError('delivery link forbidden')
    if {p.name for p in directory.iterdir()} != {'bundle.zip', 'READY.json'}:
        raise ValueError('delivery must contain exactly bundle.zip and READY.json')
    if any(p.is_symlink() or p.is_junction() for p in directory.iterdir()):
        raise ValueError('delivery child link forbidden')
    ready = json.loads((directory/'READY.json').read_text(encoding='utf-8-sig'))
    if ready.get('protocolVersion') != VERSION or ready.get('archive') != 'bundle.zip':
        raise ValueError('invalid readiness/version')
    if not (0 < (directory/'bundle.zip').stat().st_size <= MAX_BYTES):
        raise ValueError('archive size limit')
    data = (directory/'bundle.zip').read_bytes()
    if digest(data) != ready['archiveSha256'] or len(data) != ready['archiveBytes']:
        raise ValueError('archive checksum/size mismatch')
    with zipfile.ZipFile(directory/'bundle.zip') as z:
        info = z.infolist()
        if len(info) > 10002 or sum(i.file_size for i in info) > MAX_BYTES:
            raise ValueError('expanded size/count limit')
        names = [safe_path(i.filename) for i in info]
        if len(set(n.casefold() for n in names)) != len(names):
            raise ValueError('duplicate/case-colliding ZIP names')
        if any(i.is_dir() or stat.S_ISLNK(i.external_attr >> 16) for i in info):
            raise ValueError('non-file ZIP entry')
        files = {n: z.read(n) for n in names}  # also checks CRC
    package = files['PACKAGE.json']
    audit('PACKAGE.json', package)
    meta = json.loads(package)
    metadata_check(meta)
    for key in ['packageId', 'sender', 'recipient']:
        if ready[key] != meta[key]:
            raise ValueError('readiness identity mismatch')
    if digest(package) != ready['packageManifestSha256'] or digest(files['SHA256SUMS.txt']) != ready['shaManifestSha256']:
        raise ValueError('manifest hash mismatch')
    entries = meta['payload']
    paths = [safe_path(e['path']) for e in entries]
    if len(paths) != len(set(paths)) or set(files) != set(paths) | {'PACKAGE.json', 'SHA256SUMS.txt'}:
        raise ValueError('unlisted/missing payload file')
    expected_sums = ''.join(f'{digest(d)}  {n}\n' for n, d in sorted(files.items()) if n != 'SHA256SUMS.txt').encode()
    if files['SHA256SUMS.txt'] != expected_sums:
        raise ValueError('SHA manifest must exactly cover every file except itself')
    for entry in entries:
        name = entry['path']
        if entry['role'] not in ROLES or entry['size'] != len(files[name]) or entry['sha256'] != digest(files[name]):
            raise ValueError('payload metadata mismatch: ' + name)
        audit(name, files[name])
    missing = sorted(set(meta['requiredPaths']) - set(paths))
    if missing and (meta['completion'] != 'PARTIAL' or not meta['missingItems']):
        raise ValueError('undeclared missing required paths')
    return {'protocolVersion': VERSION, 'packageId': meta['packageId'], 'sender': meta['sender'],
            'recipient': meta['recipient'], 'archiveSha256': ready['archiveSha256'],
            'fileCount': len(paths), 'completion': meta['completion'],
            'missingPaths': missing, 'missingItems': meta['missingItems'],
            'scope': meta['scope'], 'integrity': 'PASS', 'contentReview': 'NOT_PERFORMED'}

def receipt(exchange, directory, recipient, state, note):
    if state not in STATES or not note.strip():
        raise ValueError('invalid state or empty note')
    result = verify(directory)
    if result['recipient'] != recipient:
        raise ValueError('cannot acknowledge on behalf of another recipient')
    result.update({'state': state, 'note': note, 'recordedAt': stamp()})
    if state == 'RECEIVED':
        result['note'] += ' [Integrity only; no execution or integration authorization.]'
    elif state == 'INTEGRATED':
        result['contentReview'] = 'HUMAN_REPORTED_INTEGRATED; evidence must be linked in note'
    else:
        result['contentReview'] = 'RECIPIENT_REPORTED; see note'
    dest = Path(exchange)/'receipts'/recipient
    dest.mkdir(parents=True, exist_ok=True)
    output = dest/(result['packageId']+'-'+uuid.uuid4().hex+'.json')
    with output.open('x', encoding='utf-8') as f:
        f.write(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    return output

def discover(exchange, recipient):
    if recipient not in {'codex', 'zcode'}:
        raise ValueError('invalid recipient')
    exchange = Path(exchange).resolve()
    sender = 'zcode' if recipient == 'codex' else 'codex'
    lane = exchange / f'{sender}-to-{recipient}'
    deliveries = []
    if not lane.exists():
        return {'recipient': recipient, 'deliveries': [], 'pendingReview': 0}
    for folder in sorted(lane.iterdir()):
        if folder.name.startswith('_') or not folder.is_dir() or not (folder/'READY.json').exists():
            continue
        try:
            result = verify(folder)
            if result['sender'] != sender or result['recipient'] != recipient or result['packageId'] != folder.name:
                raise ValueError('lane identity mismatch')
            received = False
            resolution = None
            for p in (exchange/'receipts'/recipient).glob(folder.name+'-*.json'):
                try:
                    r = json.loads(p.read_text(encoding='utf-8-sig'))
                    if r.get('packageId') != result['packageId'] or r.get('archiveSha256') != result['archiveSha256'] or r.get('recipient') != recipient:
                        continue
                    received = True
                    if r.get('state') in {'NEEDS_REVISION', 'INTEGRATED'}:
                        resolution = r.get('state')
                except (ValueError, OSError):
                    continue
            if not received:
                receipt(exchange, folder, recipient, 'RECEIVED', 'Automatically discovered and integrity-checked; awaiting content review.')
            result.update({'packageDirectory': str(folder), 'newlyReceived': not received,
                           'resolution': resolution, 'needsReview': resolution is None})
            deliveries.append(result)
        except Exception as error:
            deliveries.append({'packageDirectory': str(folder), 'status': 'REJECTED',
                               'errorType': type(error).__name__, 'needsReview': False})
    return {'recipient': recipient, 'deliveries': deliveries,
            'pendingReview': sum(d.get('needsReview', False) for d in deliveries),
            'rejectedCount': sum(d.get('status') == 'REJECTED' for d in deliveries)}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('publish')
    p.add_argument('--exchange', required=True); p.add_argument('--source', required=True); p.add_argument('--spec', required=True)
    p = sub.add_parser('verify'); p.add_argument('--package', required=True)
    p = sub.add_parser('discover')
    p.add_argument('--exchange', required=True); p.add_argument('--recipient', required=True, choices=['codex', 'zcode'])
    p = sub.add_parser('receipt')
    p.add_argument('--exchange', required=True); p.add_argument('--package', required=True)
    p.add_argument('--recipient', required=True, choices=['codex', 'zcode'])
    p.add_argument('--state', required=True, choices=sorted(STATES)); p.add_argument('--note', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'publish':
            print(publish(args.exchange, args.source, args.spec))
        elif args.command == 'verify':
            print(json.dumps(verify(args.package), ensure_ascii=False, indent=2))
        elif args.command == 'discover':
            print(json.dumps(discover(args.exchange, args.recipient), ensure_ascii=False, indent=2))
        else:
            print(receipt(args.exchange, args.package, args.recipient, args.state, args.note))
    except Exception as error:
        # Do not render invalid file contents, which could include credentials.
        print(json.dumps({'status': 'REJECTED', 'errorType': type(error).__name__}, ensure_ascii=False))
        raise SystemExit(2)
