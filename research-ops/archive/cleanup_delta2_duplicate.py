import argparse, hashlib, json, subprocess
from pathlib import Path

ROOT=Path('/home/ubuntu/lanes')
REPOS={'grad_init_metric_v1':'e9578cc154b793d0776bd982478106143b9bb0e9'}
SUB='STUDIES/delta2_sidechecks_v1/artifacts'

def audit():
    records=[]
    for lane,commit in REPOS.items():
        repo=ROOT/lane/'repo'
        actual=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
        if actual!=commit: raise ValueError('Commit drift')
        tree=subprocess.check_output(['git','-C',str(repo),'ls-tree','-r','-z',commit,'--',SUB])
        expected=set()
        for entry in tree.split(b'\0'):
            if not entry: continue
            meta,name=entry.split(b'\t',1);mode,kind,blob=meta.decode().split();name=name.decode()
            if mode not in ('100644','100755') or kind!='blob': raise ValueError('Nonregular git entry')
            path=repo/name
            if path.is_symlink() or not path.resolve().is_relative_to((repo/SUB).resolve()): raise ValueError('Path escape')
            raw=path.read_bytes();digest=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            if digest!=blob: raise ValueError('Modified file '+str(path))
            expected.add(path)
            records.append(dict(path=str(path),repository=str(repo),commit=commit,relative=name,blob=blob,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
        actual_files={p for p in (repo/SUB).rglob('*') if p.is_file() or p.is_symlink()}
        if not expected or expected!=actual_files: raise ValueError('Untracked/missing files')
    return dict(files=records,total_bytes=sum(r['bytes'] for r in records),scope='Only identical Git-tracked historical raw files in one retired source checkout; Git objects retained')

p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
if not a.apply:
    result=audit()
    with open(a.manifest,'x') as f: json.dump(result,f,indent=2)
    print(json.dumps(dict(files=len(result['files']),bytes=result['total_bytes'])))
else:
    sealed=json.loads(Path(a.manifest).read_bytes());current=audit()
    if current!=sealed: raise ValueError('Audit changed')
    # Individual files only; no recursive directory removal or computed shell commands.
    deleted=[]
    for r in sealed['files']:
        path=Path(r['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=r['sha256']: raise ValueError('File changed before delete')
        path.unlink();deleted.append(r['path'])
    with open(a.manifest+'.deleted.json','x') as f: json.dump(dict(deleted=deleted,bytes=sealed['total_bytes']),f,indent=2)
    print(json.dumps(dict(deleted=len(deleted),bytes=sealed['total_bytes'])))
