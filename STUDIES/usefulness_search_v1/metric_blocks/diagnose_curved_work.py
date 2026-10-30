"""Post-hoc mechanism diagnostic, not a replacement for frozen promotion gates."""
import json
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;r=p/'local_recovery/curved_cold_validation01';s=json.loads((r/'SUMMARY.json').read_text());assert s['passed'];var=np.tile([1.,51.],12);arms=[a for a in s['builds'] if a.startswith('direct_')];errors={a:[] for a in arms};calls={a:[] for a in arms}
for b in range(16):
    for a in arms:
        data=json.loads((r/f'batch-{b:02d}'/f'RAW-{a}.json').read_text())
        for c in data['chains']:
            sm=c['summary'] if '_wal_' in a else c['conditional_summary' if a.endswith('_recycled') else 'ordinary_summary'];errors[a].append(float(np.mean(((np.array(sm['mean'][24:48])-var)/var)**2)));calls[a].append(c['target_calls'])
errors={a:np.array(v) for a,v in errors.items()};calls={a:np.array(v) for a,v in calls.items()};idx=np.random.default_rng(942060001).integers(0,64,(10000,64));base='direct_wal_recycled';rows=[]
for a in arms:
    if a==base:continue
    ratio=float(errors[a].mean()*calls[a].mean()/(errors[base].mean()*calls[base].mean()));boot=errors[a][idx].mean(1)*calls[a][idx].mean(1)/(errors[base][idx].mean(1)*calls[base][idx].mean(1));rows.append(dict(control=a,mean_target_calls=float(calls[a].mean()),base_mean_target_calls=float(calls[base].mean()),target_call_ratio=float(calls[a].mean()/calls[base].mean()),mse_times_target_calls_ratio=ratio,paired_bootstrap_interval=np.quantile(boot,[.025,.975]).tolist()))
concentration={a:dict(largest_replicate_index=int(np.argmax(errors[a])),largest_replicate_error_share=float(errors[a].max()/errors[a].sum()),top_four_error_share=float(np.sort(errors[a])[-4:].sum()/errors[a].sum())) for a in arms}
out=dict(post_hoc=True,rows=rows,error_concentration=concentration,scope='Finite-run second-moment MSE times actual density/gradient-call counts, including warmup. Above one favors recycled WAL. Not measured runtime, an expensive-likelihood speed projection, or an application advantage. Calibration not amortized in this work diagnostic. Replicate concentration is descriptive and no outlier is removed.')
(p/'CURVED-COLD-WORK-DIAGNOSIS.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
