"""Restore reviewed component bytes, pinned to immutable commits; never overwrite different data."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,shutil,subprocess,tempfile

ROOT=Path(__file__).resolve().parents[1]
def run(*args,cwd=None):return subprocess.check_output(['git',*args],cwd=cwd)
def relative(value):
 p=PurePosixPath(value)
 if p.is_absolute() or '..' in p.parts or '\\' in value or ':' in value:raise ValueError('Invalid archive path')
 return Path(*p.parts)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--destination',type=Path,default=ROOT);ap.add_argument('--local-components',type=Path)
 args=ap.parse_args();dest=args.destination.resolve(strict=True)
 lock=json.loads((ROOT/'components.lock.json').read_text('utf-8'));assert lock['schemaVersion']==1
 with tempfile.TemporaryDirectory(prefix='agent-components-') as temp:
  restored=0
  for c in lock['components']:
   assert c['repository']=='https://github.com/Alita23333/'+c['name']+'.git'
   if args.local_components:repo=args.local_components/c['name']
   else:
    repo=Path(temp)/c['name'];subprocess.check_call(['git','clone','--quiet','--no-checkout','--depth','1','--branch',c['tag'],c['repository'],str(repo)])
   assert run('rev-parse','HEAD',cwd=repo).decode().strip()==c['commit'],'Component commit changed'
   source_map=run('show',c['commit']+':SOURCE_MAP.json',cwd=repo)
   assert hashlib.sha256(source_map).hexdigest()==c['sourceMapSha256']
   for row in c['restore']:
    relative(row['sourcePath']);target=dest/relative(row['productPath'])
    assert target.resolve().is_relative_to(dest),'Destination escaped'
    data=run('show',c['commit']+':'+row['sourcePath'],cwd=repo)
    assert hashlib.sha256(data).hexdigest()==row['sha256']
    if target.exists():assert target.is_file() and target.read_bytes()==data,'Different existing file: '+row['productPath']
    else:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    restored+=1
  print('Verified/restored',restored,'component source files from',len(lock['components']),'pinned commits')
if __name__=='__main__':main()
