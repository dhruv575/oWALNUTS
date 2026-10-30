import gzip,hashlib,json
from pathlib import Path
import numpy as np
from selector_full_shape import select
root=Path(__file__).resolve().parent;s=json.loads((root/'SUMMARY.json').read_text());assert s['unchanged'] and len(s['rows'])==72
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in s['inputs'].items())
durable=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence')/root.name;jobs=0;stages=0;equivalent=[];repairs=[]
def read(p):return json.loads(p.read_text())
for sup in (root/'runs').glob('*/SUPERVISION.json'):
    r=read(sup);assert r['group_drained'];jobs+=1;folder=sup.parent
    for name,e in read(durable/folder.name/'MANIFEST.json').items():
        raw=(folder/name).read_bytes();gz=(durable/folder.name/(name+'.gz')).read_bytes()
        assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256'] and hashlib.sha256(gz).hexdigest()==e['gzip_sha256'] and gzip.decompress(gz)==raw
for row in [r for r in s['rows'] if r['arm']=='scaled']:
    prefix=f"{row['model']}-{row['seed']}";pilot=root/'runs'/(prefix+'-pilot')/'RESULT.json'
    if not pilot.exists():assert row['error']=='pilot_failed';continue
    p=read(pilot);d=len(p['draws'][0][0]);ps=read(pilot.parent/'SUPERVISION.json');policies={};results={}
    for arm in ['scaled','hybrid','v4','fisher','dense','auto']:
        folder=root/'runs'/(prefix+'-'+arm);rr=next(r for r in s['rows'] if r['model']==row['model'] and r['seed']==row['seed'] and r['arm']==arm)
        if not (folder/'POLICY.json').exists():assert not rr['passed'];continue
        policy=read(folder/'POLICY.json');policies[arm]=policy;inp=read(folder/'INPUT.json');args=read(folder/'SAMPLER-INPUT.json')
        assert inp['policy']==arm and inp['pilot']==str(pilot) and policy['pilot_sha256']==hashlib.sha256(pilot.read_bytes()).hexdigest()
        assert args['starts']==np.asarray(p['draws'])[:,-1,:].tolist() and args['seed']==row['seed']+100000 and args['warmup']==750 and args['draws']==2000
        assert args['arm']==policy['mode']
        if policy['mass'] is not None:assert args['mass']==np.asarray(policy['mass']).ravel().tolist()
        calls=400+64*d if arm in ['scaled','hybrid'] else (400 if arm=='fisher' else (64*d if arm=='v4' else 0))
        assert policy['calls']==calls;stages+=1
        if (folder/'RESULT.json').exists() and 'calls' in rr:
            r=read(folder/'RESULT.json');results[arm]=r;sup=read(folder/'SUPERVISION.json')
            assert rr['calls']==p['target_calls']+calls+r['target_calls']
            assert rr['seconds']==ps['elapsed_seconds']+sup['elapsed_seconds']
    for arm in ['scaled','hybrid']:
        if arm not in policies or arm not in results:continue
        policy=policies[arm];branch=policy['branch']
        if branch in results and branch!=arm:
            assert {k:v for k,v in results[arm].items() if k!='seconds'}=={k:v for k,v in results[branch].items() if k!='seconds'}
            equivalent.append(dict(model=row['model'],seed=row['seed'],arm=arm,branch=branch))
        if branch=='scaled_block':
            assert arm=='scaled' and not policy['gate']['use_fisher'] and policy['selection']['blocks']
            if 'fisher' in policies:
                fc=np.linalg.inv(policies['fisher']['mass']);c,info=select(policy['coarse'],policy['fine'],np.diag(fc));m=np.linalg.inv(c);m=(m+m.T)/2
                assert info['blocks']==policy['selection']['blocks'] and np.array_equal(m,policy['mass'])
            repairs.append(dict(model=row['model'],seed=row['seed']))
result=dict(passed=True,jobs=jobs,matched_stages=stages,costs_verified=True,full_invocation_timing_verified=True,durable_hashes_verified=True,exact_branch_results=equivalent,scaled_blocks=repairs)
(root/'VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
