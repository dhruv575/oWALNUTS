import hashlib,json,tarfile
from pathlib import Path
repo=Path(__file__).resolve().parents[2];study=repo/'STUDIES/usefulness_search_v1/real_counts_v1';archive=study/'training_archive01/evidence.tar.gz';receipt=json.loads((Path(__file__).parent/'real-counts-training-s3-20261030/VERIFICATION.json').read_text(encoding='utf-8-sig'));assert receipt['passed'] and hashlib.sha256(archive.read_bytes()).hexdigest()==receipt['sha256']
with tarfile.open(archive) as t:manifest=json.load(t.extractfile('MANIFEST.json'))
mapping={'reference_remote01':'/home/ubuntu/lanes/real-counts-reference-20261030','importance_remote01':'/home/ubuntu/lanes/real-counts-importance-20261030','sampler_screen_remote01':'/home/ubuntu/lanes/real-counts-sampler-screen-20261030'};files=[]
for folder,remote in mapping.items():
    prefix='study/'+folder+'/results/'
    for n,m in manifest.items():
        if n.startswith(prefix) and Path(n).name in ['DRAWS-STATS.npz','FUNCTIONALS.npz','RAW.json','DRAWS.npz','GRID.npz']:
            local=study/folder/'results'/n[len(prefix):];assert local.stat().st_size==m['bytes'] and hashlib.sha256(local.read_bytes()).hexdigest()==m['sha256'];files.append(dict(path=remote+'/results/'+n[len(prefix):],archive_member=n,**m))
assert files;out=Path(__file__).parent/'real-counts-reclaim-plan-20261030.json';assert not out.exists();result=dict(archive=receipt,allowed_roots=list(mapping.values()),files=files,total_bytes=sum(x['bytes'] for x in files),scope='Completed raw artifacts only,after all prediction and raw audits; sources,summaries and runtime dependencies retained');out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(files=len(files),bytes=result['total_bytes'])))
