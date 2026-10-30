"""Exposed affine-transform recovery qualification, not sampling validation."""
import json,sys,hashlib
from pathlib import Path
study=Path(__file__).resolve().parent;root=study/'local_recovery/native_transform_probe01'
if len(sys.argv)==1:
    root.mkdir(exist_ok=False);sys.path.insert(0,str(study/'local_recovery/inputs'))
    from resource_monitor import execute
    r=execute([sys.executable,str(Path(__file__)),'worker'],str(root),180,root,2*1024**3,64*1024**2,root/'worker.log',output_scan_interval=2)
    (root/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained']
else:
    import numpy as np,nutpie
    from native_common import model_files,native_model
    so,data,source=model_files('arK-arK');results={};rows=[]
    for store in [False,True]:
        t=nutpie.sample(native_model(so,data,source),draws=100,tune=200,chains=4,cores=4,seed=940700001,save_warmup=True,progress_bar=False,adaptation='low_rank',target_accept=.8,maxdepth=10,store_unconstrained=True,store_transformed=store,store_gradient=store,store_mass_matrix=store,mass_matrix_eigval_cutoff=2.,mass_matrix_gamma=1e-5)
        arrays={k:np.asarray(v.values).copy() for k,v in t['sample_stats'].data_vars.items()};results[store]=arrays
        np.savez_compressed(root/('stored.npz' if store else 'plain.npz'),**{k:v for k,v in arrays.items() if v.dtype.kind in 'biuf'});t.close()
    a=results[True];assert np.array_equal(results[False]['unconstrained_draw'],a['unconstrained_draw'])
    for c in range(4):
        x=a['unconstrained_draw'][c];z=a['transformed_position'][c];g=a['gradient'][c];gz=a['transformed_gradient'][c]
        assert len(np.unique(a['transformation_index'][c]))==1
        design=np.column_stack([z,np.ones(100)]);coef,_,rank,_=np.linalg.lstsq(design[:50],x[:50],rcond=None)
        assert rank==x.shape[1]+1 and np.linalg.cond(design[:50])<1e8
        A=coef[:-1].T;mu=coef[-1];C=A@A.T
        residual=float(np.max(np.abs(design[50:]@coef-x[50:]))/(1+np.max(np.abs(x[50:]))))
        gradient_residual=float(np.max(np.abs(g@A-gz))/(1+np.max(np.abs(gz))))
        assert residual<1e-10 and gradient_residual<1e-10 and np.linalg.eigvalsh(C).min()>0
        rows.append(dict(chain=c,heldout_relative_position_residual=residual,relative_gradient_residual=gradient_residual,design_condition=float(np.linalg.cond(design[:50])),A=A.tolist(),mu=mu.tolist(),covariance=C.tolist()))
    out=dict(passed=True,scope=__doc__,exact_retained_trajectory_parity=True,rows=rows,inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),study/'native_common.py',so,data,source]})
    (root/'SUMMARY.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(passed=True,chains=4)))
