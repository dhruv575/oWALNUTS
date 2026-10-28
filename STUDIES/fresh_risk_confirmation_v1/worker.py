"""Thin calendar/inference/tail dispatcher, with fixed admission and no retries."""
import argparse,hashlib,importlib.metadata,importlib.util,json,os,sys,time
from pathlib import Path
from data_contract import MONTHS,load_sealed
from tail_inputs import seal_inference
from tail_worker import exclusive
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);loaded=importlib.util.module_from_spec(spec);sys.modules[name]=loaded;spec.loader.exec_module(loaded);return loaded
def admit(path,expected_status='frozen_scoring_authorized'):
    spec=json.loads(Path(path).read_bytes());draft=json.loads(Path(__file__).with_name('COMPUTE-DRAFT.json').read_bytes())
    if expected_status not in ('frozen_scoring_authorized','development_authorized') or spec.get('status')!=expected_status:raise ValueError('Study not authorized')
    for key in ('K','window','probabilities','shards','bounds'):
        if spec[key]!=draft[key]:raise ValueError('Frozen setting changed: '+key)
    if len(spec['months'])!=3:raise ValueError('All panels required')
    for actual,want in zip(spec['months'],draft['months']):
        expected=dict(want)
        if expected_status=='development_authorized':expected['seeds']=dict(candidate=dict(initial=993711000,warm=993712000),references=[993713000]*8,bootstrap=17)
        if actual!=expected:raise ValueError('Month/seeds changed')
    if spec['bootstrap_seeds']!={m['month']:m['seeds']['bootstrap'] for m in spec['months']}:raise ValueError('Bootstrap identities changed')
    if spec['reference']['engine_options']!=draft['reference']['engine_options'] or spec['reference'].get('api_and_target_verified')is not True:raise ValueError('Reference configuration changed')
    if sys.prefix!=spec['runtime']['prefix']:raise ValueError('Runtime prefix drift')
    for name,want in spec['runtime']['packages'].items():
        if importlib.metadata.version(name)!=want:raise ValueError('Package drift: '+name)
    for name,want in {**spec['sources'],**spec['runtime']['binaries']}.items():
        if sha(name)!=want:raise ValueError('Source/runtime drift: '+name)
    return spec
def month_spec(spec,month):
    row=next(m for m in spec['months'] if m['month']==month)
    return dict(spec,origins=row['origins'],reference_ticks=row['reference_ticks'],seeds=row['seeds'])
def tail_spec(spec,root):
    root=Path(root).resolve();seal=root/'INFERENCE-INPUT-SEAL.json'
    return dict(spec,input=dict(root=str(root),inventory_sha256=sha(seal)))
def inference(spec,phase,month,index,root,y=None,updates=None):
    from reuse import calendar
    selected=month_spec(spec,month);mods=calendar(month,spec['e62_root']);root=Path(root)/'inference'/month;root.mkdir(parents=True,exist_ok=True)
    record=root/'jobs'/f'{phase}-{index:02d}.json';start=time.monotonic();state=dict(phase=phase,month=month,index=index,status='running',pid=os.getpid())
    exclusive(record.with_suffix('.start.json'),state)
    try:
        if phase!='reference' and index!=0:raise ValueError('Unexpected index')
        if y is None:y=load_sealed(spec['acquisition'],month)
        count=selected['origins'] if updates is None else updates
        if updates is not None and not (spec['status']=='development_authorized' and updates==32):raise ValueError('Development-only short panel')
        if phase=='native':result=mods['worker'].candidate(selected,y,root,updates=count)
        elif phase=='baselines':result=mods['baseline'].run(y,root/'baselines',deadline=start+spec['bounds']['baselines_seconds'],planned_ticks=count,development=updates is not None)
        elif phase=='reference':result=mods['reference'].run(selected,y,root,index)
        else:raise ValueError('Unknown inference phase')
        state.update(status=result['status'],result=result)
    except BaseException as error:state.update(status='failed',error=repr(error))
    state['elapsed_seconds']=time.monotonic()-start;exclusive(record,state);return state
def terminal_accounting(spec,root,jobs):
    from reuse import calendar
    import tail_report
    root=Path(root);native={};errors=[]
    for m in MONTHS:
        mods=calendar(m['month'],spec['e62_root']);folder=root/'inference'/m['month'];folder.mkdir(parents=True,exist_ok=True)
        rows=mods['ledger'].build(folder);refs=mods['ledger'].references(folder);integrity=mods['ledger'].validate_artifacts(folder)
        exclusive(folder/'terminal-ledger.json',rows);exclusive(folder/'terminal-references.json',refs)
        native[m['month']]=dict(planned_origins=m['origins'],available_scores={a:sum(r['arms'][a]['status']=='ok' for r in rows) for a in ('candidate','rolling_t5','ewma_t5')},references_complete=sum(r['status']=='complete' for r in refs),reference_diagnostics_pass=sum(r.get('reference_diagnostics_pass')is True for r in refs),artifact_integrity=integrity)
        if not integrity['integrity_ok']:errors.append('Native artifact integrity: '+m['month'])
    seal=root/'INFERENCE-INPUT-SEAL.json'
    if seal.exists():
        for name,want in json.loads(seal.read_bytes())['files'].items():
            if sha(root/name)!=want:errors.append('Inference seal drift: '+name)
    # No seal means arithmetic never admitted; the fixed empty tail ledger still exists.
    selected=dict(spec,input=dict(root=str(root.resolve()),inventory_sha256=sha(seal) if seal.exists() else None))
    tails=tail_report.terminal_accounting(selected,root/'tails',jobs)
    result=dict(accounting_complete=True,planned_origins=4320,planned_references=24,planned_arm_origins=12960,native=native,tail=tails,artifact_integrity=dict(integrity_ok=not errors and tails['artifact_integrity']['integrity_ok'],errors=errors))
    exclusive(root/'evidence-validation.json',result);return result
def batch_summary(spec,root):
    import tail_report
    value=tail_report.batch_summary(spec,Path(root)/'tails');exclusive(Path(root)/'aggregate.json',value);return value
def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['native','baselines','reference','tail_candidate','tail_reference','report']);p.add_argument('--month');p.add_argument('--index',type=int,default=0);p.add_argument('--shard',type=int);p.add_argument('--manifest',required=True);p.add_argument('--root',required=True);a=p.parse_args();spec=admit(a.manifest);before=sha(a.manifest)
    if a.phase in ('native','baselines','reference'):result=inference(spec,a.phase,a.month,a.index,a.root)
    elif a.phase=='report':
        import tail_report
        result=tail_report.run(spec,Path(a.root)/'tails',a.month)
    else:
        import tail_worker
        result=tail_worker.run_shard(tail_spec(spec,a.root),a.phase.removeprefix('tail_'),a.shard,Path(a.root)/'tails')
    admit(a.manifest)
    if sha(a.manifest)!=before:raise ValueError('Manifest drift')
    return 0 if result['status']=='complete' else 1
if __name__=='__main__':raise SystemExit(main())
