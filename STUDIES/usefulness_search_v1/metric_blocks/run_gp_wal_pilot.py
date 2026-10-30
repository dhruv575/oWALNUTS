import concurrent.futures,hashlib,json,shutil,sys
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';ref=json.loads((l/'gp_fresh_reference01/SUMMARY.json').read_text());assert all(x['passed'] for x in ref['references'])
r=l/'gp_wal_pilot01';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'))
from resource_monitor import execute
hashes={str(p/n):hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ['gp_wal_pilot_worker.py','run_gp_wal_pilot.py','GP-WAL-PILOT-PROTOCOL.md','bounded_transport.py','gp_workflow_setup.py']}
def run(scenario):
    d=r/f'scenario-{scenario}';d.mkdir();assert shutil.disk_usage(r).free>2*1024**3
    command=[sys.executable,str(p/'gp_wal_pilot_worker.py'),str(d),'walnuts_dense','.9',str(950200001+scenario),str(scenario),'raw']
    supervised=execute(command,str(p),180,d,2*1024**3,64*1024**2,d/'worker.log',output_scan_interval=2);(d/'SUPERVISION.json').write_text(json.dumps(supervised,indent=2)+'\n')
    complete=supervised['exit_code']==0 and supervised['group_drained'] and (d/'SUMMARY.json').exists();result=json.loads((d/'SUMMARY.json').read_text()) if complete else {}
    return dict(scenario=scenario,completed=complete,passed=bool(complete and result['passed'] and (d/'MAP-SETUP.json').exists()),result=result,supervision=supervised)
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for row in pool.map(run,range(4)):
        rows.append(row);print(json.dumps(dict(scenario=row['scenario'],passed=row['passed'])),flush=True)
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in hashes.items())
(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,all_qualified=all(x['passed'] for x in rows),rows=rows,inputs=hashes),indent=2)+'\n')
