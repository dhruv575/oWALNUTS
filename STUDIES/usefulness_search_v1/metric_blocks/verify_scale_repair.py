import hashlib,json
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parent;work=root.parent;s=json.loads((root/'SUMMARY.json').read_text());assert s['unchanged'] and len(s['rows'])==3
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in s['inputs'].items())
binary=work/'model01/source/STUDIES/metric_autoselect_confirmation_v1/target/release/online';bh=hashlib.sha256(binary.read_bytes()).hexdigest()
for row in s['rows']:
    seed=row['seed'];parent=work/f'hybrid0{(seed-929300001)//4+1}';prefix=f'sblrc-blr-{seed}';folder=root/'runs'/str(seed)
    old=json.loads((parent/'SUMMARY.json').read_text());assert old['inputs'][str(binary)]==bh
    p=json.loads((parent/'runs'/(prefix+'-pilot')/'RESULT.json').read_text());f=json.loads((parent/'runs'/(prefix+'-fit')/'RESULT.json').read_text())
    a=json.loads((folder/'INPUT.json').read_text());b=json.loads((parent/'runs'/(prefix+'-v4')/'INPUT.json').read_text())
    assert {k:v for k,v in a.items() if k!='mass'}=={k:v for k,v in b.items() if k!='mass'}
    assert a['starts']==np.asarray(p['draws'])[:,-1,:].tolist() and a['warmup']==750 and a['draws']==2000 and a['seed']==seed+100000
    sup=json.loads((folder/'SUPERVISION.json').read_text());assert sup['group_drained'] and sup['exit_code']==0
    r=json.loads((folder/'RESULT.json').read_text());assert row['calls']==p['target_calls']+f['score_calls']+f['probe_calls']+r['target_calls']
    for fp in folder.iterdir():
        if fp.is_file():
            dp=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence/scalerepair01')/str(seed)/fp.name
            assert hashlib.sha256(fp.read_bytes()).digest()==hashlib.sha256(dp.read_bytes()).digest()
    for arm,ratio in row['ratios'].items():
        control=next(v for v in old['rows'] if v['model']=='sblrc-blr' and v['seed']==seed and v['arm']==arm)
        assert control['passed'] and abs(ratio-row['efficiency']/control['efficiency'])<=1e-12
result=dict(passed=True,jobs=3,matched_stages=3,costs_verified=True,durable_files_verified=True,binary_sha256=bh,controls_reused=True)
(root/'VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
