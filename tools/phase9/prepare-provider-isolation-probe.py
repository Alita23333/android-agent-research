"""Prepare a separate experiment APK from exact runtime bytes and a small first-party JNI shim."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / 'experiments/provider-isolation'
OUT = Path(os.environ.get('PROBE_EVIDENCE_DIR', ROOT / 'docs/handoff/evidence/provider-isolation1'))
OUT.mkdir(parents=True, exist_ok=True)
facade = ROOT / 'app/src/main/java/dev/alita/androidagent/execution/IsolatedProviderProcess.java'
copy = PROJECT / 'build/product-source/dev/alita/androidagent/execution/IsolatedProviderProcess.java'
copy.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(facade, copy)
assert copy.read_bytes() == facade.read_bytes()
(OUT / 'facade-source-sha256.txt').write_text(hashlib.sha256(facade.read_bytes()).hexdigest() + '\n', encoding='utf-8')
assets = PROJECT / 'build/payload/assets/libraries'
assets.mkdir(parents=True, exist_ok=True)
native = PROJECT / 'build/payload/jniLibs/arm64-v8a'
native.mkdir(parents=True, exist_ok=True)
manifest = {}
for line in (ROOT / 'app/src/main/assets/zcode-runtime/payload-SHA256SUMS.txt').read_text().splitlines():
    value, name = line.split('  ', 1)
    manifest[name] = value
names = ['libc++_shared.so', 'libz.so.1', 'libcares.so', 'libcrypto.so.3', 'libssl.so.3',
         'libicudata.so.78', 'libicuuc.so.78', 'libicui18n.so.78', 'libsqlite3.so', 'libnode.so']
rows = []
for index, name in enumerate(names):
    key = 'jniLibs/arm64-v8a/libnode.so' if name == 'libnode.so' else 'assets/zcode-runtime/lib/' + name
    source = ROOT / 'app/src/main' / key
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert manifest[key] == digest
    # PackageManager extracts .so files into the APK native-library directory. Logical ELF
    # SONAME/DT_NEEDED and all bytes remain unchanged; the FD loader supplies original names.
    alias = 'libprovider_payload_' + str(index) + '.so'
    # Libraries without SONAME (notably libsqlite3.so) must retain their actual basename.
    packaged = name if name.endswith('.so') else alias
    if packaged != alias:
        (native / alias).unlink(missing_ok=True)
    shutil.copyfile(source, native / packaged)
    (assets / name).unlink(missing_ok=True)  # exact locally generated file, never production assets
    rows.append(dict(name=name, packagedName=packaged, sha256=digest, source=key))
data = dict(libraries=rows, source='Existing validated runtime5 payload; no binary patch', node='24.18.0', packaging='APK native-library files via read-only Binder FDs')
(assets.parent / 'payload-identity.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
clang = os.environ['ANDROID_CLANG']
source = PROJECT / 'src/main/native/node_probe.c'
argv = [clang, '--target=aarch64-linux-android31', '-shared', '-fPIC', '-O2', '-Wall', '-Wextra', '-Werror',
        '-Wl,-z,max-page-size=16384', '-Wl,-z,common-page-size=16384', str(source), '-ldl', '-o', str(native / 'libnodeprobe.so')]
p = subprocess.run(argv, capture_output=True)
(OUT / 'native-build.json').write_text(json.dumps(dict(argv=argv, exit=p.returncode,
    stdout=p.stdout.decode(), stderr=p.stderr.decode()), indent=2) + '\n', encoding='utf-8')
assert p.returncode == 0, 'JNI shim compilation failed; raw log retained'
tool = Path(clang).parent / 'llvm-readelf.exe'
readelf = subprocess.run([str(tool), '-l', str(native / 'libnodeprobe.so')], capture_output=True, check=True)
(OUT / 'shim-elf.txt').write_bytes(readelf.stdout)
(OUT / 'payload-identity.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
print('Prepared exact runtime libraries and separate JNI probe shim; no production source changed')
