import hashlib,json,shutil
from pathlib import Path
p=Path(__file__).resolve().parent;out=p/'archive-final';out.mkdir(exist_ok=False)
h=lambda f:hashlib.file_digest(f.open('rb'),'sha256').hexdigest()
raw=[]
for f in p.rglob('*'):
 if not f.is_file() or out in f.parents or p/'archive-ready' in f.parents:continue
 rel=f.relative_to(p)
 if f.name.endswith('-raw.json'):raw.append(dict(path=str(f.resolve()),sha256=h(f),bytes=f.stat().st_size));continue
 dst=out/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dst)
(out/'raw-manifest.json').write_text(json.dumps(dict(note='Raw arrays retained at original paths; excluded from compact archive',files=raw),indent=2))
(out/'.gitattributes').write_text('* -text\n')
(out/'CHECKSUMS.json').write_text(json.dumps({str(f.relative_to(out)):h(f) for f in out.rglob('*') if f.is_file()},indent=2))
print(len(raw),sum(x['bytes'] for x in raw))

