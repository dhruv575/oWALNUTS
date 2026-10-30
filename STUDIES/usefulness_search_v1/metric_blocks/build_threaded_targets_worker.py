import hashlib,json,shutil,sys
from pathlib import Path
import numpy as np
import bridgestan as bs
from bridgestan.compile import compile_model,set_bridgestan_path
study=Path(__file__).resolve().parent;local=study/'local_recovery';model=sys.argv[1];out=Path(sys.argv[2]);work=Path(sys.argv[3]);originals=local/'inputs/models'
source=originals/(model+'.stan');data=originals/(model+'.data.json');original=originals/(model+'_model.so');pilot=local/'localscaled01/runs'/(model+'-929600001-pilot')/'RESULT.json'
base=Path(json.loads((local/'threaded_build01/SUPERVISION.json').read_text())['build_directory']);set_bridgestan_path(base/'bridgestan-2.9.0')
work.mkdir(exist_ok=False);shutil.copy2(source,work/source.name);flags=['-j1','STAN_THREADS=true'];so=compile_model(work/source.name,make_args=flags)
old=bs.StanModel(str(original),data=data.read_text(),seed=1);new=bs.StanModel(str(so),data=data.read_text(),seed=1)
assert old.param_unc_names()==new.param_unc_names() and 'STAN_THREADS=true' in new.model_info()
q=np.asarray(json.loads(pilot.read_text())['draws']);q=q.reshape(-1,q.shape[-1]);ix=np.random.default_rng(929899998).choice(len(q),64,replace=False);points=q[ix]
differences=[];errors=[]
for x in points:
    a,ga=old.log_density_gradient(x);b,gb=new.log_density_gradient(x);assert np.isfinite(a) and np.isfinite(b) and np.isfinite(ga).all() and np.isfinite(gb).all()
    differences.append(float(a-b));errors.append(float(np.max(np.abs(ga-gb)/(1+np.abs(ga)))))
de=float(np.max(np.abs(np.asarray(differences)-differences[0])));ge=max(errors)
for p in [source,data,so]:shutil.copy2(p,out/p.name)
r=dict(passed=de<=1e-6 and ge<=1e-7,model=model,density_error=de,gradient_error=ge,point_indices=ix.tolist(),points=points.tolist(),density_differences=differences,gradient_errors=errors,model_info=new.model_info(),make_args=flags,new_library_sha256=hashlib.sha256(so.read_bytes()).hexdigest(),inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,data,original,pilot,Path(__file__),study/'THREADED-TARGETS-PREFLIGHT.md']})
(out/'SUMMARY.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k not in ['points','point_indices','density_differences','gradient_errors','inputs']}));assert r['passed']
