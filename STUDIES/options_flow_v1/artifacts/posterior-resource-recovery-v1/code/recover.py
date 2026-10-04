"""Explicit posthoc existing-draw recovery. No fitting or sampler invocation."""
import argparse,gc,hashlib,json,sys,time,zipfile
from pathlib import Path
START=time.perf_counter();CPU=time.process_time()

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def save(path,value):
    from run import clean
    with Path(path).open('x') as f:json.dump(clean(value),f,indent=2,allow_nan=False)

def verify_archive(spec):
    root=Path(spec['archived_study_directory']).resolve()
    plan=json.loads(Path(spec['original_plan']).read_text())
    bound={str(Path(p).resolve()).casefold():h for p,h in plan['bindings'].items()}
    rows=spec['source_manifest']
    with zipfile.ZipFile(spec['source_archive']) as archive:
        members={n for n in archive.namelist() if n.endswith('.py')}
        if set(rows)!=members:raise ValueError('Archive Python inventory differs')
        expected=set()
        for name,row in rows.items():
            path=Path(row['extracted']).resolve()
            if not path.is_relative_to(root):raise ValueError('Extracted source escapes archived study')
            expected.add(path)
            digest=hashlib.sha256(archive.read(name)).hexdigest()
            if digest!=row['sha256'] or sha(path)!=digest or bound.get(str(Path(row['original']).resolve()).casefold())!=digest:raise ValueError('Archive/extracted/original source mismatch')
        if set(root.rglob('*.py'))!=expected:raise ValueError('Unexpected extracted source inventory')

def verify(spec):
    for path,digest in spec['immutable_inputs'].items():
        if sha(path)!=digest:raise ValueError('Immutable original/archive/source changed: '+path)
    verify_archive(spec)

def recover(spec_path):
    spec=json.loads(Path(spec_path).read_text());out=Path(spec['out']);out.mkdir(exist_ok=False)
    sys.path.insert(0,spec['archived_study_directory'])
    from reference_bank_allocation import memory_limit,peak_memory
    from hardware_control import get_affinity
    result=dict(cell_id=spec['cell_id'],status='failed',posthoc=True,resampled=False,original_statuses_preserved=True,qualified=False)
    phase='admission';phase_tick=time.perf_counter();guard=None
    try:
        if spec['memory_bytes']!=8*1024**3 or spec['timeout_seconds']!=1800:raise ValueError('Fixed recovery resource policy required')
        if Path(spec_path).with_suffix('.sha256').read_text().strip()!=sha(spec_path):raise ValueError('Frozen recovery spec differs')
        guard=memory_limit(spec['memory_bytes'])
        verify(spec)
        if get_affinity()!=[0]:raise ValueError('Recovery requires contained CPU0')
        if spec['original_terminal_archived'] is not True:raise ValueError('Original terminal/archive required')
        import numpy as np
        from adapter import validate_report
        plan=json.loads(Path(spec['original_plan']).read_text());cell=next(c for c in plan['cells'] if c['id']==spec['cell_id'])
        fixture=json.loads(Path(cell['fixture']).read_text());report=json.loads(Path(spec['report']).read_text());raw=Path(spec['raw'])
        required=[spec['original_plan'],spec['report'],spec['raw'],cell['fixture'],spec['original_status'],spec['source_archive']]
        if any(str(Path(p).resolve()) not in spec['immutable_inputs'] for p in required):raise ValueError('Missing exact original input/archive binding')
        if spec['posterior_sha256']!=plan['posterior_sha256']:raise ValueError('Wrong posterior')
        result.update(cell_id=cell['id'],backend=cell['backend'],original_status=json.loads(Path(spec['original_status']).read_text()),posterior_sha256=plan['posterior_sha256'],original_raw_sha256=spec['immutable_inputs'][str(raw.resolve())])
        validate_report(report,cell,fixture,plan,raw)
        gc.collect();from posterior_resource.stream_extract import extract
        phase='extraction';phase_tick=time.perf_counter()
        extraction=extract(raw,out/'extracted',chains=4,draws=8000,dimension=1012,rho=fixture['data']['rho'],x_next=fixture['holdout']['x'][0][0])
        flags=extraction.pop('divergence_arrays');result['extraction']=extraction
        extraction['canonical_sha256']=sha(out/'extracted'/'canonical.npy');extraction['compact_sha256']=sha(out/'extracted'/'compact.npz')
        q=np.load(out/'extracted'/'canonical.npy',mmap_mode='r');compact=np.load(out/'extracted'/'compact.npz')
        from evaluate import summarize
        from precision_tiers import precision_screen
        from predictive_cdf import PredictiveMixture
        names=['beta_bar','tau','mu_h','sigma_h','h_terminal','h_mean']+[p+str(g) for g in range(4) for p in ['alpha_','beta_']]
        result['checkpoints']=[]
        for n in [4000,8000]:
            phase=f'diagnostics-{n}';phase_tick=time.perf_counter();ct=phase_tick;evaluation=summarize(q[:,:n],fixture,cell['seed']+130000)
            if cell['backend']=='public':
                if len(flags)!=4 or any(len(v)!=8000 for v in flags):raise ValueError('Public raw divergence shape differs')
                divergences=sum(sum(v[:n]) for v in flags)
            else:
                matches=[c for c in report['checkpoints'] if c['draws_per_chain']==n]
                if len(matches)!=1:raise ValueError('Reference prefix telemetry missing')
                divergences=matches[0]['retained_divergences_total']
            fit_report=dict(status='completed',draws=n,evaluation=evaluation,retained_divergences=divergences,healthy=evaluation['computational_screen_pass'] and divergences==0)
            if set(evaluation['canonical_parameter_diagnostics'])!={f'q_{i}' for i in range(1012)} or evaluation['chain_count']!=4:raise ValueError('Full canonical/chain diagnostic scope differs')
            ds=[*evaluation['functionals'].values(),*evaluation['canonical_parameter_diagnostics'].values()]
            finite_healthy=all(np.isfinite([d['rhat'],d['bulk_ess'],d['tail_ess']]).all() and 0<d['rhat']<=1.01 and min(d['bulk_ess'],d['tail_ess'])>=400 for d in ds)
            fit_report['healthy']=bool(finite_healthy and divergences==0)
            if set(evaluation['functionals'])!=set(names) or len(evaluation['forecast']['rows'])!=4:raise ValueError('Full scope mismatch')
            screen=precision_screen(fit_report,.02,names=names,require_forecast=True)
            save(out/f'checkpoint-{n}.json',dict(fit_report,screen=screen));diagnostic_seconds=time.perf_counter()-ct
            phase=f'predictive-cdf-{n}';phase_tick=time.perf_counter();pt=phase_tick;count=4*n
            mix=PredictiveMixture('flow',compact['cdf_location'][:,:n].reshape(-1),compact['cdf_future_mean'][:,:n].reshape(-1),compact['cdf_future_sd'][:,:n].reshape(-1),np.zeros(count),np.full(count,1/count),fixture['data']['nu'],2048,dict(group=0,x_next=fixture['holdout']['x'][0][0],horizon=1))
            quantiles=mix.quantiles();save(out/f'predictive-cdf-{n}.json',quantiles)
            result['checkpoints'].append(dict(draws=n,full_gate_pass=screen['pass'],diagnostic_seconds=diagnostic_seconds,predictive_cdf_seconds=time.perf_counter()-pt,predictive_cdf=quantiles,checkpoint_sha256=sha(out/f'checkpoint-{n}.json'),predictive_cdf_sha256=sha(out/f'predictive-cdf-{n}.json')))
        result.update(status='posthoc_analysis_completed',accuracy_qualified=False,reference_bank_resolved=False)
        verify(spec)
    except Exception as exc:result['error']=f'{type(exc).__name__}: {exc}'
    finally:
        result.update(last_phase=phase,last_phase_elapsed_seconds=time.perf_counter()-phase_tick,additional_worker_seconds_before_final_report=time.perf_counter()-START,additional_process_cpu_seconds=time.process_time()-CPU,resources=peak_memory(),memory_cap_bytes=spec['memory_bytes'])
        save(out/'recovery-result.json',result)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--spec',required=True);a=p.parse_args();r=recover(a.spec);raise SystemExit(0 if r['status']=='posthoc_analysis_completed' else 2)
