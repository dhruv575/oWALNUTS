import shutil
from pathlib import Path
p=Path(__file__).resolve().parent;old=p/'local_recovery/quadratic_transport_supervision01'
for n in ['quadratic_transport_diagnostic.py','run_quadratic_transport.py']:shutil.copy2(p/n,old/n)
f=p/'quadratic_transport_diagnostic.py';s=f.read_text().replace("r=l/'quadratic_transport01'","r=l/'quadratic_transport02'")
s=s.replace("for f in files:hashes[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()","for f in files:\n        if f.exists():hashes[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()")
s=s.replace("qualification=json.loads(files[3].read_text())['native']['passed'];row=dict(model=name,prior_native_qualified=qualification)","qualification=json.loads(files[3].read_text())['native']['passed'] if files[3].exists() else False;row=dict(model=name,prior_native_qualified=qualification,qualification_artifact_present=files[3].exists())")
f.write_text(s);f=p/'run_quadratic_transport.py';f.write_text(f.read_text().replace('quadratic_transport_supervision01','quadratic_transport_supervision02').replace("l/'quadratic_transport01'","l/'quadratic_transport02'"))
