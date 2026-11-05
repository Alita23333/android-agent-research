"""Build a separate first-party JNI shim and package exact existing runtime libraries.
No download, binary patch, Core modification or replacement of the runtime5 manifest.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'app/build/isolated-runtime'
NATIVE = OUT / 'jniLibs/arm64-v8a'
ASSETS = OUT / 'assets'
NATIVE.mkdir(parents=True, exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)
original = ROOT / 'app/src/main/assets/zcode-runtime/payload-SHA256SUMS.txt'
sums = dict((name, digest) for digest, name in (line.split('  ', 1) for line in original.read_text().splitlines()))
names = ['libc++_shared.so', 'libz.so.1', 'libcares.so', 'libcrypto.so.3', 'libssl.so.3',
         'libicudata.so.78', 'libicuuc.so.78', 'libicui18n.so.78', 'libsqlite3.so', 'libnode.so']
rows = []
for index, name in enumerate(names):
    relative = 'jniLibs/arm64-v8a/libnode.so' if name == 'libnode.so' else 'assets/zcode-runtime/lib/' + name
    source = ROOT / 'app/src/main' / relative
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest == sums[relative], 'existing runtime payload pin mismatch'
    packaged = name if name.endswith('.so') else f'libisolated_payload_{index}.so'
    if name != 'libnode.so':  # Node already belongs to the product native source set.
        shutil.copyfile(source, NATIVE / packaged)
    rows.append(dict(name=name, packagedName=packaged, source=relative, sha256=digest))
clang = os.environ['ANDROID_CLANG']
argv = [clang, '--target=aarch64-linux-android31', '-shared', '-fPIC', '-O2', '-Wall', '-Wextra', '-Werror',
        '-Wl,-z,max-page-size=16384', '-Wl,-z,common-page-size=16384',
        str(ROOT / 'app/src/main/native/isolated_node.c'), '-ldl', '-llog', '-o', str(NATIVE / 'libisolatednode.so')]
process = subprocess.run(argv, capture_output=True)
(OUT / 'native-build.json').write_text(json.dumps(dict(argv=argv, exit=process.returncode,
    stdout=process.stdout.decode(), stderr=process.stderr.decode()), indent=2)+'\n', encoding='utf-8')
assert process.returncode == 0, 'JNI compilation failed; see app/build/isolated-runtime/native-build.json'
elf = subprocess.run([str(Path(clang).parent / 'llvm-readelf.exe'), '-l', str(NATIVE / 'libisolatednode.so')], capture_output=True, check=True).stdout
(OUT / 'shim-elf.txt').write_bytes(elf)
assert all(int(line.split()[-1], 16) >= 16384 for line in elf.decode().splitlines() if line.strip().startswith('LOAD'))
manifest = dict(version=1, node='24.18.0', libraries=rows,
    payloadManifestSha256=hashlib.sha256(original.read_bytes()).hexdigest(),
    shimSha256=hashlib.sha256((NATIVE / 'libisolatednode.so').read_bytes()).hexdigest())
(ASSETS / 'isolated-provider-runtime.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
print('Prepared exact10 runtime libraries and separate16KB JNI shim; original runtime5 manifest unchanged')
