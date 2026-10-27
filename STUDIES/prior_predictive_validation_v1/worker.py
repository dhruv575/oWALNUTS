"""Single bounded campaign job. No execution without final authorized manifest."""
import argparse,hashlib,importlib.util,importlib.metadata,json,sys,time
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
    import nutpie
    stream,tick=SENTINELS[index];directory=root/f'sentinel-{index:02d}';directory.mkdir(exist_ok=True);path=directory/'reference.json'
    if path.exists():raise FileExistsError(path)
    result=dict(index=index,stream=stream,tick=tick,status='running');atomic(path,result)
    try:
        data=load_data(root/f'stream-{stream:02d}');values=tick_inputs(data,tick)
        config=spec['reference'];stan=Path(config['stan_path'])
        if digest(stan)!=config['stan_sha256']:raise ValueError('Stan target source mismatch')
        compiled=nutpie.compile_stan_model(code=stan.read_text())
        draws,metadata=fit(nutpie,compiled,values['window'],302710000+index*1000,config)
        raw=directory/'draws.npy';np.save(raw,draws,allow_pickle=False);result.update(compact=dict(file=raw.name,sha256=digest(raw)),metadata=metadata)
        evaluator=Evaluator(spec['evaluator']['path'],spec['evaluator']['sha256'],config['evaluation_cap_seconds']);score=evaluator(draws,values['label'])
        arrays=dict(logpdf=score['logpdf_by_chain_draw'],pit=score['pit_by_chain_draw'],scaled_density=score['density_mcse']['scaled_density']);np.savez_compressed(directory/'score-arrays.npz',**arrays)
        result['score_arrays']=dict(file='score-arrays.npz',sha256=digest(directory/'score-arrays.npz'))
        def mean_mcse(a):return 0. if np.ptp(a)==0 else float(np.asarray(az.mcse(a,method='mean')).item())
        precision=log_density_mcse(arrays['logpdf'],mean_mcse);pit_mcse=mean_mcse(arrays['pit']);metrics={}
        variables={name:draws[:,:,i] for i,name in enumerate(['mu','log_sigma','beta','h_last'])};variables.update(pit=arrays['pit'],density=arrays['scaled_density'])
        for name,a in variables.items():metrics[name]=dict(rhat=float(np.asarray(az.rhat(a)).item()),bulk_ess=float(np.asarray(az.ess(a,method='bulk')).item()),tail_ess=float(np.asarray(az.ess(a,method='tail')).item()))
        good=all(np.isfinite(list(v.values())).all() and v['rhat']<=1.01 and v['bulk_ess']>=1000 and v['tail_ess']>=1000 for v in metrics.values()) and sum(metadata['divergences'])==0 and np.isfinite([pit_mcse,precision['delta_mcse']]).all() and pit_mcse<=.005 and precision['delta_mcse']<=.01
        result.update(status='complete',reference_diagnostics_pass=bool(good),diagnostics=metrics,precision=dict(logpdf_delta_mcse=precision['delta_mcse'],pit_mcse=pit_mcse),score={k:score[k] for k in ('cdf','logpdf','numerical')})
    except Exception as exc:result.update(status='failed',error=repr(exc))
    atomic(path,result);return dict(status=result['status'])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('kind',choices=['candidate','sides','reference','report']);parser.add_argument('--id',type=int,default=0);parser.add_argument('--manifest',required=True);parser.add_argument('--root',type=Path,required=True);a=parser.parse_args()
    spec=admit(a.manifest,a.kind);started=time.monotonic();root=a.root.resolve();record=root/'job-records'/f'{a.kind}-{a.id:02d}.json'
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
if __name__=='__main__':main()
