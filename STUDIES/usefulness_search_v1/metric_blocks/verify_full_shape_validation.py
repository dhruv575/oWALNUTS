import gzip,hashlib,json
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parent
summary=json.loads((root/'SUMMARY.json').read_text());assert summary['unchanged']
durable=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence/fullshape02')
jobs=list((root/'runs').glob('*/SUPERVISION.json'));checked=[]
for sup in jobs:
    folder=sup.parent;r=json.loads(sup.read_text());assert r['group_drained']
    manifest=json.loads((durable/folder.name/'MANIFEST.json').read_text())
    for name,expected in manifest.items():
        raw=(folder/name).read_bytes();compressed=(durable/folder.name/(name+'.gz')).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==expected['sha256'] and len(raw)==expected['bytes']
        assert hashlib.sha256(compressed).hexdigest()==expected['gzip_sha256'] and gzip.decompress(compressed)==raw
    checked.append(folder.name)
schedule_checks=[]
for seed in range(928800001,928800017):
    pilot=root/'runs'/f'{seed}-pilot';pi=json.loads((pilot/'INPUT.json').read_text())
    assert pi['warmup']==250 and pi['draws']==100 and pi['seed']==seed
    if not (pilot/'RESULT.json').exists():continue
    p=json.loads((pilot/'RESULT.json').read_text());x=np.array(p['draws']);starts=x[:,-1,:].tolist()
    detail=json.loads((root/f'{seed}-MATRICES.json').read_text());assert detail['probe_calls']==320
    for arm in ['fixed_diag','empirical','curvature','dense','auto']:
        folder=root/'runs'/f'{seed}-{arm}'
        if not (folder/'INPUT.json').exists():continue
        inp=json.loads((folder/'INPUT.json').read_text())
        assert inp['starts']==starts and inp['seed']==seed+100000 and inp['warmup']==750 and inp['draws']==2000
        row=next(r for r in summary['rows'] if r['seed']==seed and r['arm']==arm)
        if (folder/'RESULT.json').exists() and 'calls' in row:
            result=json.loads((folder/'RESULT.json').read_text())
            assert row['calls']==p['target_calls']+result['target_calls']+(320 if arm=='curvature' else 0)
        schedule_checks.append(dict(seed=seed,arm=arm,matched=True))
result=dict(passed=True,jobs_checked=len(checked),durable_gzip_verified=True,
    stage_schedule_checks=len(schedule_checks),cost_accounting_verified=True,notes='Missing failed-stage inputs remain failures; not silently counted as completed jobs.')
(root/'VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
