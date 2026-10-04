"""Read-only stdlib postrun audit; run only after all six cells terminal."""
import argparse,json,hashlib,math,struct
from pathlib import Path
NAMES=['beta_bar','tau','mu_h','sigma_h','h_terminal','h_mean']+[s+str(g) for g in range(4) for s in ['alpha_','beta_']]

def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def normalized(d):return {str(Path(k).resolve()).casefold():v for k,v in d.items()}
def starts(path,key="initial_positions"):
    with Path(path).open('rb') as f:f.seek(max(0,Path(path).stat().st_size-1000000));tail=f.read().decode()
    marker='"'+key+'":';i=tail.rfind(marker)
    if i<0:raise ValueError('Raw initial positions not in bounded tail')
    return json.JSONDecoder().raw_decode(tail[i+len(marker):].lstrip())[0]
def matrix_equal(a,b):return len(a)==len(b) and all(len(x)==len(y) for x,y in zip(a,b)) and all(math.isfinite(x) and abs(x-y)<1e-12 for aa,bb in zip(a,b) for x,y in zip(aa,bb))
def gate(fit,cell):
    e=fit['evaluation'];d=list(e['functionals'].values())+list(e['canonical_parameter_diagnostics'].values())
    health=e['chain_count']==4 and len(e['canonical_parameter_diagnostics'])==cell['dimension'] and fit['retained_divergences']==0 and all(math.isfinite(v[k]) and (v[k]<=1.01 if k=='rhat' else v[k]>=400) for v in d for k in ['rhat','bulk_ess','tail_ess'])
    values={k:max(v['endpoint_mcse'])/(v['interval_90'][1]-v['interval_90'][0]) for k,v in e['functionals'].items()}
    values.update({f'forecast{i}':max(v['endpoint_mcse'])/(v['upper']-v['lower']) for i,v in enumerate(e['forecast']['rows'])})
    scope=set(e['functionals'])==set(NAMES) and set(e['canonical_parameter_diagnostics'])=={f'q_{j}' for j in range(cell['dimension'])} and [(r['horizon'],r['group']) for r in e['forecast']['rows']]==[(h,g) for h in range(1,cell['forecast_rows']//4+1) for g in range(4)]
    intervals=[(v['interval_90'],v['endpoint_mcse']) for v in e['functionals'].values()]+[([v['lower'],v['upper']],v['endpoint_mcse']) for v in e['forecast']['rows']]
    precision=all(len(i)==len(m)==2 and all(math.isfinite(v) for v in [*i,*m]) and i[1]>i[0] and min(m)>=0 and max(m)/(i[1]-i[0])<=.02 for i,m in intervals)
    return dict(health=health,precision=precision,scope=scope,passed=fit.get('status')=='completed' and health and precision and scope,ratios=values,divergences=fit['retained_divergences'])
def canonical_digest(path,draws,dimension):
    """Stream one canonical vector at a time; hash exact finite float64 values.

    Call only after the entire campaign is terminal: memory is bounded but
    reading all posterior bytes is substantial I/O. This is checkpoint parity,
    not independent accuracy, and does not hash JSON formatting differences.
    """
    digest=hashlib.sha256();decoder=json.JSONDecoder();buffer=''
    with Path(path).open('r',encoding='utf-8') as handle:
        marker='"canonical_draws":'
        while marker not in buffer:
            chunk=handle.read(65536)
            if not chunk or len(buffer)>1000000:raise ValueError('Canonical array prefix not found')
            buffer+=chunk
        buffer=buffer.split(marker,1)[1]
        def replenish():
            nonlocal buffer
            chunk=handle.read(65536)
            if not chunk:raise ValueError('Truncated canonical array')
            buffer+=chunk
        def consume(token):
            nonlocal buffer
            buffer=buffer.lstrip()
            while not buffer:replenish();buffer=buffer.lstrip()
            if not buffer.startswith(token):raise ValueError('Unexpected canonical array shape')
            buffer=buffer[len(token):]
        consume('[')
        for chain in range(4):
            if chain:consume(',')
            consume('[')
            for draw in range(draws):
                if draw:consume(',')
                buffer=buffer.lstrip()
                while True:
                    try:row,end=decoder.raw_decode(buffer);break
                    except json.JSONDecodeError:replenish();buffer=buffer.lstrip()
                if not isinstance(row,list) or len(row)!=dimension or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in row):raise ValueError('Invalid canonical vector')
                digest.update(struct.pack('<'+str(dimension)+'d',*row));buffer=buffer[end:]
            consume(']')
        consume(']')
    return dict(shape=[4,draws,dimension],float64_sha256=digest.hexdigest(),meaning='Exact finite float64 canonical retained values; excludes formatting and metadata')

def audit(directory):
    root=Path(directory);path=root/'plan.json';plan=load(path);checks={};results={};hashes={}
    def ck(k,v):checks[k]=bool(v)
    ck('plan_digest',sha(path)==path.with_suffix('.sha256').read_text().strip())
    ck('six_intended',len(plan['cells'])==6 and len({c['id'] for c in plan['cells']})==6)
    ck('study_sources',all(sha(k)==v for k,v in plan['study_bindings'].items()))
    ck('bound_files',all(sha(k)==v for k,v in plan['bound_files'].items()))
    ck('frozen_scope',plan['frozen'] and plan['expected']==6 and plan['timeout_seconds']==1800 and plan['tiers']==[1000,2000,4000,8000])
    for cell in plan['cells']:
        name=cell['id']
        try:
            name=cell['id'];sp=root/(name+'-status.json');out=root/name
            if not sp.exists():results[name]=dict(success=False,status='missing',cost=None);ck(name+'_terminal',False);continue
            status=load(sp);row=dict(success=False,status=status['status'],cost=status.get('elapsed_seconds'));results[name]=row;ck(name+'_terminal',True)
            if status['status']=='unattempted_provenance_abort':
                ck(name+'_attempted',False);continue
            ck(name+'_cost',isinstance(row['cost'],(int,float)) and math.isfinite(row['cost']) and row['cost']>0)
            ck(name+'_fixture',sha(cell['fixture'])==cell['fixture_sha256'])
            hp=root/(name+'-hardware.json')
            if not hp.exists():ck(name+'_hardware',False);continue
            h=load(hp);ck(name+'_hardware_hash',sha(hp)==status.get('hardware_sha256'));ck(name+'_containment',h.get('job_active_processes_after_cleanup')==0 and h.get('realized_cpus')==[0] and h.get('containment',{}).get('assigned_before_worker_execution') is True)
            ck(name+'_cost_enclosure',row['cost']>=h['elapsed_seconds']);row['wrapper_seconds']=h['elapsed_seconds'];ck(name+'_wrapper_positive',math.isfinite(h['elapsed_seconds']) and h['elapsed_seconds']>0)
            ck(name+'_exit_evidence',load(root/(name+'-exit.json'))['returncode']==status['returncode']==h['returncode'])
            ck(name+'_plan_at_start',load(root/(name+'-started.json'))['plan_sha256']==sha(path))
            if h['status']=='worker-timeout':
                ck(name+'_timeout',status['returncode']==h['returncode']==124 and h['elapsed_seconds']>=1800 and not status['success']);row['status']='budgeted_computational_timeout'
                partial=[]
                for n in [1000,2000,4000,8000]:
                    fp=out/(f'draws-{n}-report.json' if cell['arm']=='numpyro_continuation' else f'draws-{n}/fit-report.json')
                    if fp.exists():
                        hashes[str(fp)]=sha(fp);partial.append(dict(draws=n,**gate(load(fp),cell)))
                        raw=out/f'draws-{n}/python-pymc-flow-raw.json'
                        if raw.exists():ck(f'{name}_{n}_partial_starts',matrix_equal(starts(raw),cell['starts']))
                row['partial_attempts']=partial
                for candidate in ['started.json','plan.json','python-pymc-flow-report.json','numpyro-continuation-report.json']:
                    pp=out/candidate
                    if pp.exists():hashes[str(pp)]=sha(pp)
                continue
            arm=cell['arm'];rp=out/('numpyro-continuation-report.json' if arm=='numpyro_continuation' else 'python-pymc-flow-report.json')
            if not rp.exists():ck(name+'_report',False);continue
            r=load(rp);hashes[str(rp)]=sha(rp);ck(name+'_report_hash',sha(rp)==status['report_sha256']);ck(name+'_identity',r['seed']==cell['seed'] and r['settings']['chains']==4 and r['settings']['warmup']==1000)
            if arm=='owalnuts_continuation':
                actual=normalized(r['bindings']);expected=normalized(plan['study_bindings']);expected.update({k:v for k,v in normalized(plan['bound_files']).items() if Path(k).name in ['python.exe','__init__.py','_owalnuts.pyd']});expected[str(Path(cell['fixture']).resolve()).casefold()]=cell['fixture_sha256'];ck(name+'_runtime',all(actual.get(k)==v for k,v in expected.items()))
                ck(name+'_report_starts',matrix_equal(r['initial_positions'],cell['starts']))
                ck(name+'_predictive_seed',r['predictive_seed']==cell['predictive_seed'])
            else:
                ck(name+'_runtime',r['source_sha256']=={Path(k).name:v for k,v in plan['study_bindings'].items()} and r['fixture_sha256']==cell['fixture_sha256'])
                if arm=='restart':
                    ck(name+'_extension',r['extension_sha256']==next(v for k,v in plan['bound_files'].items() if Path(k).name=='_owalnuts.pyd') and Path(r['extension_path']).resolve()==(Path(plan['pythonpath'])/'owalnuts/_owalnuts.pyd').resolve())
                    ck(name+'_adapter',r['adapter_source_sha256']==next(v for k,v in plan['bound_files'].items() if Path(k).name=='__init__.py'))
                else:ck(name+'_acceptance',r['settings']['target_accept']==.9)
            if arm!='numpyro_continuation':
                ck(name+'_block_parity',r['model']=='flow' and r['settings']['block_size']==32 and r['parity'].get('passed') is True and bool(r['parity'].get('cases')) and r['precision_plan']['names']==NAMES)
            else:ck(name+'_coordinates',r['coordinates']=='noncentered')
            if r['status']!='completed':
                row['status']='worker_failed';row['error']=r.get('error');ck(name+'_failed_not_success',not status['success']);continue
            attempts=[]
            for a in r['attempts']:
                n=a['draws'];fp=out/(f'draws-{n}-report.json' if arm=='numpyro_continuation' else f'draws-{n}/fit-report.json');g=gate(load(fp),cell);hashes[str(fp)]=sha(fp);ck(f'{name}_{n}_gate',g['passed']==a['screen']['pass'] and g['scope']);ck(f'{name}_{n}_scope',set(a['screen']['parameter_functionals'])==set(NAMES) and a['screen']['forecast_rows']==cell['forecast_rows'] and a['screen']['threshold']==.02);attempts.append(dict(draws=n,**g))
                if arm!='numpyro_continuation' or n==r['attempts'][-1]['draws']:
                    raw=out/'numpyro-continuation-raw.json' if arm=='numpyro_continuation' else out/f'draws-{n}/python-pymc-flow-raw.json';ck(f'{name}_{n}_starts',matrix_equal(starts(raw),cell['starts']))
            ck(name+'_final_gate',gate(r,cell)=={k:v for k,v in attempts[-1].items() if k!='draws'})
            ck(name+'_firstpass',[a['draws'] for a in attempts]==[1000,2000,4000,8000][:len(attempts)] and not any(a['passed'] for a in attempts[:-1]) and (attempts[-1]['passed'] or attempts[-1]['draws']==8000))
            passed=attempts[-1]['passed'] and status['returncode']==h['returncode']==0 and h['status']=='completed';ck(name+'_success',passed==status['success']==r['precision_pass']);row.update(success=passed,attempts=attempts)
            inv=load(out/'invocation-timing.json');worker=next(v for k,v in inv.items() if k.startswith('seconds_'));ck(name+'_worker_cost',h['elapsed_seconds']>=worker>=r['end_to_end_seconds']);row['worker_seconds']=worker
            if arm=='restart':ck(name+'_restart_cost',abs(r['total_fit_and_report_seconds']-sum(a['fit_and_report_seconds'] for a in r['attempts']))<1e-7 and r['end_to_end_seconds']>=r['total_fit_and_report_seconds']+r['parity_seconds']+r['compilation']['compile_seconds'])
            elif arm=='numpyro_continuation':
                cp=r['checkpoints'];ck(name+'_adaptation',len({x['adaptation_sha256'] for x in cp})==1);ck(name+'_reference_batches',[x['draws_per_chain'] for x in cp]==list(range(1000,attempts[-1]['draws']+1,1000)));ck(name+'_batch_cost',r['end_to_end_seconds']>=r['warmup_seconds']+sum(x['seconds'] for x in cp))
            else:
                ck(name+'_sampling_cost',abs(r['total_sampling_seconds']-r.get('adapt_seconds',0)-sum(a.get('sampling_seconds',0) for a in r['attempts']))<1e-7)
                base=r['warmup_target_calls'];frozen=json.dumps(r['adapted_metadata'],sort_keys=True)
                for a in r['attempts']:
                    n=a['draws'];raw=out/f'draws-{n}/python-pymc-flow-raw.json';metadata=None
                    ck(f'{name}_{n}_frozen_metric',json.dumps(starts(raw,'adapted_metadata'),sort_keys=True)==frozen)
                    base+=a['added_target_calls'];ck(f'{name}_{n}_callbacks',base==a['cumulative_target_calls'])
                ck(name+'_callbacks_total',base==r['total_target_calls']);ck(name+'_metadata_present',bool(r['adapted_metadata']))
        except Exception as exc:
            ck(name+'_audit_complete',False)
            results.setdefault(name,dict(success=False,cost=None,status='invalid_artifacts'))
            results[name].update(success=False,audit_error=f'{type(exc).__name__}: {exc}')
    checkpoint_parity=[]
    for periods in [128,1000]:
        left=results[f'T{periods}-restart'];right=results[f'T{periods}-owalnuts_continuation']
        shared=sorted({a['draws'] for a in left.get('attempts',[])} & {a['draws'] for a in right.get('attempts',[])})
        for draws in shared:
            entry=dict(periods=periods,draws=draws,meaning='Same-seed checkpoint parity only; not independent accuracy')
            try:
                digests=[canonical_digest(root/f'T{periods}-{arm}'/f'draws-{draws}/python-pymc-flow-raw.json',draws,periods+12) for arm in ['restart','owalnuts_continuation']]
                entry.update(restart=digests[0],continuation=digests[1],exactly_equal=digests[0]==digests[1])
                ck(f'T{periods}_{draws}_checkpoint_parity',entry['exactly_equal'])
            except Exception as exc:
                entry.update(exactly_equal=False,error=str(exc));ck(f'T{periods}_{draws}_checkpoint_parity',False)
            checkpoint_parity.append(entry)
    pairs=[]
    for case in [128,1000]:
        for a,b in [('restart','owalnuts_continuation'),('owalnuts_continuation','numpyro_continuation')]:
            x=results[f'T{case}-{a}'];y=results[f'T{case}-{b}'];pairs.append(dict(case=case,a=a,b=b,b_over_a_ratio=y['cost']/x['cost'] if x['success'] and y['success'] and all(checks.values()) else None))
    return dict(phase='development',qualified=False,expected=6,checks=checks,integrity_pass=all(checks.values()),results=results,pairs=pairs,checkpoint_parity=checkpoint_parity,report_sha256=hashes,total_driver_seconds=sum(r['cost'] for r in results.values() if isinstance(r.get('cost'),(int,float)) and math.isfinite(r['cost'])),successful_cells=sum(r['success'] for r in results.values()),limitations=['Allfailed/missing outcomes retained; same-case successful pairs only have ratios.','Stored gates checked, estimators not reestimated.','Canonical starts inspected in bounded tails; large posterior arrays not loaded.','Adaptedmetadata equality checked from bounded raw tails and callbacks reconciled; no full posterior rescan.'])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--out',required=True);a=p.parse_args();result=audit(a.directory)
    with Path(a.out).open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
