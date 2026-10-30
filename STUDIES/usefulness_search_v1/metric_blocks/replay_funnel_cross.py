import hashlib,json
from pathlib import Path
import numpy as np
from scipy.special import ndtr
study=Path(__file__).resolve().parent;root=study/'local_recovery/funnel_cross01'
summary=json.loads((root/'SUMMARY.json').read_text())
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in summary['inputs'].items())
analysis=json.loads((study/'FUNNEL-CROSS-ANALYSIS.json').read_text());checks=[];starts={}
for row in analysis['rows']:
    folder=root/row['folder'];raw=json.loads((folder/'RAW.json').read_text());sup=json.loads((folder/'SUPERVISION.json').read_text());spec=json.loads((folder/'INPUT.json').read_text())
    assert sup['group_drained'] and sup['exit_code']==0
    key=row['pilot_seed'];ss=[c['start'] for c in spec['chains']]
    if key in starts:assert starts[key]==ss
    starts[key]=ss
    x=np.asarray([c['draws'] for c in raw['chains']]).transpose(2,0,1)[:,:,2000:]
    assert x.shape==(10,4,20000)
    u=ndtr(np.concatenate([x[:1]/3,x[1:]*np.exp(-x[:1]/2)]))
    def gate(d):
        return all(d[k] is not None and np.isfinite(d[k]) for k in ['rhat','bulk','tail','mcse']) and d['rhat']<=1.01 and d['bulk']>=400 and d['tail']>=400
    for f in row['features']:
        name=f['name']
        if name.startswith('U'):
            prefix,kind=name.split('_');v=u[int(prefix[1:])];v=v if kind=='mean' else v<.05 if kind=='lower' else v>.95
        elif name=='joint_lower_median':v=(u[0]<.5)&(u[1]<.5)
        elif name=='centered_product':v=(u[0]-.5)*(u[1]-.5)
        else:v=x[0]<-int(name[-1])
        assert abs(float(v.mean())-f['estimate'])<1e-14
        assert abs(f['error']-(f['estimate']-f['exact']))<1e-14
        passed=f['z'] is not None and abs(f['error'])<=f['tolerance'] and f['mcse']<=f['tolerance']/2 and abs(f['z'])<=4.5
        if not name.startswith('omega_'):passed=passed and gate(f)
        assert bool(passed)==f['passed']
    expected=np.isfinite(x).all() and row['divergences_including_discard']==0 and row['depth_caps_including_discard']==0 and all(f['passed'] for f in row['features']) and all(gate(c[k]) for c in row['coordinates'] for k in ['raw','uniform'])
    assert bool(expected)==row['qualified']
    assert row['target_calls']==sum(c['target_calls'] for c in raw['chains'])
    for c in raw['chains']:assert c['target_calls']==c['work']['all_phase_calls']==c['work']['target_calls_initial']+c['work']['target_calls_forward']+c['work']['target_calls_reverse']
    checks.append(dict(folder=row['folder'],moments_replayed=len(row['features']),qualified=row['qualified'],peak_rss=sup['peak_rss']))
(study/'FUNNEL-CROSS-REPLAY.json').write_text(json.dumps(dict(passed=True,common_starts_verified=True,source_hashes_unchanged=True,checks=checks),indent=2)+'\n');print('All 16 moment/qualification/telemetry/source replays passed')
