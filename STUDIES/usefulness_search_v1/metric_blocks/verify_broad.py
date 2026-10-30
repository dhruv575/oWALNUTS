import gzip,hashlib,json
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parent
s=json.loads((root/'SUMMARY.json').read_text());assert s['unchanged'] and len(s['rows'])==72
durable=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence/broad01');jobs=0;fallbacks=[];stages=0
for sup in (root/'runs').glob('*/SUPERVISION.json'):
    r=json.loads(sup.read_text());assert r['group_drained'];jobs+=1;folder=sup.parent
    manifest=json.loads((durable/folder.name/'MANIFEST.json').read_text())
    for name,e in manifest.items():
        raw=(folder/name).read_bytes();gz=(durable/folder.name/(name+'.gz')).read_bytes()
        assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256']
        assert hashlib.sha256(gz).hexdigest()==e['gzip_sha256'] and gzip.decompress(gz)==raw
for row in [r for r in s['rows'] if r['arm']=='candidate']:
    prefix=f"{row['model']}-{row['seed']}";pilot=root/'runs'/(prefix+'-pilot')/'RESULT.json'
    if not pilot.exists():continue
    p=json.loads(pilot.read_text());starts=np.asarray(p['draws'])[:,-1,:].tolist();d=len(starts[0]);sel=root/(prefix+'-SELECTION.json')
    if sel.exists():assert json.loads(sel.read_text())['probe_calls']==64*d
    for arm in ['candidate','dense','auto']:
        folder=root/'runs'/(prefix+'-'+arm)
        if not (folder/'INPUT.json').exists():continue
        inp=json.loads((folder/'INPUT.json').read_text())
        assert inp['starts']==starts and inp['seed']==row['seed']+100000 and inp['warmup']==750 and inp['draws']==2000;stages+=1
        rr=next(r for r in s['rows'] if r['model']==row['model'] and r['seed']==row['seed'] and r['arm']==arm)
        if 'calls' in rr and (folder/'RESULT.json').exists():
            result=json.loads((folder/'RESULT.json').read_text());assert rr['calls']==p['target_calls']+result['target_calls']+(64*d if arm=='candidate' else 0)
    if row.get('selection') is not None and not row['selection']['blocks']:
        a=json.loads((root/'runs'/(prefix+'-candidate')/'RESULT.json').read_text());b=json.loads((root/'runs'/(prefix+'-auto')/'RESULT.json').read_text())
        assert {k:v for k,v in a.items() if k!='seconds'}=={k:v for k,v in b.items() if k!='seconds'}
        fallbacks.append(dict(model=row['model'],seed=row['seed'],exact_non_timing_result=True))
result=dict(passed=True,jobs=jobs,matched_stages=stages,fallbacks=fallbacks,durable_hashes_verified=True,costs_verified=True)
(root/'VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
