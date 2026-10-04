"""Read-only stdlib postrun audit; run only after all nine cells terminal."""
import argparse,json,hashlib,math
from pathlib import Path

def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def normalized(d):return {str(Path(k).resolve()).casefold():v for k,v in d.items()}
def starts(path,key="initial_positions"):
    with Path(path).open('rb') as f:f.seek(max(0,Path(path).stat().st_size-1000000));tail=f.read().decode()
    marker='"'+key+'":';i=tail.rfind(marker)
    if i<0:raise ValueError('Raw initial positions not in bounded tail')
    return json.JSONDecoder().raw_decode(tail[i+len(marker):].lstrip())[0]
def matrix_equal(a,b):return len(a)==len(b) and all(len(x)==len(y) for x,y in zip(a,b)) and all(math.isfinite(x) and abs(x-y)<1e-12 for aa,bb in zip(a,b) for x,y in zip(aa,bb))
def gate(fit):
    e=fit['evaluation'];d=list(e['functionals'].values())+list(e['canonical_parameter_diagnostics'].values())
    health=e['chain_count']==4 and len(e['canonical_parameter_diagnostics'])==130 and fit['retained_divergences']==0 and all(math.isfinite(v[k]) and (v[k]<=1.01 if k=='rhat' else v[k]>=400) for v in d for k in ['rhat','bulk_ess','tail_ess'])
    values={k:max(v['endpoint_mcse'])/(v['interval_90'][1]-v['interval_90'][0]) for k,v in e['functionals'].items()}
    values.update({f'forecast{i}':max(v['endpoint_mcse'])/(v['upper']-v['lower']) for i,v in enumerate(e['forecast']['rows'])})
    scope=set(e['functionals'])=={'h_initial','h_terminal','h_mean','sigma_obs','sigma_rw'} and len(e['forecast']['rows'])==1
    precision=all(math.isfinite(x) and 0<=x<=.02 for x in values.values())
    return dict(health=health,precision=precision,scope=scope,passed=health and precision and scope,ratios=values,divergences=fit['retained_divergences'])
def audit(directory):
    root=Path(directory);path=root/'plan.json';plan=load(path);checks={};results={};hashes={}
    def ck(k,v):checks[k]=bool(v)
    ck('plan_digest',sha(path)==path.with_suffix('.sha256').read_text().strip())
    ck('nine_intended',len(plan['cells'])==9 and len({c['id'] for c in plan['cells']})==9)
    ck('study_sources',all(sha(k)==v for k,v in plan['study_bindings'].items()))
    ck('bound_files',all(sha(k)==v for k,v in plan['bound_files'].items()))
    for cell in plan['cells']:
        name=cell['id'];sp=root/(name+'-status.json');out=root/name
        if not sp.exists():results[name]=dict(success=False,status='missing',cost=None);ck(name+'_terminal',False);continue
        status=load(sp);row=dict(success=False,status=status['status'],cost=status.get('elapsed_seconds'));results[name]=row;ck(name+'_terminal',True)
        if status['status']=='unattempted_provenance_abort':continue
        ck(name+'_cost',isinstance(row['cost'],(int,float)) and math.isfinite(row['cost']) and row['cost']>0)
        ck(name+'_fixture',sha(cell['fixture'])==cell['fixture_sha256'])
        hp=root/(name+'-hardware.json')
        if not hp.exists():ck(name+'_hardware',False);continue
        h=load(hp);ck(name+'_hardware_hash',sha(hp)==status.get('hardware_sha256'));ck(name+'_containment',h.get('job_active_processes_after_cleanup')==0 and h.get('realized_cpus')==[0] and h.get('containment',{}).get('assigned_before_worker_execution') is True)
        ck(name+'_cost_enclosure',row['cost']>=h['elapsed_seconds']);row['wrapper_seconds']=h['elapsed_seconds']
        if h['status']=='worker-timeout':
            ck(name+'_timeout',status['returncode']==h['returncode']==124 and h['elapsed_seconds']>=600 and not status['success']);row['status']='budgeted_computational_timeout';continue
        arm=cell['arm'];rp=out/('numpyro-continuation-report.json' if arm=='numpyro_continuation' else 'python-pymc-report.json')
        if not rp.exists():ck(name+'_report',False);continue
        r=load(rp);hashes[str(rp)]=sha(rp);ck(name+'_report_hash',sha(rp)==status['report_sha256']);ck(name+'_identity',r['seed']==cell['seed'] and r['coordinates']=='observation_residual' and r['settings']['chains']==4 and r['settings']['warmup']==1000)
        if arm=='owalnuts_continuation':
            actual=normalized(r['bindings']);expected=normalized(plan['study_bindings']);expected.update({k:v for k,v in normalized(plan['bound_files']).items() if Path(k).name in ['python.exe','__init__.py','_owalnuts.pyd']});expected[str(Path(cell['fixture']).resolve()).casefold()]=cell['fixture_sha256'];ck(name+'_runtime',all(actual.get(k)==v for k,v in expected.items()))
            ck(name+'_report_starts',matrix_equal(r['initial_positions'],cell['starts']))
        else:
            ck(name+'_runtime',r['source_sha256']=={Path(k).name:v for k,v in plan['study_bindings'].items()} and r['fixture_sha256']==cell['fixture_sha256'])
            if arm=='restart':ck(name+'_extension',r['extension_sha256']==next(v for k,v in plan['bound_files'].items() if Path(k).name=='_owalnuts.pyd'))
            else:ck(name+'_acceptance',r['settings']['target_accept']==.9)
        if r['status']!='completed':row['status']='worker_failed';continue
        attempts=[]
        for a in r['attempts']:
            n=a['draws'];fp=out/(f'draws-{n}-report.json' if arm=='numpyro_continuation' else f'draws-{n}/fit-report.json');g=gate(load(fp));ck(f'{name}_{n}_gate',g['passed']==a['screen']['pass'] and g['scope']);attempts.append(dict(draws=n,**g))
            if arm!='numpyro_continuation' or n==r['attempts'][-1]['draws']:
                raw=out/'numpyro-continuation-raw.json' if arm=='numpyro_continuation' else out/f'draws-{n}/python-pymc-raw.json';ck(f'{name}_{n}_starts',matrix_equal(starts(raw),cell['starts']))
        ck(name+'_firstpass',[a['draws'] for a in attempts]==[1000,2000,4000,8000][:len(attempts)] and not any(a['passed'] for a in attempts[:-1]) and (attempts[-1]['passed'] or attempts[-1]['draws']==8000))
        passed=attempts[-1]['passed'] and status['returncode']==h['returncode']==0 and h['status']=='completed';ck(name+'_success',passed==status['success']==r['precision_pass']);row.update(success=passed,attempts=attempts)
        inv=load(out/'invocation-timing.json');worker=next(v for k,v in inv.items() if k.startswith('seconds_'));ck(name+'_worker_cost',h['elapsed_seconds']>=worker>=r['end_to_end_seconds']);row['worker_seconds']=worker
        if arm=='restart':ck(name+'_restart_cost',abs(r['total_fit_and_report_seconds']-sum(a['fit_and_report_seconds'] for a in r['attempts']))<1e-7 and r['end_to_end_seconds']>=r['total_fit_and_report_seconds']+r['parity_seconds']+r['compilation']['compile_seconds'])
        elif arm=='numpyro_continuation':
            cp=r['checkpoints'];ck(name+'_adaptation',len({x['adaptation_sha256'] for x in cp})==1);ck(name+'_batch_cost',r['end_to_end_seconds']>=r['warmup_seconds']+sum(x['seconds'] for x in cp))
        else:
            ck(name+'_sampling_cost',abs(r['total_sampling_seconds']-r.get('adapt_seconds',0)-sum(a.get('sampling_seconds',0) for a in r['attempts']))<1e-7)
            base=None;frozen=json.dumps(r['adapted_metadata'],sort_keys=True)
            for a in r['attempts']:
                n=a['draws'];raw=out/f'draws-{n}/python-pymc-raw.json';metadata=None
                ck(f'{name}_{n}_frozen_metric',json.dumps(starts(raw,'adapted_metadata'),sort_keys=True)==frozen)
                if base is None:base=a['cumulative_target_calls']-a['added_target_calls']
                base+=a['added_target_calls'];ck(f'{name}_{n}_callbacks',base==a['cumulative_target_calls'])
            ck(name+'_callbacks_total',base==r['total_target_calls']);ck(name+'_metadata_present',bool(r['adapted_metadata']))
    pairs=[]
    for case in [0,3,5]:
        for a,b in [('restart','owalnuts_continuation'),('owalnuts_continuation','numpyro_continuation')]:
            x=results[f'case{case:02d}-{a}'];y=results[f'case{case:02d}-{b}'];pairs.append(dict(case=case,a=a,b=b,b_over_a_ratio=y['cost']/x['cost'] if x['success'] and y['success'] and all(checks.values()) else None))
    return dict(phase='development',qualified=False,expected=9,checks=checks,integrity_pass=all(checks.values()),results=results,pairs=pairs,report_sha256=hashes,limitations=['Allfailed/missing outcomes retained; same-case successful pairs only have ratios.','Stored gates checked, estimators not reestimated.','Canonical starts inspected in bounded tails; large posterior arrays not loaded.','Adaptedmetadata equality checked from bounded raw tails and callbacks reconciled; no full posterior rescan.'])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--out',required=True);a=p.parse_args();result=audit(a.directory)
    with Path(a.out).open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
