"""Independent stdlib-only postpilot audit. Never imports the production adapter."""
import argparse,datetime,hashlib,json,math
from pathlib import Path

def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def tail(p,key):
    with Path(p).open('rb') as f:f.seek(max(0,Path(p).stat().st_size-1000000));s=f.read().decode()
    return json.JSONDecoder().raw_decode(s[s.rindex('"'+key+'":')+len(key)+3:].lstrip())[0]
def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def truth(f,flow):
    q=f['truth'];t=len(f['data']['y'])
    if flow:
        g=len(f['data']['y'][0]);v=dict(beta_bar=q[0],tau=math.exp(q[1]),mu_h=q[2],sigma_h=math.exp(q[3]),h_terminal=q[-1],h_mean=sum(q[4+2*g:])/t)
        for j in range(g):v['alpha_'+str(j)]=.3*q[4+j];v['beta_'+str(j)]=q[0]+math.exp(q[1])*q[4+g+j]
        forecasts={(i+1,j):y for i,row in enumerate(f['holdout']['y']) for j,y in enumerate(row)}
    else:
        v=dict(h_initial=q[0],h_terminal=q[t-1],h_mean=sum(q[:t])/t,sigma_obs=math.exp(q[-2]),sigma_rw=math.exp(q[-1]));forecasts={(i+1,None):y for i,y in enumerate(f['holdout']['y'])}
    return v,forecasts

def audit(directory):
    p=Path(directory);plan=load(p/'plan.json');checks={};results=[];summaries={};inventory={}
    def check(name,value):checks[name]=bool(value)
    def read(path):inventory[str(path)]=sha(path);return load(path)
    check('plan_sha256',sha(p/'plan.json')==(p/'plan.sha256').read_text().strip())
    check('expected20',plan['expected']==20 and len(plan['ordered'])==20)
    check('source_runtime_build_bytes',all(sha(k)==v for k,v in plan['bound_files'].items()))
    for mp,mhash in plan['manifests'].items():
        m=read(mp);check(mp+'_hash',sha(mp)==mhash);key=Path(mp).name.removesuffix('-manifest.json');public=m['procedure']['worker_kind']=='public';flow=m['model']=='flow';procedure=m['procedure'];group=[]
        for c in m['cells']:
            name=c['id'];row=dict(id=name,usable=False,errors=[]);results.append(row);group.append(row)
            try:
                f=read(c['fixture_path']);check(name+'_fixture',sha(c['fixture_path'])==c['fixture_sha256'] and f['seed']==c['dataset_seed'] and f['prior_predictive'] is True)
                vals,future=truth(f,flow);selected={s['name']:vals[s['key']] if s['kind']=='functional' else future[(s['horizon'],s.get('group'))] for s in m['selectors']};check(name+'_truth',selected==c['truth'])
                status=read(c['status_path']);hw=read(c['hardware_path']);marker=read(c['started_path']);row['controller_seconds']=status.get('elapsed_seconds');row['wrapper_seconds']=hw.get('elapsed_seconds')
                check(name+'_terminal',status['status']=='worker_terminal' and status['returncode']==hw['returncode']);check(name+'_hardware',status['hardware_sha256']==sha(c['hardware_path']) and hw['job_active_processes_after_cleanup']==0 and hw['realized_cpus']==[0] and hw['command']==c['worker_command'] and hw['containment']['assigned_before_worker_execution'] is True)
                check(name+'_cost',finite(row['controller_seconds']) and finite(row['wrapper_seconds']) and row['controller_seconds']>=row['wrapper_seconds']>0)
                check(name+'_marker',all(marker.get(k)==v for k,v in dict(protocol_sha256=m['protocol_sha256'],procedure_sha256=m['procedure_sha256'],fixture_sha256=c['fixture_sha256'],dataset_seed=c['dataset_seed']).items()))
                out=Path(c['output_directory']);rp=out/('python-pymc-flow-report.json' if public and flow else 'python-pymc-report.json' if public else 'numpyro-continuation-report.json')
                if hw['status']=='worker-timeout':
                    check(name+'_timeout',status['returncode']==124 and hw['elapsed_seconds']>=600);row['failure']='budgeted_computational_timeout';continue
                r=read(rp);check(name+'_report_hash',status['report_sha256']==sha(rp))
                if r['status']!='completed':row['failure']='worker_failed';continue
                check(name+'_identity',r['seed']==c['chain_seed'] and r['arm']==procedure['worker_arm'] and r['coordinates']==procedure['coordinates'])
                actual=r['bindings'] if public else r['source_sha256'];check(name+'_sources',all(actual.get(k)==v for k,v in c['source_sha256'].items()))
                if public:check(name+'_runtime',all(actual.get(k)==v for k,v in procedure['runtime_bindings'].items()) and r['parity']['passed'])
                else:check(name+'_report_fixture',r['fixture_sha256']==c['fixture_sha256'])
                gates=[];counts=[];intervals={}
                for a in r['attempts']:
                    n=a['draws'];counts.append(n);fit=read(out/(f'draws-{n}/fit-report.json' if public else f'draws-{n}-report.json'));e=fit['evaluation'];fs=e['functionals'];qs=e['canonical_parameter_diagnostics'];forecasts=e['forecast']['rows']
                    check(name+f'_{n}_scope',set(fs)==set(vals) and set(qs)=={f'q_{i}' for i in range(44 if flow else 34)} and len(forecasts)==len(future) and {(z['horizon'],z.get('group')) for z in forecasts}==set(future))
                    healthy=fit['status']=='completed' and e['chain_count']==4 and fit['retained_divergences']==0 and all(all(finite(d.get(k)) for k in ('rhat','bulk_ess','tail_ess')) and 0<d['rhat']<=1.01 and d['bulk_ess']>=400 and d['tail_ess']>=400 for d in list(fs.values())+list(qs.values()))
                    ratios=[]
                    for z in list(fs.values())+forecasts:
                        b=z['interval_90'] if 'interval_90' in z else [z['lower'],z['upper']];se=z['endpoint_mcse'];valid=len(b)==len(se)==2 and all(finite(v) for v in b+se) and b[1]>b[0] and min(se)>=0;ratios.append(max(se)/(b[1]-b[0]) if valid else float('inf'))
                    passed=healthy and max(ratios)<=.02;gates.append(passed);check(name+f'_{n}_gate',passed==a['screen']['pass'])
                    raw=out/f'draws-{n}'/('python-pymc-flow-raw.json' if flow else 'python-pymc-raw.json') if public else out/'numpyro-continuation-raw.json'
                    if public or n==r['attempts'][-1]['draws']:check(name+f'_{n}_starts',tail(raw,'initial_positions')==f['data']['initial_positions'])
                    if public:check(name+f'_{n}_frozen',tail(raw,'adapted_metadata')==r['adapted_metadata'])
                    row['final_health']=healthy;row['final_max_endpoint_ratio']=max(ratios);row['retained_divergences']=fit['retained_divergences']
                check(name+'_first_pass',counts==procedure['tiers'][:len(counts)] and not any(gates[:-1]) and (gates[-1] or counts[-1]==8000) and r['precision_pass']==gates[-1]);row['selected_draws']=counts[-1]
                if public:
                    calls=r['warmup_target_calls']
                    for a in r['attempts']:calls+=a['added_target_calls'];check(name+f"_{a['draws']}_callbacks",calls==a['cumulative_target_calls'])
                    check(name+'_total_callbacks',calls==r['total_target_calls'])
                else:check(name+'_frozen_reference',len({z['adaptation_sha256'] for z in r['checkpoints']})==1 and [z['draws_per_chain'] for z in r['checkpoints']]==list(range(1000,counts[-1]+1,1000)))
                invocation=read(out/'invocation-timing.json');worker=next(v for k,v in invocation.items() if k.startswith('seconds_'));row['worker_seconds']=worker
                check(name+'_stage_cost_enclosure',finite(worker) and hw['elapsed_seconds']>=worker>=r['end_to_end_seconds'])
                if public:check(name+'_sampling_cost',math.isclose(r['total_sampling_seconds'],r['adapt_seconds']+sum(a['sampling_seconds'] for a in r['attempts']),rel_tol=1e-12,abs_tol=1e-7))
                else:check(name+'_sampling_cost',r['end_to_end_seconds']>=r['warmup_seconds']+sum(a['seconds'] for a in r['checkpoints']))
                row['usable']=gates[-1] and status['returncode']==0 and hw['status']=='completed'
                fore={(z['horizon'],z.get('group')):z for z in forecasts}
                for s in m['selectors']:
                    z=fs[s['key']] if s['kind']=='functional' else fore[(s['horizon'],s.get('group'))];intervals[s['name']]=z['interval_90'] if s['kind']=='functional' else [z['lower'],z['upper']]
                row['coverage']={k:b[0]<=selected[k]<=b[1] for k,b in intervals.items()}
            except Exception as exc:row['errors'].append(type(exc).__name__+': '+str(exc));check(name+'_read_complete',False)
        usable=[r for r in group if r['usable']];summaries[key]={'intended':len(group),'usable':len(usable),'coverage':{s['name']:{'covered':sum(r['coverage'][s['name']] for r in usable),'conditional_denominator':len(usable),'unconditional_denominator':len(group)} for s in m['selectors']}}
        nr=p/(key+'-normalized.json')
        if nr.exists():
            normalized=read(nr);check(key+'_normalized_denominator',{r['id'] for r in normalized}=={c['id'] for c in m['cells']} and len(normalized)==len(group));check(key+'_normalized_usable',all(z['usable']==next(r['usable'] for r in group if r['id']==z['id']) and z['provenance_valid'] for z in normalized))
    check('all20_read',len(results)==20);return dict(qualified=False,integrity_pass=all(checks.values()),checks=checks,cells=results,summaries=summaries,artifact_sha256=inventory,limitations=['Feasibility only:8candidate/2reference datasets per model.','No posterior-array diagnostic recomputation; reported numerical diagnostics independently gated.','All failures remain unconditional denominators; conditional coverage uses usable fits only.'])

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('directory');ap.add_argument('--output',required=True);args=ap.parse_args();result=audit(args.directory)
    with Path(args.output).open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps({'integrity_pass':result['integrity_pass'],'failed_checks':[k for k,v in result['checks'].items() if not v]}))
