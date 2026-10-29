import time,sys,json,traceback
from pathlib import Path
source=Path(__file__).resolve().parent.parent/'source'
if source.is_dir():sys.path.insert(0,str(source))
import numpy as np
import owalnuts
from targets import Target,NAMES
from sampling import CONFIGS,fit
from metrics import assess


class Shifted:
    def __init__(self,name,offset):
        self.base=Target(name);self.dim=self.base.dim;self.offset=np.zeros(self.dim);self.offset[0]=offset
    def __call__(self,q):return self.base(q-self.offset)
    def initial(self):return self.base.initial() # No oracle shift of starting positions.
    def features(self,q):return self.base.features(q-self.offset)
    def truth(self):return self.base.truth()
    def tolerance(self):return self.base.tolerance()
    @property
    def calls(self):return self.base.calls
    @calls.setter
    def calls(self,v):self.base.calls=v
    @property
    def nonfinite(self):return self.base.nonfinite
    @nonfinite.setter
    def nonfinite(self,v):self.base.nonfinite=v


def run(name,path,rep,selection,out):
    rep=int(rep);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    selected=json.loads(Path(selection).read_text())['selected'][name]
    seed=645000000+NAMES.index(name)*100000+(10000 if path=='abrupt' else 0)+rep*1000
    results=[]
    for mode in ['walnuts_warm','nuts_cold','walnuts_cold']:
        series_start=time.monotonic();rows=[];initialization=0.;session=None
        try:
            if mode=='walnuts_warm':
                stamp=time.monotonic();target=Shifted(name,0);c=CONFIGS[selected['walnuts']]
                first=owalnuts.sample(target,dim=target.dim,init=target.initial(),chains=4,threads=1,warmup=750,draws=3000,seed=seed,
                    tuning=owalnuts.Tuning(max_depth=10),adaptation=owalnuts.Adaptation(target_accept=c['accept']))
                initial_metrics=assess(target,first.samples,int(first.divergent[:,750:].sum()),int((first.depth[:,750:]>=10).sum()))
                np.savez_compressed(out/'warm-initial.npz',draws=first.samples)
                session=owalnuts.WarmSession(target,first.warm_state(),seed=seed+100,threads=1,tuning=owalnuts.Tuning(max_depth=10))
                initialization=time.monotonic()-stamp
            else:initial_metrics=None
            for tick in range(1,7):
                offset=.1*tick if path=='smooth' else (0. if tick<3 else 2.)
                stamp=time.monotonic();target=Shifted(name,offset)
                if session is not None:
                    session.retarget(target,session.state());chunk=session.refresh(3250);q=chunk.samples[:,250:,:]
                    div=sum(int(d['divergent'][250:].sum()) for d in chunk.diagnostics)
                    depth=sum(int((d['depth'][250:]>=10).sum()) for d in chunk.diagnostics)
                    info=dict(target_calls=target.calls,divergences=div,depth_hits=depth)
                else:
                    engine=mode.split('_')[0];q,info=fit(target,selected[engine],seed+200+tick*10+(mode=='walnuts_cold'),3000)
                metrics=assess(target,q,info['divergences'],info['depth_hits']);np.savez_compressed(out/f'{mode}-{tick}.npz',draws=q)
                elapsed=time.monotonic()-stamp
                if 'seconds' in info:info['sampler_seconds']=info.pop('seconds')
                rows.append(dict(tick=tick,offset=offset,seconds=elapsed,metrics=metrics,**info))
            results.append(dict(mode=mode,status='ok',initialization_seconds=initialization,initial_metrics=initial_metrics,updates=rows,total_seconds=time.monotonic()-series_start))
        except Exception as exc:
            results.append(dict(mode=mode,status='failed',error=repr(exc),updates=rows,total_seconds=time.monotonic()-series_start));(out/f'{mode}-ERROR.txt').write_text(traceback.format_exc())
        finally:
            if session is not None:session.close()
        (out/'RESULT.json').write_text(json.dumps(dict(name=name,path=path,rep=rep,seed=seed,results=results),indent=2,allow_nan=False)+'\n')


if __name__=='__main__':run(*sys.argv[1:])
