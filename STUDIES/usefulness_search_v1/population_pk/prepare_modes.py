import json
import numpy as np
from native import Native,ROOT
primary=json.loads((ROOT/'PREPARED.json').read_text());secondary=json.loads((ROOT/'SYMMETRY-SCALED.json').read_text());assert secondary['optimizer_success'] and secondary['gradient_max']<.01
b=Native();mode=np.array(secondary['optimized_q']);H=np.empty((43,43));h=1e-4
for j in range(43):
 e=np.zeros(43);e[j]=h;H[:,j]=-(b.value(mode+e)[1]-b.value(mode-e)[1])/(2*h)
H=(H+H.T)/2;eig,V=np.linalg.eigh(H);assert eig.min()>0;cov=(V/eig)@V.T;L=np.linalg.cholesky(cov)
starts=np.array(primary['starts']);starts[1]=mode+.2*L@np.sin(np.arange(1,44));starts[3]=mode-.2*L@np.sin(np.arange(1,44))
ratio=secondary['optimized_log_density']-secondary['original_log_density']+.5*(np.linalg.slogdet(cov)[1]-np.linalg.slogdet(primary['cov'])[1])
result=dict(starts=starts.tolist(),secondary_mode=mode.tolist(),secondary_cov=cov.tolist(),secondary_L=L.tolist(),secondary_hessian_min=float(eig.min()),laplace_log_mass_ratio=float(ratio),laplace_mass_ratio_is_unverified_approximation=True)
(ROOT/'MODES.json').write_text(json.dumps(result,indent=2)+'\n');b.close();print(json.dumps({k:v for k,v in result.items() if k not in ['starts','secondary_mode','secondary_cov','secondary_L']}))
