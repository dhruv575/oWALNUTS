import json,time
import numpy as np
from native import Native,ROOT
from pymc_control import FixedNUTS
p=json.loads((ROOT/'PREPARED.json').read_text());m=json.loads((ROOT/'MODES.json').read_text());center=np.array(p['mode']);L=np.array(p['L']);x=np.linalg.solve(L,(np.array(m['starts'])-center).T).T
b=Native(center,L,x);start=time.monotonic();f=FixedNUTS(b,x[0],.05,933100001)
lp=f.model.compile_logp(mode='FAST_COMPILE');grad=f.model.compile_dlogp(mode='FAST_COMPILE')
for q in x:
 value,g=b.value(q);assert abs(lp({'q':q})-value)<1e-10;assert np.max(abs(grad({'q':q})-g))<1e-10
steps=[]
for c in range(4):
 q=x[c]
 for i in range(4):
  q,s=f.draw(q);assert abs(s['step_size']-.05)<1e-14;steps.append(int(s['tree_size']))
assert type(f.kernel.potential).__name__=='QuadPotentialDiag'
r=dict(passed=True,seconds=time.monotonic()-start,steps=steps,mass_type=type(f.kernel.potential).__name__,step_size=f.kernel.step_size,calls_errors=b.counts())
(ROOT/'PYMC-CHECK.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));b.close()
