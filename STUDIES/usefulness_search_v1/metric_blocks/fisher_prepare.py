import hashlib,json,sys,time
from pathlib import Path
import numpy as np
import bridgestan as bs
from fisher_high_precision import covariance_from_samples
inp=json.loads(Path(sys.argv[1]).read_text());pilot=Path(inp['pilot']);raw=pilot.read_bytes();p=json.loads(raw)
start=time.monotonic();target=bs.StanModel(inp['model'],data=Path(inp['data']).read_text(),seed=1)
x=np.array(p['draws']);flat=x.reshape(-1,x.shape[-1]);scores=np.array([target.log_density_gradient(q)[1] for q in flat])
c=covariance_from_samples(flat,scores);mass=np.linalg.inv(c);mass=(mass+mass.T)/2
assert np.isfinite(mass).all() and np.linalg.eigvalsh(mass).min()>0 and np.linalg.norm(c@mass-np.eye(len(c)))<=1e-7
r=dict(covariance=c.tolist(),mass=mass.tolist(),scores=scores.tolist(),target_calls=len(flat),seconds=time.monotonic()-start,
    pilot_sha256=hashlib.sha256(raw).hexdigest(),gamma=0,decimal_precision=80)
Path(sys.argv[2]).write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
