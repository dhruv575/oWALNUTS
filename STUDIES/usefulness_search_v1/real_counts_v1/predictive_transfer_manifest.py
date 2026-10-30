import hashlib,json
from pathlib import Path
p=Path(__file__).resolve().parent;assert json.loads((p/'PREDICTIVE-SCORE-AUDIT.json').read_text())['passed'];assert json.loads((p/'audit01/SUMMARY.json').read_text())['passed']
files={str(f.relative_to(p)):dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in p.rglob('*') if f.is_file() and f.name!='TRANSFER-MANIFEST.json' and '__pycache__' not in f.parts}
(p/'TRANSFER-MANIFEST.json').write_text(json.dumps(files,indent=2)+'\n');print(json.dumps(dict(files=len(files),bytes=sum(x['bytes'] for x in files.values()))))
