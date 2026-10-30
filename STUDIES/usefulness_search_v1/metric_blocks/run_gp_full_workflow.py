import hashlib,json,shutil,sys
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_full_workflow01';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'))
from resource_monitor import execute
configs=[('raw','walnuts_dense',.9),('raw','diag',.999),('affine','walnuts_dense',.9),('affine','diag',.99),('bounded','walnuts_dense',.9),('bounded','diag',.999),('importance','importance',0)]
files=[p/n for n in ['gp_full_sampler_worker.py','gp_full_importance_worker.py','gp_conditional_confirmation_worker.py','time_gp_workflow.py','run_gp_full_workflow.py','GP-FULL-WORKFLOW-PROTOCOL.md','gp_workflow_setup.py','bounded_transport.py','native_common.py']]
files += [l/'gp_conditional_local01'/n for n in ['common.py','conditional_v3.py','prepare_conditional_v3.py']]
hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files};(r/'INPUT-HASHES.json').write_text(json.dumps(hashes,indent=2)+'\n');rows=[]
for fold in range(4):
    order=configs[fold:]+configs[:fold]
    for transform,mode,accept in order:
        assert shutil.disk_usage(r).free>2*1024**3
        seed=949300001+fold;d=r/f'{fold}-{transform}-{mode}';d.mkdir()
        worker=[sys.executable,str(p/'gp_full_importance_worker.py'),str(d),str(seed)] if transform=='importance' else [sys.executable,str(p/'gp_full_sampler_worker.py'),str(d),mode,str(accept),str(seed),str(fold),transform]
        command=[sys.executable,str(p/'time_gp_workflow.py'),str(d)]+worker
        supervised=execute(command,str(p),600,d,3*1024**3,256*1024**2,d/'worker.log',output_scan_interval=2);(d/'SUPERVISION.json').write_text(json.dumps(supervised,indent=2)+'\n')
        resultpath=d/('RESULT.json' if transform=='importance' else 'SUMMARY.json');complete=supervised['exit_code']==0 and supervised['group_drained'] and resultpath.exists()
        result=json.loads(resultpath.read_text()) if complete else {};row=dict(fold=fold,transform=transform,mode=mode,seed=seed,completed=complete,passed=bool(complete and result['passed']),result=result)
        if (d/'PROCESS-TIME.json').exists():row['timing']=json.loads((d/'PROCESS-TIME.json').read_text())
        rows.append(row);(r/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps({k:row[k] for k in ['fold','transform','mode','passed']}),flush=True)
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in hashes.items())
(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,all_qualified=len(rows)==28 and all(x['passed'] for x in rows),rows=rows,inputs=hashes),indent=2)+'\n')
