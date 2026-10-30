import hashlib,json
from pathlib import Path
import numpy as np
from scipy.special import ndtr
from scipy.integrate import quad
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'compact_validation01'
for name in ['compact_recycling_test01','compact_original_test01','compact_validation01']:
    s=json.loads((local/name/'SUMMARY.json').read_text());assert s['passed'] and s['unchanged']
    for p,h in s['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
original=json.loads((local/'recycling_source03/ORIGINAL-SOURCE.json').read_text())
for p,h in original.items():assert hashlib.sha256((study.parents[2]/p).read_bytes()).hexdigest()==h
analysis=json.loads((study/'COMPACT-VALIDATION-ANALYSIS.json').read_text());rows=[]
for t in analysis['rows']:
    target=t['target'];d=len(t['truth'])//4;variance=np.array([2.,2.] if d==2 else [9.]+([np.exp(4.5)]*9 if target=='funnel' else [1.]*9));tail=ndtr(-2/np.sqrt(variance))
    if target=='funnel':tail[1:]=quad(lambda z:ndtr(-2*np.exp(-1.5*z))*np.exp(-z*z/2)/np.sqrt(2*np.pi),-12,12,epsabs=1e-12)[0]
    truth=np.concatenate([np.zeros(d),variance,np.full(d,.5),tail]);assert np.allclose(truth,t['truth'],atol=1e-11,rtol=1e-13)
    estimates=[[],[]];variances=[[],[]];times=[0.,0.]
    for batch in range(16):
        folder=root/f'{target}-{batch:02d}';sup=json.loads((folder/'SUPERVISION.json').read_text());assert sup['exit_code']==0 and sup['group_drained'];data=[]
        for arm in ['original','observed']:
            r=json.loads((folder/f'RAW-{arm}.json').read_text());data.append(r)
            canonical=json.loads(json.dumps(r))
            for c in canonical['chains']:c.pop('seconds')
            digest=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            rec=[x for x in json.loads((folder/'TIMINGS.json').read_text()) if x['arm']==arm];assert len(rec)==3 and all(x['canonical_sha256']==digest for x in rec)
            times[int(arm=='observed')]+=sum(x['seconds'] for x in rec)
            for c in r['chains']:
                s=c['summary'];blocks=np.array(s['block_means']);sizes=np.array(s['block_sizes']);mean=np.average(blocks,weights=sizes,axis=0)
                assert sizes.sum()==s['count']==1000 and np.allclose(mean,s['mean'],rtol=2e-13,atol=1e-10)
                estimates[int(arm=='observed')].append(s['mean']);variances[int(arm=='observed')].append(blocks.var(axis=0,ddof=1)/20)
        for a,b in zip(data[0]['chains'],data[1]['chains']):
            for k in a:
                if k not in ['seconds','summary']:assert a[k]==b[k]
    assert abs(times[1]/times[0]-t['cost_ratio'])<1e-12
    e=np.array(estimates)-truth;v=np.array(variances);scale=np.concatenate([np.sqrt(variance),variance,np.ones(2*d)]);sq=(e/scale)**2
    for j,f in enumerate(t['families']):
        section=slice(j*d,(j+1)*d);ratio=sq[0,:,section].mean()/sq[1,:,section].mean();assert abs(ratio-f['ratio'])<1e-10
    for j,f in enumerate(t['functionals']):
        assert abs(sq[0,:,j].mean()/sq[1,:,j].mean()-f['mse_ratio'])<1e-10
        assert np.array_equal(np.mean(abs(e[:,:,j])<=1.96*np.sqrt(v[:,:,j]),axis=1),f['coverage95'])
    rows.append(dict(target=target,replicates=64,means_blocks_hashes_work_truth_cost_mse_and_coverage_verified=True))
assert not analysis['primary_passed']
(study/'COMPACT-VALIDATION-REPLAY.json').write_text(json.dumps(dict(passed=True,production_source_unchanged=True,rows=rows),indent=2)+'\n');print('Independent compact validation replay passed; primary failure preserved')
