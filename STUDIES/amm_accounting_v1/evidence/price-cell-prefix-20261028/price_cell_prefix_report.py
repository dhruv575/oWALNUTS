"""Retrospective prefix diagnostics; no independent runs or timing inference."""
import hashlib,json,sys,time
from pathlib import Path
import numpy as np
import arviz as az
import pandas as pd


def run(root,predictive,out):
    root=Path(root);predictive=Path(predictive);out=Path(out);out.mkdir(exist_ok=False)
    start=time.monotonic();rows=[];bindings={}
    for j in range(4):
        folder=root/'run01'/f'job-{j}'/'fit';p=folder/'warm-draws.npz'
        bindings[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        with np.load(p) as f:q=f['draws']
        p=predictive/'run01'/f'fixture-{j}-functionals.npz';bindings[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        with np.load(p) as f:values={f'cdf_{k}':f[f'warm_cdf_{k}'] for k in range(3)}
        cold=pd.read_csv(predictive/'run01'/f'fixture-{j}-cold.csv',index_col=0)
        n=12 if j<2 else 250
        if q.shape!=(4,4000,3+2*n) or not np.isfinite(q).all():raise ValueError('Draw contract')
        for budget in (64,256,1024):
            a=q[:,:budget,:]
            coordinates=az.summary(az.from_dict(posterior=dict(mu=a[:,:,0],log_sigma=a[:,:,1],beta=a[:,:,2],z=a[:,:,3:3+n],u=a[:,:,3+n:])),round_to='none')
            coordinates.to_csv(out/f'fixture-{j}-k{budget}-coordinates.csv')
            bad=(coordinates.r_hat>1.01)|(coordinates.ess_bulk<400)|(coordinates.ess_tail<400)|(~np.isfinite(coordinates[['r_hat','ess_bulk','ess_tail']]).all(axis=1))
            summary=az.summary(az.from_dict(posterior={k:v[:,:budget] for k,v in values.items()}),round_to='none')
            table=summary.add_prefix('warm_').join(cold.add_prefix('cold_'))
            table['absolute_mean_difference']=abs(summary['mean']-cold['mean'])
            table['combined_z']=(summary['mean']-cold['mean'])/np.hypot(summary.mcse_mean,cold.mcse_mean)
            table.to_csv(out/f'fixture-{j}-k{budget}-functionals.csv')
            rows.append(dict(fixture=j,budget=budget,coordinate_failure_count=int(bad.sum()),coordinates=len(coordinates),functional_max_rhat=float(summary.r_hat.max()),functional_min_bulk_ess=float(summary.ess_bulk.min()),functional_min_tail_ess=float(summary.ess_tail.min()),functional_max_mcse=float(summary.mcse_mean.max()),max_absolute_cdf_difference=float(table.absolute_mean_difference.max()),max_abs_combined_z=float(abs(table.combined_z).max())))
    result=dict(rows=rows,bindings=bindings,elapsed_seconds=time.monotonic()-start,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='Retrospective nested prefixes of one shifted synthetic update. No new seeds, independent replication, measured prefix latency, or empirical predictive accuracy. Failed diagnostics undermine MCSE interpretation.')
    (out/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':run(*sys.argv[1:])
