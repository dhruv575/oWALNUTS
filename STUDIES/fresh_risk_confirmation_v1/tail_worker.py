"""Persistent deterministic stored-draw arithmetic shards; never samples."""
import argparse,hashlib,importlib.metadata,json,os,sys,time
from pathlib import Path
from tail_inputs import Archive,module,origins,references,MONTHS
from tail_evaluator import tails,baseline,score,precision
from tail_report import terminal_accounting,batch_summary

def startup(spec,reference=False):
    """Cold JIT/import overhead is a worker cost, never a first-origin failure."""
    import numpy as np
    start=time.perf_counter();backend=module(spec['dependencies']['numerical_backend'],'bound_tail_backend')
    backend.Backend('exact_t5').cdf(5,np.array([[0.]]));density=None
    if reference:
        import arviz
        density=module(spec['dependencies']['predictive_density'],'bound_tail_density')
        literal=np.tile(np.array([-10.,np.log(.12),0.,-10.]),(4,4,1))
        density.evaluate_observation(literal,0.,deadline=time.monotonic()+60)
    return backend,density,time.perf_counter()-start

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def exclusive(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())

def admit(path,expected_status='frozen_authorized'):
    spec=json.loads(Path(path).read_bytes())
    if spec.get('status')!=expected_status or expected_status not in ['frozen_authorized','development_authorized']:raise ValueError('Tail study not authorized')
    draft=json.loads(Path(__file__).with_name('COMPUTE-DRAFT.json').read_bytes())
    for key in ['months','probabilities','shards','bounds','bootstrap_seeds']:
        if spec[key]!=draft[key]:raise ValueError('Fixed setting changed: '+key)
    if sys.prefix!=spec['runtime']['prefix']:raise ValueError('Runtime prefix drift')
    for k,v in spec['runtime']['packages'].items():
        if importlib.metadata.version(k)!=v:raise ValueError('Package drift: '+k)
    for file,want in {**spec['sources'],**spec['runtime']['binaries']}.items():
        if sha(file)!=want:raise ValueError('Source/runtime drift: '+file)
    return spec

def failure(error):
    value=dict(status='unavailable',error=type(error).__name__,reason=str(error))
    if hasattr(error,'diagnostics'):value['numerical']=error.diagnostics
    return value

def candidate_row(archive,spec,backend,month,tick):
    row=dict(month=month,tick=tick,arms={});y=archive.label(month,tick);row['label']=y
    for arm in ['candidate','rolling_t5','ewma_t5']:
        start=time.perf_counter()
        try:
            q=tails(archive.candidate(month,tick),backend,start+spec['bounds']['origin_seconds']) if arm=='candidate' else baseline(archive.baseline(month,tick,arm))
            q['risk']=score(q,y);row['arms'][arm]=q
        except Exception as error:row['arms'][arm]=failure(error)
        row['arms'][arm]['postprocess_seconds']=time.perf_counter()-start
    return row

def reference_row(archive,spec,backend,density,root,month,index,tick):
    start=time.perf_counter();deadline=start+spec['bounds']['reference_origin_seconds'];row=dict(month=month,index=index,tick=tick,status='unavailable')
    try:
        draws,original=archive.reference(month,index,tick);row['original_reference_diagnostics_pass']=original['reference_diagnostics_pass'];q=tails(draws,backend,deadline);row.update(status='ok',reference=q)
        try:row['reference_precision']=precision(draws,q,density,deadline)
        except Exception as error:row['reference_precision']=failure(error)
        path=Path(root)/'rows'/month/f'{tick:06d}.json'
        if not path.exists():row['candidate_precision']=dict(status='unavailable',reason='Candidate row missing')
        else:
            raw=path.read_bytes();row['candidate_row_sha256']=hashlib.sha256(raw).hexdigest();candidate=json.loads(raw)['arms']['candidate']
            if candidate['status']=='ok':
                row['differences']={key:candidate[key]-q[key] for key in ['q05','q95','width']}
                try:row['candidate_precision']=precision(archive.candidate(month,tick),candidate,density,deadline)
                except Exception as error:row['candidate_precision']=failure(error)
            else:row['candidate_precision']=dict(status='unavailable',reason='Candidate numerical result unavailable')
    except Exception as error:row.update(failure(error))
    row['postprocess_seconds']=time.perf_counter()-start;return row

def run_shard(spec,phase,shard,root):
    if type(shard)is not int or not 0<=shard<12:raise ValueError('Fixed shard required')
    root=Path(root);start=time.monotonic();job=root/'jobs'/f'{phase}-{shard:02d}';exclusive(job.with_suffix('.start.json'),dict(phase=phase,shard=shard,pid=os.getpid(),started_unix=time.time()))
    os.environ.setdefault('NUMBA_CACHE_DIR',str(root/'cache'/f'{phase}-{shard:02d}'))
    archive=Archive(spec);backend,density,startup_seconds=startup(spec,phase=='reference')
    queue=[x for i,x in enumerate(origins() if phase=='candidate' else references()) if i%12==shard];state=dict(phase=phase,shard=shard,status='running',planned=len(queue),completed=0,output_hashes={},startup_seconds=startup_seconds)
    try:
        for item in queue:
            month=item[0];tick=item[-1];marker=root/'started'/phase/month/f'{tick:06d}.json';exclusive(marker,dict(month=month,tick=tick,shard=shard))
            value=candidate_row(archive,spec,backend,month,tick) if phase=='candidate' else reference_row(archive,spec,backend,density,root,month,item[1],tick)
            destination=root/('rows' if phase=='candidate' else 'references')/month/f'{tick:06d}.json';exclusive(destination,value);state['completed']+=1;state['output_hashes'][destination.relative_to(root).as_posix()]=sha(destination)
        state['input_integrity']=archive.verify_used();state['status']='complete'
    except BaseException as error:state.update(status='failed',error=repr(error))
    try:state['input_integrity']=archive.verify_used()
    except Exception as error:state.update(status='failed',integrity_error=repr(error),input_integrity=dict(hashes=archive.used))
    state['elapsed_seconds']=time.monotonic()-start;exclusive(job.with_suffix('.json'),state);return state

def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['candidate','reference','report']);parser.add_argument('--shard',type=int);parser.add_argument('--month');parser.add_argument('--manifest',required=True);parser.add_argument('--root',required=True);args=parser.parse_args();spec=admit(args.manifest);before=sha(args.manifest)
    if args.phase=='report':
        from tail_report import run
        result=run(spec,args.root,args.month)
    else:result=run_shard(spec,args.phase,args.shard,args.root)
    admit(args.manifest)
    if sha(args.manifest)!=before:raise ValueError('Manifest drift')
    return 0 if result['status']=='complete' else 1

if __name__=='__main__':raise SystemExit(main())
