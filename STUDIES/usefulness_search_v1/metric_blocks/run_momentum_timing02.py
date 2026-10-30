import hashlib,json,sys,shutil,tomllib
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'momentum_pool_timing02';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
assert json.loads((l/'momentum_pool_test02/SUMMARY.json').read_text())['passed']
builds=[json.loads((l/'cold_recycling_build03/SUMMARY.json').read_text())['rows'][0],json.loads((l/'momentum_pool_build01/SUMMARY.json').read_text())['rows'][0]]
for b in builds:assert hashlib.sha256(Path(b['binary']).read_bytes()).hexdigest()==b['binary_sha256']
def registry(folder):return sorted((q['name'],q['version'],q.get('checksum')) for q in tomllib.loads((p/folder/'Cargo.lock').read_text())['package'] if 'source' in q)
assert registry('cold_wal_original_runner')==registry('momentum_pool_runner')
files=[Path(__file__),p/'momentum_timing_worker02.py',p/'MOMENTUM-POOL-TIMING-REPAIR.md',l/'momentum_pool_source01/src/kernel.rs'];hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files};(r/'SOURCE-SNAPSHOT.json').write_text(json.dumps(dict(files=hashes,builds=builds),indent=2))
targets=['banana_direct','banana_latent','funnel'];rng=np.random.default_rng(943200001);jobs=[(ti,i) for ti in range(3) for i in range(20)];rng.shuffle(jobs);rows=[]
for ti,i in jobs:
    target=targets[ti];spec=json.loads((l/'cold_recycling_test01'/f'{target}-diagonal-original/INPUT.json').read_text())
    for ci,c in enumerate(spec['chains']):c['seed']=943100001+10000*ti+4*i+ci
    order=rng.permutation(2).tolist();outputs={};times={};sampler={}
    for arm in order:
        assert shutil.disk_usage(r).free>1024**3;folder=r/f'{target}-{i:02d}-{arm}';folder.mkdir();(folder/'INPUT.json').write_text(json.dumps(spec));command=[sys.executable,str(p/'momentum_timing_worker02.py'),builds[arm]['binary'],str(folder/'INPUT.json'),str(folder/'RAW.json'),str(folder/'TIME.json')]
        result=execute(command,str(r),190,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(result,indent=2));assert result['exit_code']==0 and result['group_drained'];outputs[arm]=json.loads((folder/'RAW.json').read_text());times[arm]=json.loads((folder/'TIME.json').read_text())['seconds'];sampler[arm]=sum(c['seconds'] for c in outputs[arm]['chains'])
    assert len(outputs[0]['chains'])==len(outputs[1]['chains'])==4
    for a,b in zip(outputs[0]['chains'],outputs[1]['chains']):
        for k in a:
            if k!='seconds':assert a[k]==b[k],(target,i,k)
    rows.append(dict(target=target,replicate=i,order=order,seconds=times,sampler_seconds=sampler,exact_parity=True));(r/'PROGRESS.json').write_text(json.dumps(rows,indent=2));print(json.dumps(dict(completed=len(rows),target=target,replicate=i,speedup=times[0]/times[1])),flush=True)
summary=[]
for ti,target in enumerate(targets):
    subset=[x for x in rows if x['target']==target];out=dict(target=target,pairs=len(subset))
    for key in ['seconds','sampler_seconds']:
        logs=np.log([x[key][0]/x[key][1] for x in subset]);boot=np.random.default_rng(943300001+ti).choice(logs,(10000,len(logs)),replace=True).mean(axis=1);out[key]=dict(speedup=float(np.exp(logs.mean())),interval=np.exp(np.quantile(boot,[.025,.975])).tolist())
    summary.append(out)
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in hashes.items())
passed=summary[0]['seconds']['interval'][0]>1.05 and all(x['seconds']['interval'][0]>.95 for x in summary[1:]);(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,screen_passed=passed,rows=summary,exact_parity=True),indent=2));print(json.dumps(summary),flush=True)
