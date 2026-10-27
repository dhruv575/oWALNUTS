import ctypes,hashlib,json,sys
from pathlib import Path
import numpy as np
import owalnuts
from common import fixture
from sv_target_snapshot import compile_target
if sys.prefix!='/home/ubuntu/lanes/resident-predictive-build-20261027/env':raise RuntimeError('native prefix differs')
root=Path(sys.argv[1]); expected='db2c445a7a94da67d55d22d3b367c44544630655f07c88068e5456a2c7d93863'
binaries=list(Path(owalnuts.__file__).parent.glob('*.so'))
identity={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in binaries}
if expected not in identity.values():raise RuntimeError('native identity differs')
f=compile_target(); rows=[]
for n in (12,250):
 for variant in (0,1,-1):
  y,q=fixture(n,variant);g=np.zeros_like(q)
  p=ctypes.POINTER(ctypes.c_double)
  lp=f.ctypes(len(q),q.ctypes.data_as(p),g.ctypes.data_as(p),ctypes.c_void_p(y.ctypes.data))
  rows.append(dict(n=n,variant=variant,lp=lp,gradient=g.tolist()))
(root/'native-fixtures.json').write_text(json.dumps(dict(prefix=sys.prefix,executable=sys.executable,binaries=identity,rows=rows),indent=2))
