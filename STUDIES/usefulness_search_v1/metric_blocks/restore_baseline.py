import hashlib,json,shutil,subprocess,tarfile
from pathlib import Path
base=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030');work=base/'work';archive=work/'reconsider-evidence.tar.gz';expected='f4603f795562c0b1b6e67e7dc9184da8ec22d4377f053795a5ede6ce13d3a729'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected
with tarfile.open(archive,'r:gz') as tar:
 manifest=json.load(tar.extractfile('EVIDENCE-MANIFEST.json'))['files'];names=set()
 for m in tar:
  if m.name=='EVIDENCE-MANIFEST.json':continue
  assert m.isfile() and m.name not in names;names.add(m.name);assert manifest[m.name]==dict(bytes=m.size,sha256=hashlib.sha256(tar.extractfile(m).read()).hexdigest())
 assert names==set(manifest)
old=work/'reconsider';old.mkdir(exist_ok=False)
with tarfile.open(archive,'r:gz') as tar:tar.extractall(old,filter='data')
binary=old/'STUDIES/metric_autoselect_confirmation_v1/target/release/pdb';binary.parent.mkdir(parents=True);shutil.copy2(old/'study-pdb',binary);binary.chmod(0o755)
(work/'audit').mkdir()
subprocess.run(['sudo','-n','mount','-o','remount,size=6G',str(work)],check=True)
r=dict(sha256=expected,verified_members=len(manifest),source='Previously exact-version S3-restored local archive; bytes reverified before extraction',previous_s3_version='qdsWDPfzKcTqSlU0mOwKUGMPEyqErQvD',baseline=str(old),workspace=str(work));(base/'evidence/RESTORE.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
