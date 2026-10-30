import json
from pathlib import Path
import numpy as np
import arviz as az
from predictive import features
ROOT=Path(__file__).resolve().parent;final=json.loads((ROOT/'run01/FINAL.json').read_text());assert final['dependencies_unchanged'];assert len(final['jobs'])==6
rows=[];summaries={}
for folder in sorted((ROOT/'run01').glob('*/result')):
 r=json.loads((folder/'RESULT.json').read_text());q=np.load(folder/'draws.npz')['q'];f=features(q);assert f.shape==(4,4000,68) and np.isfinite(f).all()
 idata=az.from_dict(posterior={'f':f});s=az.summary(idata,round_to='none');s.to_json(folder/'DIAGNOSTICS.json',orient='split',indent=2);summaries[r['seed']]=s
 diagnostics=dict(rhat_max=float(s.r_hat.max()),ess_bulk_min=float(s.ess_bulk.min()),ess_tail_min=float(s.ess_tail.min()))
 passed=diagnostics['rhat_max']<=1.01 and diagnostics['ess_bulk_min']>=400 and diagnostics['ess_tail_min']>=200 and r['divergences_by_phase'][1]==0 and r['depth_hits_by_phase'][1]==0 and r['errors_by_phase'][1]==0
 rows.append(dict(engine=r['engine'],seed=r['seed'],seconds=r['seconds'],calls_errors=r['calls_errors'],divergences_by_phase=r['divergences_by_phase'],primary_fraction=r['primary_fraction'],mode_mass_unresolved=True,passed=bool(passed),**diagnostics))
s1=summaries[935100001];s2=summaries[935100002];z=np.abs(s1['mean']-s2['mean'])/np.sqrt(s1.mcse_mean**2+s2.mcse_mean**2);refs=[r for r in rows if r['engine']=='pymc_jump'];qualified=all(r['passed'] for r in refs) and np.isfinite(z).all() and z.max()<=4.5
out=dict(rows=rows,independent_reference_mean_z=z.tolist(),maximum_reference_mean_z=float(z.max()),practical_reference_qualified=bool(qualified),unvisited_mode_mass_unbounded=True,application_value_unproven=True)
(ROOT/'REFERENCE-AUDIT.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
