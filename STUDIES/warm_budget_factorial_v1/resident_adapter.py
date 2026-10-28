"""Posterior-only resident path: same target/remap; deliberately no quantile roots."""
import time
import numpy as np
class InitializationFailure(RuntimeError):
    def __init__(self,cause,payload):self.payload=payload;super().__init__(str(cause))

class DrawResident:
    def __init__(self,owalnuts,targets,y,seed_map):
        self.closed=False;self.ow=owalnuts;self.targets=targets;self.y=np.array(y,copy=True)
        self.compiled=targets.compile_target();self.functional=targets.compile_functional();self.owner=targets.TargetOwner(self.compiled,self.y)
        tuning=owalnuts.Tuning(step_size=.5,max_depth=10,min_micro_steps=1,max_refinement_levels=8,max_error=1.,divergence_threshold=1000.,u_turn_rule='momentum_sum',exhaustion_rule='stop')
        adaptation=owalnuts.Adaptation(target_accept=.8,adapt_step_size=True,adapt_mass=True,metric_regularization='stan',trapped_chain_restart=True)
        init=np.zeros((4,253));init[:,0]=2*np.log(.005);init[:,1]=np.log(.2)
        started=time.perf_counter()
        fitted=owalnuts.sample(self.owner.target,253,init=init,chains=4,warmup=1000,draws=200,seed=seed_map['initial'],threads=4,tuning=tuning,adaptation=adaptation,admit_worst_case=True)
        keys=('metadata','seed','depth','stop','target_evaluations','divergent','trapped_chain_checks','work_retained','work_discarded','work_total','warmup_end','sampling_end')
        self.initial=dict(seconds=time.perf_counter()-started,summary=fitted.summary(),config=fitted.config,chain_metadata=[c.get('metadata') for c in fitted.chains],chains=[{k:c[k] for k in keys if k in c} for c in fitted.chains],chain_warnings=fitted.chain_warnings())
        try:
            self.session=owalnuts.WarmSession(self.owner.target,fitted.warm_state(),seed=seed_map['warm'],threads=4,tuning=tuning,max_target_evaluations=None,admit_worst_case=True)
        except Exception as exc:raise InitializationFailure(exc,dict(phase='session_creation',initial_fit=self.initial,seeds=seed_map)) from exc
    def advance(self,y_new,k):
        if self.closed:raise RuntimeError('closed/poisoned')
        start=time.perf_counter()
        try:
            if type(k) is not int or k not in (400,1600) or np.ndim(y_new)!=0 or not np.isfinite(y_new):raise ValueError('fixedK400or1600/finite scalar observation required')
            next_y=np.append(self.y[1:],y_new);state=self.targets.remap(self.session.state());owner=self.targets.TargetOwner(self.compiled,next_y)
            self.session.retarget(owner.target,state);self.owner=owner;self.y=next_y
            prepared=time.perf_counter();chunk=self.session.refresh_functionals(k,[self.functional]);sampled=time.perf_counter();values=np.array(chunk.values,copy=True)
            return values,dict(preparation_seconds=prepared-start,sampling_seconds=sampled-prepared,seed=int(chunk.seed),call_index=int(chunk.call_index),target_calls=int(chunk.target_calls),work=chunk.work,metadata=chunk.metadata,diagnostics=chunk.diagnostics,initial=self.initial if chunk.call_index==0 else None)
        except Exception:
            self.close();raise
    def close(self):
        if not self.closed:self.closed=True;self.session.close()
