"""Execute the fixed T=1 comparison inside the external resource monitor."""
import json,sys,time
from pathlib import Path
import numpy as np
import arviz as az
import nutpie
from price_cell_rejection import reference


def run(out):
    out=Path(out);out.mkdir(exist_ok=False);started=time.monotonic()
    draws,meta=reference()
    np.savez_compressed(out/'rejection.npz',draws=draws)
    meta['accepted']=len(draws)
    (out/'REJECTION.json').write_text(json.dumps(meta,indent=2)+'\n')
    if meta['nonfinite'] or len(draws)<10000:raise ValueError('Rejection admission failed')
    compiled=nutpie.compile_stan_model(code=Path(__file__).with_name('price_cell_sv.stan').read_text(),cleanup=False)
    model=compiled.with_data(seed=398123783,n=1,lower_cell=np.array([-.0005]),upper_cell=np.array([.0005]),initial=0.,rho=.95)
    trace=nutpie.sample(model,chains=4,cores=4,tune=2000,draws=4000,seed=398123782,
        init_mean=np.array([2*np.log(.005),np.log(.2),0.,0.,0.]),save_warmup=True,
        progress_bar=False,target_accept=.9,maxdepth=10,low_rank_modified_mass_matrix=False,transform_adapt=False)
    trace.to_netcdf(out/'trace.nc')
    labels=['mu','log_sigma','beta','z','u'];columns=[]
    for name in labels:
        a=np.asarray(trace.posterior[name].transpose('chain','draw',...))
        columns.append(a.reshape(4,4000,-1)[:,:,0])
    full=np.stack(columns,axis=-1);np.savez_compressed(out/'nuts.npz',draws=full)
    rows=[]
    for i,name in enumerate(labels):
        a=full[:,:,i];r=draws[:,i]
        mcse=float(az.mcse(a,method='mean'));refse=float(r.std(ddof=1)/np.sqrt(len(r)))
        row=dict(name=name,rhat=float(az.rhat(a)),ess_bulk=float(az.ess(a,method='bulk')),
            ess_tail=float(az.ess(a,method='tail')),mean=float(a.mean()),mcse=mcse,
            reference_mean=float(r.mean()),reference_se=refse,
            standardized_difference=float((a.mean()-r.mean())/np.hypot(mcse,refse)),
            quantiles=np.quantile(a,[.1,.5,.9]).tolist(),reference_quantiles=np.quantile(r,[.1,.5,.9]).tolist())
        row['diagnostic_pass']=row['rhat']<=1.01 and min(row['ess_bulk'],row['ess_tail'])>=400
        rows.append(row)
    divergences=int(trace.sample_stats['diverging'].sum())
    result=dict(scope='Single synthetic T1 fixture only',rows=rows,divergences=divergences,
        diagnostic_pass=divergences==0 and all(r['diagnostic_pass'] for r in rows),
        mean_disagreement_flags=[r['name'] for r in rows if abs(r['standardized_difference'])>4],
        elapsed_seconds=time.monotonic()-started)
    (out/'REPORT.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    for group in trace.groups():getattr(trace,group).close()
    trace.close()
    return result


if __name__=='__main__':print(json.dumps(run(sys.argv[1])))
