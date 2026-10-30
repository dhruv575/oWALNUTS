import hashlib,json
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parent;rows=[];inputs={}
for i in range(1,5):
    p=root/f'hybrid0{i}/SUMMARY.json';v=root/f'hybrid0{i}/VERIFICATION.json'
    assert json.loads(v.read_text())['passed'];s=json.loads(p.read_text());assert s['unchanged'];rows+=s['rows']
    inputs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();inputs[str(v)]=hashlib.sha256(v.read_bytes()).hexdigest()
assert len(rows)==480 and len({(r['model'],r['seed'],r['arm']) for r in rows})==480
rng=np.random.default_rng(929399999);models={};losses=[];signals=[];fisher_losses=[]
for model in sorted(set(r['model'] for r in rows)):
    rr=[r for r in rows if r['model']==model];hr=sorted([r for r in rr if r['arm']=='hybrid'],key=lambda r:r['seed'])
    assert [r['seed'] for r in hr]==list(range(929300001,929300017))
    entry=dict(passes={a:sum(r['passed'] for r in rr if r['arm']==a) for a in ['hybrid','v4','fisher','dense','auto']},comparisons={},branches={})
    for h in hr:
        branch=(h.get('selection') or {}).get('branch','failed');entry['branches'][branch]=entry['branches'].get(branch,0)+1
    for arm in ['v4','fisher','dense','auto']:
        pairs=[]
        for h in hr:
            c=next(r for r in rr if r['seed']==h['seed'] and r['arm']==arm)
            pair=dict(seed=h['seed'],hybrid_passed=h['passed'],control_passed=c['passed'],qualified=h['passed'] and c['passed'])
            if arm in ['v4','auto'] and c['passed'] and not h['passed']:losses.append(dict(model=model,seed=h['seed'],control=arm))
            if pair['qualified']:pair['ratio']=h['efficiency']/c['efficiency']
            pairs.append(pair)
        e=dict(pairs=pairs)
        if all(p['qualified'] for p in pairs):
            log=np.log([p['ratio'] for p in pairs]);boots=np.exp(log[rng.integers(0,16,(10000,16))].mean(1))
            e.update(geomean=float(np.exp(log.mean())),ci95=np.quantile(boots,[.025,.975]).tolist(),worst=float(np.exp(log.min())))
            if arm=='fisher' and e['geomean']<.9:fisher_losses.append(model)
        entry['comparisons'][arm]=e
    signal=model in ['arma-arma11','garch-garch11','gp_pois_regr-gp_pois_regr','eight_schools-eight_schools_centered'] and all(entry['comparisons'][a].get('geomean',0)>=1.2 and entry['comparisons'][a].get('ci95',[0])[0]>1 for a in ['auto','v4'])
    entry['non_gaussian_signal']=signal
    if signal:signals.append(model)
    models[model]=entry
result=dict(continuation_gate=not losses and bool(signals) and not fisher_losses,models=models,accuracy_losses=losses,signals=signals,fisher_efficiency_losses=fisher_losses,inputs=inputs,limitations='Exploratory per-target intervals, six-target family, no application or novelty claim.')
(root/'HYBRID-COMPARISON.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['models','inputs']}))
