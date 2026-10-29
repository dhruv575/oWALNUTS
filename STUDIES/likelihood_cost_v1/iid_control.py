"""Supplement: analytic posterior followed by independent exact draws."""
import time
START=time.monotonic()
import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'source'))
import numpy as np
from targets import Target,SIZES
from metrics import assess
IMPORT_SECONDS=time.monotonic()-START

root=Path(sys.argv[1]);root.mkdir(exist_ok=False);rows=[]
source=Path(__file__).resolve().parent.parent/'source'
manifest={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),source/'targets.py',source/'geometry.py',source/'metrics.py']}
(root/'SOURCE-HASHES.json').write_text(json.dumps(manifest,indent=2)+'\n')
for case,n in enumerate(SIZES):
    for rep in range(8):
        start=time.monotonic();t=Target(n);setup=time.monotonic()-start
        start=time.monotonic();q=t.iid(4*6000,805000000+case*1000+rep).reshape(4,6000,24);draw_seconds=time.monotonic()-start
        start=time.monotonic();metrics=assess(t,q);diagnostic=time.monotonic()-start
        np.savez_compressed(root/f'{case}-{rep}.npz',draws=q)
        rows.append(dict(case=case,n=n,rep=rep,seed=805000000+case*1000+rep,draws=6000,setup_seconds=setup,draw_seconds=draw_seconds,diagnostic_seconds=diagnostic,metrics=metrics))
(root/'RESULTS.json').write_text(json.dumps(dict(rows=rows,shared_import_seconds=IMPORT_SECONDS,process_seconds=time.monotonic()-START,scope='Analytic Gaussian posterior IID supplement; per-case setup/generation/diagnostics exclude amortized process import and serialization'),indent=2)+'\n')
print(json.dumps(dict(completed=len(rows),passed=sum(r['metrics']['passed'] for r in rows))))
