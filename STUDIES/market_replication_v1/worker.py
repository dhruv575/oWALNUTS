"""Month-aware E62 adapter; no network, retries or automatic authorization."""
import argparse,hashlib,importlib.metadata,importlib.util,json,os,sys,time
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);loaded=importlib.util.module_from_spec(spec);sys.modules[name]=loaded;spec.loader.exec_module(loaded);return loaded

def exclusive(path,value):
    with Path(path).open('x',encoding='utf-8') as handle:json.dump(value,handle,indent=2,allow_nan=False);handle.write('\n')

def admit(path):
    spec=json.loads(Path(path).read_bytes())
    if spec.get('status')!='frozen_scoring_authorized':raise ValueError('Replication scoring not authorized')
    from data_contract import MONTHS
    if len(spec['months'])!=3:raise ValueError('All3 panels required')
    for i,(actual,want)in enumerate(zip(spec['months'],MONTHS)):
        if any(actual.get(k)!=v for k,v in want.items()):raise ValueError('Fixed month contract changed')
        seeds=dict(candidate=dict(initial=2026102801000000+100000*i,warm=2026102802000000+100000*i),references=[502710000+100000*i+1000*j for j in range(8)],bootstrap=2026102803000000+100000*i)
        if actual['seeds']!=seeds:raise ValueError('Reserved month seeds changed')
    if spec['K']!=400 or spec['window']!=250:raise ValueError('Fixed K/window changed')
    draft=json.loads(Path(__file__).with_name('COMPUTE-DRAFT.json').read_bytes())
    if spec['bounds']!=draft['bounds']:raise ValueError('Fixed batch/scoring caps changed')
    if spec['reference']['engine_options']!=draft['reference']['engine_options'] or spec['reference'].get('api_and_target_verified')is not True:raise ValueError('Reference settings unverified/changed')
    if sys.prefix!=spec['runtime']['prefix']:raise ValueError('Runtime prefix mismatch')
    for package,version in spec['runtime']['packages'].items():
        if importlib.metadata.version(package)!=version:raise ValueError('Package drift: '+package)
    for file,want in {**spec['sources'],**spec['runtime']['binaries']}.items():
        if sha(file)!=want:raise ValueError('Frozen source/runtime drift: '+file)
    return spec

def month_spec(spec,month):
    row=next(v for v in spec['months'] if v['month']==month)
    return dict(spec,origins=row['origins'],reference_ticks=row['reference_ticks'],seeds=row['seeds'])

def terminal_accounting(spec,month,root,jobs):
    from reuse import calendar
    modules=calendar(month,spec['e62_root']);root=Path(root);root.mkdir(parents=True,exist_ok=True)
    rows=modules['ledger'].build(root);refs=modules['ledger'].references(root);integrity=modules['ledger'].validate_artifacts(root)
    n=modules['contract']['origins'];valid={arm:sum(r['arms'][arm]['status']=='ok' for r in rows) for arm in ['candidate','rolling_t5','ewma_t5']}
    expected={(p,i) for p,count in [('candidate',1),('baselines',1),('reference',8),('report',1)] for i in range(count)}
    identities=[(j['phase'],j['index']) for j in jobs]
    job_accounting=len(identities)==11 and set(identities)==expected
    execution=job_accounting and all(j.get('status')=='exited' and j.get('exit_code')==0 and j.get('group_drained')is True and not j.get('orphaned_children_after_leader_exit',False) for j in jobs)
    validation=dict(month=month,accounting_complete=job_accounting and len(rows)==n and len(refs)==8 and integrity['integrity_ok'],execution_complete=execution,
      planned_origins=n,planned_forecasts=n*3,planned_references=8,valid_scores=valid,all_planned_forecasts_available=all(v==n for v in valid.values()),
      references_complete=sum(r['status']=='complete' for r in refs),reference_diagnostics_pass=sum(r.get('reference_diagnostics_pass')is True for r in refs),artifact_integrity=integrity,qualification=None)
    exclusive(root/'terminal-ledger.json',rows);exclusive(root/'terminal-references.json',refs);exclusive(root/'terminal-validation.json',validation);return validation

def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['candidate','baselines','reference','report']);parser.add_argument('--month',required=True);parser.add_argument('--index',type=int,default=0);parser.add_argument('--manifest',required=True);parser.add_argument('--root',type=Path,required=True);args=parser.parse_args()
    spec=admit(args.manifest);selected=month_spec(spec,args.month)
    from reuse import calendar
    from data_contract import load_sealed
    modules=calendar(args.month,spec['e62_root']);root=args.root.resolve();root.mkdir(parents=True,exist_ok=True);jobs=root/'jobs';jobs.mkdir(exist_ok=True)
    record=jobs/f'{args.phase}-{args.index:02d}.json'
    if record.exists() or record.with_suffix('.start.json').exists():raise FileExistsError('No job retry')
    if args.phase!='reference' and args.index!=0:raise ValueError('Unexpected job index')
    frozen=sha(args.manifest);started=time.monotonic();state=dict(month=args.month,phase=args.phase,index=args.index,status='running',pid=os.getpid(),manifest_sha256=frozen,started_unix=time.time());exclusive(record.with_suffix('.start.json'),state)
    try:
        if args.phase!='report':y=load_sealed(spec['acquisition'],args.month)
        if args.phase=='candidate':result=modules['worker'].candidate(selected,y,root,updates=selected['origins'])
        elif args.phase=='baselines':result=modules['baseline'].run(y,root/'baselines',deadline=started+300,planned_ticks=selected['origins'])
        elif args.phase=='reference':result=modules['reference'].run(selected,y,root,args.index)
        else:
            rows=modules['ledger'].build(root);exclusive(root/'ledger.json',rows)
            summary=modules['report'].summarize(rows,seed=selected['seeds']['bootstrap']);summary.update(month=args.month,artifact_integrity=modules['ledger'].validate_artifacts(root),references=modules['ledger'].references(root))
            summary['phase_records']={p.name:json.loads(p.read_bytes()) for p in jobs.glob('*.json') if '.start.'not in p.name}
            if not summary['artifact_integrity']['integrity_ok']:raise ValueError('Artifact integrity failure')
            exclusive(root/'summary.json',summary)
            exclusive(root/'evidence-validation.json',dict(month=args.month,accounting_complete=True,execution_complete=None,execution_note='Final process accounting resolved by batch terminal callback',planned_origins=selected['origins'],planned_references=8,valid_scores={a:summary['status_counts'][a].get('ok',0) for a in ['candidate','rolling_t5','ewma_t5']},artifact_integrity=summary['artifact_integrity']))
            result=dict(status='complete')
        state.update(status=result['status'],result=result);admit(args.manifest)
        if sha(args.manifest)!=frozen:raise ValueError('Manifest drift during job')
        state['postrun_bindings_held']=True
    except BaseException as error:state.update(status='failed',error=type(error).__name__,reason=str(error))
    finally:state.update(elapsed_seconds=time.monotonic()-started,ended_unix=time.time());exclusive(record,state)
    return 0 if state['status']=='complete' else 1

if __name__=='__main__':raise SystemExit(main())
