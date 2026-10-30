import hashlib,json,shutil,sys
from pathlib import Path
from resource_monitor import execute
p=Path(__file__).resolve().parent;r=p/'results';r.mkdir(exist_ok=False);hashes=json.loads((p/'MANIFEST.json').read_text());runtime=json.loads((p/'RUNTIME.json').read_text());base=Path(runtime['root'])
def verify():
 for name,h in hashes.items():assert hashlib.sha256((p/name).read_bytes()).hexdigest()==h
 assert hashlib.sha256((base/'MANIFEST.json').read_bytes()).hexdigest()==runtime['manifest_sha256']
 for name,h in json.loads((base/'MANIFEST.json').read_text()).items():assert hashlib.sha256((base/name).read_bytes()).hexdigest()==h
 for name,h in runtime['shims'].items():assert hashlib.sha256((base/name).read_bytes()).hexdigest()==h
verify();configs=[('raw','walnuts_dense',.9),('raw','diag',.999),('affine','walnuts_dense',.9),('affine','diag',.99),('bounded','walnuts_dense',.9),('bounded','diag',.999),('importance','importance',0)];rows=[]
for fold in range(4):
 for transform,mode,accept in configs[fold:]+configs[:fold]:
  assert shutil.disk_usage(r).free>1024**3;seed=950900001+fold;d=r/f'{fold}-{transform}-{mode}';d.mkdir()
  worker=[sys.executable,str(p/'gp_widegrid_worker.py'),str(d),str(seed),str(fold)] if transform=='importance' else [sys.executable,str(p/'gp_aws_qualified_sampler.py'),str(d),mode,str(accept),str(seed),str(fold),transform]
  result=execute([sys.executable,str(p/'time_gp_workflow.py'),str(d)]+worker,str(p),600,d,3*1024**3,256*1024**2,d/'worker.log',output_scan_interval=2);(d/'SUPERVISION.json').write_text(json.dumps(result,indent=2)+'\n');f=d/('RESULT.json' if transform=='importance' else 'SUMMARY.json');complete=result['exit_code']==0 and result['group_drained'] and f.exists();value=json.loads(f.read_text()) if complete else {};row=dict(fold=fold,transform=transform,mode=mode,seed=seed,completed=complete,passed=bool(complete and value['passed']),result=value)
  if (d/'PROCESS-TIME.json').exists():row['timing']=json.loads((d/'PROCESS-TIME.json').read_text())
  rows.append(row);(r/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps({k:row[k] for k in ['fold','transform','mode','passed']}),flush=True)
verify();(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,all_qualified=len(rows)==28 and all(x['passed'] for x in rows),rows=rows,inputs=hashes,runtime=runtime),indent=2)+'\n')
