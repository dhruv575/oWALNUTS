"""All-coordinate blocked-slice comparison to frozen iid T1 references."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
import arviz as az


def run(root,reference,out):
    root=Path(root);reference=Path(reference);out=Path(out);out.mkdir(exist_ok=False)
    manifest=json.loads((Path(__file__).parent/'REFERENCE-MANIFEST.json').read_text())
    receipt=json.loads((root/'run01/SUPERVISION.json').read_text());jobs=json.loads((root/'run01/FINAL.json').read_text())
    if not receipt['group_drained']:raise ValueError('Campaign still active')
    rows=[];bindings={}
    for j,cap in enumerate((.5,1.,2.)):
        relevant=[r for r in jobs if r['index']//4==j]
        if len(relevant)!=4 or not all(r.get('exit_code')==0 and r.get('group_drained') for r in relevant):
            rows.append(dict(cap=cap,status='incomplete'));continue
        arrays=[]
        for c in range(4):
            p=root/f'run01/job-{4*j+c}/fit/draws.npz';bindings[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
            with np.load(p) as f:
                if f['warmup'].shape!=(1000,4) or f['draws'].shape!=(4000,4):raise ValueError('Shape')
                arrays.append(f['draws'])
        draws=np.stack(arrays)
        if not np.isfinite(draws).all():raise ValueError('Finite draws')
        p=reference/f'run01/job-{j}/fit/reference.npz';h=hashlib.sha256(p.read_bytes()).hexdigest();bindings[str(p)]=h
        assert h==manifest[f'run01/job-{j}/fit/reference.npz']['sha256']
        with np.load(p) as f:ref=f['draws'].copy()
        ref[:,1]=np.log(cap)-np.logaddexp(0.,ref[:,1])
        names=['mu','log_sigma','beta','z']
        summary=az.summary(az.from_dict(posterior={name:draws[:,:,k] for k,name in enumerate(names)}),round_to='none')
        summary['reference_mean']=ref.mean(axis=0);summary['reference_mcse']=ref.std(axis=0,ddof=1)/np.sqrt(len(ref))
        summary['combined_z']=(summary['mean']-summary.reference_mean)/np.hypot(summary.mcse_mean,summary.reference_mcse)
        summary.to_csv(out/f'cap-{j}-coordinates.csv')
        bad=(~np.isfinite(summary[['r_hat','ess_bulk','ess_tail']]).all(axis=1))|(summary.r_hat>1.01)|(summary.ess_bulk<400)|(summary.ess_tail<400)
        rows.append(dict(cap=cap,status='compared',failed_coordinates=summary.index[bad].tolist(),max_abs_mean_z=float(abs(summary.combined_z).max()),flags_over_4=summary.index[abs(summary.combined_z)>4].tolist()))
    result=dict(rows=rows,bindings=bindings,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='T1 independent-control admission only; no repeated-tie or market fidelity claim')
    (out/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':run(*sys.argv[1:])
