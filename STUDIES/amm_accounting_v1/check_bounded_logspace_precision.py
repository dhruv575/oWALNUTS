"""Record arbitrary-precision evidence at the captured underflow proposal."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
import mpmath as mp
from bounded_rescaled_logspace import target
from test_bounded_rescaled_logspace import mp_density

root=Path(__file__).resolve().parent;p=root/'evidence/bounded-failure-capture-20261028/CAPTURE.npz'
with np.load(p) as f:q=f['capture'][1:];y=f['y']
v,g=target(q,y,.5);rows=[]
with mp.workdps(90):
    expected=mp_density(q,y,.5);error=abs(mp.mpf(v)-expected)
    assert error<mp.mpf('.001')
    for i in [0,1,2,3,len(q)-1]:
        def fn(x):
            a=list(map(mp.mpf,q));a[i]=x
            return mp_density(a,y,.5)
        derivative=mp.diff(fn,mp.mpf(q[i]));difference=abs(mp.mpf(g[i])-derivative)
        np.testing.assert_allclose(g[i],float(derivative),rtol=1e-9,atol=1e-8)
        rows.append(dict(index=i,actual=float(g[i]),expected=mp.nstr(derivative,40),absolute_error=mp.nstr(difference,20)))
    result=dict(dps=90,mpmath=mp.__version__,python=sys.version,density_actual=v,density_expected=mp.nstr(expected,50),density_absolute_error=mp.nstr(error,20),gradient_checks=rows,sources={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ['bounded_rescaled_logspace.py','test_bounded_rescaled_logspace.py','check_bounded_logspace_precision.py']},capture_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),scope='Captured proposal density plus five selected derivatives; additional underflow fixtures cover all their coordinates in tests')
out=Path(sys.argv[1])
with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(result))
