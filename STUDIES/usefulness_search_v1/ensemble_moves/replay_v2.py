import hashlib,json,sys,time
from pathlib import Path
import numpy as np
import bridgestan,owalnuts
from move import EnsembleMove
root=Path(__file__).resolve().parent;arm=sys.argv[1];out=root/('replay-v2-'+arm);out.mkdir(exist_ok=False)
assert arm in ('local','ensemble')
source=Path('/dev/shm/bounded-init-20261030/run01/012/RESULT.json')
models=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models');name='hudson_lynx_hare-lotka_volterra'
deps=[source,models/(name+'_model.so'),models/(name+'.data.json')]
(out/'INPUTS.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in deps},indent=2)+'\n')
chains=json.loads(source.read_text())['chains_data'];x=np.array([c['samples'][0] for c in chains]);mass=np.array([c['mass_diagonal'] for c in chains]);steps=np.array([c['final_step_size'] for c in chains])
model=bridgestan.StanModel(str(deps[1]),data=str(deps[2]),seed=1);calls=0;errors=0
def target(q):
 global calls,errors
 calls+=1
 try:
  lp,g=model.log_density_gradient(q)
  if not np.isfinite(lp) or not np.isfinite(g).all():raise ValueError('nonfinite')
  return float(lp),g
 except (RuntimeError,ValueError):
  errors+=1;return -np.inf,np.zeros(8)
def density(q):return target(q)[0]
move=EnsembleMove(np.array([np.diag(1/np.sqrt(m)) for m in mass]));rng=np.random.default_rng(940300001)
np.savez_compressed(out/'initial.npz',x=x,mass=mass,steps=steps)
initial_lp=[density(q) for q in x];accepted=np.zeros(4,int);invalid=0;draws=[];ends=[];history=[];div=0;depth=0;start=time.monotonic()
for chunk in range(100):
 state=owalnuts.WarmState(positions=x,step_sizes=steps,mass_diagonal=mass)
 f=owalnuts.sample_warm(target,state,draws=10,seed=940200001+1000*chunk,threads=1,tuning=owalnuts.Tuning(max_depth=10,max_error=1.))
 assert np.array_equal(f.final_step_size,steps)
 assert np.array_equal(f.warm_state().mass_diagonal,mass)
 draws.append(f.samples.copy());x=f.warm_state().positions.copy();div+=int(f.divergent.sum());depth+=int((f.depth>=10).sum())
 if arm=='ensemble':
  x,meta=move.sweep(x,density,rng);accepted+=meta['accepted'];invalid+=meta['invalid']
 ends.append(x.copy());history.append([density(q) for q in x])
 (out/'PROGRESS.json').write_text(json.dumps(dict(chunk=chunk+1,calls=calls,errors=errors,accepted=accepted.tolist(),seconds=time.monotonic()-start))+'\n')
np.savez_compressed(out/'draws.npz',local=np.concatenate(draws,axis=1),post_sweep=np.array(ends),log_density=np.array(history))
r=dict(arm=arm,seconds=time.monotonic()-start,calls=calls,errors=errors,accepted=accepted.tolist(),invalid_proposals=invalid,divergences=div,depth_stops=depth,initial_log_density=initial_lp,final_log_density=history[-1],median_log_density=np.median(history,axis=0).tolist(),mechanics_only=True)
(out/'RESULT.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
