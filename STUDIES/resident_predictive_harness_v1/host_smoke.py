"""Representative development workload; requires external 600-second process-group supervisor."""
import argparse,dataclasses,json,platform,sys,time
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import owalnuts,numba,scipy
from harness import Resident,identity,memory,PROCESS
from numerical_backend import Backend
from sv_target import compile_target,compile_functional,TargetOwner,RHO
HERE=Path(__file__).resolve().parent

def encode(x):
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    raise TypeError(type(x).__name__)
BASELINE_SHA='4987d11039d0e64eb3c1a41022186a071b85701324d429817a279fccd3a9c14c'
def load_baseline(directory):
    if identity(directory/'results.json')['sha256']!=BASELINE_SHA:raise ValueError('Baseline result hash mismatch')
    r=json.loads((directory/'results.json').read_text())
    if r['status']!='complete' or [x['tick'] for x in r['rows']]!=[1,2,3,4] or not all(x['status']=='ok' for x in r['rows']):raise ValueError('Incomplete baseline')
    for row in r['rows']:
        if identity(directory/f"tick-{row['tick']:03d}.npy")['sha256']!=row['compact_identity']['sha256']:raise ValueError('Baseline compact hash mismatch')
    if identity(directory/'data.json')['sha256']!=r['data_identity']['sha256']:raise ValueError('Baseline data hash mismatch')
    return r

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);parser.add_argument('--numerical-backend',choices=['scipy','exact_t5'],default='scipy');parser.add_argument('--baseline',type=Path);a=parser.parse_args()
    if a.out.exists():raise SystemExit('Refusing to overwrite smoke outputs')
    a.out.mkdir(parents=True)
    tuning=owalnuts.Tuning(step_size=.5,max_depth=10,min_micro_steps=1,max_refinement_levels=8,
        max_error=1.,divergence_threshold=1000.,u_turn_rule='momentum_sum',exhaustion_rule='stop')
    adaptation=owalnuts.Adaptation(target_accept=.8,adapt_step_size=True,adapt_mass=True,
        metric_regularization='stan',trapped_chain_restart=True)
    result=dict(kind='N250/K400 development cost smoke; no accuracy qualification',status='running',
        started_utc=datetime.now(timezone.utc).isoformat(),rows=[],planned_updates=4,
        python=sys.version,platform=platform.platform(),versions=dict(numpy=np.__version__,scipy=scipy.__version__,numba=numba.__version__),
        tuning=dataclasses.asdict(tuning),adaptation=dataclasses.asdict(adaptation),defaults=dict(owalnuts.DEFAULTS),
        configuration=dict(n=250,k=400,chains=4,threads=4,initial_warmup=1000,initial_draws=200,
            data_seed=99371013,initial_seed=99371012,resident_seed=99371011,
            max_target_evaluations=None,admit_worst_case=True,append_z=0.,append_mass=1.,
            quadrature_nodes=[64,128],cdf_discrepancy_limit=1e-6,endpoint_discrepancy_limit=1e-6,
            root_residual_limit=1e-8,numerical_deadline_seconds=30,cache_bytes_per_rule=67108864,chunk=512),
        sources=[identity(HERE/'host_smoke.py'),identity(HERE/'harness.py'),identity(HERE/'sv_target.py'),identity(PROCESS),identity(owalnuts.__file__)],
        native=[identity(p) for p in Path(owalnuts.__file__).parent.glob('*.so')],memory_start=memory())
    def save():
        tmp=a.out/'results.partial';tmp.write_text(json.dumps(result,indent=2,default=encode));tmp.replace(a.out/'results.json')
    save();resident=None
    try:
        baseline=None
        if a.numerical_backend=='exact_t5':
            if a.baseline is None:raise ValueError('Exact backend comparison requires frozen baseline')
            baseline=load_baseline(a.baseline)
            if sys.prefix!='/home/ubuntu/lanes/resident-predictive-build-20261027/env':raise ValueError('Unexpected isolated environment prefix')
            if result['versions']!=baseline['versions']:raise ValueError('Runtime package versions differ from baseline')
            result['baseline_identity']=identity(a.baseline/'results.json')
        backend_start=time.perf_counter();backend=Backend(a.numerical_backend)
        result['numerical_backend']=backend.metadata;result['backend_initialization_seconds']=time.perf_counter()-backend_start
        rng=np.random.default_rng(99371013);mu0=2*np.log(.005);h=mu0+.2/np.sqrt(1-RHO*RHO)*rng.normal()
        data=[];truth=[];parameters=[]
        for i in range(255):
            mu=mu0+(i>=251);sigma=.4 if i>=251 else .2
            if i:h=mu+RHO*(h-mu)+sigma*rng.normal()
            truth.append(float(h));parameters.append([float(mu),sigma]);data.append(float(np.exp(h/2)*rng.standard_t(5)))
        (a.out/'data.json').write_text(json.dumps(dict(seed=99371013,returns=data,h=truth,parameters=parameters,shift_return_index=251),indent=2))
        result['data_identity']=identity(a.out/'data.json')
        if baseline is not None and result['data_identity']['sha256']!=baseline['data_identity']['sha256']:raise ValueError('Generated data differ from baseline')
        if baseline is not None and (result['configuration']!=baseline['configuration'] or result['tuning']!=baseline['tuning'] or result['adaptation']!=baseline['adaptation']):raise ValueError('Sampler config differs from baseline')
        if baseline is not None and [x['sha256'] for x in result['native']]!=[x['sha256'] for x in baseline['native']]:raise ValueError('Native identity differs from baseline')
        save()
        started=time.perf_counter();compiled=compile_target();functional=compile_functional()
        result['compile_seconds']=time.perf_counter()-started
        result['phase']='initial_fit';save()
        owner=TargetOwner(compiled,np.array(data[:250]));init=np.zeros((4,253));init[:,0]=mu0;init[:,1]=np.log(.2)
        started=time.perf_counter()
        fitted=owalnuts.sample(owner.target,253,init=init,chains=4,warmup=1000,draws=200,
            seed=99371012,threads=4,tuning=tuning,adaptation=adaptation,admit_worst_case=True)
        result['initial_fit_seconds']=time.perf_counter()-started
        result['initial_fit_summary']=fitted.summary()
        result['initial_chain_metadata']=[c.get('metadata') for c in fitted.chains]
        result['initial_chain_diagnostics']=[c.get('diagnostics') for c in fitted.chains]
        result['initial_config']=fitted.config;save()
        resident=Resident(compiled,functional,data[:250],fitted.warm_state(),seed=99371011,
            tuning=tuning,max_target_evaluations=None,admit_worst_case=True,numerical_backend=a.numerical_backend)
        for tick in range(1,5):
            result['phase']='tick';result['in_progress_tick']=tick;save()
            row=resident.tick(data[249+tick],400);row['tick']=tick;row['new_observation']=data[249+tick]
            # Durable compact persistence is outside the directly measured tick, explicitly recorded.
            result['rows'].append(row);result['in_progress_tick']=None;save()
            diskstart=time.perf_counter()
            if hasattr(resident,'last_values') and row.get('phase') in ('complete','summary'):
                raw=a.out/f'tick-{tick:03d}.npy';np.save(raw,resident.last_values,allow_pickle=False);row['compact_identity']=identity(raw)
            save()
            row['compact_and_first_save_seconds']=time.perf_counter()-diskstart;save()
            if baseline is not None and row['status']=='ok':
                old=baseline['rows'][tick-1]
                reference=np.load(a.baseline/f'tick-{tick:03d}.npy',allow_pickle=False)
                same=resident.last_values.dtype==reference.dtype and resident.last_values.shape==reference.shape and resident.last_values.tobytes()==reference.tobytes()
                width=old['return_p5_p50_p95'][2]-old['return_p5_p50_p95'][0]
                delta=float(np.max(np.abs(np.array(row['return_p5_p50_p95'])-old['return_p5_p50_p95'])))
                scale_delta=float(np.max(np.abs(np.array(row['scale_p50_p95'])/old['scale_p50_p95']-1)))
                row['baseline_comparison']=dict(compact_bit_identical=same,max_return_absolute_difference=delta,return_tolerance=1e-10*width,max_scale_relative_difference=scale_delta,scale_relative_tolerance=1e-12)
                save()
                if not same or delta>1e-10*width or scale_delta>1e-12:raise ValueError('Frozen baseline equivalence failed')
            if row['status']!='ok':break
        result['status']='complete' if len(result['rows'])==4 and all(r['status']=='ok' for r in result['rows']) else 'failed'
    except Exception as exc:result.update(status='failed',error=repr(exc))
    finally:
        if resident is not None:resident.close()
        result['unattempted_ticks']=[i for i in range(1,5) if i not in [r['tick'] for r in result['rows']] and i!=result.get('in_progress_tick')]
        result['memory_end']=memory();result['ended_utc']=datetime.now(timezone.utc).isoformat();save()
if __name__=='__main__':main()
