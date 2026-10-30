import hashlib,json,tarfile
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';archive=l/'gp_aws_full_remote01.tar.gz';root=l/'gp_aws_full_remote01';audit=json.loads((root/'results/AUDIT.json').read_text());assert audit['passed'] and len(audit['rows'])==28
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='40172aa47ddd1fbf02a4c0b6f57534bd10ed1f6721b2de9d6977e304744539ab'
manifest={}
with tarfile.open(archive) as t:
 for entry in t.getmembers():
  if not entry.isfile():continue
  rel=Path(entry.name).relative_to('gp-full-cost-20261030');assert '..' not in rel.parts
  data=t.extractfile(entry).read();f=root/rel;assert f.read_bytes()==data;manifest[str(rel)]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
out=l/'gp_aws_full_failed_archive01';out.mkdir(exist_ok=False);(out/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n');receipt=dict(passed=True,members=len(manifest),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),archive=str(archive),scope='Remote tar matches local transfer and every extracted member; separate post-transfer audit covers 28 outcomes; runtime binaries remain separate dependency')
(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
