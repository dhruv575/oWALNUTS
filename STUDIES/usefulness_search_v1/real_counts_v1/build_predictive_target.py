import hashlib,json,shutil
from pathlib import Path
import numpy as np,bridgestan as bs
from bridgestan.compile import compile_model,set_bridgestan_path
from scipy.linalg import solve_triangular
base=Path(__file__).resolve().parent;local=base.parent/'metric_blocks/local_recovery';out=base/'predictive_target01';out.mkdir(exist_ok=False);work=Path('/home/dhruv/.cache/owalnuts/real-counts-predictive01');work.mkdir(exist_ok=False)
source=base/'predictive_gp.stan';data=base/'data01/GP-TRAIN.json';cfg=json.loads(data.read_text());future=20*(np.arange(1931,1962)-1851)/79;cfg.update(N_future=31,x_future=future.tolist());(out/'DATA.json').write_text(json.dumps(cfg)+'\n')
compiler=Path(json.loads((local/'threaded_build01/SUPERVISION.json').read_text())['build_directory'])/'bridgestan-2.9.0';set_bridgestan_path(compiler);shutil.copy2(source,work/source.name);library=Path(compile_model(work/source.name,make_args=['-j1','STAN_THREADS=true']));shutil.copy2(library,out/library.name)
raw=bs.StanModel(str(local/'gp_aws_runtime_bundle01/models/raw.so'),data=data.read_text(),seed=1);pred=bs.StanModel(str(out/library.name),data=(out/'DATA.json').read_text(),seed=1);assert raw.param_unc_names()==pred.param_unc_names()
rn=raw.param_names(include_tp=True,include_gq=False);pn=pred.param_names(include_tp=True,include_gq=True);ix=[rn.index(n) for n in ['rho','alpha']+[f'f.{j}' for j in range(1,80)]];px=[pn.index(rn[i]) for i in ix];mx=[pn.index(f'future_mean.{j}') for j in range(1,32)];vx=[pn.index(f'future_variance.{j}') for j in range(1,32)]
reference=base/'reference_remote01/results/2/DRAWS-STATS.npz';q=np.load(reference)['sample_stats__unconstrained_draw'].reshape(-1,81);points=np.r_[q[np.linspace(0,len(q)-1,16,dtype=int)],np.random.default_rng(951700001).normal(scale=.25,size=(8,81))];rows=[]
for point in points:
    a,g=raw.log_density_gradient(point);b,h=pred.log_density_gradient(point);rv=np.asarray(raw.param_constrain(point,include_tp=True,include_gq=False));pv=np.asarray(pred.param_constrain(point,include_tp=True,include_gq=True));rho,alpha=np.exp(point[:2]);basis=np.r_[point[:2],np.zeros(79)];L=np.empty((79,79))
    for j in range(79):
        basis[2+j]=1;L[:,j]=np.asarray(raw.param_constrain(basis,include_tp=True,include_gq=False))[ix[2:]];basis[2+j]=0
    B=alpha**2*np.exp(-.5*((np.asarray(cfg['x'])[:,None]-future[None,:])/rho)**2);A=solve_triangular(L,B,lower=True);mu=A.T@point[2:];var=alpha**2+1e-10-np.sum(A*A,axis=0)
    row=dict(density_error=float(abs(a-b)),gradient_error=float(max(abs(g-h))),physical_error=float(max(abs(rv[ix]-pv[px]))),mean_error=float(max(abs(mu-pv[mx]))),variance_error=float(max(abs(var-pv[vx]))),min_variance=float(min(pv[vx])))
    assert np.isfinite(pv).all() and all(row[k]<=1e-8 for k in ['density_error','gradient_error','physical_error']) and row['mean_error']<=1e-6 and row['variance_error']<=1e-6 and row['min_variance']>=0,row
    rows.append(row)
result=dict(passed=True,points=points.tolist(),rows=rows,library=str(out/library.name),library_sha256=hashlib.sha256((out/library.name).read_bytes()).hexdigest(),inputs={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [source,data,reference,Path(__file__),base/'PREDICTIVE-TARGET-PROTOCOL.md']},scope='Deterministic conditional moments only; no scoring or predictive Monte Carlo qualification')
(out/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,points=len(rows))),flush=True)
