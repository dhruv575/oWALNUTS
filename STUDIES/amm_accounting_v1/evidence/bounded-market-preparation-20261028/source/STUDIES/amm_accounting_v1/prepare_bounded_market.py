"""Verify sealed development data and freeze causal fixtures plus baseline scores."""
import hashlib,json,sys,time
from pathlib import Path
import numpy as np

root=Path(__file__).resolve().parent
sys.path.insert(0,str(root.parent/'predictive_value_diagnostic_v1'))
import baselines

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def run(parent_path,output):
    parent_path=Path(parent_path);parent=json.loads(parent_path.read_text())
    contract_root=Path(parent['worker_path']).parent
    sources={}
    for name in ['data_contract.py','acquire.py']:
        p=contract_root/name;digest=sha(p)
        if parent['sources'].get(str(p))!=digest:raise ValueError('Inherited contract binding: '+str(p))
        sources[str(p)]=digest
    sources[str(Path(baselines.__file__).resolve())]=sha(baselines.__file__)
    sources[str(Path(__file__).resolve())]=sha(__file__)
    sources[str(root/'BOUNDED-MARKET-DESIGN.md')]=sha(root/'BOUNDED-MARKET-DESIGN.md')
    sys.path.insert(0,str(contract_root));import data_contract
    out=Path(output);out.mkdir(exist_ok=False);rows=[];labels=[];scores=[];start=time.monotonic()
    for month in ['2025-12','2026-01','2026-02']:
        spec=data_contract.configure(month);y=data_contract.load_sealed(parent['acquisition'],month)
        np.savez_compressed(out/f'returns-{month}.npz',y=y)
        initial=baselines.fit_t5(y[:250],deadline=time.monotonic()+60)
        for tick in spec['reference_ticks']:
            i=len(rows);item=data_contract.inputs(y,int(tick));history=y[:250+tick].copy();window=item['window']
            assert np.array_equal(history[-250:],window) and item['label_index']==len(history)
            assert item['current_index']==len(history)-1 and item['label_available_ms']>item['origin_ms']
            fixture=out/f'case-{i:02d}.npz';np.savez_compressed(fixture,window=window,history=history)
            rows.append(dict(index=i,month=month,tick=int(tick),fixture=fixture.name,sha256=sha(fixture),history_count=len(history),current_index=item['current_index'],label_index=item['label_index'],origin_ms=item['origin_ms'],label_available_ms=item['label_available_ms'],unique_window_returns=int(len(np.unique(window))),zero_returns=int((window==0).sum())))
            labels.append(dict(index=i,label=item['label']))
            methods=dict(rolling_t5=baselines.fit_t5(window,deadline=time.monotonic()+60),ewma_t5=baselines.ewma_t5(history,initial),nig_ar1=dict(status='ok',**baselines.nig_ar1(history)))
            for name,fit in methods.items():
                score=baselines.score_distribution(fit['location'],fit['scale'],fit['df'],item['label']) if fit['status']=='ok' else None
                scores.append(dict(index=i,month=month,tick=int(tick),method=name,fit=fit,score=score))
        (out/f'initial-{month}.json').write_text(json.dumps(initial,indent=2,allow_nan=False)+'\n')
    assert len(rows)==24 and len(scores)==72
    for name,values in [('FIXTURES.json',rows),('LABELS.json',labels),('BASELINES.json',scores)]:
        (out/name).write_text(json.dumps(values,indent=2,allow_nan=False)+'\n')
    report=dict(status='complete',origins=24,baseline_slots=72,unavailable_baselines=sum(r['score'] is None for r in scores),sources=sources,parent_sha256=sha(parent_path),acquisition=parent['acquisition'],elapsed_seconds=time.monotonic()-start,files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in out.iterdir() if p.is_file()},scope='Previously examined development data; no candidate sampling or holdout claim')
    (out/'PREPARATION.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['status','origins','baseline_slots','unavailable_baselines','elapsed_seconds','scope']}))

if __name__=='__main__':run(sys.argv[1],sys.argv[2])
