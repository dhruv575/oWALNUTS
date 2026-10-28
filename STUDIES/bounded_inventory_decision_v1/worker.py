"""Fixed exposed-artifact bounded-decision shards; no sampler or acquisition."""
import argparse,hashlib,importlib.metadata,io,json,os,sys,time
from pathlib import Path
import numpy as np
from inputs import Archive,module,origins,references
from bounded_loss import evaluate,baseline,score,precision,COST,ABS_TOL,TAIL_BOUND
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def exclusive(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def admit(path,expected_status='frozen_authorized'):
    spec=json.loads(Path(path).read_bytes());draft=json.loads(Path(__file__).with_name('COMPUTE-DRAFT.json').read_bytes())
    if expected_status not in ('frozen_authorized','development_authorized') or spec.get('status')!=expected_status:raise ValueError('Bounded decision experiment not authorized')
    for key in ('months','shards','bounds','bootstrap_seeds','decision_cost','absolute_tolerance','omitted_tail_bound'):
        if spec[key]!=draft[key]:raise ValueError('Frozen setting changed: '+key)
    if (spec['decision_cost'],spec['absolute_tolerance'],spec['omitted_tail_bound'])!=(COST,ABS_TOL,TAIL_BOUND):raise ValueError('Numerical constants changed')
    if sys.prefix!=spec['runtime']['prefix']:raise ValueError('Runtime prefix drift')
    for name,want in spec['runtime']['packages'].items():
        if importlib.metadata.version(name)!=want:raise ValueError('Runtime package drift')
    for name,want in {**spec['sources'],**spec['runtime']['binaries']}.items():
        if sha(name)!=want:raise ValueError('Source/runtime drift: '+name)
    return spec
def startup(spec):
    start=time.perf_counter();backend=module(spec['dependencies']['numerical_backend'],'bound_inventory_backend');backend.Backend('exact_t5').cdf(5,np.array([[0.]]))
    import arviz
    return backend,time.perf_counter()-start
def failure(error):return dict(status='unavailable',error=type(error).__name__,reason=str(error))
def save_array(path,a):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:np.save(f,a,allow_pickle=False);f.flush();os.fsync(f.fileno())
    return dict(file=str(path),sha256=sha(path),shape=list(a.shape))
def candidate_row(archive,spec,backend,root,m,t):
    y=archive.label(m,t);row=dict(month=m,tick=t,label=y,arms={});spots={(a,c) for a,b,c in references()}
    for arm in ('candidate','rolling_t5','ewma_t5'):
        start=time.perf_counter();deadline=start+spec['bounds']['origin_seconds']
        try:
            result=evaluate(archive.candidate(m,t),backend,deadline) if arm=='candidate' else baseline(archive.baseline(m,t,arm),backend.Backend('exact_t5'),deadline)
            if arm=='candidate':
                values=result.pop('per_chain_draw_downside')
                if (m,t)in spots:
                    p=Path(root)/'functional'/m/f'{t:06d}.npy';record=save_array(p,values);record['file']=p.relative_to(root).as_posix();result['functional']=record
            result['score']=score(result['mean_downside'],y);row['arms'][arm]=result
        except Exception as error:row['arms'][arm]=failure(error)
        row['arms'][arm]['postprocess_seconds']=time.perf_counter()-start
    return row
def reference_row(archive,spec,backend,root,m,i,t):
    start=time.perf_counter();row=dict(month=m,index=i,tick=t,status='unavailable')
    try:
        draws,original=archive.reference(m,i,t);value=evaluate(draws,backend,start+spec['bounds']['reference_origin_seconds']);values=value.pop('per_chain_draw_downside');p=Path(root)/'reference-functional'/m/f'{t:06d}.npy';record=save_array(p,values);record['file']=p.relative_to(root).as_posix();value['functional']=record
        row.update(status='ok',reference=value,original_reference_diagnostics_pass=original['reference_diagnostics_pass'])
        try:row['reference_precision']=precision(values)
        except Exception as error:row['reference_precision']=failure(error)
        source=Path(root)/'rows'/m/f'{t:06d}.json'
        if source.exists():
            raw=source.read_bytes();row['candidate_row_sha256']=hashlib.sha256(raw).hexdigest();candidate=json.loads(raw)['arms']['candidate']
            if candidate['status']=='ok':
                row['candidate_minus_reference']=candidate['mean_downside']-value['mean_downside']
                try:
                    record=candidate['functional'];raw=(Path(root)/record['file']).read_bytes()
                    if hashlib.sha256(raw).hexdigest()!=record['sha256']:raise ValueError('Candidate functional identity changed')
                    a=np.load(io.BytesIO(raw),allow_pickle=False)
                    if a.shape!=(4,400):raise ValueError('Candidate functional shape')
                    row['candidate_precision']=precision(a)
                except Exception as error:row['candidate_precision']=failure(error)
            else:row['candidate_precision']=dict(status='unavailable',reason='Candidate integral unavailable')
        else:row['candidate_precision']=dict(status='unavailable',reason='Candidate row missing')
    except Exception as error:row.update(failure(error))
    row['postprocess_seconds']=time.perf_counter()-start;return row
def run_shard(spec,phase,shard,root):
    if type(shard)is not int or not 0<=shard<12:raise ValueError('Fixed shard required')
    root=Path(root);started=time.monotonic();job=root/'jobs'/f'{phase}-{shard:02d}';exclusive(job.with_suffix('.start.json'),dict(phase=phase,shard=shard,pid=os.getpid()))
    os.environ.setdefault('NUMBA_CACHE_DIR',str(root/'cache'/f'{phase}-{shard:02d}'));state=dict(phase=phase,shard=shard,status='failed',completed=0,output_hashes={});archive=None
    try:
        archive=Archive(spec);backend,state['startup_seconds']=startup(spec);queue=(origins() if phase=='candidate' else references())[shard::12];state['planned']=len(queue)
        for item in queue:
            m=item[0];t=item[-1];exclusive(root/'started'/phase/m/f'{t:06d}.json',dict(month=m,tick=t,shard=shard))
            row=candidate_row(archive,spec,backend,root,m,t) if phase=='candidate' else reference_row(archive,spec,backend,root,m,item[1],t)
            path=root/('rows' if phase=='candidate' else 'references')/m/f'{t:06d}.json';exclusive(path,row);state['output_hashes'][path.relative_to(root).as_posix()]=sha(path);state['completed']+=1
        state['status']='complete'
    except BaseException as error:state.update(status='failed',error=repr(error))
    if archive is not None:
        try:state['input_integrity']=archive.verify_used()
        except Exception as error:state.update(status='failed',integrity_error=repr(error),input_integrity=dict(hashes=archive.used))
    state['elapsed_seconds']=time.monotonic()-started;exclusive(job.with_suffix('.json'),state);return state
def terminal_accounting(spec,root,jobs):
    from report import terminal_accounting as finish
    return finish(spec,root,jobs)
def batch_summary(spec,root):
    from report import batch_summary as finish
    return finish(spec,root)
def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['candidate','reference','report']);p.add_argument('--shard',type=int);p.add_argument('--month');p.add_argument('--manifest',required=True);p.add_argument('--root',required=True);a=p.parse_args();spec=admit(a.manifest);before=sha(a.manifest)
    if a.phase=='report':
        from report import run
        result=run(spec,a.root,a.month)
    else:result=run_shard(spec,a.phase,a.shard,a.root)
    admit(a.manifest)
    if sha(a.manifest)!=before:raise ValueError('Manifest drift')
    return 0 if result['status']=='complete' else 1
if __name__=='__main__':raise SystemExit(main())
