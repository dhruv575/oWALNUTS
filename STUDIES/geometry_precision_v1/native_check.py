"""Pinned nutpie C ABI and WALNUTS C ABI around the identical Numba target."""
import time
START=time.monotonic()
import sys,json,traceback,ctypes
from pathlib import Path
source=Path(__file__).resolve().parent.parent/'source'
if source.is_dir():sys.path.insert(0,str(source))
import numpy as np
import numba,owalnuts,nutpie
from nutpie.compile_pymc import CompiledPyMCModel
from targets import Target,core
from metrics import assess

CONFIGS=['walnuts_99','nuts_99','nuts_lowrank99','nuts_drawmass99']
BUDGETS=[3000,6000,12000]


class Native:
    def __init__(self,target):
        d=target.dim;kind=target.kind;P=target.precision.copy();self.counter=np.zeros(2,dtype=np.float64)
        sig=numba.types.int64(numba.types.uint64,numba.types.CPointer(numba.types.double),numba.types.CPointer(numba.types.double),numba.types.CPointer(numba.types.double),numba.types.voidptr)
        @numba.cfunc(sig,nopython=True,error_model='numpy')
        def nuts_logp(dim,qp,gp,lp,user):
            if dim!=d:return -1
            counts=numba.carray(user,(2,),dtype=numba.types.float64);counts[0]+=1
            q=numba.carray(qp,(d,));g=numba.carray(gp,(d,));value,gradient=core(q,kind,P)
            for i in range(d):g[i]=gradient[i]
            lp[0]=value
            if not np.isfinite(value) or not np.isfinite(gradient).all():counts[1]+=1;return 1
            return 0
        esig=numba.types.int64(numba.types.uint64,numba.types.uint64,numba.types.CPointer(numba.types.double),numba.types.CPointer(numba.types.double),numba.types.voidptr)
        @numba.cfunc(esig,nopython=True)
        def expand(dim,expanded,qp,out,user):
            if dim!=d or expanded!=d:return -1
            for i in range(d):out[i]=qp[i]
            return 0
        @numba.cfunc(owalnuts.numba_raw_signature(),nopython=True,error_model='numpy')
        def walnuts_logp(dim,qp,gp,user):
            if dim!=d:return np.nan
            counts=numba.carray(user,(2,),dtype=numba.types.float64);counts[0]+=1
            q=numba.carray(qp,(d,));g=numba.carray(gp,(d,));value,gradient=core(q,kind,P)
            for i in range(d):g[i]=gradient[i]
            if not np.isfinite(value) or not np.isfinite(gradient).all():
                counts[1]+=1
                for i in range(d):g[i]=0.
                return -np.inf
            return value
        self.nuts_logp=nuts_logp;self.expand=expand;self.walnuts_logp=walnuts_logp
        starts=iter(target.initial());self.initial_calls=0
        def initial(seed):self.initial_calls+=1;return next(starts).copy()
        self.nuts=CompiledPyMCModel(dims=None,compiled_logp_func=nuts_logp,compiled_expand_func=expand,initial_point_func=initial,
            shared_data={},user_data=self.counter,n_expanded=d,shape_info=(['q'],None,[(d,)]),logp_func=None,expand_func=None,_n_dim=d,_shapes={'q':(d,)},_coords={})
        self.walnuts=owalnuts.from_cfunc(walnuts_logp,d,user_data=self.counter.ctypes.data)

    def values(self,q):
        q=np.ascontiguousarray(q,dtype=float);g=np.empty_like(q);h=np.empty_like(q);lp=np.zeros(1)
        ptr=ctypes.POINTER(ctypes.c_double);user=ctypes.c_void_p(self.counter.ctypes.data)
        status=self.nuts_logp.ctypes(len(q),q.ctypes.data_as(ptr),g.ctypes.data_as(ptr),lp.ctypes.data_as(ptr),user)
        other=self.walnuts_logp.ctypes(len(q),q.ctypes.data_as(ptr),h.ctypes.data_as(ptr),user)
        return status,lp[0],g,other,h


def sample(target,owner,config,seed,draws):
    owner.counter[:]=0;start=time.monotonic()
    if config.startswith('walnuts'):
        fit=owalnuts.sample(owner.walnuts,dim=target.dim,init=target.initial(),chains=4,threads=1,warmup=750,draws=draws,seed=seed,
            tuning=owalnuts.Tuning(max_depth=10),adaptation=owalnuts.Adaptation(target_accept=.99))
        q=fit.samples;div=int(fit.divergent[:,750:].sum());depth=int((fit.depth[:,750:]>=10).sum())
    else:
        extra={'use_grad_based_mass_matrix':False} if config=='nuts_drawmass99' else {}
        fit=nutpie.sample(owner.nuts,chains=4,cores=1,tune=750,draws=draws,seed=seed,progress_bar=False,save_warmup=False,target_accept=.99,maxdepth=10,
            low_rank_modified_mass_matrix=config=='nuts_lowrank99',transform_adapt=False,**extra)
        q=np.asarray(fit.posterior.q.values);div=int(fit.sample_stats.diverging.sum());depth=int(fit.sample_stats.maxdepth_reached.sum());fit.close()
        if owner.initial_calls!=4:raise ValueError('Initial point identity')
    return q,dict(seconds=time.monotonic()-start,target_calls=int(owner.counter[0]),nonfinite_calls=int(owner.counter[1]),divergences=div,depth_hits=depth)


def run(config,rep,draws,out):
    rep=int(rep);draws=int(draws);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    seed=675000000+CONFIGS.index(config)*100000+rep*1000+BUDGETS.index(draws)
    result=dict(name='banana',config=config,rep=rep,draws=draws,seed=seed,runtime_import_seconds=time.monotonic()-START)
    try:
        start=time.monotonic();t=Target('banana');owner=Native(t);result['setup_seconds']=time.monotonic()-start
        q,info=sample(t,owner,config,seed,draws);result.update(info)
        start=time.monotonic();result['metrics']=assess(t,q,info['divergences'],info['depth_hits']);result['diagnostic_seconds']=time.monotonic()-start
        np.savez_compressed(out/'draws.npz',draws=q);result['status']='ok'
    except Exception as exc:
        result.update(status='failed',error=repr(exc));(out/'ERROR.txt').write_text(traceback.format_exc())
    result['total_seconds']=time.monotonic()-START
    (out/'RESULT.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':run(*sys.argv[1:])
