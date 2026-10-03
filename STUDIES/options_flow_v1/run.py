"""Isolated paired runs. Qualification is refused without frozen protocol approval."""
import argparse,hashlib,json,subprocess,sys,time,traceback,os,platform
from pathlib import Path
import numpy as np
from model import simulate,load_fixture
from evaluate import summarize
from baselines import empirical_forecast
from original_units import forecast_in_original_units
from build import verify_attestation
from hardware_control import wrapper_command,parse_cpus
HERE=Path(__file__).resolve().parent


def clean(value):
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,list):return [clean(v) for v in value]
    if isinstance(value,float) and not np.isfinite(value):return None
    return value


def execute(fixture_path,out,arm,exe,seed,warmup,draws,chains,timeout,require_attestation=False,cpus=None,reference_script=None):
    if arm not in ('numpyro','numpyro-noncentered','diagonal','dense','noncentered','autodiff','autodiff-noncentered','autodiff-dense'):
        raise ValueError('Unknown arm')
    if min(warmup,draws,chains)<1 or timeout<=0:
        raise ValueError('Positive iteration/chain counts and timeout required')
    fixture=load_fixture(fixture_path); out.mkdir(parents=True,exist_ok=True)
    raw_path=out/f'{arm}-raw.json'; log=out/f'{arm}.log'
    if any(p.exists() for p in [raw_path,log,out/f'{arm}-report.json']): raise FileExistsError(f'Refusing stale output overwrite: {raw_path}')
    data_path=out/'data.json'
    if data_path.exists():
        if json.loads(data_path.read_text())!=fixture['data']:
            raise ValueError('Output directory already belongs to different data')
    else:
        with data_path.open('x',encoding='utf-8') as handle:json.dump(fixture['data'],handle,allow_nan=False)
    command=([sys.executable,str(reference_script or HERE/'reference.py'),str(data_path),str(raw_path),str(seed),str(warmup),str(draws),str(chains)]+(['noncentered'] if arm=='numpyro-noncentered' else [])
             if arm.startswith('numpyro') else [str(exe),str(data_path),str(raw_path),arm,str(seed),str(warmup),str(draws),str(chains)])
    affinity_path=out/f'{arm}-affinity.json'
    if cpus is not None:command=wrapper_command(command,cpus,affinity_path,timeout)
    report={'arm':arm,'seed':seed,'phase':'exploratory','fixture_sha256':hashlib.sha256(Path(fixture_path).read_bytes()).hexdigest(),
            'settings':{'warmup':warmup,'draws':draws,'chains':chains,'chain_execution':'sequential','cpus':cpus},'command':command,'status':'failed'}
    report['reference_implementation']=str(reference_script or HERE/'reference.py') if arm.startswith('numpyro') else None
    report['environment']={'python':platform.python_version(),'platform':platform.platform(),'thread_environment':{k:os.environ.get(k) for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','XLA_FLAGS']}}
    source_files=sorted(HERE.glob('*.py'))+sorted((HERE/'src').rglob('*.rs'))+[HERE/'Cargo.toml',HERE/'Cargo.lock']
    report['source_hash_note']='Current sources at launch, not attestation that existing binary was built from them.'
    report['source_sha256']={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files if p.exists()}
    report['git_head']=subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True).stdout.strip()
    report['git_dirty']=bool(subprocess.run(['git','status','--porcelain'],capture_output=True,text=True).stdout.strip())
    if exe and Path(exe).exists():report['executable_sha256']=hashlib.sha256(Path(exe).read_bytes()).hexdigest()
    if not arm.startswith('numpyro'):
        try:
            report['build_attestation']=verify_attestation(HERE,exe)
        except ValueError as exc:
            if require_attestation:raise
            report['build_attestation_error']=str(exc)
    with (out/f'{arm}-report.json').open('x',encoding='utf-8') as handle:
        json.dump(dict(report,status='running'),handle,indent=2)
    start=time.perf_counter()
    try:
        with log.open('w') as stream:
            proc=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout+(30 if cpus is not None else 0),check=False)
        report['process_seconds']=time.perf_counter()-start
        if cpus is not None:
            report['affinity']=json.loads(affinity_path.read_text())
            if report['affinity'].get('realized_cpus')!=sorted(cpus):raise ValueError('CPU affinity evidence mismatch')
        if proc.returncode: raise RuntimeError(f'Worker exit code {proc.returncode}; see {log}')
        raw=json.loads(raw_path.read_text()); q=np.asarray([c['draws'] for c in raw['chains']])
        expected=(chains,draws,4+2*len(fixture['data']['x'][0])+len(fixture['data']['y']))
        if q.shape!=expected or raw['seed']!=seed or raw['arm']!=arm:raise ValueError(f'Worker contract mismatch: {q.shape}, expected {expected}, arm={raw["arm"]}')
        evaluation_start=time.perf_counter()
        report['evaluation']=summarize(q,fixture,predictive_seed=seed+130000)
        if 'holdout' in fixture:
            report['no_flow_baseline']=empirical_forecast(fixture)
            report['forecast_original_units']=forecast_in_original_units(report['evaluation']['forecast'],fixture)
            report['baseline_original_units']=forecast_in_original_units(report['no_flow_baseline'],fixture)
        report['parameter_units']='Model units; standardized when fixture scaling is present'
        report['data_provenance_note']='source and provenance are declarations, not independent verification'
        report['evaluation_seconds']=time.perf_counter()-evaluation_start
        report['end_to_end_seconds']=time.perf_counter()-start
        divergences=sum(c['retained_divergences'] for c in raw['chains'])
        report['retained_divergences']=divergences
        report['healthy']=report['evaluation']['computational_screen_pass'] and divergences==0
        report['timing_seconds']=raw.get('timing_seconds',{'worker_total':raw['wall_seconds']})
        report['status']='completed'
        report['qualified']=False
        report['qualification_note']='Exploratory output only; frozen study calibration, precision and paired performance gates remain required.'
    except Exception as exc:
        report.setdefault('process_seconds',time.perf_counter()-start)
        report['failed_elapsed_seconds']=time.perf_counter()-start
        report['error']=str(exc);report['traceback']=traceback.format_exc()
    (out/f'{arm}-report.json').write_text(json.dumps(clean(report),indent=2,allow_nan=False))
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--fixture',type=Path);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--exe',type=Path);p.add_argument('--arms',default='numpyro');p.add_argument('--seed',type=int,default=101)
    p.add_argument('--warmup',type=int,default=100);p.add_argument('--draws',type=int,default=100);p.add_argument('--chains',type=int,default=4)
    p.add_argument('--periods',type=int,default=32);p.add_argument('--groups',type=int,default=3);p.add_argument('--holdout',type=int,default=8)
    p.add_argument('--prior',action='store_true');p.add_argument('--timeout',type=float,default=600)
    p.add_argument('--require-attestation',action='store_true',help='Refuse Rust binaries not bound to current build sources')
    p.add_argument('--reference-script',type=Path,help='Independent NumPyro worker implementation override')
    p.add_argument('--cpus',type=parse_cpus,help='Enforce identical worker CPU mask, e.g. 0 or 0,1')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    fixture=a.fixture
    if fixture is None:
        fixture=a.out/'fixture.json'
        if fixture.exists():raise FileExistsError('Use a new output directory or explicit existing --fixture')
        fixture.write_text(json.dumps(simulate(a.seed,a.periods,a.groups,a.holdout,a.prior),indent=2))
    reports=[]
    for arm in a.arms.split(','):
        if not arm.startswith('numpyro') and not a.exe:p.error('--exe required for Rust arms')
        reports.append(execute(fixture,a.out,arm,a.exe,a.seed,a.warmup,a.draws,a.chains,a.timeout,a.require_attestation,a.cpus,a.reference_script))
        print(arm,reports[-1]['status'],reports[-1].get('healthy'),flush=True)
    return int(any(r['status']!='completed' for r in reports))
if __name__=='__main__':raise SystemExit(main())
