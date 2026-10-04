"""Independent stdlib-only terminal audit. Never launch while timing is live."""
import argparse,json,hashlib,math,collections,datetime
from pathlib import Path

def load(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def tail_field(path,key):
    path=Path(path)
    with path.open('rb') as f:
        f.seek(max(0,path.stat().st_size-1000000));text=f.read().decode()
    token='"'+key+'":';pos=text.rfind(token)
    if pos<0:raise ValueError('Missing bounded-tail raw field: '+key)
    return json.JSONDecoder().raw_decode(text[pos+len(token):].lstrip())[0]
def maximum_delta(a,b):
    if len(a)!=len(b) or any(len(x)!=len(y) for x,y in zip(a,b)):raise ValueError('Matrix shape mismatch')
    return max(abs(x-y) for aa,bb in zip(a,b) for x,y in zip(aa,bb))

def audit(directory):
    p=Path(directory).resolve();plan=load(p/'plan.json');root=p.parent.parent
    checks={};results={};hashes={}
    def check(name,value):checks[name]=bool(value)
    check('plan_digest',sha(p/'plan.json')==(p/'plan.sha256').read_text().strip())
    check('sources_current',plan['source_sha256']=={f.name:sha(f) for f in root.glob('*.py')})
    check('bound_current',all(sha(k)==v for k,v in plan['bound_files'].items()))
    check('runner',sha(p/'execute.py')==plan['runner_sha256'])
    check('denominator',len(plan['cells'])==12 and len({c['id'] for c in plan['cells']})==12)
    for cell in plan['cells']:
        name=cell['id'];status_path=p/(name+'.status.json')
        if not status_path.exists():
            results[name]={'outcome':'missing','success':False,'cost_seconds':None};check(name+'_terminal_status',False);continue
        status=load(status_path);check(name+'_terminal_status',True);row={'outcome':status.get('worker_status'),'success':False,'cost_seconds':status.get('elapsed_seconds')};results[name]=row
        check(name+'_status_plan',status.get('plan_sha256')==sha(p/'plan.json'))
        fixture=load(cell['fixture']);check(name+'_fixture',sha(cell['fixture'])==cell['fixture_sha256'])
        hp=cell['command'][cell['command'].index('--record')+1]
        if not Path(hp).exists():check(name+'_hardware',False);continue
        hardware=load(hp);row['hardware_status']=hardware.get('status')
        check(name+'_hardware_hash',sha(hp)==status.get('hardware_sha256'))
        check(name+'_all_costs',all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>0 for v in [row['cost_seconds'],hardware.get('elapsed_seconds')]) and row['cost_seconds']>=hardware['elapsed_seconds'])
        check(name+'_cpu',hardware.get('realized_cpus')==hardware.get('requested_cpus')==[0] and hardware.get('enforced_before_worker_launch'))
        check(name+'_containment',hardware.get('containment',{}).get('assigned_before_worker_execution') is True and hardware.get('containment',{}).get('kind')=='windows-job-object' and hardware.get('job_active_processes_after_cleanup')==0)
        check(name+'_command',hardware['command']==cell['command'][cell['command'].index('--')+1:])
        row['wrapper_seconds']=hardware.get('elapsed_seconds')
        if hardware.get('status')=='worker-timeout':
            row['outcome']='budgeted_computational_timeout'
            check(name+'_timeout_failed',status.get('accepted') is False and status.get('precision_pass') is False and status.get('returncode')==hardware.get('returncode')==124 and status.get('worker_status')=='operational_timeout' and hardware['elapsed_seconds']>=1800)
            row['partial_fits']=[]
            partial_root=Path(cell['report']).parent
            for n in [1000,2000,4000,8000]:
                fp=partial_root/f'draws-{n}/fit-report.json'
                if not fp.exists():continue
                fit=load(fp);hashes[str(fp)]=sha(fp);e=fit['evaluation']
                ds=list(e['functionals'].values())+list(e['canonical_parameter_diagnostics'].values())
                conv=e['chain_count']==4 and len(e['canonical_parameter_diagnostics'])==130 and all(math.isfinite(v[k]) and (v[k]<=1.01 if k=='rhat' else v[k]>=400) for v in ds for k in ['rhat','bulk_ess','tail_ess'])
                ratios=[max(v['endpoint_mcse'])/(v['interval_90'][1]-v['interval_90'][0]) for v in e['functionals'].values()]
                ratios.extend(max(v['endpoint_mcse'])/(v['upper']-v['lower']) for v in e['forecast']['rows'])
                raw=fp.parent/'python-pymc-raw.json'
                check(f'{name}_{n}_partial_raw_exists',raw.exists())
                if raw.exists():check(f'{name}_{n}_partial_starts',maximum_delta(tail_field(raw,'initial_positions'),fixture['data']['initial_positions'])<1e-12)
                row['partial_fits'].append(dict(draws=n,convergence=conv,divergences=fit['retained_divergences'],max_endpoint_ratio=max(ratios),endpoint_precision=all(math.isfinite(v) and 0<=v<=.02 for v in ratios),sampling_seconds=fit.get('sampling_seconds'),sampler_health=fit.get('sampler_health'),final=False))
            unfinished=Path(cell['report'])
            if unfinished.exists():
                report=load(unfinished);hashes[str(unfinished)]=sha(unfinished)
                check(name+'_timeout_report_identity',all(report.get(k)==v for k,v in {'source_sha256':plan['source_sha256'],'fixture_sha256':cell['fixture_sha256'],'seed':cell['seed'],'coordinates':cell['coordinates']}.items()))
                row['unfinished_report_status']=report.get('status')
            else:check(name+'_timeout_report_available',False)
            continue
        rp=Path(cell['report'])
        if not rp.exists():row['outcome']='missing_report';check(name+'_report_available',False);continue
        report=load(rp);hashes[str(rp)]=sha(rp)
        check(name+'_report_hash',sha(rp)==status.get('report_sha256'))
        check(name+'_identity',report.get('source_sha256')==plan['source_sha256'] and report.get('fixture_sha256')==cell['fixture_sha256'] and report.get('seed')==cell['seed'] and report.get('coordinates')==cell['coordinates'])
        if report.get('status')!='completed':row['outcome']='worker_failure';continue
        candidate=cell['arm'].startswith('candidate');settings=report['settings']
        check(name+'_settings',settings['chains']==4 and settings['warmup']==1000 and (candidate or settings['target_accept']==.9))
        attempts=[]
        for a in report['attempts']:
            n=a['draws'];fit=load(rp.parent/(f'draws-{n}/fit-report.json' if candidate else f'draws-{n}-report.json'));e=fit['evaluation']
            diagnostics=list(e['functionals'].values())+list(e['canonical_parameter_diagnostics'].values())
            convergence=e['chain_count']==4 and len(e['canonical_parameter_diagnostics'])==130 and all(math.isfinite(v[k]) and (v[k]<=1.01 if k=='rhat' else v[k]>=400) for v in diagnostics for k in ['rhat','bulk_ess','tail_ess'])
            ratios={k:max(v['endpoint_mcse'])/(v['interval_90'][1]-v['interval_90'][0]) for k,v in e['functionals'].items()}
            forecasts=e['forecast']['rows'];ratios.update({f'forecast_{i}':max(v['endpoint_mcse'])/(v['upper']-v['lower']) for i,v in enumerate(forecasts)})
            healthy=convergence and fit['retained_divergences']==0;precision=all(math.isfinite(v) and 0<=v<=.02 for v in ratios.values());passed=healthy and precision
            check(f'{name}_{n}_scope',set(e['functionals'])==set(plan['screen']['functionals']) and len(forecasts)==1)
            check(f'{name}_{n}_gate',passed==a['screen']['pass'] and all(abs(v-a['screen']['ratios'][k])<1e-12 for k,v in ratios.items()))
            attempts.append({'draws':n,'convergence':convergence,'divergences':fit['retained_divergences'],'endpoint_precision':precision,'pass':passed,'reasons':a['screen']['reasons']})
            if candidate or n==settings['draws']:
                raw=rp.parent/(f'draws-{n}/python-pymc-raw.json' if candidate else 'numpyro-continuation-raw.json')
                starts=tail_field(raw,'initial_positions');check(f'{name}_{n}_physical_starts',maximum_delta(starts,fixture['data']['initial_positions'])<1e-12)
        final=attempts[-1];success=final['pass'] and hardware['status']=='completed' and hardware['returncode']==0 and status['returncode']==0
        check(name+'_stop',not any(v['pass'] for v in attempts[:-1]) and final['pass']==report['precision_pass'] and (final['pass'] or final['draws']==8000) and [v['draws'] for v in attempts]==[1000,2000,4000,8000][:len(attempts)])
        check(name+'_accepted',success==status['accepted'])
        inv=load(rp.parent/'invocation-timing.json');worker_seconds=next(v for k,v in inv.items() if k.startswith('seconds_'))
        check(name+'_enclosing_costs',row['cost_seconds']>=hardware['elapsed_seconds']>=worker_seconds>=report['end_to_end_seconds'])
        if candidate:
            check(name+'_parity',report['parity']['passed'])
            check(name+'_restart_costs',abs(report['total_fit_and_report_seconds']-sum(v['fit_and_report_seconds'] for v in report['attempts']))<1e-7 and report['end_to_end_seconds']>=report['total_fit_and_report_seconds']+report['compilation']['compile_seconds']+report['parity_seconds'])
        else:
            cp=report['checkpoints'];check(name+'_adaptation',len({v['adaptation_sha256'] for v in cp})==1 and all(v['start_iterations']==[1000+i*1000]*4 and v['end_iterations']==[2000+i*1000]*4 for i,v in enumerate(cp)))
            check(name+'_continuation_costs',report['end_to_end_seconds']>=report['warmup_seconds']+sum(v['seconds'] for v in cp))
        row.update(outcome='passed' if success else 'health_or_precision_failed',success=success,attempts=attempts,worker_seconds=worker_seconds,internal_seconds=report['end_to_end_seconds'],stage_costs={k:v for k,v in report.items() if ('seconds' in k or 'phase' in k) and k not in ['evaluation']})
    check('all_twelve_terminal',len(results)==12 and all((p/(c['id']+'.status.json')).exists() for c in plan['cells']))
    pairs=[]
    for case in [0,3,5]:
        for a,b in [('candidate_residual','candidate_whitened'),('reference_residual','reference_whitened'),('candidate_whitened','reference_whitened')]:
            x=results[f'local-{case:02d}-{a}'];y=results[f'local-{case:02d}-{b}'];pairs.append({'case':case,'a':a,'b':b,'b_over_a_cost_ratio':y['cost_seconds']/x['cost_seconds'] if x['success'] and y['success'] and all(checks.values()) else None})
    return {'phase':'exploratory','qualified':False,'expected':12,'terminal_status_count':sum((p/(c['id']+'.status.json')).exists() for c in plan['cells']),'checks':checks,'integrity_pass':all(checks.values()),'results':results,'pairs':pairs,'report_sha256':hashes,'limitations':['Development-selected cases, no calibration/general speed inference.','Stored diagnostics/MCSE independently gated, not reestimated.','Bounded raw physical-start checks; full posterior shape and whitening inversion require separate checks.','All failure/missing cells retained; incomplete costs remain null.']}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    result=audit(args.directory)
    with Path(args.out).open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
