"""Recompute phase-correct diagnostics from frozen first-panel outputs."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
import arviz as az


def report(root,out):
    root=Path(root);out=Path(out);out.mkdir(exist_ok=False);rows=[];bindings={}
    for i in range(4):
        folder=root/'run01'/f'job-{i}'/'fit'
        for name in ('draws.npz','SAMPLER.json','REPORT.json'):
            p=folder/name;bindings[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        raw=json.loads((folder/'SAMPLER.json').read_text());warmup=raw['config']['warmup']
        with np.load(folder/'draws.npz') as f:q=f['draws']
        n=12 if i<2 else 250
        if q.shape!=(4,4000,3+2*n) or not np.isfinite(q).all():raise ValueError('Draw contract')
        div=np.array([c['divergent'] for c in raw['chains']]);depth=np.array([c['depth'] for c in raw['chains']])
        if warmup!=2000 or div.shape!=(4,6000) or depth.shape!=(4,6000):raise ValueError('Phase contract')
        trace=az.from_dict(posterior=dict(mu=q[:,:,0],log_sigma=q[:,:,1],beta=q[:,:,2],z=q[:,:,3:3+n],u=q[:,:,3+n:]))
        summary=az.summary(trace,round_to='none');summary.to_csv(out/f'fixture-{i}-coordinates.csv')
        bad=(~np.isfinite(summary[['r_hat','ess_bulk','ess_tail']]).all(axis=1))|(summary.r_hat>1.01)|(summary.ess_bulk<400)|(summary.ess_tail<400)
        rows.append(dict(index=i,coordinate_failures=summary.index[bad].tolist(),retained_divergences=int(div[:,warmup:].sum()),warmup_divergences=int(div[:,:warmup].sum()),retained_max_depth_hits=int((depth[:,warmup:]>=10).sum()),diagnostic_pass=not bool(bad.any()) and not bool(div[:,warmup:].any())))
    result=dict(fixtures=rows,bindings=bindings,correction='Original worker aggregated warmup and retained divergence/depth arrays. This report separates phases without resampling. Original reports preserved.')
    (out/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':report(sys.argv[1],sys.argv[2])
