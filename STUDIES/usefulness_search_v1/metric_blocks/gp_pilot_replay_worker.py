import hashlib,json,sys,time
from pathlib import Path
import numpy as np
import nutpie
from native_common import LOCAL,STUDY,model_files,counter_handle,counter_read,native_model
from bounded_transport import fit
out=Path(sys.argv[1]);fold=int(sys.argv[2]);seed=946200001+2*fold
old=LOCAL/f'gp_fresh_comparison01/low_rank-{seed}'
original=json.loads((old/'SUMMARY.json').read_text());assert original['passed']
spec=json.loads((old/'INPUT.json').read_text());kwargs=spec['settings'];assert kwargs['seed']==seed and kwargs['draws']==2000 and kwargs['tune']==1100
so,data,source=model_files('gp_pois_regr-gp_pois_regr');shim=LOCAL/'nativemodels01/gp_pois_regr-gp_pois_regr/counted_model.so'
build=json.loads((shim.parent/'BUILD.json').read_text());assert hashlib.sha256(shim.read_bytes()).hexdigest()==build['shim_sha256']
c=counter_handle(shim);c.ow_reset_target_calls();t=time.perf_counter();trace=nutpie.sample(native_model(shim,data,source),**kwargs);sampling=time.perf_counter()-t;calls=counter_read(c)
q=np.asarray(trace.sample_stats.unconstrained_draw.values).copy();trace.close();assert q.shape==(4,2000,13) and np.isfinite(q).all()
np.savez_compressed(out/'DRAWS.npz',q=q);prior=np.load(old/'DRAWS-STATS.npz')['sample_stats__unconstrained_draw']
t=time.perf_counter();m=fit(q[:,:100].reshape(-1,13));fitting=time.perf_counter()-t
t=time.perf_counter();(out/'MAP.json').write_text(json.dumps(m,indent=2)+'\n');serialization=time.perf_counter()-t
mapfile=LOCAL/f'bounded_transport01/fold-{fold}/MAP.json';previous=json.loads(mapfile.read_text())
checks=dict(draws_bit_identical=np.array_equal(q,prior,equal_nan=True),calls_identical=calls==original['calls'],map_identical=m==previous)
files=[Path(__file__),STUDY/'bounded_transport.py',STUDY/'GP-PILOT-REPLAY-PROTOCOL.md',old/'INPUT.json',old/'SUMMARY.json',old/'DRAWS-STATS.npz',mapfile,so,data,source,shim]
result=dict(fold=fold,seed=seed,passed=bool(all(checks.values())),checks={k:bool(v) for k,v in checks.items()},calls=calls,sampling_seconds=sampling,map_fit_seconds=fitting,map_serialization_seconds=serialization,inputs={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files})
(out/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
