from pathlib import Path
import hashlib
root = Path(__file__).resolve().parents[2] / 'app/src/main'
manifest = root / 'assets/zcode-runtime/payload-SHA256SUMS.txt'
paths = [line.split(maxsplit=1)[1].lstrip('*') for line in manifest.read_text().splitlines() if len(line.split(maxsplit=1)) == 2]
paths.append('assets/zcode-runtime/vision-pipeline.cjs')
manifest.write_text(''.join(hashlib.sha256((root/path).read_bytes()).hexdigest() + '  ' + path + '\n' for path in sorted(set(paths))), encoding='utf-8')
print('SHA-256 entries refreshed:', len(set(paths)))
