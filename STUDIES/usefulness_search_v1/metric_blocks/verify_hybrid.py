import gzip,hashlib,json
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parent
s=json.loads((root/'SUMMARY.json').read_text());assert s['unchanged'] and len(s['rows'])==120
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in s['inputs'].items())
durable=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence')/root.name;jobs=0;stages=0;equivalent=[]
for sup in (root/'runs').glob('*/SUPERVISION.json'):
    r=json.loads(sup.read_text());assert r['group_drained'];jobs+=1;folder=sup.parent
    manifest=json.loads((durable/folder.name/'MANIFEST.json').read_text())
    for name,e in manifest.items():
        raw=(folder/name).read_bytes();gz=(durable/folder.name/(name+'.gz')).read_bytes()
        assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256']
        assert hashlib.sha256(gz).hexdigest()==e['gzip_sha256'] and gzip.decompress(gz)==raw
for row in [r for r in s['rows'] if r['arm']=='hybrid']:
    prefix=f"{row['model']}-{row['seed']}";pilot=root/'runs'/(prefix+'-pilot')/'RESULT.json'
    if not pilot.exists():assert row['error']=='pilot_failed';continue
    p=json.loads(pilot.read_text());fit=root/'runs'/(prefix+'-fit')/'RESULT.json';prep=json.loads(fit.read_text()) if fit.exists() else None
    d=len(p['draws'][0][0]);starts=np.asarray(p['draws'])[:,-1,:].tolist()
    if prep:
        assert prep['pilot_sha256']==hashlib.sha256(pilot.read_bytes()).hexdigest() and prep['score_calls']==400 and prep['probe_calls']==64*d
        branch='fisher' if prep['gate']['use_fisher'] and prep['fisher_mass'] is not None else ('v4' if prep['selection']['blocks'] else 'auto')
        assert prep['branch']==branch
    for arm in ['hybrid','v4','fisher','dense','auto']:
        rr=next(r for r in s['rows'] if r['model']==row['model'] and r['seed']==row['seed'] and r['arm']==arm)
        folder=root/'runs'/(prefix+'-'+arm)
        if not folder.exists():assert 'error' in rr;continue
        inp=json.loads((folder/'INPUT.json').read_text());assert inp['starts']==starts and inp['seed']==row['seed']+100000 and inp['warmup']==750 and inp['draws']==2000
        stages+=1;ec=0;et=0
        if arm=='hybrid':
            ec=400+64*d;et=sum(prep[k] for k in ['score_seconds','gate_seconds','fisher_seconds','probe_seconds'])
            expected='auto' if branch=='auto' else 'fixed_dense';mass=prep['fisher_mass'] if branch=='fisher' else prep['v4_mass']
        elif arm=='v4':
            ec=64*d;et=prep['probe_seconds'];expected='fixed_dense' if prep['selection']['blocks'] else 'auto';mass=prep['v4_mass']
        elif arm=='fisher':
            ec=400;et=prep['score_seconds']+prep['fisher_seconds'];expected='fixed_dense';mass=prep['fisher_mass']
        else:expected=arm
        assert inp['arm']==expected
        if expected=='fixed_dense':assert inp['mass']==np.asarray(mass).ravel().tolist()
        result=folder/'RESULT.json'
        if result.exists():
            r=json.loads(result.read_text());assert rr['calls']==p['target_calls']+ec+r['target_calls']
            assert abs(rr['seconds']-(p['seconds']+et+r['seconds']))<=1e-9
    hp=root/'runs'/(prefix+'-hybrid')/'RESULT.json'
    if prep and hp.exists():
        bp=root/'runs'/(prefix+'-'+branch)/'RESULT.json'
        if bp.exists():
            a=json.loads(hp.read_text());b=json.loads(bp.read_text())
            assert {k:v for k,v in a.items() if k!='seconds'}=={k:v for k,v in b.items() if k!='seconds'}
            equivalent.append(dict(model=row['model'],seed=row['seed'],branch=branch))
result=dict(passed=True,jobs=jobs,matched_stages=stages,costs_verified=True,durable_hashes_verified=True,exact_branch_results=equivalent)
(root/'VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
