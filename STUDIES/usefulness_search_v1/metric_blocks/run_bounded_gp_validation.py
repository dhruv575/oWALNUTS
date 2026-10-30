import concurrent.futures,hashlib,json,sys,shutil
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'bounded_gp_validation01';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
cal=json.loads((l/'bounded_gp_calibration01/SUMMARY.json').read_text());assert cal['completed']
configs=[('raw','walnuts_dense',.9),('raw','low_rank',.99),('affine','walnuts_dense',.9),('affine','diag',.99),('bounded','walnuts_dense',.9),('bounded','low_rank',.99)]
for transform,mode,accept in configs[4:]:
    selected=next(x['selection'] for x in cal['selected'] if x['engine']==('walnuts' if mode.startswith('walnuts') else 'native'));assert selected['mode']==mode and selected['target_accept']==accept
hashes={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ['bounded_gp_validation_worker.py','run_bounded_gp_validation.py','BOUNDED-GP-VALIDATION-PROTOCOL.md']};rows=[];jobs=[(fold,rep,t,m,a) for fold in range(4) for rep in range(2) for t,m,a in (configs if rep==0 else list(reversed(configs)))]
def run(job):
    fold,rep,transform,mode,accept=job;seed=948700001+2*fold+rep;d=r/f'{fold}-{rep}-{transform}-{mode}';d.mkdir();assert shutil.disk_usage(r).free>2*1024**3
    command=[sys.executable,str(p/'bounded_gp_validation_worker.py'),str(d),mode,str(accept),str(seed),str(fold),transform];result=execute(command,str(p),300,d,2*1024**3,256*1024**2,d/'worker.log',output_scan_interval=2);(d/'SUPERVISION.json').write_text(json.dumps(result,indent=2)+'\n');complete=result['exit_code']==0 and result['group_drained'] and (d/'SUMMARY.json').exists();return json.loads((d/'SUMMARY.json').read_text()) if complete else dict(fold=fold,transform=transform,mode=mode,target_accept=accept,seed=seed,passed=False,completed=False,supervision=result)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    futures=[pool.submit(run,job) for job in jobs]
    for future in concurrent.futures.as_completed(futures):
        row=future.result();rows.append(row);(r/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(dict(completed=len(rows),fold=row['fold'],seed=row['seed'],transform=row['transform'],mode=row['mode'],passed=row['passed'])),flush=True)
assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items());qualified=len(rows)==48 and all(x['passed'] for x in rows);contrasts=[]
if qualified:
    pilot={x['fold']:x['pilot_gradient_calls'] for x in json.loads((l/'gp_transport_calibration01/COST-LEDGER.json').read_text())['pilots']};rng=np.random.default_rng(948800001);ix=rng.integers(0,4,(10000,4))
    def efficiency(fold,rep,transform,mode,inclusive):
        row=next(x for x in rows if x['fold']==fold and x['seed']==948700001+2*fold+rep and x['transform']==transform and x['mode']==mode);cost=row['calls']['gradient']+(pilot[fold] if inclusive and transform!='raw' else 0);return row['bulk']/cost
    for inclusive in [False,True]:
        for transform,mode,_ in configs:
            if transform=='bounded' and mode=='walnuts_dense':continue
            logs=np.asarray([[np.log(efficiency(fold,rep,'bounded','walnuts_dense',inclusive)/efficiency(fold,rep,transform,mode,inclusive)) for rep in range(2)] for fold in range(4)]);boot=np.exp(logs.mean(1)[ix].mean(1));contrasts.append(dict(pilot_inclusive=inclusive,comparator=transform+'-'+mode,ratio=float(np.exp(logs.mean())),interval=np.quantile(boot,[.025,.975]).tolist()))
passed=qualified and all(x['interval'][0]>1.2 for x in contrasts if x['pilot_inclusive']);(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,all_qualified=qualified,primary_passed=passed,contrasts=contrasts,rows=sorted(rows,key=lambda x:(x['fold'],x['seed'],x['transform'],x['mode'])),source_hashes=hashes),indent=2)+'\n');print(json.dumps(dict(all_qualified=qualified,primary_passed=passed,contrasts=contrasts)),flush=True)
