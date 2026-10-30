import json
from pathlib import Path
import numpy as np
study=Path(__file__).resolve().parent;root=study/'local_recovery/recycling_mse_timing01';assert json.loads((root/'SUMMARY.json').read_text())['passed']
mse=json.loads((study/'RECYCLING-MSE-ANALYSIS.json').read_text());rng=np.random.Generator(np.random.PCG64(941330101));idx=rng.integers(0,16,size=(10000,16));rows=[]
lines=['# Direct timing audit of recycling MSE screen','','| Target | Direct observed/original cost (95% CI) | Family | MSE/cost ratio | Descriptive conservative range |','|---|---|---|---|---|']
for t in mse['targets']:
    records=json.loads((root/t['target']/'TIMINGS.json').read_text());assert len(records)==96
    times=np.zeros((2,3,16))
    for r in records:times[int(r['arm']=='observed'),r['repeat'],r['batch']]=r['seconds']
    assert (times>0).all();means=times.mean(axis=1);cost=float(means[1].sum()/means[0].sum());boot=means[1,idx].sum(axis=1)/means[0,idx].sum(axis=1);ci=np.quantile(boot,[.025,.975]).tolist();families=[]
    for f in t['families']:
        interval=[f['ci95'][0]/ci[1],f['ci95'][1]/ci[0]]
        row=dict(family=f['family'],mse_ratio=f['ratio'],direct_cost_adjusted=f['ratio']/cost,descriptive_range=interval,statistical_lead=f['ci95'][0]>1.2 and not f['bias_flag'],cost_supported_lead=f['ci95'][0]>1.2 and interval[0]>1 and not f['bias_flag']);families.append(row)
        lines.append(f"| {t['target']} | {cost:.3f} [{ci[0]:.3f}, {ci[1]:.3f}] | {f['family']} | {row['direct_cost_adjusted']:.3f} | [{interval[0]:.3f}, {interval[1]:.3f}] |")
    rows.append(dict(target=t['target'],direct_cost_ratio=cost,ci95=ci,repetition_ratios=(times[1].sum(axis=1)/times[0].sum(axis=1)).tolist(),total_seconds=times.sum(axis=(1,2)).tolist(),families=families))
lines+=['','The range combines separate MSE and cost interval endpoints; it is not a calibrated joint 95% interval. All replay outputs match the original canonical records. Earlier supervisor-based advance flags are retained as historical output and are not a practical-efficiency conclusion.']
(study/'RECYCLING-MSE-TIMING-ANALYSIS.json').write_text(json.dumps(dict(rows=rows),indent=2)+'\n');(study/'RECYCLING-MSE-TIMING-REPORT.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
