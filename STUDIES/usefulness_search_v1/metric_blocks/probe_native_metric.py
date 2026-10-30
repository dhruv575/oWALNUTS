"""Bounded exposed API probe: can the pinned native engine export its metric?"""
import json,sys
from pathlib import Path
study=Path(__file__).resolve().parent;root=study/'local_recovery/native_metric_probe01'
if len(sys.argv)==1:
    root.mkdir(exist_ok=False);sys.path.insert(0,str(study/'local_recovery/inputs'))
    from resource_monitor import execute
    r=execute([sys.executable,str(Path(__file__)),'worker'],str(root),180,root,2*1024**3,64*1024**2,root/'worker.log',output_scan_interval=2)
    (root/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n')
    assert r['exit_code']==0 and r['group_drained']
else:
    import numpy as np,nutpie
    from native_common import model_files,native_model
    so,data,source=model_files('arK-arK');results={};rows=[]
    for store in [False,True]:
        t=nutpie.sample(native_model(so,data,source),draws=100,tune=200,chains=4,cores=4,seed=940700001,save_warmup=True,progress_bar=False,adaptation='low_rank',target_accept=.8,maxdepth=10,store_unconstrained=True,store_mass_matrix=store,mass_matrix_eigval_cutoff=2.,mass_matrix_gamma=1e-5)
        stats=t['sample_stats'];arrays={k:np.asarray(v.values).copy() for k,v in stats.data_vars.items()};results[store]=arrays['unconstrained_draw']
        numeric={k:v for k,v in arrays.items() if v.dtype.kind in 'biuf'};np.savez_compressed(root/('stored.npz' if store else 'plain.npz'),**numeric)
        rows.append(dict(store_mass_matrix=store,fields={k:dict(shape=list(v.shape),dtype=str(v.dtype)) for k,v in arrays.items()}));t.close()
    out=dict(scope=__doc__,exact_retained_trajectory_parity=bool(np.array_equal(results[False],results[True])),rows=rows)
    (root/'SUMMARY.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
