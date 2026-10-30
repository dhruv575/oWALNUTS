import hashlib,json
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;r=p/'local_recovery/curved_cold_calibration01';s=json.loads((r/'SUMMARY.json').read_text());assert s['passed']
for f,h in s['inputs'].items():assert hashlib.sha256(Path(f).read_bytes()).hexdigest()==h
variance=np.tile([1.,51.],12);rows=[];selected=[]
for rep in ['direct','latent']:
    for engine in ['wal','native']:
        for mode in ['ordinary','recycled']:
            candidates=[]
            for i,cfg in enumerate(s['configs'][engine]):
                arm=f'{engine}_{mode}_{i}';est=[];times=[];div=0
                for b in range(4):
                    f=r/f'{rep}-{b:02d}';data=json.loads((f/f'RAW-{arm}.json').read_text());ts=json.loads((f/'TIMINGS.json').read_text());times.append(np.mean([t['seconds'] for t in ts if t['arm']==arm]))
                    for c in data['chains']:
                        sm=c['summary'] if engine=='wal' else c['ordinary_summary' if mode=='ordinary' else 'conditional_summary'];assert sm['count']==2000;est.append(sm['mean'][24:48]);div+=c['retained_divergences']
                mse=float(np.mean(((np.array(est)-variance)/variance)**2));cost=float(np.mean(times));row=dict(representation=rep,engine=engine,mode=mode,index=i,config=cfg,divergences=div,eligible=div==0,mse=mse,mean_batch_seconds=cost,one_pass_calibration_seconds=float(sum(times)),objective=mse*cost);rows.append(row);candidates.append(row)
            choice=min(candidates,key=lambda c:(not c['eligible'],c['divergences'] if not c['eligible'] else 0,c['objective'],c['index']));selected.append(dict(choice,all_candidate_calibration_seconds=sum(c['one_pass_calibration_seconds'] for c in candidates),actual_three_pass_research_seconds=3*sum(c['one_pass_calibration_seconds'] for c in candidates)))
out=dict(passed=True,selection_frozen=True,candidates=rows,selected=selected,calibration_summary_sha256=hashlib.sha256((r/'SUMMARY.json').read_bytes()).hexdigest(),scope='Calibration choices only; any ineligible choice is diagnostic and cannot promote')
(p/'CURVED-COLD-SELECTION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(selected,indent=2))
