import ctypes,hashlib,json,platform,shutil,subprocess,sys
from pathlib import Path
import numpy as np,bridgestan as bs,nutpie
from native_common import counter_handle,counter_read,native_model
p=Path(__file__).resolve().parent;out=p/'preflight';out.mkdir(exist_ok=False);manifest=json.loads((p/'MANIFEST.json').read_text())
for name,h in manifest.items():assert hashlib.sha256((p/name).read_bytes()).hexdigest()==h
rows=[]
for arm in ['raw','bounded']:
 d=out/arm;d.mkdir();so=p/'models'/(arm+'.so');source=p/'models'/(arm+'.stan');data=p/'data'/('0.json' if arm=='raw' else '0-bounded.json')
 for name in ['count_target.cpp','bridgestan.h']:shutil.copyfile(p/name,d/name)
 (d/'original_path.h').write_text('#define ORIGINAL_LIBRARY '+json.dumps(str(so))+'\n');shim=d/'counted_model.so'
 command=['g++','-shared','-fPIC','-O2','-std=c++17',str(d/'count_target.cpp'),'-Wl,--no-as-needed',str(so),'-Wl,--as-needed','-ldl','-o',str(shim)];subprocess.run(command,check=True,timeout=90)
 counted=bs.StanModel(str(shim),data=data.read_text(),seed=1);direct=bs.StanModel(str(so),data=data.read_text(),seed=1);c=counter_handle(shim);c.ow_reset_target_calls();a=counted.log_density_gradient(np.zeros(13));counts=counter_read(c);b=direct.log_density_gradient(np.zeros(13));assert counts==dict(value=0,gradient=1,hessian=0,hvp=0) and np.allclose(a[0],b[0],rtol=1e-12) and np.allclose(a[1],b[1],rtol=1e-12)
 c.ow_reset_target_calls();trace=nutpie.sample(native_model(shim,data,source),draws=20,tune=30,chains=4,cores=4,seed=950600001,save_warmup=True,progress_bar=False,adaptation='diag',target_accept=.9,maxdepth=10,store_unconstrained=True,step_size_jitter=0.);q=np.asarray(trace.sample_stats.unconstrained_draw);assert q.shape==(4,20,13) and np.isfinite(q).all();native_counts=counter_read(c);assert native_counts['gradient']>0;trace.close()
 spec=dict(model=str(so),data=str(data),starts=np.random.default_rng(950600001).uniform(-2,2,(4,13)).tolist(),seed=950600001,warmup=30,draws=20,arm='dense',target_accept=.9);(d/'INPUT.json').write_text(json.dumps(spec));subprocess.run([str(p/'gp-wal-tuned-runner'),str(d/'INPUT.json'),str(d/'RAW.json')],check=True,timeout=90);raw=json.loads((d/'RAW.json').read_text());assert np.asarray(raw['draws']).shape==(4,20,13) and np.isfinite(raw['draws']).all()
 rows.append(dict(arm=arm,passed=True,command=command,shim_sha256=hashlib.sha256(shim.read_bytes()).hexdigest(),probe_counts=counts,native_calls=native_counts,wal_calls=raw['target_calls']))
for name,h in manifest.items():assert hashlib.sha256((p/name).read_bytes()).hexdigest()==h
(out/'SUMMARY.json').write_text(json.dumps(dict(passed=True,rows=rows,python=sys.version,platform=platform.platform(),numpy=np.__version__,nutpie=nutpie.__version__,bridgestan=bs.__version__,scope='Runtime/counter/finite-draw smoke only; no posterior qualification or timing comparison'),indent=2)+'\n');print(json.dumps(rows))
