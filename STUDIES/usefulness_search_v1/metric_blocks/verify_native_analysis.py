"""Independent scalar replay of aggregate qualification, ratios and screen gate."""
import hashlib,json,math,statistics
from pathlib import Path

root=Path(__file__).resolve().parent
report=json.loads((root/'NATIVE-SCREEN-ANALYSIS.json').read_text())
rows=[]
for i in range(1,5):
    rows+=json.loads((root/'local_recovery'/f'nativescreen{i:02d}'/'SUMMARY.json').read_text())['rows']
for p,h in report['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
def qualifies(r):
    bounds={'rhat':(None,1.01),'bulk':(400,None),'tail':(400,None),'divergences':(0,0),'max_z':(None,4.5),'max_mean_sd':(None,.1),'max_sd_error':(None,.1)}
    for k,(lo,hi) in bounds.items():
        v=r.get(k)
        if v is None or not math.isfinite(v) or (lo is not None and v<lo) or (hi is not None and v>hi):return False
    return True
assert len(rows)==168
lookup={(r['model'],r['arm'],r['seed']):r for r in rows};assert len(lookup)==168
losses=[];signals=[];ratio_count=0
for m in report['models']:
    name=m['model'];group=[r for r in rows if r['model']==name]
    seeds=sorted({r['seed'] for r in group});assert seeds==list(range(940600001,940600005))
    for arm,total in m['passes'].items():
        subset=[r for r in group if r['arm']==arm];assert len(subset)==4
        assert sum(qualifies(r) for r in subset)==total
    for s in seeds:
        if qualifies(lookup[name,'walnuts_auto',s]) and not qualifies(lookup[name,'scaled_fast',s]):losses.append(dict(model=name,seed=s))
    native=[a for a,n in m['passes'].items() if a.startswith('native_') and n==4]
    assert native==m['fully_qualified_native']
    control_gains={}
    for arm,comparison in m['fast_scaled_vs'].items():
        good=all(qualifies(lookup[name,a,s]) for a in ['scaled_fast',arm] for s in seeds)
        assert (comparison is not None)==good
        if not good:continue
        gains=[]
        for key,cost in [('efficiency','calls'),('time_efficiency','seconds')]:
            ratios=[]
            for s in seeds:
                a,b=lookup[name,'scaled_fast',s],lookup[name,arm,s]
                ratios.append((a['bulk']/a[cost])/(b['bulk']/b[cost]))
            estimate=math.exp(statistics.mean(math.log(v) for v in ratios))
            assert math.isclose(estimate,comparison[key]['geometric_mean'],rel_tol=1e-12)
            assert all(math.isclose(a,b,rel_tol=1e-12) for a,b in zip(ratios,comparison[key]['paired_ratios']))
            gains.append(estimate);ratio_count+=1
        control_gains[arm]=all(g>=1.2 for g in gains)
    signals.append(bool(name not in ['arK-arK','sblrc-blr'] and native and all(control_gains.get(a,False) for a in ['walnuts_auto']+native)))
assert losses==report['paired_accuracy_losses']
for m,signal in zip(report['models'],signals):assert m['promising_efficiency_signal']==(signal and not losses)
assert report['promising_efficiency_signal']==(any(signals) and not losses)
out=dict(passed=True,rows=len(rows),replayed_ratio_estimates=ratio_count,scope='Independent scalar qualification, point estimates and gate; bootstrap intervals are not independently replayed.',analysis_sha256=hashlib.sha256((root/'NATIVE-SCREEN-ANALYSIS.json').read_bytes()).hexdigest())
(root/'NATIVE-SCREEN-REPLAY.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
