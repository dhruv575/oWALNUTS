import concurrent.futures,hashlib,json,shutil,sys
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_newdata_importance01';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
assert json.loads((l/'gp_newdata_comparison01/SUMMARY.json').read_text())['completed']
files=[p/n for n in ['gp_newdata_importance_worker.py','run_gp_newdata_importance.py','GP-NEWDATA-IMPORTANCE-PROTOCOL.md','gp_conditional_confirmation_worker.py']]+[l/'gp_conditional_local01'/n for n in ['common.py','conditional_v3.py','prepare_conditional_v3.py']]+[l/'gp_fresh_reference01/SUMMARY.json']+[l/f'gp_fresh_data01/scenario-{i}/DATA.json' for i in range(4)]
hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files};(r/'INPUT-HASHES.json').write_text(json.dumps(hashes,indent=2)+'\n')
def run(job):
    scenario,rep=job;seed=950000001+2*scenario+rep;d=r/f'{scenario}-{rep}';d.mkdir();assert shutil.disk_usage(r).free>2*1024**3
    result=execute([sys.executable,str(p/'gp_newdata_importance_worker.py'),str(d),str(seed),str(scenario)],str(p),300,d,2*1024**3,128*1024**2,d/'worker.log',output_scan_interval=2);(d/'SUPERVISION.json').write_text(json.dumps(result,indent=2)+'\n');complete=result['exit_code']==0 and result['group_drained'] and (d/'SETUP.json').exists();row=json.loads((d/'RESULT.json').read_text()) if complete else dict(passed=False,supervision=result);return dict(scenario=scenario,rep=rep,seed=seed,completed=complete,result=row)
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    for future in concurrent.futures.as_completed([pool.submit(run,(i,j)) for i in range(4) for j in range(2)]):
        row=future.result();rows.append(row);(r/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(dict(completed=len(rows),scenario=row['scenario'],rep=row['rep'],passed=row['result']['passed'])),flush=True)
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in hashes.items())
(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,all_qualified=all(x['result']['passed'] for x in rows),rows=rows,inputs=hashes),indent=2)+'\n')
