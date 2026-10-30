import hashlib,json
from pathlib import Path
import numpy as np
study=Path(__file__).resolve().parent;root=study/'local_recovery';rows=[];inputs={};frozen=None;jobs=0;stages=0
for i in range(1,9):
    p=root/f'localscaled{i:02d}/SUMMARY.json';v=p.parent/'VERIFICATION.json'
    verification=json.loads(v.read_text());assert verification['passed']
    archive=json.loads((root/f'localscaled{i:02d}_archive/VERIFICATION.json').read_text());assert archive['passed']
    s=json.loads(p.read_text());assert s['unchanged'];rows+=s['rows'];jobs+=verification['jobs'];stages+=verification['matched_stages']
    fingerprint={Path(k).name:value for k,value in s['inputs'].items()};assert len(fingerprint)==len(s['inputs'])
    if frozen is None:frozen=fingerprint
    else:assert fingerprint==frozen,'Source/target changed'
    for file in [p,v]:inputs[str(file)]=hashlib.sha256(file.read_bytes()).hexdigest()
assert len(rows)==576 and len({(r['model'],r['seed'],r['arm']) for r in rows})==576
rng=np.random.default_rng(929599999);models={};losses=[];signals=[];fisher_losses=[]
arms=['scaled','hybrid','v4','fisher','dense','auto']
for model in sorted(set(r['model'] for r in rows)):
    rr=[r for r in rows if r['model']==model];hr=sorted([r for r in rr if r['arm']=='scaled'],key=lambda r:r['seed'])
    assert [r['seed'] for r in hr]==list(range(929600001,929600017))
    entry=dict(passes={a:sum(r['passed'] for r in rr if r['arm']==a) for a in arms},comparisons={},branches={})
    for h in hr:
        branch=(h.get('selection') or {}).get('branch','failed');entry['branches'][branch]=entry['branches'].get(branch,0)+1
    for arm in arms[1:]:
        pairs=[]
        for h in hr:
            c=next(r for r in rr if r['seed']==h['seed'] and r['arm']==arm)
            pair=dict(seed=h['seed'],scaled_passed=h['passed'],control_passed=c['passed'],qualified=h['passed'] and c['passed'])
            if arm in ['hybrid','v4','auto'] and c['passed'] and not h['passed']:losses.append(dict(model=model,seed=h['seed'],control=arm))
            if pair['qualified']:pair.update(ratio=h['efficiency']/c['efficiency'],operational_time_ratio=c['seconds']/h['seconds'],operational_ess_rate_ratio=(h['bulk']/h['seconds'])/(c['bulk']/c['seconds']))
            pairs.append(pair)
        e=dict(pairs=pairs)
        if all(p['qualified'] for p in pairs):
            log=np.log([p['ratio'] for p in pairs]);indices=rng.integers(0,16,(10000,16));boots=np.exp(log[indices].mean(1))
            timing=np.log([p['operational_time_ratio'] for p in pairs]);tb=np.exp(timing[indices].mean(1))
            rate=np.log([p['operational_ess_rate_ratio'] for p in pairs]);rb=np.exp(rate[indices].mean(1))
            e.update(geomean=float(np.exp(log.mean())),ci95=np.quantile(boots,[.025,.975]).tolist(),worst=float(np.exp(log.min())),operational_time_geomean=float(np.exp(timing.mean())),operational_time_ci95=np.quantile(tb,[.025,.975]).tolist(),operational_ess_rate_geomean=float(np.exp(rate.mean())),operational_ess_rate_ci95=np.quantile(rb,[.025,.975]).tolist())
            if arm=='fisher' and e['geomean']<.9:fisher_losses.append(model)
        entry['comparisons'][arm]=e
    signal=model in ['arma-arma11','garch-garch11','gp_pois_regr-gp_pois_regr','eight_schools-eight_schools_centered'] and all(entry['comparisons'][a].get('geomean',0)>=1.2 and entry['comparisons'][a].get('ci95',[0])[0]>1 for a in ['auto','v4'])
    entry['non_gaussian_signal']=signal
    if signal:signals.append(model)
    models[model]=entry
result=dict(continuation_gate=not losses and bool(signals) and not fisher_losses,models=models,accuracy_losses=losses,signals=signals,fisher_efficiency_losses=fisher_losses,inputs=inputs,source_and_target_hashes_identical=True,total_jobs=jobs,total_matched_stages=stages,analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),limitations='Local WSL only; exploratory per-target intervals; no application or novelty claim. Operational times include supervised invocations and shared pilot, exclude common diagnostics/controller IO.')
(study/'LOCAL-SCALED-COMPARISON.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['models','inputs']}))
