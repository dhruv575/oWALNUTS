import hashlib,json,shutil
from pathlib import Path
import numpy as np,bridgestan as bs
from bridgestan.compile import compile_model,set_bridgestan_path
base=Path(__file__).resolve().parent;local=base.parent/'metric_blocks/local_recovery';out=base/'model01';out.mkdir(exist_ok=False);work=Path('/home/dhruv/.cache/owalnuts/spatial-counts-model01');work.mkdir(exist_ok=False);source=base/'spatial_gp.stan';data=base/'data01/GP-TRAIN.json';cfg=json.loads(data.read_text());manifest=json.loads((base/'data01/MANIFEST.json').read_text());assert hashlib.sha256(data.read_bytes()).hexdigest()==manifest['files']['GP-TRAIN.json']
compiler=Path(json.loads((local/'threaded_build01/SUPERVISION.json').read_text())['build_directory'])/'bridgestan-2.9.0';set_bridgestan_path(compiler);shutil.copy2(source,work/source.name);library=Path(compile_model(work/source.name,make_args=['-j1','STAN_THREADS=true']));shutil.copy2(library,out/library.name);target=bs.StanModel(str(out/library.name),data=data.read_text(),seed=1);assert target.param_unc_num()==205
names=target.param_names(include_tp=True,include_gq=False);ix=[names.index(n) for n in ['rho','alpha']+[f'beta.{j}' for j in range(1,4)]+[f'f.{j}' for j in range(1,201)]];points=np.random.default_rng(952100001).normal(scale=.25,size=(8,205));X=np.asarray(cfg['x']);dist=np.sum((X[:,None,:]-X[None,:,:])**2,axis=2);rows=[];offset=[]
for q in points:
    value,g=target.log_density_gradient(q);v=np.asarray(target.param_constrain(q,include_tp=True,include_gq=False))[ix];physical=np.r_[v,np.exp(v[5:])];assert physical.shape==(405,) and np.isfinite(physical).all() and np.isfinite(value) and np.isfinite(g).all();rho,alpha=np.exp(q[:2]);L=np.linalg.cholesky(alpha**2*np.exp(-.5*dist/rho**2)+np.eye(200)*1e-10);f=np.asarray(cfg['design'])@(np.asarray(cfg['coef_scale'])*q[2:5])+L@q[5:];fe=float(max(abs(f-v[5:])));formula=2*q[0]-rho+q[1]-alpha**2/8-.5*(q[2:]@q[2:])+np.asarray(cfg['y'])@(np.log(cfg['exposure'])+f)-cfg['exposure']*np.exp(f).sum();offset.append(float(value-formula));errors=[]
    for j in [0,1,2,5,204]:
        plus=q.copy();minus=q.copy();plus[j]+=1e-4;minus[j]-=1e-4;fd=(target.log_density(plus)-target.log_density(minus))/2e-4;errors.append(float(abs(fd-g[j])/max(1,abs(g[j]))))
    assert fe<=1e-5 and max(errors)<=1e-3,dict(f_error=fe,gradient_errors=errors);rows.append(dict(f_error=fe,gradient_scaled_errors=errors))
assert np.ptp(offset)<=1e-5
result=dict(passed=True,dimension=205,functionals=405,points=points.tolist(),rows=rows,density_offset_spread=float(np.ptp(offset)),library_sha256=hashlib.sha256((out/library.name).read_bytes()).hexdigest(),inputs={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [source,data,Path(__file__),base/'MODEL-PREFLIGHT-PROTOCOL.md']},scope='Model numerical preflight only; no posterior qualification')
(out/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,dimension=205,functionals=405)),flush=True)
