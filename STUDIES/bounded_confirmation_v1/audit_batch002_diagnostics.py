"""Recompute final-batch diagnostics through explicit ArviZ APIs, not worker summary."""
import concurrent.futures,hashlib,json,os,sys,time
from pathlib import Path
import numpy as np
import pandas as pd
import arviz as az

ROOT=Path('/home/ubuntu/lanes/bounded-confirmation-20261028')
MANIFEST=Path('/home/ubuntu/lanes/bounded-confirmation-20261028/batch-002/RAW-MANIFEST.json')

def scalar(value):
    a=np.asarray(value)
    assert a.size==1
    return a.item()

def audit(task):
    j,method=task;folder=ROOT/f'batch-002/job-{j}/fit/{method}'
    manifest=json.loads(MANIFEST.read_text())
    for name in ['draws.npz','joint.npz','predictive.npz','coordinates.csv','functionals.csv']:
        p=folder/name
        with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        assert digest==manifest[p.relative_to(ROOT).as_posix()]['sha256']
    with np.load(folder/'draws.npz') as data:s=data['draws'].copy()
    cap=json.loads((ROOT/'CALENDAR.json').read_text())['cells'][j]['cap']
    # Reconstruct using the defining transforms without the worker helper.
    log_sigma=np.log(cap)-np.logaddexp(0,s[:,:,1]);sigma=np.exp(log_sigma)
    z=s[:,:,3:];latent=np.empty_like(z);latent[:,:,0]=z[:,:,0]/np.sqrt(1-.95**2)
    for t in range(1,z.shape[2]):latent[:,:,t]=.95*latent[:,:,t-1]+z[:,:,t]
    h=s[:,:,0,None]+sigma[:,:,None]*latent
    beta=np.exp(h.mean(axis=2)/2)*s[:,:,2]
    with np.load(folder/'joint.npz') as data:joint=data['draws'].copy()
    np.testing.assert_allclose(beta,joint[:,:,2],rtol=1e-12,atol=1e-15)
    beta_roundoff=float(np.max(np.abs(beta-joint[:,:,2])))
    # Use archived physical values for exact rank/tie reproduction after checking
    # the independently reconstructed transform; algebraic roundoff can split ties.
    beta=joint[:,:,2]
    values={'mu':s[:,:,0],'log_sigma':log_sigma,'beta':beta,'b':s[:,:,2]}
    values.update({f'z[{i}]':z[:,:,i] for i in range(z.shape[2])})
    with np.load(folder/'predictive.npz') as pred:
        functions={'density':pred['scaled_density'].copy(),'pit':pred['pit'].copy()}
    max_errors={k:0. for k in ['r_hat','ess_bulk','ess_tail','mcse_mean']}
    for group,csv in [(values,'coordinates.csv'),(functions,'functionals.csv')]:
        saved=pd.read_csv(folder/csv,index_col=0)
        assert set(group)==set(saved.index)
        for name,a in group.items():
            estimates=dict(r_hat=scalar(az.rhat(a,method='rank')),ess_bulk=scalar(az.ess(a,method='bulk')),ess_tail=scalar(az.ess(a,method='tail')),mcse_mean=scalar(az.mcse(a,method='mean')))
            assert estimates['r_hat']<=1.01 and min(estimates['ess_bulk'],estimates['ess_tail'])>=400
            for k,v in estimates.items():
                prior=float(saved.loc[name,k]);err=abs(v-prior)/max(1.,abs(prior));max_errors[k]=max(max_errors[k],err)
                assert np.isclose(v,prior,rtol=1e-8,atol=1e-10),(j,method,name,k,v,prior)
    return dict(index=j,method=method,coordinates=len(values),functionals=len(functions),beta_reconstruction_max_absolute_error=beta_roundoff,max_scaled_errors=max_errors)

if __name__=='__main__':
    start=time.monotonic();out=Path(sys.argv[1]);assert not out.exists()
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(audit,[(j,m) for j in range(24,36) for m in ['nuts','walnuts']]))
    result=dict(scope='Confirmation batch 002 only: independently reconstructed coordinates and explicit ArviZ rank/ESS/MCSE APIs; same diagnostic library, not an independent statistical estimator',fits=len(rows),rows=rows,elapsed_seconds=time.monotonic()-start,arviz=az.__version__,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(fits=len(rows),elapsed_seconds=result['elapsed_seconds'])))
