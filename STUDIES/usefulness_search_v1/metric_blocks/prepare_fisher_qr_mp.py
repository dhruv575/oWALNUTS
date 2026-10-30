import hashlib,json,shutil
from pathlib import Path
study=Path(__file__).resolve().parent;root=study/'local_recovery/fisherqr01';root.mkdir(exist_ok=False)
for name in ['fisher_qr_mp.py','fisher_high_precision.py','fisher_dense.py','FISHER-QR-MP-PREFLIGHT.md','test_fisher_qr_mp_models.py']:
    shutil.copy2(study/name,root/name)
old=(study/'test_fisher_high_precision.py').read_text()
new=old.replace('fisher_high_precision','fisher_qr_mp').replace('FISHER-HIGH-PRECISION-PREFLIGHT.md','FISHER-QR-MP-PREFLIGHT.md')
(root/'test_fisher_qr_mp.py').write_text(new)
(root/'TEST-PROVENANCE.json').write_text(json.dumps(dict(parent_sha256=hashlib.sha256((study/'test_fisher_high_precision.py').read_bytes()).hexdigest(),substitutions={'fisher_high_precision':'fisher_qr_mp','FISHER-HIGH-PRECISION-PREFLIGHT.md':'FISHER-QR-MP-PREFLIGHT.md'},no_gate_changes=True),indent=2)+'\n')
print(root)
