"""Practical re-adapting NUTS comparator, not exact warm continuation."""
import os,tempfile,time
from pathlib import Path
import numpy as np
from literal_reference import load,sha,write,extract_full,extract_compact
from rolling_initialization import initialization_center

class DrawResident:
    def __init__(self,y,seeds,settings,output,retain_ticks):
        self.closed=False;self.y=np.asarray(y,dtype=float).copy();self.seeds=seeds;self.tick=0
        self.output=Path(output);self.output.mkdir(exist_ok=False);self.retained=set(retain_ticks);self.settings=settings
        if self.y.shape!=(250,) or not np.isfinite(self.y).all():raise ValueError('Finite T250 history')
        os.environ['BRIDGESTAN']=settings['bridgestan_sdk']
        work=self.output/'compiler-workspace';work.mkdir();os.environ['TMPDIR']=str(work);tempfile.tempdir=str(work)
        import nutpie,bridgestan
        self.nutpie=nutpie;self.adapter=load(settings['adapter'],'rolling_nutpie_data')
        capture=load(settings['capture_path'],'rolling_nutpie_capture');captures=[]
        started=time.perf_counter()
        with capture.capture_compiler(bridgestan,self.output/'captured-libraries',captures):
            self.compiled=nutpie.compile_stan_model(code=Path(settings['stan_path']).read_text(),cleanup=False)
        if not captures:raise ValueError('Compiler provenance missing')
        write(self.output/'COMPILER.json',captures);compiled_seconds=time.perf_counter()-started
        center=np.r_[2*np.log(.005),np.log(.2),0.,np.zeros(250)]
        values,telemetry=self._fit(self.y,center,seeds['initial'],200,0,True)
        self.initial=dict(compile_seconds=compiled_seconds,fit=telemetry,scope='New adaptation, jittered center; no inherited metric or chain state')

    def _fit(self,window,center,seed,draws,tick,preserve):
        if type(seed) is not int or not 0<=seed<2**32-1:raise ValueError('Interoperable seed pair')
        model=self.compiled.with_data(seed=seed+1,**self.adapter.stan_data(window))
        if model.library is not self.compiled.library:raise ValueError('Library reuse failed')
        started=time.perf_counter()
        trace=self.nutpie.sample(model,chains=4,cores=4,tune=1000,draws=draws,seed=seed,init_mean=center,
            save_warmup=True,progress_bar=False,**self.settings['engine_options'])
        sampled=time.perf_counter();full=extract_full(trace,draws);compact,metadata=extract_compact(trace,draws)
        if trace.warmup_posterior.sizes['draw']!=1000:raise ValueError('Warmup retention mismatch')
        diagnostics=[dict(divergent=np.asarray(trace.sample_stats['diverging'].transpose('chain','draw'))[i].copy()) for i in range(4)]
        self.last=full[:,-1,:].copy()
        detail=dict(seed=seed,initialization_seed=seed+1,call_index=tick-1,initialization_center=center.copy(),
            sampling_seconds=sampled-started,tune=1000,draws=draws,diagnostics=diagnostics,metadata=metadata,
            target_calls=None,work=None,limitation='No inherited per-chain state, metric or step size; target call count unavailable')
        if preserve:
            directory=self.output/f'tick-{tick:06d}';directory.mkdir()
            trace.to_netcdf(directory/'trace.nc');np.savez_compressed(directory/'draws.npz',full=full,compact=compact)
            detail['artifacts']=dict(trace=str(directory/'trace.nc'),trace_sha256=sha(directory/'trace.nc'),draws=str(directory/'draws.npz'),draws_sha256=sha(directory/'draws.npz'))
        for group in trace.groups():getattr(trace,group).close()
        trace.close();detail['extraction_storage_seconds']=time.perf_counter()-sampled
        return compact,detail

    def advance(self,y_new,k):
        if self.closed:raise RuntimeError('Closed comparator')
        if k!=400 or not np.isscalar(y_new) or not np.isfinite(y_new):raise ValueError('Fixed K400 finite observation')
        try:
            started=time.perf_counter();window=np.r_[self.y[1:],float(y_new)];center,_=initialization_center(self.last)
            tick=self.tick+1;seed=self.seeds['warm']+4*(tick-1)
            preparation=time.perf_counter()-started
            values,telemetry=self._fit(window,center,seed,k,tick,tick in self.retained)
            telemetry['preparation_seconds']=preparation;self.y=window;self.tick=tick
            return values,telemetry
        except Exception:self.close();raise

    def close(self):self.closed=True
