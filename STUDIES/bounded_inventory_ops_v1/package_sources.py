"""Copy tracked reviewed source bytes plus pinned dependencies; never package market inputs."""
import argparse,hashlib,json,shutil,subprocess,tarfile
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def package(main,study_repo,ops_repo,out):
    main=Path(main);study_repo=Path(study_repo);ops_repo=Path(ops_repo);out=Path(out);out.mkdir(exist_ok=False)
    files={}
    for repo,directory in ((study_repo,'STUDIES/bounded_inventory_decision_v1'),(ops_repo,'STUDIES/bounded_inventory_ops_v1')):
        names=subprocess.check_output(['git','ls-files','-z','--',directory],cwd=repo).decode().split('\0')
        for name in filter(None,names):
            source=repo/name
            if source.suffix.lower() not in ('.py','.json','.md','.sha256') and source.name!='.gitattributes':raise ValueError('Unexpected package file '+name)
            if source.stat().st_size>2*1024*1024:raise ValueError('Unexpected source size '+name)
            blob=subprocess.check_output(['git','show','HEAD:'+name],cwd=repo)
            if hashlib.sha256(blob).hexdigest()!=sha(source):raise ValueError('Uncommitted or normalized source bytes '+name)
            destination=out/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination);files[name]=sha(destination)
    dependencies=json.loads((out/'STUDIES/bounded_inventory_decision_v1/DEPENDENCY-INVENTORY.json').read_bytes())
    dependencies['STUDIES/market_replication_v1/acquire.py']=sha(main/'STUDIES/market_replication_v1/acquire.py')
    for name,want in dependencies.items():
        source=main/name
        if sha(source)!=want:raise ValueError('Dependency drift '+name)
        destination=out/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination);files[name]=want
    metadata=dict(scope='Source only; no market values, draws, outcome reports, or acquired payloads',files=files,
        source_commits={str(r):subprocess.check_output(['git','rev-parse','HEAD'],cwd=r).decode().strip() for r in (study_repo,ops_repo)},transitive_acquire_sha256=dependencies['STUDIES/market_replication_v1/acquire.py'])
    with (out/'BUNDLE-MANIFEST.json').open('x') as f:json.dump(metadata,f,indent=2);f.write('\n')
    archive=out.with_suffix('.tar.gz')
    with tarfile.open(archive,'x:gz') as tf:
        for name in sorted(files):tf.add(out/name,arcname=name)
        tf.add(out/'BUNDLE-MANIFEST.json',arcname='BUNDLE-MANIFEST.json')
    print(json.dumps(dict(bundle=str(out),archive=str(archive),sha256=sha(archive),files=len(files),bytes=archive.stat().st_size)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--main',required=True);p.add_argument('--study-repo',required=True);p.add_argument('--ops-repo',required=True);p.add_argument('--out',required=True);a=p.parse_args();package(a.main,a.study_repo,a.ops_repo,a.out)
