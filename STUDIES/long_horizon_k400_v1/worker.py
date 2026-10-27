"""One frozen data/lane/reference/report subprocess. No retries or adaptive scope."""
import argparse,json,os,subprocess,tempfile,time
from pathlib import Path
import numpy as np
from runtime import admit,module,sha,save_array,load_data,evaluator
from linear_runner import run_lane,exclusive,packed
from data_model import generate,canonical_targets
from checkpoint import checkpoint,reference_reliability

def data_job(spec,root):
    p=root/'data';p.mkdir(exist_ok=False)
    try:
        d=generate(spec['protocol']['seeds']['data']);arrays={k:save_array(p/(k+'.npy'),d[k]) for k in ('control_y','shift_y','control_h','shift_h')}
        exclusive(p/'DATA.json',dict(seed=d['seed'],parameters=d['parameters'],first_shifted_index=d['first_shifted_index'],arrays=arrays));return dict(status='complete')
    except Exception as exc:
        exclusive(p/'GENERATION-FAILURE.json',dict(status='failed',error=repr(exc),payload=getattr(exc,'payload',None)));raise

def lane_job(spec,root,index):
    variant=('control','shift')[index//2];rep=index%2;y=load_data(root,variant);deps=spec['dependencies'];backend=module(deps['resident_adapter'],'bound_resident_adapter');target=module(deps['sv_target'],'bound_sv_target');score=evaluator(spec)
    import owalnuts
    p=spec['protocol'];seeds=dict(initial=p['seeds']['initial'][rep],warm=p['seeds']['warm'][rep]);out=root/'lanes'/f'{variant}-r{rep}'
    r=run_lane(y,updates=2000,seeds=seeds,score_ticks=p['checkpoints'],retain_ticks=p['checkpoints'],engine_factory=lambda window,s:backend.DrawResident(owalnuts,target,window,s),score_hook=lambda a,w,label,t:checkpoint(a,w,label,t,score),output=out,metadata_hook=lambda t,c,l:dict(variant=variant,replicate=rep))
    return dict(status=r['status'],native_completed=r['native_completed'],score_counts=r['score_counts'])

def reference_job(spec,root,index):
    p=spec['protocol'];variant,tick=canonical_targets(p['checkpoints'])[index];out=root/'references'/f'{index:02d}';out.mkdir(parents=True,exist_ok=False);result=dict(status='running',index=index,variant=variant,tick=tick,contexts={});exclusive(out/'START.json',result)
    try:
        y=load_data(root,variant);window=y[tick:250+tick];tmp=out/'compiler-workspace';tmp.mkdir();os.environ['TMPDIR']=str(tmp.resolve());tempfile.tempdir=str(tmp.resolve());os.environ['BRIDGESTAN']=spec['reference']['sdk']
        import nutpie,bridgestan
        deps=spec['dependencies'];capture=module(deps['compiler_capture'],'bound_compiler_capture');adapter=module(deps['sentinel_adapter'],'bound_sentinel_adapter');captures=[]
        with capture.capture_compiler(bridgestan,out/'captured-libraries',captures):compiled=nutpie.compile_stan_model(code=Path(deps['stan']).read_text(encoding='utf-8-sig'),cleanup=False)
        if not captures:raise ValueError('Missing compiled-library identity')
        exclusive(out/'COMPILED.json',dict(compiler_captures=captures,stan_sha256=sha(deps['stan']),variant=variant,tick=tick))
        seed=p['seeds']['reference_base']+p['seeds']['reference_stride']*index
        draws,metadata=adapter.fit(nutpie,compiled,window,seed,dict(api_and_target_verified=True,engine_options=spec['reference']['engine_options']))
        result.update(draws=save_array(out/'draws.npy',draws),metadata=metadata,compiler_captures=captures,sample_seed=seed,model_seed=seed+1)
        exclusive(out/'DRAWS.json',dict(draws=result['draws'],metadata=metadata,compiler_captures=captures,sample_seed=seed,model_seed=seed+1,variant=variant,tick=tick))
        score=evaluator(spec);arrays={}
        for context in (('control','shift') if tick<=1000 else (variant,)):
            observed=load_data(root,context);current=observed[tick:250+tick]
            if not np.array_equal(current,window):raise ValueError('Invalid shared posterior target')
            # No cache: each actual query/label is evaluated separately, including shifted label at tick1000.
            scored=checkpoint(draws,current,float(observed[250+tick]),tick,score);reliability=reference_reliability(draws,scored,metadata['divergences'])
            result['contexts'][context]=dict(score=packed(scored,context,arrays,True),reliability=reliability)
        with (out/'score-arrays.npz').open('xb') as f:np.savez_compressed(f,**arrays);f.flush();os.fsync(f.fileno())
        result.update(status='complete',score_arrays=dict(file='score-arrays.npz',sha256=sha(out/'score-arrays.npz')))
    except Exception as exc:result.update(status='failed',error=repr(exc),numerical_failure=getattr(exc,'diagnostics',None))
    exclusive(out/'RESULT.json',result);return dict(status=result['status'])

def main():
    p=argparse.ArgumentParser();p.add_argument('kind',choices=['data','lane','reference','analysis']);p.add_argument('--index',type=int,default=0);p.add_argument('--manifest',required=True);p.add_argument('--root',required=True);a=p.parse_args();spec=admit(a.manifest);root=Path(a.root);started=time.monotonic();record=dict(kind=a.kind,index=a.index,status='running');records=root/'job-records';records.mkdir(exist_ok=True)
    exclusive(records/f'{a.kind}-{a.index:02d}-START.json',record)
    try:
        if a.kind=='data':value=data_job(spec,root)
        elif a.kind=='lane':value=lane_job(spec,root,a.index)
        elif a.kind=='reference':value=reference_job(spec,root,a.index)
        else:
            from analyze import analyze
            value=analyze(root,spec['protocol'])
        record.update(value);admit(a.manifest);record['postrun_bindings_match']=True
    except Exception as exc:record.update(status='failed',error=repr(exc))
    record['elapsed_seconds']=time.monotonic()-started;exclusive(records/f'{a.kind}-{a.index:02d}.json',record)
    return 1 if record['status']=='failed' else 0
if __name__=='__main__':raise SystemExit(main())
