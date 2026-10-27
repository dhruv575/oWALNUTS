"""Eight fixed independent posterior audits; never replace candidate forecasts."""
import io,json,os,tempfile,time
from pathlib import Path
import numpy as np
from data_contract import inputs
from linear_runner_snapshot import exclusive
from worker import module,sha

TICKS=[1,213,426,638,851,1063,1276,1488]

def mean_mcse(values):
    import arviz as az
    return 0. if np.ptp(values)==0 else float(np.asarray(az.mcse(values,method='mean')).item())

def precision(logs,pits):
    if logs.ndim!=2 or pits.shape!=logs.shape or not np.isfinite(logs).all() or not np.isfinite(pits).all() or np.any((pits<0)|(pits>1)):raise ValueError('Invalid precision arrays')
    scaled=np.exp(logs-logs.max());lp=mean_mcse(scaled)/float(scaled.mean());pit=mean_mcse(pits)
    if not np.isfinite([lp,pit]).all() or min(lp,pit)<0:raise ValueError('Unavailable precision estimates')
    return dict(status='available',logpdf_delta_mcse=lp,pit_mcse=pit)

def run(spec,y,root,index):
    if type(index)is not int or not 0<=index<8:raise ValueError('Fixed reference index required')
    if spec['reference_ticks']!=TICKS:raise ValueError('Reference schedule changed')
    root=Path(root);tick=TICKS[index];out=root/'references'/f'{index:02d}';out.mkdir(parents=True,exist_ok=False)
    value=inputs(y,tick);result=dict(index=index,tick=tick,status='running',origin_ms=value['origin_ms'],label_available_ms=value['label_available_ms'])
    try:
        import arviz as az
        import nutpie,bridgestan
        config=spec['reference'];workspace=out/'compiler-workspace';workspace.mkdir()
        os.environ['TMPDIR']=str(workspace.resolve());tempfile.tempdir=str(workspace.resolve())
        os.environ['BRIDGESTAN']=config['sdk_path']
        if sha(Path(config['sdk_path'])/'Makefile')!=config['sdk_makefile_sha256']:raise ValueError('SDK Makefile mismatch')
        capture=module(spec['dependencies']['compiler_capture'],'frozen_real_compiler_capture')
        adapter=module(spec['dependencies']['independent_adapter'],'frozen_real_independent_adapter')
        stan=Path(config['stan_path'])
        if sha(stan)!=config['stan_sha256']:raise ValueError('Stan target changed')
        captures=[]
        with capture.capture_compiler(bridgestan,out/'captured-libraries',captures):
            compiled=nutpie.compile_stan_model(code=stan.read_text(encoding='utf-8-sig'),cleanup=False)
        if not captures:raise ValueError('Compiler provenance missing')
        result['compiler_captures']=captures
        exclusive(out/'compile-checkpoint.json',dict(result,phase='compiled'))
        draws,metadata=adapter.fit(nutpie,compiled,value['window'],spec['seeds']['references'][index],config)
        raw=out/'draws.npy'
        with raw.open('xb') as handle:np.save(handle,draws,allow_pickle=False)
        result.update(compact=dict(file=raw.name,sha256=sha(raw)),metadata=metadata)
        exclusive(out/'draws-checkpoint.json',dict(result,phase='draws_saved'))
        evaluator=module(spec['dependencies']['predictive_density'],'frozen_real_reference_density')
        score=evaluator.evaluate_observation(draws,value['label'],rho=.95,nu=5,orders=(64,128),chunk=512,deadline=time.monotonic()+30)
        logs=score['logpdf_by_chain_draw'];pits=score['pit_by_chain_draw'];scaled=score['density_mcse']['scaled_density']
        arrays_path=out/'score-arrays.npz'
        with arrays_path.open('xb') as handle:np.savez_compressed(handle,logpdf=logs,pit=pits,scaled_density=scaled)
        result.update(score_arrays=dict(file=arrays_path.name,sha256=sha(arrays_path)))
        exclusive(out/'score-checkpoint.json',dict(result,phase='score_arrays_saved'))
        result['precision']=precision(logs,pits)
        metrics={};variables={name:draws[:,:,i] for i,name in enumerate(['mu','log_sigma','beta','h_last'])};variables.update(pit=pits,density=scaled)
        for name,a in variables.items():metrics[name]=dict(rhat=float(np.asarray(az.rhat(a)).item()),bulk_ess=float(np.asarray(az.ess(a,method='bulk')).item()),tail_ess=float(np.asarray(az.ess(a,method='tail')).item()))
        passed=all(np.isfinite(list(v.values())).all() and v['rhat']<=1.01 and v['bulk_ess']>=1000 and v['tail_ess']>=1000 for v in metrics.values()) and sum(metadata['divergences'])==0 and result['precision']['pit_mcse']<=.005 and result['precision']['logpdf_delta_mcse']<=.01
        result.update(status='complete',reference_diagnostics_pass=bool(passed),diagnostics=metrics,score={key:score[key] for key in ['logpdf','pit','numerical']})
        result['candidate_precision']=None;result['candidate_minus_reference']=None
        try:
            candidate_path=root/'candidate/records'/f'{tick:06d}.json'
            if candidate_path.exists():
                candidate=json.loads(candidate_path.read_bytes())
                if candidate['score_status']=='ok':
                    source=root/'candidate'/candidate['arrays']['file'];raw_arrays=source.read_bytes()
                    if __import__('hashlib').sha256(raw_arrays).hexdigest()!=candidate['arrays']['sha256']:
                        result['candidate_integrity_error']='Candidate arrays changed';raise ValueError(result['candidate_integrity_error'])
                    with np.load(io.BytesIO(raw_arrays),allow_pickle=False) as saved:
                        c_log=saved['score__logpdf_by_chain_draw'];c_pit=saved['score__pit_by_chain_draw']
                        if c_log.shape!=(4,400):raise ValueError('Candidate precision shape mismatch')
                        result['candidate_precision']=precision(c_log,c_pit)
                    if passed:result['candidate_minus_reference']=dict(logpdf=candidate['score']['logpdf']-score['logpdf'],pit=candidate['score']['pit']-score['pit'])
        except Exception as error:result['candidate_precision']=dict(status='unavailable',reason=repr(error))
    except Exception as error:
        result.update(status='failed',error=type(error).__name__,reason=str(error))
        if hasattr(error,'diagnostics'):result['numerical_failure']=error.diagnostics
    exclusive(out/'reference.json',result);return result
