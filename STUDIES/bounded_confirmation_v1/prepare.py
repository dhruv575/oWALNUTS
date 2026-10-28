"""Freeze all causal fixtures and baseline slots before candidate sampling."""
import concurrent.futures,hashlib,json,sys,time,traceback
from pathlib import Path
import numpy as np
import data_contract
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'predictive_value_diagnostic_v1'))
import baselines

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def baseline_task(task):
    i,month,tick,window,history,initial,label=task;rows=[]
    methods={'rolling_t5':lambda:baselines.fit_t5(window,deadline=time.monotonic()+60),'ewma_t5':lambda:baselines.ewma_t5(history,initial),'nig_ar1':lambda:dict(status='ok',**baselines.nig_ar1(history))}
    for name,fn in methods.items():
        try:
            fit=fn();score=baselines.score_distribution(fit['location'],fit['scale'],fit['df'],label) if fit['status']=='ok' else None
            rows.append(dict(index=i,month=month,tick=tick,method=name,fit=fit,score=score))
        except Exception as e:rows.append(dict(index=i,month=month,tick=tick,method=name,fit=dict(status='failed',error=repr(e),traceback=traceback.format_exc()),score=None))
    return rows

def run(bindings_path,output):
    bindings=json.loads(Path(bindings_path).read_text());out=Path(output);out.mkdir(exist_ok=False)
    rows=[];labels=[];tasks=[];start=time.monotonic()
    for month in ['2025-09','2025-10']:
        spec=data_contract.configure(month);y=data_contract.load_sealed(bindings,month)
        np.savez_compressed(out/f'returns-{month}.npz',y=y)
        try:initial=baselines.fit_t5(y[:250],deadline=time.monotonic()+60)
        except Exception as e:initial=dict(status='failed',error=repr(e))
        (out/f'initial-{month}.json').write_text(json.dumps(initial,indent=2,allow_nan=False)+'\n')
        for tick in range(1,spec['origins']+1):
            i=len(rows);item=data_contract.inputs(y,tick);history=y[:250+tick].copy();window=item['window']
            assert np.array_equal(history[-250:],window) and item['label_index']==len(history)
            p=out/f'case-{i:04d}.npz';np.savez_compressed(p,window=window,history=history)
            rows.append(dict(index=i,month=month,tick=tick,fixture=p.name,sha256=sha(p),history_count=len(history),current_index=item['current_index'],label_index=item['label_index'],origin_ms=item['origin_ms'],label_available_ms=item['label_available_ms']))
            labels.append(dict(index=i,label=item['label']))
            tasks.append((i,month,tick,window,history,initial,item['label']))
    assert len(rows)==2928
    scores=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        for batch in pool.map(baseline_task,tasks,chunksize=1):
            scores.extend(batch)
            with (out/'BASELINE-PROGRESS.jsonl').open('a') as f:f.write(json.dumps(batch,allow_nan=False)+'\n')
    assert len(scores)==8784
    for name,value in [('FIXTURES.json',rows),('LABELS.json',labels),('BASELINES.json',scores)]:
        (out/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    sources={str(p.resolve()):sha(p) for p in [Path(__file__),Path(data_contract.__file__),Path(baselines.__file__)]}
    report=dict(status='complete',origins=2928,baseline_slots=8784,unavailable_baselines=sum(r['score'] is None for r in scores),bindings_sha256=sha(bindings_path),sources=sources,elapsed_seconds=time.monotonic()-start,files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in out.iterdir() if p.is_file()})
    (out/'PREPARATION.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['status','origins','baseline_slots','unavailable_baselines','elapsed_seconds']}))

if __name__=='__main__':run(*sys.argv[1:])
