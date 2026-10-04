"""Exploratory masked-flow NumPyro continuation; no market qualification claim."""
import time
STARTED=time.perf_counter()
import argparse
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
import traceback
import numpy as np
import jax
import jax.numpy as jnp
from jax.scipy.special import gammaln
from reference_continuation import ContinuedReference
from flow_starts import canonical_starts,to_noncentered
from masked_flow import validate,canonical,log_density
from masked_forecast import summarize,forecast,precision_forecast_screen
from precision_tiers import precision_screen
from run import clean

HERE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def sources():return {p.name:sha(p) for p in sorted(HERE.glob('*.py'))}
def write(path,value):Path(path).write_text(json.dumps(clean(value),indent=2,allow_nan=False),encoding='utf-8')
def names(groups):
    return ['beta_bar','tau','mu_h','sigma_h','h_terminal','h_mean']+[name for g in range(groups) for name in (f'alpha_{g}',f'beta_{g}')]

def screen(report,groups,cells):
    evaluation={k:v for k,v in report['evaluation'].items() if k!='forecast'}
    parameter=precision_screen(dict(report,evaluation=evaluation),names=names(groups),require_forecast=False)
    predictive=precision_forecast_screen(report['evaluation']['forecast'],cells)
    return {'pass':parameter['pass'] and predictive['pass'],'parameter':parameter,'predictive':predictive,'qualified':False}

def target(data):
    validate(data)
    return lambda q:-log_density(q,data,jnp,gammaln,noncentered=True)

def execute(fixture_path,out,seed,*,warmup=1000,chains=4,batch=1000,tiers=(1000,2000,4000,8000),target_accept=.9):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    attempts=[];engine=None;plan={};report={'status':'running','qualified':False}
    write(out/'report.json',report)
    try:
        if isinstance(seed,bool) or not isinstance(seed,int) or not 0<=seed<2**32-130000:raise ValueError('Invalid sampler/predictive seed')
        if any(isinstance(v,bool) or not isinstance(v,int) for v in [warmup,chains,batch,*tiers]) or warmup<1 or chains<4 or batch<4 or not tiers or any(v<4 or v%batch for v in tiers) or any(b<=a for a,b in zip(tiers,tiers[1:])):raise ValueError('Invalid chain, warmup, batch or tier settings')
        fixture_path=Path(fixture_path).resolve();fixture=json.loads(fixture_path.read_text());data=fixture['data'];y,_,_=validate(data)
        starts=canonical_starts(data,chains);sampling_starts=to_noncentered(starts,data)
        # Validate the entire future schema before adapting. The family depends
        # solely on declared covariate availability, never observed labels.
        preflight=forecast(np.repeat(starts[:,None,:],4,axis=1),data,fixture['holdout'],seed+130000)
        cells=[[r['horizon'],r['group']] for r in preflight['rows'] if r['forecast_available']]
        if not cells:raise ValueError('No available future covariates for the declared precision family')
        from hardware_control import get_affinity
        plan=dict(phase='exploratory',model='masked_flow',arm='numpyro-masked-noncentered-continuation',fixture=str(fixture_path),fixture_sha256=sha(fixture_path),source=sources(),seed=seed,predictive_seed=seed+130000,warmup=warmup,chains=chains,batch=batch,tiers=list(tiers),target_accept=target_accept,parameter_functionals=names(y.shape[1]),forecast_cells=cells,relative_mcse=.02,forecast_family_policy='Every available future-x row, irrespective of target observation',cpu_affinity=get_affinity(),runtime={'python':platform.python_version(),**{p:importlib.metadata.version(p) for p in ['numpy','scipy','jax','jaxlib','numpyro','arviz']}},compilation_timing='Included in warmup and first retained batch; no artificial separate compile',qualified=False)
        write(out/'plan.json',plan)
        def verify():
            if sha(fixture_path)!=plan['fixture_sha256'] or sources()!=plan['source']:raise RuntimeError('Bound fixture/source changed during run')
        engine=ContinuedReference(target(data),sampling_starts,seed,warmup,batch,target_accept)
        engine.adapt();convert=jax.jit(jax.vmap(jax.vmap(lambda q:canonical(q,data,jnp))))
        for retained in tiers:
            while len(engine.chunks)*batch<retained:engine.append()
            tick=time.perf_counter();draws=np.asarray(convert(jnp.asarray(engine.samples)));conversion_seconds=time.perf_counter()-tick
            tick=time.perf_counter();evaluation=summarize(draws,fixture,seed+130000);evaluation_seconds=time.perf_counter()-tick
            verify()
            report=dict(status='completed',plan=plan,seed=seed,draws=retained,healthy=bool(evaluation['computational_screen_pass'] and engine.divergences==0),evaluation=evaluation,retained_divergences=engine.divergences,warmup_seconds=engine.warmup_seconds,checkpoints=engine.checkpoints.copy(),conversion_seconds=conversion_seconds,evaluation_seconds=evaluation_seconds,qualified=False)
            result=screen(report,y.shape[1],cells);report['precision_pass']=result['pass']
            attempts.append(dict(draws=retained,screen=result,cumulative_seconds=time.perf_counter()-STARTED))
            write(out/f'draws-{retained}-report.json',report)
            write(out/'report.json',dict(report,attempts=attempts))
            if result['pass']:break
        write(out/'raw.json',dict(canonical_draws=draws.tolist(),initial_positions=starts.tolist(),sampling_initial_positions=sampling_starts.tolist(),seed=seed,checkpoints=engine.checkpoints))
        verify()
    except Exception as exc:
        report=dict(status='failed',healthy=False,precision_pass=False,error=f'{type(exc).__name__}: {exc}',traceback=traceback.format_exc(),plan=plan,qualified=False,checkpoints=engine.checkpoints if engine else [])
    report.update(attempts=attempts,end_to_end_seconds=time.perf_counter()-STARTED,timing_scope='Worker invocation including imports, warmup/compilation, all retained batches, diagnostics, prediction and raw serialization; excludes external launcher overhead')
    write(out/'report.json',report)
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--fixture',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--seed',type=int,required=True)
    p.add_argument('--warmup',type=int,default=1000);p.add_argument('--chains',type=int,default=4);p.add_argument('--batch',type=int,default=1000);p.add_argument('--tiers',type=int,nargs='+',default=[1000,2000,4000,8000]);p.add_argument('--target-accept',type=float,default=.9)
    a=p.parse_args();r=execute(a.fixture,a.out,a.seed,warmup=a.warmup,chains=a.chains,batch=a.batch,tiers=a.tiers,target_accept=a.target_accept)
    raise SystemExit(0 if r.get('precision_pass') else 2)
if __name__=='__main__':main()

