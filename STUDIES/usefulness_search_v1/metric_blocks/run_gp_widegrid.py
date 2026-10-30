import concurrent.futures,hashlib,json,shutil,sys
from pathlib import Path
from resource_monitor import execute
p=Path(__file__).resolve().parent;r=p/'results';r.mkdir(exist_ok=False);hashes=json.loads((p/'MANIFEST.json').read_text())
def verify():
 for name,h in hashes.items():assert hashlib.sha256((p/name).read_bytes()).hexdigest()==h
verify()
def run(job):
 scenario,rep=job;seed=950100001+2*scenario+rep;d=r/f'{scenario}-{rep}';d.mkdir();assert shutil.disk_usage(r).free>1024**3
 supervision=execute([sys.executable,str(p/'gp_widegrid_worker.py'),str(d),str(seed),str(scenario)],str(p),300,d,2*1024**3,128*1024**2,d/'worker.log',output_scan_interval=2);(d/'SUPERVISION.json').write_text(json.dumps(supervision,indent=2)+'\n');complete=supervision['exit_code']==0 and supervision['group_drained'] and (d/'SETUP.json').exists();result=json.loads((d/'RESULT.json').read_text()) if complete else dict(passed=False,supervision=supervision);return dict(scenario=scenario,rep=rep,seed=seed,completed=complete,result=result)
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
 for future in concurrent.futures.as_completed([pool.submit(run,(i,j)) for i in range(4) for j in range(2)]):
  row=future.result();rows.append(row);(r/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(dict(completed=len(rows),scenario=row['scenario'],rep=row['rep'],passed=row['result']['passed'])),flush=True)
verify();(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,all_qualified=all(x['result']['passed'] for x in rows),rows=rows,inputs=hashes),indent=2)+'\n')
