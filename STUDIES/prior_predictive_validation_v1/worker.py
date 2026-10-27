"""Single bounded campaign job. No execution without final authorized manifest."""
import argparse,hashlib,importlib.util,importlib.metadata,json,sys,time,os,tempfile,subprocess
from pathlib import Path
import numpy as np
from evidence import atomic,digest,save_data,load_data,preserve_candidate
from generator import generate,tick_inputs
from stream_driver import run_stream
from evaluator_adapter import Evaluator
from baseline import score as baseline_score
from ledger import build_ledger,sentinel_ledger
from report import summarize

def admit(path,kind):
    spec=json.loads(Path(path).read_text())
    if spec.get('status')!='frozen_authorized':raise ValueError('Draft cannot execute')
    if sys.prefix!=spec['runtimes'][kind]['prefix']:raise ValueError('Unexpected interpreter prefix')
    for name,version in spec['runtimes'][kind]['packages'].items():
        if importlib.metadata.version(name)!=version:raise ValueError('Package drift '+name)
    for name,want in spec['runtimes'][kind].get('binaries',{}).items():
        if digest(name)!=want:raise ValueError('Runtime binary drift '+name)
    for name,want in spec['sources'].items():
        if digest(name)!=want:raise ValueError('Frozen source mismatch '+name)
    return spec

def load_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def candidate(spec,root,stream):
    directory=root/f'stream-{stream:02d}'
    try:data=generate(stream);save_data(directory,data)
    except Exception as exc:
        atomic(directory/'generation-failure.json',dict(status='failed',error=repr(exc),payload=getattr(exc,'payload',None)));raise
    evaluator=Evaluator(spec['evaluator']['path'],spec['evaluator']['sha256'],spec['evaluator']['call_cap_seconds'])
    from resident_adapter import DrawResident
    import owalnuts
    target=load_module(spec['target_path'],'frozen_synthetic_target')
    result=run_stream(data,lambda y,seeds:DrawResident(owalnuts,target,y,seeds),evaluator,None,lambda r,a:preserve_candidate(directory,r,a))
    return dict(status=result['status'],valid_ticks=result['valid_ticks'])

def sides(spec,root,stream):
    directory=root/f'stream-{stream:02d}';data=load_data(directory);path=directory/'side.json'
    if path.exists():raise FileExistsError(path)
    evaluator=Evaluator(spec['evaluator']['path'],spec['evaluator']['sha256'],spec['side_oracle_call_cap_seconds'])
    result=dict(stream=stream,planned_ticks=32,status='running',rows=[],in_progress=None);atomic(path,result)
    for tick in range(1,33):
        values=tick_inputs(data,tick);row=dict(tick=tick);result['rows'].append(row)
        for arm in ['baseline','oracle']:
            result['in_progress']=dict(tick=tick,arm=arm);atomic(path,result);started=time.monotonic()
            try:
                value=baseline_score(values['window'],values['label']) if arm=='baseline' else evaluator.oracle(data['parameters'],values['current_latent'],values['label'])
                from ledger import valid_score
                if not valid_score(value):raise ValueError('Invalid side score')
                row[arm]={k:v for k,v in value.items() if k in ('cdf','logpdf','numerical','df','scale','location','training_pairs')};row[arm+'_status']='ok'
            except Exception as exc:
                row[arm+'_status']='unavailable';row[arm+'_error']=repr(exc)
                if hasattr(exc,'diagnostics'):row[arm+'_numerical_failure']=exc.diagnostics
            row[arm+'_seconds']=time.monotonic()-started;result['in_progress']=None;atomic(path,result)
    result['status']='complete' if all(r[a+'_status']=='ok' for r in result['rows'] for a in ['baseline','oracle']) else 'partial';atomic(path,result)
    return dict(status=result['status'])

def reference(spec,root,index):
    from sentinel_adapter import SENTINELS,fit,log_density_mcse
    import arviz as az
    stream,tick=SENTINELS[index];directory=root/f'sentinel-{index:02d}';directory.mkdir(exist_ok=True);path=directory/'reference.json'
    if path.exists():raise FileExistsError(path)
    result=dict(index=index,stream=stream,tick=tick,status='running');atomic(path,result)
    try:
        data=load_data(root/f'stream-{stream:02d}');values=tick_inputs(data,tick)
        config=spec['reference'];stan=Path(config['stan_path'])
        workspace=directory/'compiler-workspace';workspace.mkdir(exist_ok=False)
        os.environ['TMPDIR']=str(workspace.resolve());tempfile.tempdir=str(workspace.resolve())
        sdk=Path(config['bridgestan_sdk'])
        if digest(sdk/'Makefile')!=config['sdk_makefile_sha256']:raise ValueError('BridgeStan SDK binding changed')
        os.environ['BRIDGESTAN']=str(sdk.resolve())
        import nutpie,bridgestan
        capture=load_module(config['capture_path'],'frozen_compiler_capture')
        if digest(stan)!=config['stan_sha256']:raise ValueError('Stan target source mismatch')
        captures=[]
        with capture.capture_compiler(bridgestan,directory/'captured-libraries',captures):
            compiled=nutpie.compile_stan_model(code=stan.read_text(encoding='utf-8-sig'),cleanup=False)
        if not captures:raise ValueError('Compiled library provenance missing')
        result['compiler_captures']=captures;atomic(path,result)
        draws,metadata=fit(nutpie,compiled,values['window'],302710000+index*1000,config)
        raw=directory/'draws.npy';np.save(raw,draws,allow_pickle=False);result.update(compact=dict(file=raw.name,sha256=digest(raw)),metadata=metadata)
        evaluator=Evaluator(spec['evaluator']['path'],spec['evaluator']['sha256'],config['evaluation_cap_seconds']);score=evaluator(draws,values['label'])
        arrays=dict(logpdf=score['logpdf_by_chain_draw'],pit=score['pit_by_chain_draw'],scaled_density=score['density_mcse']['scaled_density']);np.savez_compressed(directory/'score-arrays.npz',**arrays)
        result['score_arrays']=dict(file='score-arrays.npz',sha256=digest(directory/'score-arrays.npz'))
        def mean_mcse(a):return 0. if np.ptp(a)==0 else float(np.asarray(az.mcse(a,method='mean')).item())
        precision=log_density_mcse(arrays['logpdf'],mean_mcse);pit_mcse=mean_mcse(arrays['pit']);metrics={}
        # Descriptive candidate uncertainty at the same eight fixed sentinels; never a gate.
        try:
            candidate_path=root/f'stream-{stream:02d}'/'candidate.json';result['candidate_precision']=None
            if candidate_path.exists():
                candidate_result=json.loads(candidate_path.read_text());candidate_row=next((r for r in candidate_result['rows'] if r['tick']==tick and r.get('candidate_status')=='ok'),None)
                if candidate_row is not None:
                    entry=candidate_row['score_arrays'];array_path=candidate_path.parent/entry['file'];raw_arrays=array_path.read_bytes()
                    if hashlib.sha256(raw_arrays).hexdigest()!=entry['sha256']:
                        result['candidate_integrity_error']='Candidate score arrays changed'
                        raise ValueError(result['candidate_integrity_error'])
                    import io
                    with np.load(io.BytesIO(raw_arrays),allow_pickle=False) as saved:
                        c_log=saved['row__forecast__logpdf_by_chain_draw'];c_pit=saved['row__forecast__pit_by_chain_draw']
                        result['candidate_precision']=dict(logpdf_delta_mcse=log_density_mcse(c_log,mean_mcse)['delta_mcse'],pit_mcse=mean_mcse(c_pit),source_sha256=entry['sha256'],scope='descriptive; no qualification gate')
    
        except Exception as exc:result['candidate_precision']=dict(status='unavailable',reason=repr(exc))
        variables={name:draws[:,:,i] for i,name in enumerate(['mu','log_sigma','beta','h_last'])};variables.update(pit=arrays['pit'],density=arrays['scaled_density'])
        for name,a in variables.items():metrics[name]=dict(rhat=float(np.asarray(az.rhat(a)).item()),bulk_ess=float(np.asarray(az.ess(a,method='bulk')).item()),tail_ess=float(np.asarray(az.ess(a,method='tail')).item()))
        good=all(np.isfinite(list(v.values())).all() and v['rhat']<=1.01 and v['bulk_ess']>=1000 and v['tail_ess']>=1000 for v in metrics.values()) and sum(metadata['divergences'])==0 and np.isfinite([pit_mcse,precision['delta_mcse']]).all() and pit_mcse<=.005 and precision['delta_mcse']<=.01
        result.update(status='complete',reference_diagnostics_pass=bool(good),diagnostics=metrics,precision=dict(logpdf_delta_mcse=precision['delta_mcse'],pit_mcse=pit_mcse),score={k:score[k] for k in ('cdf','logpdf','numerical')})
    except Exception as exc:result.update(status='failed',error=repr(exc))
    atomic(path,result);return dict(status=result['status'])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('kind',choices=['candidate','sides','reference','report']);parser.add_argument('--id',type=int,default=0);parser.add_argument('--manifest',required=True);parser.add_argument('--root',type=Path,required=True);a=parser.parse_args()
    spec=admit(a.manifest,a.kind);spec['_manifest_path']=str(Path(a.manifest).resolve());started=time.monotonic();root=a.root.resolve();record=root/'job-records'/f'{a.kind}-{a.id:02d}.json'
    if record.exists():raise FileExistsError('No job retries')
    result=dict(kind=a.kind,id=a.id,status='running',started_unix=time.time());atomic(record,result)
    try:
        if a.kind=='candidate':out=candidate(spec,root,a.id)
        elif a.kind=='sides':out=sides(spec,root,a.id)
        elif a.kind=='reference':out=reference(spec,root,a.id)
        else:
            ledger=build_ledger(root);atomic(root/'ledger.json',ledger)
            out=summarize(ledger,sentinel_ledger(root));atomic(root/'summary.json',out);out=dict(status='complete')
        result.update(out)
        admit(a.manifest,a.kind);result['postrun_sources_match']=True
    except Exception as exc:result.update(status='failed',error=repr(exc))
    finally:result['elapsed_seconds']=time.monotonic()-started;atomic(record,result)
    return 1 if result.get('status')=='failed' else 0
if __name__=='__main__':sys.exit(main())
