import hashlib,json
from pathlib import Path
p=Path(__file__).resolve().parent
s=json.loads((p/'summary-supervision/SUPERVISION.json').read_text());assert s['exit_code']==0 and s['group_drained']
assert (p/'results/SUMMARY.json').exists()
files={str(f.relative_to(p)):dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in p.rglob('*') if f.is_file() and f.name!='TRANSFER-MANIFEST.json' and '__pycache__' not in f.parts}
(p/'TRANSFER-MANIFEST.json').write_text(json.dumps(files,indent=2)+'\n');print(json.dumps(dict(files=len(files),bytes=sum(x['bytes'] for x in files.values()))))
