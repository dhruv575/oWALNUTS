import concurrent.futures,hashlib,json,sys,shutil
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_transport_calibration01';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
assert json.loads((l/'gp_transport_target01/SUMMARY.json').read_text())['passed'];assert json.loads((l/'gp_transport_smoke01/SUMMARY.json').read_text())['completed'];configs=[(m,a) for a in [.9,.99] for m in ['walnuts_diag','diag','walnuts_dense','low_rank']];jobs=[(fold,t,m,a) for fold in range(4) for t in ['affine','quadratic'] for m,a in (configs if fold%2==0 else list(reversed(configs)))];hashes={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ['gp_transport_calibration_worker.py','run_gp_transport_calibration.py','GP-TRANSPORT-CALIBRATION-PROTOCOL.md']};rows=[]
def run(job):
    fold,transform,mode,accept=job;seed=948300001+fold;d=r/f'{fold}-{transform}-{mode}-{accept}';d.mkdir();assert shutil.disk_usage(r).free>2*1024**3
    command=[sys.executable,str(p/'gp_transport_calibration_worker.py'),str(d),mode,str(accept),str(seed),str(fold),transform];result=execute(command,str(p),180,d,2*1024**3,64*1024**2,d/'worker.log',output_scan_interval=2);(d/'SUPERVISION.json').write_text(json.dumps(result,indent=2)+'\n');complete=result['exit_code']==0 and result['group_drained'] and (d/'SUMMARY.json').exists();return json.loads((d/'SUMMARY.json').read_text()) if complete else dict(fold=fold,transform=transform,mode=mode,target_accept=accept,seed=seed,passed=False,completed=False,supervision=result)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    futures=[pool.submit(run,job) for job in jobs]
    for future in concurrent.futures.as_completed(futures):
        row=future.result();rows.append(row);(r/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(dict(completed=len(rows),fold=row['fold'],transform=row['transform'],mode=row['mode'],accept=row['target_accept'],passed=row['passed'])),flush=True)
eligible=[];selected=[]
for transform in ['affine','quadratic']:
    for engine in ['walnuts','native']:
        group=[]
        for mode,accept in configs:
            if mode.startswith('walnuts')!=(engine=='walnuts'):continue
            subset=[x for x in rows if x['transform']==transform and x['mode']==mode and x['target_accept']==accept];assert len(subset)==4
            if all(x['passed'] for x in subset):group.append(dict(transform=transform,engine=engine,mode=mode,target_accept=accept,calls_per_min_bulk_ess_geomean=float(np.exp(np.mean(np.log([x['calls_per_min_bulk_ess'] for x in subset]))))))
        group.sort(key=lambda x:(x['calls_per_min_bulk_ess_geomean'],-x['target_accept'],'diag' not in x['mode']));eligible.extend(group);selected.append(dict(transform=transform,engine=engine,selection=group[0] if group else None))
assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items());(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,rows=sorted(rows,key=lambda x:(x['fold'],x['transform'],x['mode'],x['target_accept'])),eligible=eligible,selected=selected,source_hashes=hashes),indent=2)+'\n');print(json.dumps(selected),flush=True)
