import json
from pathlib import Path
import numpy as np
from scipy.special import expit
BASE=Path(__file__).resolve().parent
for index,case in enumerate(['weak','mixed']):
    n=np.array([5]*12 if case=='weak' else [5,5,10,10,20,20,100,100,1000,1000,10000,10000]);rng=np.random.default_rng(956000001+index);theta=rng.normal(-2,.05,12);y=rng.binomial(n,expit(theta))
    d=dict(case=case,n=n.tolist(),y=y.tolist(),seed=956000001+index,generator=dict(mu=-2,tau=.05,theta=theta.tolist()),scope='Synthetic hierarchical mechanism pilot, not real observations')
    path=BASE/(case+'.json');assert not path.exists();path.write_text(json.dumps(d,indent=2))
