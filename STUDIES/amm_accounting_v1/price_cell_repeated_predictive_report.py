"""Post-hoc fixed latent-increment CDF comparison, with numerical error audit."""
import hashlib,json,sys,time
from pathlib import Path
import numpy as np
import arviz as az
from scipy.integrate import quad
from scipy.special import stdtr
from price_cell_predictive import conditional_cdf,last_volatility


def run(root,out):
    root=Path(root);out=Path(out);out.mkdir(exist_ok=False);started=time.monotonic()
    manifest=json.loads((Path(__file__).parent/'REPEATED-MANIFEST.json').read_text())
    rows=[];bindings={};thresholds=[-.005,0.,.005]
    for j in range(12):
        path,update=divmod(j,3);folder=root/'run01'/f'job-{path}'/'fit'/f'update-{update}';traces={}
        for name in ('warm-draws.npz','cold.nc'):
            p=folder/name;h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==manifest[f'run01/job-{path}/fit/update-{update}/{name}']['sha256'];bindings[str(p)]=h
        with np.load(folder/'warm-draws.npz') as f:traces['warm']=f['draws']
        cold=az.from_netcdf(folder/'cold.nc');p=cold.posterior
        traces['cold']=np.concatenate([p[k].values[...,None] for k in ('mu','log_sigma','beta')]+[p.z.values,p.u.values],axis=2)
        methods={};arrays={};checks=[]
        for method,q in traces.items():
            n=250
            if q.shape!=(4,1024 if method=='warm' else 4000,3+2*n) or not np.isfinite(q).all():raise ValueError('Trace shape/finiteness')
            recomputed=az.summary(az.from_dict(posterior=dict(mu=q[:,:,0],log_sigma=q[:,:,1],beta=q[:,:,2],z=q[:,:,3:3+n],u=q[:,:,3+n:])),round_to='none')
            import pandas as pd
            original=pd.read_csv(folder/f'{method}-coordinates.csv',index_col=0)
            assert list(recomputed.index)==list(original.index)
            np.testing.assert_allclose(recomputed.values,original.values,rtol=1e-11,atol=1e-11)
            h=last_volatility(q);mu=q[:,:,0];sigma=np.exp(q[:,:,1]);beta=q[:,:,2]
            values={}
            for k,threshold in enumerate(thresholds):
                low=conditional_cdf(threshold,mu,sigma,beta,h,order=64)
                high=conditional_cdf(threshold,mu,sigma,beta,h,order=128)
                delta=abs(high-low);idx=np.unravel_index(np.argmax(delta),delta.shape)
                def integrand(z):
                    hn=mu[idx]+.95*(h[idx]-mu[idx])+sigma[idx]*z
                    return stdtr(5,(threshold-beta[idx])*np.exp(-hn/2))*np.exp(-z*z/2)/np.sqrt(2*np.pi)
                reference,error=quad(integrand,-12,12,epsabs=1e-12,epsrel=1e-12,limit=200)
                checks.append(dict(method=method,threshold=threshold,max_64_128_difference=float(delta[idx]),worst_chain=int(idx[0]),worst_draw=int(idx[1]),worst_128_vs_quad=float(abs(high[idx]-reference)),quad_error=float(error),pass_numerical=bool(delta[idx]<=1e-6 and abs(high[idx]-reference)<=1e-6 and error<=1e-9)))
                values[f'cdf_{k}']=high;arrays[f'{method}_cdf_{k}']=high
            summary=az.summary(az.from_dict(posterior=values),round_to='none');summary.to_csv(out/f'fixture-{j}-{method}.csv');methods[method]=summary
        left,right=methods['warm'],methods['cold'];table=left.add_prefix('warm_').join(right.add_prefix('cold_'))
        table['combined_z']=(left['mean']-right['mean'])/np.hypot(left.mcse_mean,right.mcse_mean)
        table.to_csv(out/f'fixture-{j}-comparison.csv');np.savez_compressed(out/f'fixture-{j}-functionals.npz',**arrays)
        rows.append(dict(index=j,path=path,update=update,numerical_checks=checks,max_abs_mean_z=float(abs(table.combined_z).max()),flags_over_4=table.index[abs(table.combined_z)>4].tolist(),diagnostic_failures={name:s.index[(s.r_hat>1.01)|(s.ess_bulk<400)|(s.ess_tail<400)|(~np.isfinite(s[['r_hat','ess_bulk','ess_tail']]).all(axis=1))].tolist() for name,s in methods.items()}));cold.close()
    result=dict(rows=rows,bindings=bindings,thresholds=thresholds,coordinate_reports_reproduced=True,elapsed_seconds=time.monotonic()-started,scope='Predeclared repeated-update synthetic latent-increment CDF agreement; not observed-cell forecasts, predictive calibration, decision value or profitability',sources={n:hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest() for n in ['price_cell_repeated_predictive_report.py','price_cell_predictive.py','REPEATED-MANIFEST.json']})
    (out/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':run(*sys.argv[1:])
