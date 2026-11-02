import os,sys,json,time
from pathlib import Path
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import numpy as np,bridgestan as bs
from grid_backend import Native
BASE=Path(__file__).resolve().parent
def main(destination):
    out=Path(destination);out.mkdir(exist_ok=False);rows=[]
    for nx,ny in [(20,10),(40,20),(80,40)]:
        x=np.array([[a,b] for a in np.linspace(0,4,nx) for b in np.linspace(0,2,ny)])
        design=np.column_stack([np.ones(len(x)),x[:,0]-2,x[:,1]-1])
        data=dict(N=len(x),x=x.tolist(),design=design.tolist(),coef_scale=[1.,1.,1.],exposure=1.,y=np.random.default_rng(954300000+len(x)).poisson(2.,len(x)).tolist())
        (out/f'DATA-{len(x)}.json').write_text(json.dumps(data))
        native=Native(data);stan=bs.StanModel('/home/ubuntu/lanes/spatial-counts-preflight-20261030/spatial_gp_model.so',data=json.dumps(data),seed=1)
        q=np.zeros(len(x)+5);q[:2]=[np.log(.7),np.log(1.2)]
        v,g=native.value(q);pv,pg=native.model.evaluate(q);sv=stan.log_density(q,propto=True,jacobian=True)
        checks=dict(density_error=abs(v-pv),gradient_error=float(max(abs(g-pg)/np.maximum(1,abs(pg)))),stan_density_error=abs(v-sv))
        assert checks['density_error']<=1e-5 and checks['gradient_error']<=1e-3 and checks['stan_density_error']<=1e-5
        times=[]
        for repeat in range(5):
            timing={}
            for name,fn,count in [('native',native.value,100),('stan',stan.log_density_gradient,3)] if repeat%2 else [('stan',stan.log_density_gradient,3),('native',native.value,100)]:
                start=time.perf_counter()
                for _ in range(count):fn(q)
                timing[name]=(time.perf_counter()-start)/count
            times.append(timing)
        rows.append(dict(grid=[nx,ny],N=len(x),checks=checks,timings=times));native.close();del native,stan
        (out/'PARTIAL.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows[-1]),flush=True)
    (out/'SUMMARY.json').write_text(json.dumps(dict(rows=rows,scope='Synthetic regular-grid kernel scaling only, zero latent probe; no sampling, posterior or application claim'),indent=2))
if __name__=='__main__':main(sys.argv[1])
