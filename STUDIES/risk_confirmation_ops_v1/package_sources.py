"""Package exact tracked study/ops bytes only; older dependencies stay hash-bound."""
import argparse,hashlib,json,shutil,subprocess,tarfile
from pathlib import Path
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def package(study_repo,ops_repo,out):
    out=Path(out);out.mkdir(exist_ok=False);files={};commits={}
    for repo,directory in ((Path(study_repo),'STUDIES/fresh_risk_confirmation_v1'),(Path(ops_repo),'STUDIES/risk_confirmation_ops_v1')):
        commits[str(repo)]=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo).decode().strip()
        for name in filter(None,subprocess.check_output(['git','ls-files','-z','--',directory],cwd=repo).decode().split('\0')):
            source=repo/name
            if source.stat().st_size>2*1024**2 or source.suffix not in ('.py','.md','.json','.sha256') and source.name!='.gitattributes':raise ValueError('Unexpected source payload '+name)
            if hashlib.sha256(subprocess.check_output(['git','show','HEAD:'+name],cwd=repo)).hexdigest()!=sha(source):raise ValueError('Uncommitted/normalized source '+name)
            target=out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);files[name]=sha(target)
    with (out/'BUNDLE-MANIFEST.json').open('x') as f:json.dump(dict(scope='Source and metadata only, no acquired market values or generated study outcomes',files=files,source_commits=commits),f,indent=2);f.write('\n')
    archive=out.with_suffix('.tar.gz')
    with tarfile.open(archive,'x:gz') as tf:
        for name in sorted(files):tf.add(out/name,arcname=name)
        tf.add(out/'BUNDLE-MANIFEST.json',arcname='BUNDLE-MANIFEST.json')
    print(json.dumps(dict(files=len(files),archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive))))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study-repo',required=True);p.add_argument('--ops-repo',required=True);p.add_argument('--out',required=True);a=p.parse_args();package(a.study_repo,a.ops_repo,a.out)
