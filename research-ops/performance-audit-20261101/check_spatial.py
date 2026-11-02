"""Isolated exact-model candidate; never replaces archived or active model binaries."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time
import numpy as np
import bridgestan as bs
from bridgestan.compile import compile_model, set_bridgestan_path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'STUDIES/usefulness_search_v1/spatial_counts_v1'
LOCAL=BASE.parent/'metric_blocks/local_recovery'
compiler=Path(json.loads((LOCAL/'threaded_build01/SUPERVISION.json').read_text())['build_directory'])/'bridgestan-2.9.0'
set_bridgestan_path(compiler)
data=(BASE/'data01/GP-TRAIN.json').read_text()
reference=bs.StanModel(str(BASE/'model01/spatial_gp_model.so'),data=data,seed=1)
with tempfile.TemporaryDirectory(prefix='owalnuts-spatial-performance-') as folder:
    source=Path(folder)/'spatial_gp_precomputed.stan'
    shutil.copyfile(BASE/source.name,source)
    library=compile_model(source,make_args=['-j1','STAN_THREADS=true'])
    candidate=bs.StanModel(str(library),data=data,seed=1)
    points=np.random.default_rng(952100001).normal(scale=.25,size=(8,205))
    rows=[]
    for q in points:
        av,ag=reference.log_density_gradient(q)
        bv,bg=candidate.log_density_gradient(q)
        a=reference.param_constrain(q,include_tp=True,include_gq=False)
        b=candidate.param_constrain(q,include_tp=True,include_gq=False)
        row=dict(density_error=float(abs(av-bv)),gradient_scaled_error=float(np.max(abs(ag-bg)/np.maximum(1,abs(ag)))),functional_error=float(np.max(abs(a-b))))
        rows.append(row)
    timings=[]
    for _ in range(5):
        pair=[]
        for model in [reference,candidate]:
            start=time.perf_counter()
            for _ in range(10):
                for q in points:model.log_density_gradient(q)
            pair.append((time.perf_counter()-start)/80)
        timings.append(pair)
    passed=all(r['density_error']<=1e-5 and r['gradient_scaled_error']<=1e-3 and r['functional_error']<=1e-5 for r in rows)
    result=dict(numerical_preflight_passed=passed,rows=rows,seconds_per_evaluation=timings,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),scope='Same mathematical target; numerical preflight and fixed-point latency only. No posterior qualification.')
    (Path(__file__).parent/'spatial-candidate.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
