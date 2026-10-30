from pathlib import Path
import hashlib,json,shutil,tarfile
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_aws_qualified_bundle01';r.mkdir(exist_ok=False)
source=l/'gp_aws_full_bundle01'
for f in source.rglob('*'):
 if f.is_file() and f.name!='MANIFEST.json':
  target=r/f.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,target)
s=(p/'gp_aws_full_sampler.py').read_text().replace("runtime/f'data/{fold}-{transform}.json'","STUDY/f'maps/{fold}-{transform}.json'").replace('GP-AWS-FULL-WORKFLOW-PROTOCOL.md','GP-AWS-QUALIFIED-WORKFLOW-PROTOCOL.md');(p/'gp_aws_qualified_sampler.py').write_text(s);(r/'gp_aws_qualified_sampler.py').write_text(s)
s=(p/'run_gp_aws_full_workflow.py').read_text().replace('gp_aws_full_sampler.py','gp_aws_qualified_sampler.py').replace('950700001','950900001');(p/'run_gp_aws_qualified_workflow.py').write_text(s);(r/'run_gp_aws_qualified_workflow.py').write_text(s)
for i in range(4):
 d=l/f'gp_aws_pilot_qualification01/evidence/scenario-{i}'
 for src,dst in [('MAP.json',f'{i}.json'),('SUMMARY.json',f'{i}-pilot.json'),('affine.json',f'{i}-affine.json'),('bounded.json',f'{i}-bounded.json')]:shutil.copyfile(d/src,r/'maps'/dst)
qualified=json.loads((l/'gp_aws_pilot_qualification01/evidence/SUMMARY.json').read_text());equivalence=json.loads((l/'gp_aws_map_equivalence01/SUMMARY.json').read_text());assert qualified['all_qualified'] and equivalence['passed']
shutil.copyfile(l/'gp_aws_pilot_qualification01/evidence/SUMMARY.json',r/'PILOT-QUALIFICATION.json');shutil.copyfile(l/'gp_aws_map_equivalence01/SUMMARY.json',r/'MAP-EQUIVALENCE.json')
protocol=(p/'GP-AWS-FULL-WORKFLOW-PROTOCOL.md').read_text().replace('950700001','950900001').replace('qualified pilot map','qualified AWS-specific pilot map')
protocol+='\nSeparate follow-up to the failed original AWS study. Frozen expected maps/counts/target data now come from independently qualified saved AWS pilots, not local pilots. Replay tolerance remains1e-10. Both samplers still regenerate the pilot and map each time. All28 and all original accuracy requirements retained. This exposed-map study is not new-data validation.\n'
(p/'GP-AWS-QUALIFIED-WORKFLOW-PROTOCOL.md').write_text(protocol);(r/'GP-AWS-QUALIFIED-WORKFLOW-PROTOCOL.md').write_text(protocol)
for name in ['gp_aws_qualified_sampler.py','run_gp_aws_qualified_workflow.py']:compile((r/name).read_text(),name,'exec')
manifest={str(f.relative_to(r)):hashlib.sha256(f.read_bytes()).hexdigest() for f in r.rglob('*') if f.is_file()};(r/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
with tarfile.open(l/'gp_aws_qualified_bundle01.tar.gz','w:gz') as t:
 for f in r.rglob('*'):
  if f.is_file():t.add(f,arcname=str(f.relative_to(r)),recursive=False)
print(hashlib.sha256((l/'gp_aws_qualified_bundle01.tar.gz').read_bytes()).hexdigest())
