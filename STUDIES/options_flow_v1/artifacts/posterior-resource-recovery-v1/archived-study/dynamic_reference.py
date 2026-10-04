"""Repeated same-shape refits with dynamic data and fresh full adaptation per fit.

Unlike captured-data potential closures, this model passes y/x/rho/nu as runtime
arguments and enables NumPyro jit_model_args. First fit includes compilation;
subsequent fits can reuse it. Each fit gets fresh starts, random key and warmup.
"""
import os
os.environ.setdefault('JAX_ENABLE_X64','true')
import argparse,json,time,hashlib,traceback
from pathlib import Path
import numpy as np
import jax
jax.config.update('jax_enable_x64',True)
import jax.numpy as jnp
import numpyro
import numpyro.distributions as dist
from numpyro.distributions import constraints
from numpyro.infer import MCMC,NUTS
from optimized_reference import canonical_noncentered,noncentered_log_density
from model import validate,load_fixture
from flow_starts import canonical_starts,to_noncentered
from evaluate import summarize
from run import clean

def dynamic_model(y,x,rho,nu):
    t,g=y.shape
    q=numpyro.sample('q',dist.ImproperUniform(constraints.real,(),(4+2*g+t,)))
    numpyro.factor('normalized_target',noncentered_log_density(q,dict(y=y,x=x,rho=rho,nu=nu)))

class DynamicReference:
    def __init__(self,warmup=1000,draws=1000,chains=4):
        self.warmup,self.draws,self.chains=warmup,draws,chains
        self.mcmc=MCMC(NUTS(dynamic_model,target_accept_prob=.8,max_tree_depth=10),
          num_warmup=warmup,num_samples=draws,num_chains=chains,chain_method='sequential',
          progress_bar=False,jit_model_args=True)
        self.shape=None;self.completed=0
    def fit(self,data,seed):
        y,x=validate(data);t,g=y.shape
        if self.shape is not None and self.shape!=y.shape:raise ValueError('Same-shape refits required')
        self.shape=y.shape
        args=(jnp.asarray(y),jnp.asarray(x),jnp.asarray(data['rho']),jnp.asarray(data['nu']))
        initial_positions=canonical_starts(data,self.chains)
        starts=to_noncentered(initial_positions,data)
        # warmup() resets _warmup_state internally; explicit init_params and new key reset adaptation.
        ts=time.perf_counter();self.mcmc.warmup(jax.random.PRNGKey(seed),*args,init_params={'q':jnp.asarray(starts)},extra_fields=('diverging','num_steps'))
        jax.block_until_ready(self.mcmc.last_state.z);warm_seconds=time.perf_counter()-ts
        warm_steps=np.asarray(self.mcmc.last_state.i).tolist()
        ts=time.perf_counter();self.mcmc.run(self.mcmc.post_warmup_state.rng_key,*args,extra_fields=('diverging','num_steps'))
        z=self.mcmc.get_samples(group_by_chain=True)['q'];c=canonical_noncentered # vmap for canonical single vector
        q=jax.vmap(jax.vmap(lambda v:c(v,data)))(z);jax.block_until_ready(q)
        sample_seconds=time.perf_counter()-ts;extra=self.mcmc.get_extra_fields(group_by_chain=True)
        self.completed+=1
        return dict(arm='numpyro-noncentered',reference_implementation='dynamic_data_associative_scan',seed=seed,
          initial_positions=initial_positions.tolist(),fit_index=self.completed-1,fresh_adaptation=True,warmup_state_iterations=warm_steps,
          wall_seconds=warm_seconds+sample_seconds,timing_seconds=dict(warmup_including_any_compilation=warm_seconds,
          sampling_including_any_compilation=sample_seconds,isolated_compilation=None),
          chains=[dict(draws=np.asarray(q[k]).tolist(),retained_divergences=int(np.asarray(extra['diverging'][k]).sum()),
          retained_leapfrogs=int(np.asarray(extra['num_steps'][k]).sum())) for k in range(self.chains)])

def main():
    p=argparse.ArgumentParser();p.add_argument('--fixtures',type=Path,nargs='+',required=True);p.add_argument('--seeds',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--warmup',type=int,default=1000);p.add_argument('--draws',type=int,default=1000);p.add_argument('--chains',type=int,default=4)
    a=p.parse_args();seeds=list(map(int,a.seeds.split(',')))
    if len(seeds)!=len(a.fixtures) or len(set(seeds))!=len(seeds):p.error('One distinct chain seed per fixture required')
    a.out.mkdir(parents=True,exist_ok=True)
    if any(a.out.iterdir()):raise FileExistsError('Require empty output directory')
    (a.out/'manifest.json').write_text(json.dumps(dict(phase='exploratory',intended_fits=[dict(index=i,fixture=str(path),seed=seed) for i,(path,seed) in enumerate(zip(a.fixtures,seeds))],source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}),indent=2))
    model=DynamicReference(a.warmup,a.draws,a.chains);start=time.perf_counter();reports=[]
    for index,(path,seed) in enumerate(zip(a.fixtures,seeds)):
        fit_start=time.perf_counter()
        report_path=a.out/f'{index}-report.json'
        report_path.write_text(json.dumps(dict(status='running',phase='exploratory',seed=seed,fit_index=index)))
        try:
            fixture=load_fixture(path);raw=model.fit(fixture['data'],seed)
        except Exception as exc:
            failure=dict(status='failed',phase='exploratory',seed=seed,fit_index=index,error=str(exc),traceback=traceback.format_exc(),elapsed_seconds=time.perf_counter()-fit_start)
            report_path.write_text(json.dumps(failure,indent=2));reports.append(failure);print(index,'failed',flush=True);continue
        try:
            r=dict(phase='exploratory',qualified=False,arm=raw['arm'],seed=seed,
              fixture_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),fit_index=index,status='completed',
              timing_seconds=raw['timing_seconds'],engine_seconds=raw['wall_seconds'],fresh_adaptation=True,
              warmup_state_iterations=raw['warmup_state_iterations'],settings=dict(warmup=a.warmup,draws=a.draws,chains=a.chains,chain_execution='sequential'))
            evaluation_start=time.perf_counter();q=np.asarray([c['draws'] for c in raw['chains']]);r['evaluation']=summarize(q,fixture,seed+130000)
            r['evaluation_seconds']=time.perf_counter()-evaluation_start
            r['retained_divergences']=sum(c['retained_divergences'] for c in raw['chains']);r['healthy']=r['evaluation']['computational_screen_pass'] and r['retained_divergences']==0
            (a.out/f'{index}-raw.json').write_text(json.dumps(raw,allow_nan=False))
            r['end_to_end_seconds']=time.perf_counter()-fit_start
            r['timing_scope']='Per-fit end_to_end includes fixture load, adaptation, sampling, diagnostics, predictive evaluation, raw serialization; report writing measured in timing sidecar.'
            (a.out/f'{index}-report.json').write_text(json.dumps(clean(r),indent=2,allow_nan=False))
            (a.out/f'{index}-timing.json').write_text(json.dumps(dict(fit_and_report_seconds=time.perf_counter()-fit_start),indent=2))
            reports.append(r)
            print(index,r['engine_seconds'],r['healthy'],flush=True)
        except Exception as exc:
            failure=dict(status='failed',phase='exploratory',seed=seed,fit_index=index,error=str(exc),traceback=traceback.format_exc(),elapsed_seconds=time.perf_counter()-fit_start)
            report_path.write_text(json.dumps(failure,indent=2));reports.append(failure);print(index,'failed',flush=True)
    (a.out/'cohort.json').write_text(json.dumps(dict(phase='exploratory',total_seconds=time.perf_counter()-start,fit_count=len(reports),
      first_fit_includes_compilation=True,fresh_warmup_each_fit=True,limitation='Total excludes interpreter imports; wrapper elapsed time needed for full process cost. Compilation separately unavailable.',
      software=dict(jax=jax.__version__,numpyro=numpyro.__version__)),indent=2))
    return int(any(r.get('status')!='completed' for r in reports))
if __name__=='__main__':raise SystemExit(main())
