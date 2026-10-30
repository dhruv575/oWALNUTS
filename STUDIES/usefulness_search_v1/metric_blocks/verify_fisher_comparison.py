import gzip,hashlib,json
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parent;parent=root.parent/'broad01'
s=json.loads((root/'SUMMARY.json').read_text());assert s['unchanged'] and len(s['rows'])==24
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in s['inputs'].items())
durable=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence/fishercompare01')
jobs=0;stages=0
for sup in (root/'runs').glob('*/SUPERVISION.json'):
    r=json.loads(sup.read_text());assert r['group_drained'];jobs+=1;folder=sup.parent
    manifest=json.loads((durable/folder.name/'MANIFEST.json').read_text())
    for name,e in manifest.items():
        raw=(folder/name).read_bytes();gz=(durable/folder.name/(name+'.gz')).read_bytes()
        assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256']
        assert hashlib.sha256(gz).hexdigest()==e['gzip_sha256'] and gzip.decompress(gz)==raw
for row in s['rows']:
    prefix=f"{row['model']}-{row['seed']}";pilot=parent/'runs'/(prefix+'-pilot')/'RESULT.json'
    p=json.loads(pilot.read_text());fit=root/'runs'/(prefix+'-fit')/'RESULT.json'
    if not fit.exists():assert row['error']=='fit_failed';continue
    f=json.loads(fit.read_text());assert f['pilot_sha256']==hashlib.sha256(pilot.read_bytes()).hexdigest() and f['target_calls']==400
    folder=root/'runs'/(prefix+'-fisher');inp=json.loads((folder/'INPUT.json').read_text())
    assert inp['starts']==np.asarray(p['draws'])[:,-1,:].tolist() and inp['seed']==row['seed']+100000
    assert inp['warmup']==750 and inp['draws']==2000 and inp['arm']=='fixed_dense'
    assert inp['mass']==np.asarray(f['mass']).ravel().tolist();stages+=1
    if (folder/'RESULT.json').exists():
        r=json.loads((folder/'RESULT.json').read_text())
        assert row['calls']==p['target_calls']+400+r['target_calls']
        assert abs(row['seconds']-(p['seconds']+f['seconds']+r['seconds']))<=1e-10
controls=json.loads((parent/'SUMMARY.json').read_text())['rows'];comparison={}
for model in sorted(set(r['model'] for r in s['rows'])):
    fr=[r for r in s['rows'] if r['model']==model];entry=dict(fisher_passes=sum(r['passed'] for r in fr),comparisons={})
    for arm in ['candidate','dense','auto']:
        pairs=[]
        for f in fr:
            c=next(r for r in controls if r['model']==model and r['seed']==f['seed'] and r['arm']==arm)
            pair=dict(seed=f['seed'],fisher_passed=f['passed'],other_passed=c['passed'],qualified=f['passed'] and c['passed'])
            if pair['qualified']:
                pair.update(other_over_fisher_efficiency=c['efficiency']/f['efficiency'],
                    other_over_fisher_ess_per_second=(c['bulk']/c['seconds'])/(f['bulk']/f['seconds']))
            pairs.append(pair)
        e=dict(pairs=pairs)
        if all(p['qualified'] for p in pairs):
            for key in ['other_over_fisher_efficiency','other_over_fisher_ess_per_second']:
                e[key+'_geomean']=float(np.exp(np.mean(np.log([p[key] for p in pairs]))))
        entry['comparisons'][arm]=e
    comparison[model]=entry
(root/'COMPARISON.json').write_text(json.dumps(comparison,indent=2)+'\n')
result=dict(passed=True,jobs=jobs,matched_stages=stages,costs_verified=True,durable_hashes_verified=True,controls_reused=True)
(root/'VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));print(json.dumps(comparison))
