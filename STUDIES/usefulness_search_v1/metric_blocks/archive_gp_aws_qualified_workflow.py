import hashlib,io,json,tarfile
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';root=l/'gp_aws_qualified_remote01';r=root/'results';s=json.loads((r/'SUMMARY.json').read_text());audit=json.loads((r/'AUDIT.json').read_text());assert s['completed'] and len(s['rows'])==28 and audit['passed'];files={}
def local_path(name):
 prefix='/home/ubuntu/lanes/gp-qualified-cost-20261030/'
 if name.startswith(prefix):return root/name[len(prefix):]
 prefix='/home/ubuntu/lanes/gp-portable-runtime-20261030/'
 if name.startswith(prefix):
  tail=name[len(prefix):]
  return l/'gp_aws_runtime_preflight01'/tail[len('preflight/'):] if tail.startswith('preflight/') else l/'gp_aws_runtime_bundle01'/tail
 raise ValueError('Unmapped input '+name)
for name,h in s['inputs'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h
for row in s['rows']:
 for name,h in row.get('result',{}).get('inputs',{}).items():
  f=local_path(name);assert hashlib.sha256(f.read_bytes()).hexdigest()==h;files['dependencies/'+str(f.relative_to(l))]=f
runtime=s['runtime'];bundle=l/'gp_aws_runtime_bundle01';assert hashlib.sha256((bundle/'MANIFEST.json').read_bytes()).hexdigest()==runtime['manifest_sha256']
for name,h in json.loads((bundle/'MANIFEST.json').read_text()).items():
 f=bundle/name;assert hashlib.sha256(f.read_bytes()).hexdigest()==h;files['runtime/'+name]=f
for name,h in runtime['shims'].items():
 f=l/'gp_aws_runtime_preflight01'/name[len('preflight/'):];assert hashlib.sha256(f.read_bytes()).hexdigest()==h;files['runtime/'+name]=f
for f in root.rglob('*'):
 if f.is_file() and '__pycache__' not in f.parts:files['study/'+str(f.relative_to(root))]=f
for n in ['analyze_gp_aws_qualified_workflow.py','archive_gp_aws_qualified_workflow.py','GP-AWS-QUALIFIED-WORKFLOW-RESULT.md','local_recovery/gp_aws_setup_archive01/VERIFICATION.json','local_recovery/gp_fresh_reference_archive01/VERIFICATION.json']:files[n]=p/n
out=l/'gp_aws_qualified_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
 b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(b);t.addfile(info,io.BytesIO(b))
 for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
 for n,m in manifest.items():
  b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local complete workflow/raw audit archive including runtime models and shims; reference raw archive remains separate; not S3')
(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
