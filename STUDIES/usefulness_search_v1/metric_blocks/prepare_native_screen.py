import hashlib,json
from pathlib import Path
study=Path(__file__).resolve().parent
source=(study/'scaled_policy.py').read_text();old='from fisher_high_precision import covariance_from_samples';assert source.count(old)==1
new=source.replace(old,'from fisher_qr_mp import covariance_from_samples');path=study/'scaled_policy_qr.py'
if path.exists():assert path.read_text()==new
else:path.write_text(new)
(study/'local_recovery/QR-POLICY-PROVENANCE.json').write_text(json.dumps(dict(parent_sha256=hashlib.sha256((study/'scaled_policy.py').read_bytes()).hexdigest(),derived_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),only_change='Fisher solver import: full-sample80-digit to qualified QR/small-matrix80-digit'),indent=2)+'\n')
