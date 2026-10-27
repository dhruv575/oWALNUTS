"""Compute entry; refuses execution until a separately frozen scoring manifest."""
import argparse,hashlib,importlib.metadata,importlib.util,json,os,sys,time
from pathlib import Path
import numpy as np
from data_contract import load_sealed,inputs,ORIGINS
from linear_runner_snapshot import run_lane,exclusive

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);loaded=importlib.util.module_from_spec(spec);sys.modules[name]=loaded;spec.loader.exec_module(loaded);return loaded

def admit(path,expected_status='frozen_scoring_authorized'):
    value=json.loads(Path(path).read_bytes())
    if value.get('status')!=expected_status:raise ValueError('Scoring not authorized')
    draft=json.loads(Path(__file__).with_name('COMPUTE-DRAFT.json').read_bytes())
    for key in ['origins','K','window','reference_ticks','bounds']:
        if value[key]!=draft[key]:raise ValueError('Fixed scientific setting changed: '+key)
    expected_seeds=draft['seeds'] if expected_status=='frozen_scoring_authorized' else dict(candidate=dict(initial=993711000,warm=993712000),references=[993713000]*8,bootstrap=17)
    if value['seeds']!=expected_seeds:raise ValueError('Seed reservation mismatch')
    if sys.prefix!=value['runtime']['prefix']:raise ValueError('Runtime prefix mismatch')
    for key,version in value['runtime']['packages'].items():
        if importlib.metadata.version(key)!=version:raise ValueError('Package drift: '+key)
    for file,want in {**value['sources'],**value['runtime']['binaries']}.items():
        if sha(file)!=want:raise ValueError('Frozen source/runtime changed: '+file)
    return value

def candidate(spec,y,root,updates=ORIGINS):
    if updates!=ORIGINS and not (spec.get('status')=='development_authorized' and updates==32):raise ValueError('Production panel cannot shrink')
    import owalnuts
    adapter=module(spec['dependencies']['resident_adapter'],'frozen_real_resident_adapter')
    target=module(spec['dependencies']['target'],'frozen_real_sv_target')
    evaluator=module(spec['dependencies']['predictive_density'],'frozen_real_predictive_density')
    def score(draws,window,label,tick):
        try:
            result=evaluator.evaluate_observation(draws,label,rho=.95,nu=5,orders=(64,128),chunk=512,deadline=time.monotonic()+spec['bounds']['score_call_seconds'])
            return dict(result,status='ok')
        except evaluator.IntegrationDisagreement as error:
            return dict(status='unavailable',error=type(error).__name__,reason=str(error),numerical=error.diagnostics)
    def context(tick,current,label):
        value=inputs(y,tick)
        return {key:value[key] for key in ['origin_ms','label_available_ms']}
    return run_lane(y,updates=updates,seeds=spec['seeds']['candidate'],score_ticks=range(1,updates+1),retain_ticks=range(1,updates+1),
        engine_factory=lambda history,seeds:adapter.DrawResident(owalnuts,target,history,seeds),score_hook=score,output=root/'candidate',metadata_hook=context)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['candidate','baselines','reference','report']);parser.add_argument('--index',type=int,default=0);parser.add_argument('--manifest',required=True);parser.add_argument('--root',type=Path,required=True);args=parser.parse_args()
    spec=admit(args.manifest);root=args.root.resolve();root.mkdir(parents=True,exist_ok=True);jobs=root/'jobs';jobs.mkdir(exist_ok=True)
    record=jobs/f'{args.phase}-{args.index:02d}.json'
    if record.exists() or record.with_suffix('.start.json').exists():raise FileExistsError('No job retry')
    manifest_hash=sha(args.manifest)
    started=time.monotonic();state=dict(phase=args.phase,index=args.index,status='running',pid=os.getpid(),started_unix=time.time(),manifest_sha256=manifest_hash)
    exclusive(record.with_suffix('.start.json'),state)
    try:
        if args.phase!='report':y=load_sealed(spec['acquisition']['directory'],spec['acquisition'])
        if args.phase=='candidate':result=candidate(spec,y,root)
        elif args.phase=='baselines':
            from run_baselines import run
            result=run(y,root/'baselines',deadline=started+spec['bounds']['baselines_seconds'])
        elif args.phase=='reference':
            from run_reference import run
            result=run(spec,y,root,args.index)
        else:
            from ledger import build,validate_artifacts,references
            from report import summarize
            ledger=build(root);exclusive(root/'ledger.json',ledger)
            summary=summarize(ledger);summary['artifact_integrity']=validate_artifacts(root);summary['references']=references(root)
            summary['phase_records']={path.name:__import__('json').loads(path.read_bytes()) for path in jobs.glob('*.json') if '.start.' not in path.name}
            if not summary['artifact_integrity']['integrity_ok']:raise ValueError('Artifact integrity failure')
            exclusive(root/'summary.json',summary);result=dict(status='complete')
        state.update(status=result['status'],result=result)
        admit(args.manifest)
        if sha(args.manifest)!=manifest_hash:raise ValueError('Manifest changed during job')
        state['postrun_bindings_held']=True
    except BaseException as error:state.update(status='failed',error=type(error).__name__,reason=str(error))
    finally:
        state.update(elapsed_seconds=time.monotonic()-started,ended_unix=time.time());exclusive(record,state)
    return 1 if state['status']=='failed' else 0

if __name__=='__main__':raise SystemExit(main())
