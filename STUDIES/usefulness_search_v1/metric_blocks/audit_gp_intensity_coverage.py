"""Posthoc audit only: never revises the frozen validation gate."""
import hashlib,json
from pathlib import Path
import numpy as np
import arviz as az
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_intensity_coverage01';r.mkdir(exist_ok=False)
refpath=p.parent/'gp_count/REFERENCE.json';ref=json.loads(refpath.read_text());assert ref['qualified']
oldpath=l/'localscaled01/REFERENCES.json';old=json.loads(oldpath.read_text())['gp_pois_regr-gp_pois_regr'];assert old['passed']
assert ref['names'][:13]==old['names']
rs=ref['stats'];assert max(rs['rhat'])<=1.01 and min(rs['bulk'])>=400 and min(rs['tail'])>=400
agreement={k:float(np.max(abs(np.asarray(rs[k])[:13]-old[k]))) for k in ['mean','sd','mcse']}
assert all(v<1e-10 for v in agreement.values())
batchpath=l/'bounded_gp_validation01/SUMMARY.json';batch=json.loads(batchpath.read_text());rows=[]
inputs={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),refpath,oldpath,batchpath]}
for row in batch['rows']:
    rep=row['seed']-(948700001+2*row['fold']);d=l/'bounded_gp_validation01'/f"{row['fold']}-{rep}-{row['transform']}-{row['mode']}"
    f=d/'FUNCTIONALS.npz';inputs[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest();a=np.load(f)['values'];assert a.shape==(4,8000,13)
    values=np.concatenate([a,np.exp(a[:,:,2:])],axis=2);assert np.isfinite(values).all();ds=az.convert_to_dataset({'p':values})
    stats={k:np.asarray(fn(ds).p) for k,fn in [('rhat',lambda x:az.rhat(x,method='rank')),('bulk',lambda x:az.ess(x,method='bulk')),('tail',lambda x:az.ess(x,method='tail')),('mcse',lambda x:az.mcse(x,method='mean'))]}
    mean=values.mean((0,1));sd=values.reshape(-1,24).std(0,ddof=1)
    error=abs(mean-rs['mean'])/rs['sd'];sderr=abs(sd/rs['sd']-1);z=abs(mean-rs['mean'])/np.sqrt(stats['mcse']**2+np.asarray(rs['mcse'])**2)
    # Common stricter accuracy rule, chosen after original validation; descriptive only.
    gates=dict(rhat=max(stats['rhat'])<=1.01,bulk=min(stats['bulk'])>=400,tail=min(stats['tail'])>=400,divergences=row['divergences']==0,mean_error=max(error)<=.1,sd_error=max(sderr)<=.1,combined_z=max(z)<=4)
    rows.append(dict(fold=row['fold'],seed=row['seed'],transform=row['transform'],mode=row['mode'],passed=all(gates.values()),gates={k:bool(v) for k,v in gates.items()},max_mean_error=float(max(error)),max_sd_error=float(max(sderr)),max_z=float(max(z)),min_bulk=float(min(stats['bulk'])),min_tail=float(min(stats['tail'])),max_rhat=float(max(stats['rhat'])),functionals={**{k:v.tolist() for k,v in stats.items()},'mean':mean.tolist(),'sd':sd.tolist()}))
    print(json.dumps(dict(completed=len(rows),transform=row['transform'],mode=row['mode'],passed=rows[-1]['passed'])),flush=True)
summary=dict(scope='Posthoc24-function coverage audit, no revised original qualification or superiority claim.',reference_agreement=agreement,inputs=inputs,rows=rows)
(r/'SUMMARY.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
