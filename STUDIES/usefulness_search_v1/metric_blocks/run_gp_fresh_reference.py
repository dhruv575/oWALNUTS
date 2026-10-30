import concurrent.futures,hashlib,json,shutil,sys
from pathlib import Path
import numpy as np,arviz as az
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_fresh_reference01';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'))
from resource_monitor import execute
hashes={str(p/n):hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ['gp_fresh_reference_worker.py','run_gp_fresh_reference.py','GP-FRESH-REFERENCE-PROTOCOL.md']}
def run(job):
    scenario,rep=job;d=r/f'{scenario}-{rep}';d.mkdir();assert shutil.disk_usage(r).free>2*1024**3
    supervised=execute([sys.executable,str(p/'gp_fresh_reference_worker.py'),str(d),str(scenario),str(rep)],str(p),300,d,2*1024**3,256*1024**2,d/'worker.log',output_scan_interval=2);(d/'SUPERVISION.json').write_text(json.dumps(supervised,indent=2)+'\n')
    complete=supervised['exit_code']==0 and supervised['group_drained'] and (d/'SUMMARY.json').exists()
    return json.loads((d/'SUMMARY.json').read_text()) if complete else dict(scenario=scenario,rep=rep,passed=False,completed=False,supervision=supervised)
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    futures=[pool.submit(run,(s,rep)) for s in range(4) for rep in range(2)]
    for future in concurrent.futures.as_completed(futures):
        row=future.result();rows.append(row);(r/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps({k:row[k] for k in ['scenario','rep','passed']}),flush=True)
references=[]
for scenario in range(4):
    pair=sorted([x for x in rows if x['scenario']==scenario],key=lambda x:x['rep']);assert len(pair)==2
    if not all(x['passed'] for x in pair):references.append(dict(scenario=scenario,passed=False,reason='Individual group qualification failed'));continue
    a,b=[x['stats'] for x in pair];v=np.concatenate([np.load(r/f'{scenario}-{rep}/FUNCTIONALS.npz')['values'] for rep in range(2)])
    ds=az.convert_to_dataset({'p':v});stats={k:np.asarray(fn(ds).p) for k,fn in [('rhat',lambda d:az.rhat(d,method='rank')),('bulk',lambda d:az.ess(d,method='bulk')),('tail',lambda d:az.ess(d,method='tail')),('mcse',lambda d:az.mcse(d,method='mean'))]};stats.update(mean=v.mean((0,1)),sd=v.reshape(-1,24).std(0,ddof=1))
    delta=abs(np.asarray(a['mean'])-b['mean']);z=delta/np.sqrt(np.asarray(a['mcse'])**2+np.asarray(b['mcse'])**2);sd_difference=abs(np.asarray(a['sd'])-b['sd'])/((np.asarray(a['sd'])+b['sd'])/2)
    checks=dict(finite=all(np.isfinite(x).all() for x in stats.values()),rhat=max(stats['rhat'])<=1.01,bulk=min(stats['bulk'])>=4000,tail=min(stats['tail'])>=2000,relative_mcse=max(stats['mcse']/stats['sd'])<=.02,group_z=max(z)<=4,group_mean=max(delta/stats['sd'])<=.05,group_sd=max(sd_difference)<=.1)
    references.append(dict(scenario=scenario,passed=bool(all(checks.values())),checks={k:bool(v) for k,v in checks.items()},stats={k:v.tolist() for k,v in stats.items()},max_group_z=float(max(z))))
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in hashes.items())
(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,rows=rows,references=references,inputs=hashes),indent=2,allow_nan=False)+'\n');print(json.dumps([dict(scenario=x['scenario'],passed=x['passed']) for x in references]),flush=True)
