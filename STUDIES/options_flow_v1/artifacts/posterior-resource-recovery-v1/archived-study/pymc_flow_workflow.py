"""Immutable noncentered flow model via public PyMC autodiff/Numba callback.

Experimental: compilation/parity and sampler performance require validation.
"""
import time
STARTED=time.perf_counter()
import argparse,ctypes,hashlib,json,sys,traceback,warnings
from pathlib import Path
import numpy as np
import pymc as pm
import pytensor
import pytensor.tensor as pt
import numba
import owalnuts
import owalnuts._owalnuts as extension
from model import validate
from flow_starts import canonical_starts,to_noncentered
from pymc_workflow import evaluate_cfunc


def snapshot(data):
    y,x=validate(data)
    return dict(y=np.array(y,dtype=np.float64,copy=True),
                x=np.array(x,dtype=np.float64,copy=True),
                nu=np.float64(data['nu']),rho=np.float64(data['rho']))


def data_hash(data):
    frozen=snapshot(data)
    value={k:v.tolist() if isinstance(v,np.ndarray) else float(v) for k,v in frozen.items()}
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()


def to_canonical(u,data):
    y,_=validate(data);t,g=y.shape;k=4+2*g
    q=np.array(u,dtype=np.float64,copy=True)
    if q.shape[-1]!=k+t or not np.isfinite(q).all():
        raise ValueError('Invalid noncentered parameter shape or values')
    z=q[...,k:].copy();mu=q[...,2];sig=np.exp(q[...,3]);rho=float(data['rho'])
    q[...,k]=mu+sig*z[...,0]/np.sqrt(1-rho*rho)
    for i in range(1,t):q[...,k+i]=mu+rho*(q[...,k+i-1]-mu)+sig*z[...,i]
    if not np.isfinite(q).all():raise ValueError('Nonfinite canonical conversion')
    return q


def ar_path(z,mu,sig,rho,t,block_size=0):
    if isinstance(block_size,bool) or not isinstance(block_size,(int,np.integer)) or block_size not in (0,16,32):raise ValueError('Block size must be 0, 16 or 32')
    first=mu+sig*z[0]/np.sqrt(np.float64(1)-rho*rho)
    if t==1:return first[None]
    if block_size and .5 <= float(rho) < 1:
        # Bound all inverse powers to at most 31; never inverse-power the full path.
        if block_size not in (16,32):raise ValueError('Block size must be 16 or 32')
        blocks=(t+block_size-1)//block_size;length=blocks*block_size
        innovations=pt.concatenate([z[:1]/np.sqrt(np.float64(1)-rho*rho),z[1:],pt.zeros((length-t,),dtype='float64')])
        power=np.power(rho,np.arange(block_size,dtype=np.float64))
        within=pt.cumsum(innovations.reshape((blocks,block_size))/power[None,:],axis=1)*power[None,:]
        if blocks>1:
            ends,_=pytensor.scan(fn=lambda local,previous,r:local+r*previous,
                sequences=[within[:,-1]],outputs_info=[pt.as_tensor_variable(np.float64(0))],
                non_sequences=[pt.as_tensor_variable(np.float64(rho**block_size))],strict=True)
            previous=pt.concatenate([pt.zeros((1,),dtype='float64'),ends[:-1]])
        else:previous=pt.zeros((1,),dtype='float64')
        centered=within+previous[:,None]*(rho*power)[None,:]
        return mu+sig*centered.reshape((length,))[:t]
    tail,updates=pytensor.scan(fn=lambda zi,previous,m,s,r:m+r*(previous-m)+s*zi,
        sequences=[z[1:]],outputs_info=[first],non_sequences=[mu,sig,pt.as_tensor_variable(rho)],strict=True)
    if updates:raise ValueError('Unexpected state updates in deterministic flow scan')
    return pt.concatenate([first[None],tail])


def build_model(data,block_size=0):
    frozen=snapshot(data);y,x=frozen['y'],frozen['x'];t,g=y.shape;k=4+2*g
    rho=frozen['rho'];nu=frozen['nu']
    provided=data.get('initial_positions')
    if provided is None:starts=canonical_starts(data,1)
    else:
        matrix=np.asarray(provided,dtype=np.float64)
        if matrix.ndim!=2 or matrix.shape[0]<1:raise ValueError('initial_positions must be a nonempty chain-by-dimension matrix')
        starts=canonical_starts(data,matrix.shape[0])
    initial=to_noncentered(starts,data)[0]
    with pm.Model() as model:
        q=pm.Flat('q',shape=k+t,initval=initial)
        mu=q[2];sig=pt.exp(q[3]);z=q[k:]
        h=ar_path(z,mu,sig,rho,t,block_size)
        lp=pt.sum(pm.logp(pm.Normal.dist(mu=np.array([0.,-1.,-1.,-1.5]),sigma=np.array([.5,.5,1.,.5])),q[:4]))
        lp+=pt.sum(pm.logp(pm.Normal.dist(mu=np.float64(0),sigma=np.float64(1)),q[4:]))
        location=np.float64(.3)*q[4:4+g]+(q[0]+pt.exp(q[1])*q[4+g:k])*x
        lp+=pt.sum(pm.logp(pm.StudentT.dist(nu=nu,mu=location,sigma=pt.exp(h[:,None]/np.float64(2))),y))
        pm.Potential('normalized_noncentered_flow',lp)
    return model


def compile_target(data,block_size=0):
    start=time.perf_counter();model=build_model(data,block_size)
    with warnings.catch_warnings():
        warnings.filterwarnings('error',message='.*object mode.*')
        target,dim,initial,names,unravel=owalnuts.from_pymc(model,gil_free=True)
    y,_=validate(data)
    if dim!=4+2*y.shape[1]+y.shape[0] or names!=['q']:raise ValueError('Unexpected PyMC flow layout')
    return target,dict(compile_seconds=time.perf_counter()-start,dimension=dim,names=names,
        initial=initial.tolist(),block_size=block_size,data_sha256=data_hash(data),data_policy='immutable constants; rebuild target when data changes',
        compilation_scope='model construction and public adapter compilation combined; existing disk caches may be reused')


def parity(target,data,points):
    import jax
    jax.config.update('jax_enable_x64',True)
    import jax.numpy as jnp
    from jax.scipy.special import gammaln
    from optimized_reference import noncentered_log_density
    from model import log_density
    vg=jax.jit(jax.value_and_grad(lambda u:noncentered_log_density(u,data)))
    rows=[]
    for u in points:
        value,gradient=evaluate_cfunc(target,u);ref,grad=vg(jnp.asarray(u))
        q=to_canonical(u,data);t=len(data['y'])
        centered=float(log_density(q,data))+t*u[3]-.5*np.log1p(-data['rho']**2)
        np.testing.assert_allclose(value,ref,rtol=1e-10,atol=1e-8)
        np.testing.assert_allclose(value,centered,rtol=1e-10,atol=1e-8)
        np.testing.assert_allclose(gradient,grad,rtol=1e-9,atol=1e-8)
        rows.append(dict(value_error=abs(value-float(ref)),gradient_max_error=float(np.max(np.abs(gradient-np.asarray(grad)))),point_sha256=hashlib.sha256(np.asarray(u,dtype=np.float64).tobytes()).hexdigest()))
    return dict(passed=True,cases=rows)


def sample_fit(target,fixture,starts,seed,warmup,draws):
    data=fixture['data'];sampling_starts=to_noncentered(starts,data)
    np.testing.assert_allclose(to_canonical(sampling_starts,data),starts,rtol=1e-12,atol=1e-12)
    ts=time.perf_counter();cpu=time.process_time()
    result=owalnuts.sample(target,dim=starts.shape[1],init=sampling_starts,chains=len(starts),warmup=warmup,draws=draws,seed=seed,threads=1)
    sampling_seconds=time.perf_counter()-ts;sampling_cpu_seconds=time.process_time()-cpu
    u=np.asarray(result.samples)
    if u.shape!=(len(starts),draws,starts.shape[1]) or not np.isfinite(u).all():raise ValueError('Invalid posterior samples')
    ts=time.perf_counter();q=to_canonical(u,data);conversion_seconds=time.perf_counter()-ts
    from evaluate import summarize
    ts=time.perf_counter();evaluation=summarize(q,fixture,predictive_seed=seed+130000);evaluation_seconds=time.perf_counter()-ts
    health=result.health()
    report=dict(status='completed',draws=draws,evaluation=evaluation,evaluation_seconds=evaluation_seconds,
      conversion_seconds=conversion_seconds,sampling_seconds=sampling_seconds,sampling_cpu_seconds=sampling_cpu_seconds,
      sampler_health=health,target_calls=result.target_calls,retained_divergences=health['divergences'],
      healthy=evaluation['computational_screen_pass'] and health['divergences']==0)
    raw=dict(canonical_draws=q.tolist(),initial_positions=starts.tolist(),sampling_initial_positions=sampling_starts.tolist(),sampler_health=health)
    return report,raw

def validate_parity_evidence(evidence,report,data):
    """Fail closed: only completed passing evidence for this exact target build."""
    if not isinstance(evidence,dict) or evidence.get('status')!='completed':
        raise ValueError('Parity evidence must be a completed report')
    if not isinstance(evidence.get('compilation'),dict) or not isinstance(report.get('compilation'),dict) or not isinstance(evidence.get('parity'),dict):
        raise ValueError('Parity evidence metadata must be objects')
    if evidence.get('parity',{}).get('passed') is not True:
        raise ValueError('Parity evidence must contain an actual passing parity check')
    if not evidence['parity'].get('cases'):
        raise ValueError('Parity evidence contains no tested points')
    if evidence.get('compilation',{}).get('data_sha256')!=data_hash(data):
        raise ValueError('Parity evidence data hash mismatch')
    if evidence.get('compilation',{}).get('block_size')!=report.get('compilation',{}).get('block_size') or 'block_size' not in evidence.get('compilation',{}):
        raise ValueError('Parity evidence block size mismatch')
    for key in ['model','arm','adapter_source_sha256','extension_sha256','source_sha256','software']:
        if key not in evidence or key not in report or evidence[key]!=report[key]:
            raise ValueError('Parity evidence mismatch: '+key)
    return True


def main():
    p=argparse.ArgumentParser();p.add_argument('--fixture',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seed',type=int,required=True);p.add_argument('--warmup',type=int,default=1000);p.add_argument('--draws',type=int,default=1000)
    p.add_argument('--block-size',type=int,choices=[0,16,32],default=0)
    p.add_argument('--precision-names',nargs='+',default=['beta_bar','tau','mu_h','sigma_h','h_terminal'])
    p.add_argument('--expected-cpus',help='Expected inherited CPU list; enforce externally with hardware_control.py')
    p.add_argument('--skip-runtime-parity',action='store_true',help='Production timing only: requires --parity-evidence for prevalidated source/data')
    p.add_argument('--parity-evidence',type=Path)
    p.add_argument('--tiers',type=int,nargs='+',help='Reuse compiled target, fully restart adaptation/sampling at each retained tier');p.add_argument('--chains',type=int,default=4);p.add_argument('--compile-only',action='store_true');a=p.parse_args()
    if a.skip_runtime_parity and (a.parity_evidence is None or not a.parity_evidence.is_file()):p.error('Skipping runtime parity requires existing evidence file')
    if min(a.warmup,a.draws,a.chains)<1:p.error('Positive counts required')
    if a.compile_only and a.tiers:p.error('--compile-only and --tiers cannot be combined')
    if a.tiers and (any(n<4 for n in a.tiers) or any(b<=v for v,b in zip(a.tiers,a.tiers[1:]))):p.error('Strictly increasing tiers >=4 required')
    a.out.mkdir(parents=True,exist_ok=False);fixture=json.loads(a.fixture.read_text());data=fixture['data']
    report=dict(status='running',phase='exploratory',qualified=False,arm='python-pymc-flow-noncentered',model='flow',seed=a.seed,
      fixture_sha256=hashlib.sha256(a.fixture.read_bytes()).hexdigest(),extension_path=extension.__file__,
      extension_sha256=hashlib.sha256(Path(extension.__file__).read_bytes()).hexdigest(),
      adapter_source_sha256=hashlib.sha256(Path(owalnuts.__file__).read_bytes()).hexdigest(),
      precision_plan=dict(tiers=a.tiers,threshold=.02,names=a.precision_names,forecast_scope='all reported rows; required',policy='Compile once; full warmup and retained restart per tier; all attempts charged') if a.tiers else None,
      settings=dict(block_size=a.block_size,warmup=a.warmup,draws=a.draws,chains=a.chains,threads=1,chain_execution='sequential'),
      software=dict(python=sys.version,pymc=pm.__version__,pytensor=pytensor.__version__,numba=numba.__version__,numpy=np.__version__,algorithm_revision=owalnuts.ALGORITHM_REVISION),
      source_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in Path(__file__).parent.glob('*.py')})
    report_path=a.out/'python-pymc-flow-report.json';report_path.write_text(json.dumps(report,indent=2))
    active_draws=None
    try:
        from hardware_control import get_affinity,parse_cpus
        realized=list(get_affinity());report['hardware_control']=dict(realized_cpus=realized,enforcement='External wrapper required; worker checks expected inherited mask',expected_cpus=a.expected_cpus)
        if a.expected_cpus is not None and sorted(realized)!=sorted(parse_cpus(a.expected_cpus)):raise ValueError('Inherited CPU affinity differs from expected mask')
        target,metadata=compile_target(data,a.block_size);report['compilation']=metadata
        starts=canonical_starts(data,a.chains)
        sampling_starts=to_noncentered(starts,data)
        points=[sampling_starts[0],sampling_starts[-1],sampling_starts[0]+np.random.default_rng(818).normal(0,.01,len(starts[0]))]
        ts=time.perf_counter()
        if a.skip_runtime_parity:
            evidence=json.loads(a.parity_evidence.read_text())
            validate_parity_evidence(evidence,report,data)
            report['parity']=dict(status='not_repeated',evidence_path=str(a.parity_evidence.resolve()),evidence_sha256=hashlib.sha256(a.parity_evidence.read_bytes()).hexdigest(),binding='Completed passing report verified against exact data, model, arm, adapter, extension, source snapshot, and software')
        else:report['parity']=parity(target,data,points)
        report['parity_seconds']=time.perf_counter()-ts
        report['parity_timing_note']='Runtime parity includes optional JAX/NumPyro imports and compilation; reported separately, included in invocation total. Production does not require those tools when prevalidated externally.'
        if not a.compile_only:
            from run import clean
            from precision_tiers import precision_screen
            attempts=[]
            for draws in (a.tiers or [a.draws]):
                fit_start=time.perf_counter();active_draws=draws
                fit,raw=sample_fit(target,fixture,starts,a.seed,a.warmup,draws)
                fit_dir=a.out/f'draws-{draws}' if a.tiers else a.out
                fit_dir.mkdir(exist_ok=True)
                (fit_dir/'python-pymc-flow-raw.json').write_text(json.dumps(raw,allow_nan=False))
                if a.tiers:(fit_dir/'fit-report.json').write_text(json.dumps(clean(fit),indent=2,allow_nan=False))
                screen=precision_screen(fit,.02,names=a.precision_names) if a.tiers else None
                attempts.append(dict(draws=draws,fit_and_report_seconds=time.perf_counter()-fit_start,
                  sampling_seconds=fit['sampling_seconds'],evaluation_seconds=fit['evaluation_seconds'],
                  target_calls=fit['target_calls'],screen=screen))
                report.update(fit);report['attempts']=attempts;active_draws=None
                if screen and screen['pass']:break
            report['settings']['draws']=attempts[-1]['draws']
            if a.tiers:
                report.update(attempts=attempts,precision_pass=attempts[-1]['screen']['pass'],
                  total_sampling_seconds=sum(v['sampling_seconds'] for v in attempts),
                  total_fit_and_report_seconds=sum(v['fit_and_report_seconds'] for v in attempts),
                  total_target_calls=sum(v['target_calls'] for v in attempts))
        report.update(status='completed',end_to_end_seconds=time.perf_counter()-STARTED)
    except Exception as exc:
        if active_draws is not None:
            report.setdefault('attempts',[]).append(dict(draws=active_draws,status='failed',fit_and_report_seconds=time.perf_counter()-fit_start))
        report.update(status='failed',error=str(exc),traceback=traceback.format_exc(),end_to_end_seconds=time.perf_counter()-STARTED)
    from run import clean
    report_path.write_text(json.dumps(clean(report),indent=2,allow_nan=False))
    (a.out/'invocation-timing.json').write_text(json.dumps(dict(seconds_including_imports_and_report=time.perf_counter()-STARTED)))
    print(json.dumps({k:report.get(k) for k in ['status','healthy','end_to_end_seconds','error']}))
    return int(report['status']!='completed' or (bool(a.tiers) and not report.get('precision_pass',False)))
if __name__=='__main__':raise SystemExit(main())
