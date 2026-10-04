"""Paired local-level application experiments, separate from the order-flow model."""
import argparse,hashlib,json,subprocess,sys,time,traceback
from pathlib import Path
import numpy as np
import arviz as az
from local_level import validate,simulate,functionals,predict
from run import clean
from build import verify_attestation
from hardware_control import wrapper_command,parse_cpus
from baselines import empirical_forecast
HERE=Path(__file__).resolve().parent

def diagnostics(v):
    return dict(mean=float(v.mean()),sd=float(v.std()),rhat=float(az.rhat(v,method='rank')),
      bulk_ess=float(az.ess(v,method='bulk')),tail_ess=float(az.ess(v,method='tail',prob=(.05,.95))),
      mean_mcse=float(az.mcse(v,method='mean')),interval_90=np.quantile(v,[.05,.95]).tolist(),
      endpoint_mcse=[float(az.mcse(v,method='quantile',prob=p)) for p in [.05,.95]])

def evaluate(q,fixture,seed):
    vals={k:diagnostics(v) for k,v in functionals(q).items()}
    coordinates={f'q_{j}':diagnostics(q[...,j]) for j in range(q.shape[-1])}
    all_d=list(vals.values())+list(coordinates.values())
    healthy=q.shape[0]>=4 and all(d['rhat']<=1.01 and d['bulk_ess']>=400 and d['tail_ess']>=400 for d in all_d)
    if 'truth' in fixture:
        for name,v in functionals(np.array(fixture['truth'])).items():
            vals[name]['truth']=float(v)
            vals[name]['covers_truth_90']=bool(vals[name]['interval_90'][0]<=v<=vals[name]['interval_90'][1])
    result=dict(chain_count=q.shape[0],functionals=vals,canonical_parameter_diagnostics=coordinates,computational_screen_pass=healthy)
    if 'holdout' in fixture:
        y=np.asarray(fixture['holdout']['y']);future=predict(q,fixture['data'],np.arange(1,len(y)+1),seed)
        rows=[]
        for h,observed in enumerate(y):
            pred=future['observed_log'][...,h];lo,hi=np.quantile(pred,[.05,.95])
            rows.append(dict(horizon=h+1,observed=float(observed),lower=float(lo),upper=float(hi),
              covered=bool(lo<=observed<=hi),width=float(hi-lo),interval_score=float(hi-lo+20*(max(lo-observed,0)+max(observed-hi,0))),
              endpoint_mcse=[float(az.mcse(pred,method='quantile',prob=p)) for p in [.05,.95]],
              latent_log_interval_90=np.quantile(future['latent_log'][...,h],[.05,.95]).tolist()))
        result['forecast']=dict(rows=rows,coverage=float(np.mean([r['covered'] for r in rows])),
          mean_interval_score=float(np.mean([r['interval_score'] for r in rows])),scale='observed log price',
          note='Observed intervals include Student-t noise; latent intervals separately labeled. Exponentiated Student-t has no finite price mean. Nested predictive MCSE includes future simulation noise.')
    return result

def execute(fixture_path,out,arm,exe,seed,warmup,draws,chains,timeout,require_attestation=False,cpus=None):
    if arm not in ('numpyro','numpyro-noncentered','diagonal','dense','noncentered','autodiff','autodiff-noncentered','autodiff-dense','application-settings'):raise ValueError('Unknown arm')
    if min(warmup,draws,chains)<1 or timeout<=0:raise ValueError('Positive settings required')
    fixture=json.loads(Path(fixture_path).read_text());validate(fixture['data']);out.mkdir(parents=True,exist_ok=True)
    raw=out/f'{arm}-raw.json';report_path=out/f'{arm}-report.json';log=out/f'{arm}.log';data=out/'data.json'
    if any(p.exists() for p in [raw,report_path,log]):raise FileExistsError('Immutable cell already exists')
    if data.exists():
        if json.loads(data.read_text())!=fixture['data']:raise ValueError('Output directory belongs to different data')
    else:
        with data.open('x') as stream:json.dump(fixture['data'],stream,allow_nan=False)
    command=([sys.executable,str(HERE/'local_reference.py'),str(data),str(raw),str(seed),str(warmup),str(draws),str(chains)]+(['noncentered'] if arm.endswith('noncentered') else []) if arm.startswith('numpyro') else [str(exe),str(data),str(raw),arm,str(seed),str(warmup),str(draws),str(chains)])
    affinity_path=out/f'{arm}-affinity.json'
    if cpus is not None:command=wrapper_command(command,cpus,affinity_path,timeout)
    report=dict(arm=arm,seed=seed,phase='exploratory',qualified=False,status='running',model='local_level_t',
       fixture_sha256=hashlib.sha256(Path(fixture_path).read_bytes()).hexdigest(),command=command,
       settings=dict(warmup=warmup,draws=draws,chains=chains,chain_execution='sequential',cpus=cpus),
       anchor_mode=fixture['data']['anchor_mode'],source_hash_note='Launch source snapshot is not binary build attestation',
       source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')})
    if exe:report['executable_sha256']=hashlib.sha256(Path(exe).read_bytes()).hexdigest()
    if not arm.startswith('numpyro'):
        try:report['build_attestation']=verify_attestation(HERE,exe)
        except ValueError as exc:
            if require_attestation:raise
            report['build_attestation_error']=str(exc)
    with report_path.open('x') as stream:json.dump(report,stream,indent=2)
    start=time.perf_counter()
    try:
        with log.open('w') as stream:r=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout+(30 if cpus is not None else 0))
        report['process_seconds']=time.perf_counter()-start
        if cpus is not None:
            report['affinity']=json.loads(affinity_path.read_text())
            if report['affinity'].get('realized_cpus')!=sorted(cpus):raise ValueError('CPU affinity evidence mismatch')
        if r.returncode:raise RuntimeError(f'Worker exited {r.returncode}')
        worker=json.loads(raw.read_text());q=np.asarray([c['draws'] for c in worker['chains']])
        if q.shape!=(chains,draws,len(fixture['data']['y'])+2) or not np.isfinite(q).all() or worker['arm']!=arm or worker['seed']!=seed:raise ValueError('Worker contract mismatch')
        ts=time.perf_counter();report['evaluation']=evaluate(q,fixture,seed+130000)
        if 'holdout' in fixture:report['no_flow_baseline']=empirical_forecast(fixture)
        report['evaluation_seconds']=time.perf_counter()-ts;report['end_to_end_seconds']=time.perf_counter()-start
        report['retained_divergences']=sum(c['retained_divergences'] for c in worker['chains'])
        report['healthy']=report['evaluation']['computational_screen_pass'] and report['retained_divergences']==0
        report['timing_seconds']=worker.get('timing_seconds',dict(worker_total=worker['wall_seconds']));report['status']='completed'
    except Exception as e:
        report.update(status='failed',error=str(e),traceback=traceback.format_exc(),end_to_end_seconds=time.perf_counter()-start)
    report_path.write_text(json.dumps(clean(report),indent=2,allow_nan=False));return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--fixture',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--exe',type=Path)
    p.add_argument('--arms',default='numpyro,diagonal');p.add_argument('--seed',type=int,default=99062001);p.add_argument('--periods',type=int,default=128)
    p.add_argument('--holdout',type=int,default=20);p.add_argument('--warmup',type=int,default=1000);p.add_argument('--draws',type=int,default=1000)
    p.add_argument('--require-attestation',action='store_true');p.add_argument('--cpus',type=parse_cpus);p.add_argument('--chains',type=int,default=4);p.add_argument('--timeout',type=float,default=1800);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    fixture=a.fixture
    if fixture is None:
        fixture=a.out/'fixture.json'
        if fixture.exists():raise FileExistsError('Fixture already exists')
        fixture.write_text(json.dumps(simulate(a.seed,a.periods,a.holdout,prior=False),indent=2))
    reports=[]
    for arm in a.arms.split(','):
        if not arm.startswith('numpyro') and not a.exe:p.error('Rust arms require --exe')
        r=execute(fixture,a.out,arm,a.exe,a.seed,a.warmup,a.draws,a.chains,a.timeout,a.require_attestation,a.cpus);reports.append(r);print(arm,r['status'],r.get('healthy'),flush=True)
    return int(any(r['status']!='completed' for r in reports))
if __name__=='__main__':raise SystemExit(main())
