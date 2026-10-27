"""Development resident predictive processor. No qualification or quoting policy."""
import argparse, hashlib, importlib.util, json, platform, sys, time
from pathlib import Path
import numpy as np
from scipy.optimize import brentq
from scipy.special import ndtr
import scipy, numba, owalnuts
from sv_target import TargetOwner, compile_target, compile_functional, remap, RHO
HERE=Path(__file__).resolve().parent
PROCESS=HERE.parent/'amm_predictive_review_v1/predictive-return-smoke/process.py'
spec=importlib.util.spec_from_file_location('review_return_processor',PROCESS)
processor=importlib.util.module_from_spec(spec); spec.loader.exec_module(processor)

def identity(path):
    path=Path(path); return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())

def summarize(values,deadline):
    a=np.asarray(values,dtype=float)
    if a.ndim!=3 or a.shape[-1]!=4 or not np.isfinite(a).all():
        raise ValueError('invalid compact components')
    a=a.reshape(-1,4); sigma=np.exp(a[:,1]); m=a[:,0]+RHO*(a[:,3]-a[:,0])
    if not np.isfinite(sigma).all() or np.any(sigma<=0): raise ValueError('invalid sigma')
    lo=float(np.min(m-12*sigma)); hi=float(np.max(m+12*sigma))
    def cdf_h(x):
        if time.perf_counter()>deadline: raise TimeoutError('tick deadline')
        return float(ndtr((x-m)/sigma).mean())
    hq=[brentq(lambda x:cdf_h(x)-p,lo,hi,xtol=1e-12) for p in (.5,.95)]
    scale=np.exp(np.array(hq)/2)
    if not np.isfinite(scale).all() or np.any(scale<=0): raise ValueError('scale overflow')
    cdfs=[processor.ReturnCDF(m,sigma,a[:,2],5,n,deadline,64*1024*1024) for n in (64,128)]
    rules=[c.quantiles() for c in cdfs]
    discrepancy=max(abs(cdfs[0](q)-p) for p,q in zip(processor.PS,rules[1]['quantiles']))
    width=rules[1]['quantiles'][2]-rules[1]['quantiles'][0]
    endpoint=max(abs(x-y)/width for x,y in zip(rules[0]['quantiles'],rules[1]['quantiles']))
    if discrepancy>1e-6 or endpoint>1e-6: raise ValueError('64/128 numerical disagreement')
    return dict(scale_p50_p95=scale.tolist(),return_p5_p50_p95=rules[1]['quantiles'],
        numerical=dict(nodes=[64,128],cdf_discrepancy=discrepancy,normalized_endpoint_difference=endpoint,rules=rules))

class Resident:
    def __init__(self,compiled,functional,y,state,seed=99371001):
        self.compiled=compiled; self.functional=functional; self.y=np.array(y,copy=True)
        self.owner=TargetOwner(compiled,self.y)
        self.session=owalnuts.WarmSession(self.owner.target,state,seed=seed,threads=4,
            tuning=owalnuts.Tuning(max_depth=8),max_target_evaluations=2000000,admit_worst_case=False)
    def tick(self,y_new,k):
        start=time.perf_counter(); row={'status':'failed','k':k}
        try:
            if not np.isfinite(y_new): raise ValueError('nonfinite observation')
            self.y=np.append(self.y[1:],y_new)
            state=remap(self.session.state())
            owner=TargetOwner(self.compiled,self.y)
            self.session.retarget(owner.target,state); self.owner=owner
            preparation=time.perf_counter()-start
            chunk=self.session.refresh_functionals(k,[self.functional])
            sampling_end=time.perf_counter()
            row.update(summarize(chunk.values,start+30))
            row.update(status='ok',chain_ids=list(range(chunk.values.shape[0])),shape=list(chunk.values.shape),
                       preparation_seconds=preparation,sampling_seconds=sampling_end-start-preparation,
                       summary_seconds=time.perf_counter()-sampling_end,seed=int(chunk.seed),
                       diagnostics_repr=repr(chunk.diagnostics),metadata_repr=repr(chunk.metadata))
        except Exception as exc:
            row['error']=repr(exc)
        row['total_seconds']=time.perf_counter()-start
        return row
    def close(self): self.session.close()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists(): raise SystemExit('Refusing to overwrite output')
    args.out.mkdir(parents=True)
    result=dict(kind='development smoke only; no qualification',rows=[],platform=platform.platform(),
        python=sys.version,versions=dict(numpy=np.__version__,scipy=scipy.__version__,numba=numba.__version__),
        source=[identity(HERE/'harness.py'),identity(HERE/'sv_target.py'),identity(PROCESS)],
        native=[identity(p) for p in Path(owalnuts.__file__).parent.rglob('*.pyd')],
        configuration=dict(N=12,K=8,chains=4,max_depth=8,seed=99371001,initial_seed=99371002,
        data_seed=99371003,append_innovation=0,mass_append=1,numerical_nodes=[64,128],
        max_target_evaluations=2000000,admit_worst_case=False,
        initial_warmup=100,initial_draws=10,early_shift_update=2),
        limitations='Different development seeds/initialization/API seed schedule from WP96; tiny N; no posterior accuracy claim')
    resident=None
    try:
        rng=np.random.default_rng(99371003); y=rng.standard_t(5,16)*.005
        y[13:]*=2 # first changed observation enters at update 2; explicit artificial scale jump
        started=time.perf_counter(); compiled=compile_target(); functional=compile_functional()
        owner=TargetOwner(compiled,y[:12]); init=np.zeros((4,15));init[:,0]=2*np.log(.005);init[:,1]=np.log(.2)
        fitted=owalnuts.sample(owner.target,15,init=init,chains=4,warmup=100,draws=10,
            seed=99371002,threads=4,tuning=owalnuts.Tuning(max_depth=8))
        resident=Resident(compiled,functional,y[:12],fitted.warm_state())
        result['initialization_seconds']=time.perf_counter()-started
        for tick in range(1,5):
            row=resident.tick(y[11+tick],8);row['tick']=tick;row['new_observation']=float(y[11+tick]);result['rows'].append(row)
            (args.out/'results.json').write_text(json.dumps(result,indent=2))
            if row['status']!='ok': break
        result['status']='complete' if len(result['rows'])==4 and all(r['status']=='ok' for r in result['rows']) else 'failed'
    except Exception as exc: result.update(status='failed',error=repr(exc))
    finally:
        if resident is not None: resident.close()
        (args.out/'results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(status=result['status'],rows=len(result['rows']))))
if __name__=='__main__':main()
