from pathlib import Path
import hashlib,json,shutil
p=Path(__file__).resolve().parent;o=p/'archive-ready';o.mkdir(exist_ok=False);raw=[]
def sha(f):
 with f.open('rb') as z:return hashlib.file_digest(z,'sha256').hexdigest()
for f in p.rglob('*'):
 if not f.is_file() or o in f.parents or '__pycache__' in f.parts:continue
 if f.suffix=='.npy':raw.append(dict(path=str(f.resolve()),sha256=sha(f),bytes=f.stat().st_size));continue
 d=o/f.relative_to(p);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,d)
(o/'raw-manifest.json').write_text(json.dumps(raw,indent=2));(o/'.gitattributes').write_text('* -text\n')
(o/'CHECKSUMS.json').write_text(json.dumps({f.relative_to(o).as_posix():sha(f) for f in o.rglob('*') if f.is_file()},indent=2));print(len(raw))
