import hashlib,json,shutil,tarfile
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_aws_full_bundle01';r.mkdir(exist_ok=False)
for n in ['runtime','models','data','maps']:(r/n).mkdir()
for n in ['native_common.py','gp_aws_full_sampler.py','run_gp_aws_full_workflow.py','gp_widegrid_worker.py','time_gp_workflow.py','bounded_transport.py','gp_workflow_setup.py','GP-AWS-FULL-WORKFLOW-PROTOCOL.md']:shutil.copyfile(p/n,r/n)
shutil.copyfile(l/'inputs/resource_monitor.py',r/'resource_monitor.py')
for f in (l/'gp_widegrid_bundle01/runtime').iterdir():
 if f.is_file():shutil.copyfile(f,r/'runtime'/f.name)
for f in (l/'gp_widegrid_bundle01/models').iterdir():
 if f.is_file():shutil.copyfile(f,r/'models'/f.name)
for i in range(4):
 shutil.copyfile(l/f'gp_fresh_data01/scenario-{i}/DATA.json',r/f'data/{i}.json')
 shutil.copyfile(l/f'gp_wal_pilot01/scenario-{i}/MAP.json',r/f'maps/{i}.json');shutil.copyfile(l/f'gp_wal_pilot01/scenario-{i}/SUMMARY.json',r/f'maps/{i}-pilot.json')
shutil.copyfile(l/'gp_fresh_reference01/SUMMARY.json',r/'REFERENCE.json')
preflight=json.loads((l/'gp_aws_runtime_preflight01/SUMMARY.json').read_text());assert preflight['passed']
(r/'RUNTIME.json').write_text(json.dumps(dict(root='/home/ubuntu/lanes/gp-portable-runtime-20261030',manifest_sha256=hashlib.sha256((l/'gp_aws_runtime_bundle01/MANIFEST.json').read_bytes()).hexdigest(),shims={f"preflight/{x['arm']}/counted_model.so":x['shim_sha256'] for x in preflight['rows']}),indent=2)+'\n')
for name in ['gp_aws_full_sampler.py','run_gp_aws_full_workflow.py','gp_widegrid_worker.py']:compile((r/name).read_text(),name,'exec')
manifest={str(f.relative_to(r)):hashlib.sha256(f.read_bytes()).hexdigest() for f in r.rglob('*') if f.is_file()};(r/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
with tarfile.open(l/'gp_aws_full_bundle01.tar.gz','w:gz') as t:
 for f in r.rglob('*'):
  if f.is_file():t.add(f,arcname=str(f.relative_to(r)),recursive=False)
print(hashlib.sha256((l/'gp_aws_full_bundle01.tar.gz').read_bytes()).hexdigest())
