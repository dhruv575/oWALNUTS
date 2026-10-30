import ctypes,hashlib,json,shutil,subprocess
from pathlib import Path
import numpy as np
import nutpie
from nutpie import _lib
from nutpie.compile_stan import CompiledStanModel

STUDY=Path(__file__).resolve().parent;LOCAL=STUDY/'local_recovery'
MODELS=['arma-arma11','arK-arK','sblrc-blr','eight_schools-eight_schools_centered','garch-garch11','gp_pois_regr-gp_pois_regr']
ARMS=['walnuts_auto','scaled_original','scaled_fast','fisher_fast','native_draw_diag','native_diag','native_low_rank']
def model_files(model):
    root=LOCAL/'threaded_build01' if model=='sblrc-blr' else LOCAL/'threaded_targets01'/model
    s=json.loads((root/'SUMMARY.json').read_text());assert s['passed']
    so=root/(model+'_model.so');assert hashlib.sha256(so.read_bytes()).hexdigest()==s['new_library_sha256']
    return so,root/(model+'.data.json'),root/(model+'.stan')
def counter_handle(so):
    c=ctypes.CDLL(str(so));c.ow_target_calls.argtypes=[ctypes.c_uint];c.ow_target_calls.restype=ctypes.c_uint64;c.ow_reset_target_calls.argtypes=[];c.ow_reset_target_calls.restype=None
    return c
def counter_read(c):return dict(zip(['value','gradient','hessian','hvp'],[c.ow_target_calls(i) for i in range(4)]))
def build_counter(model,root):
    so,_,_=model_files(model);prior=json.loads((LOCAL/'counter01/SUMMARY.json').read_text())
    for p in [STUDY/'count_target.cpp',LOCAL/'counter01/bridgestan.h']:
        assert hashlib.sha256(p.read_bytes()).hexdigest()==prior['inputs'][str(p)];shutil.copy2(p,root/p.name)
    (root/'original_path.h').write_text('#define ORIGINAL_LIBRARY '+json.dumps(str(so))+'\n');shim=root/'counted_model.so'
    cmd=['g++','-shared','-fPIC','-O2','-std=c++17',str(root/'count_target.cpp'),'-Wl,--no-as-needed',str(so),'-Wl,--as-needed','-ldl','-o',str(shim)]
    subprocess.run(cmd,check=True);(root/'BUILD.json').write_text(json.dumps(dict(command=cmd,model_sha256=hashlib.sha256(so.read_bytes()).hexdigest(),shim_sha256=hashlib.sha256(shim.read_bytes()).hexdigest()),indent=2)+'\n')
    return shim
def native_model(so,data,source):
    return CompiledStanModel(code=source.read_text(),library=_lib.StanLibrary(str(so)),dims=None,_coords=None,model=None,data=None).with_data(**json.loads(data.read_text()))
def native_run(compiled,seed,mode,tune=1100,draws=2000):
    kwargs=dict(draws=draws,tune=tune,chains=4,cores=4,seed=seed,save_warmup=True,progress_bar=False,adaptation=mode,target_accept=.8,maxdepth=10,store_unconstrained=True)
    if mode=='low_rank':kwargs.update(mass_matrix_eigval_cutoff=2.,mass_matrix_gamma=1e-5)
    trace=nutpie.sample(compiled,**kwargs);stats=trace['sample_stats'];q=np.asarray(stats['unconstrained_draw'].values).copy();assert np.isfinite(q).all()
    saved={}
    for group in ['sample_stats','warmup_sample_stats']:
        ds=trace[group]
        if hasattr(ds,'to_dataset'):ds=ds.to_dataset()
        for key,v in ds.data_vars.items():
            a=np.asarray(v.values)
            if key!='unconstrained_draw' and a.dtype.kind in 'biuf':saved[group+'__'+key]=a
    result=dict(draws=q,retained_divergences=int(np.asarray(stats['diverging']).sum()),native_steps=int(saved['sample_stats__n_steps'].sum()+saved['warmup_sample_stats__n_steps'].sum()))
    trace.close();return result,saved,kwargs
