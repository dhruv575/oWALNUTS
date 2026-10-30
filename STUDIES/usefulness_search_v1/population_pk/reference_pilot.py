import json,sys,time
from pathlib import Path
import numpy as np
import owalnuts,nutpie
from native import Native,ROOT
from involutions import global_exchange,local_exchange,move
engine,seed,out=sys.argv[1:];seed=int(seed);out=Path(out);out.mkdir(exist_ok=False)
p=json.loads((ROOT/'PREPARED.json').read_text());m=json.loads((ROOT/'MODES.json').read_text());center=np.array(p['mode']);L=np.array(p['L']);inv=np.linalg.inv(L)
starts=np.array(p['starts'] if engine=='nuts_primary' else m['starts']);x=(starts-center)@inv.T
b=Native(center,L,x);raw=Native();rng=np.random.default_rng(seed+100);accepted=np.zeros((4,2),int);crossings=np.zeros(4,int);history=[];div=[0,0];depth=[0,0];errors=[0,0];draws=[];start=time.monotonic();jump_evaluations=0
if engine=='nuts_primary':
 f=nutpie.sample(b.nuts,chains=4,cores=1,tune=1000,draws=4000,seed=seed,progress_bar=False,save_warmup=True,target_accept=.99,maxdepth=12,low_rank_modified_mass_matrix=False,transform_adapt=False)
 q=np.asarray(f.posterior.q.values)@L.T+center
 for phase,stats in enumerate([f.warmup_sample_stats,f.sample_stats]):
  div[phase]=int(stats.diverging.sum());depth[phase]=int(stats.maxdepth_reached.sum())
 f.close();errors=[None,b.counts()[1]]
else:
 if engine=='pymc_jump':
  from pymc_control import FixedNUTS
  kernels=[FixedNUTS(b,x[c],.05,seed+c*10000) for c in range(4)]
 for chunk in range(200):
  phase=int(chunk>=40);before=x@L.T+center;old_errors=b.counts()[1]
  if engine=='walnuts_jump':
   f=owalnuts.sample(b.walnuts,dim=43,init=x,chains=4,threads=1,warmup=0,draws=25,seed=seed+chunk*1000,tuning=owalnuts.Tuning(step_size=.05,max_depth=12,max_error=1.),adaptation=None)
   assert np.allclose(f.final_step_size,.05,rtol=0,atol=1e-14)
   local=f.samples.copy();div[phase]+=int(f.divergent.sum());depth[phase]+=int((f.depth>=12).sum())
  else:
   local=np.empty((4,25,43))
   for c in range(4):
    for j in range(25):
     x[c],s=kernels[c].draw(x[c]);assert abs(s['step_size']-.05)<1e-14
     local[c,j]=x[c];div[phase]+=int(s['diverging']);depth[phase]+=int(s['reached_max_treedepth'])
  errors[phase]+=b.counts()[1]-old_errors;qchunk=local@L.T+center;qend=qchunk[:,-1,:].copy()
  for c in range(4):
   qend[c],a,_=move(qend[c],raw.density,global_exchange,rng);accepted[c,0]+=a
   subject=int(rng.integers(12));qend[c],a,_=move(qend[c],raw.density,lambda v:local_exchange(v,subject),rng);accepted[c,1]+=a;jump_evaluations+=4
  crossings+=(qend[:,0]>qend[:,1])!=(before[:,0]>before[:,1]);x=(qend-center)@inv.T;qchunk[:,-1,:]=qend
  history.append((qend[:,0]>qend[:,1]).tolist())
  if phase:draws.append(qchunk)
  (out/'PROGRESS.json').write_text(json.dumps(dict(chunks=chunk+1,seconds=time.monotonic()-start,accepted=accepted.tolist(),crossings=crossings.tolist(),divergences=div,errors=errors))+'\n')
 q=np.concatenate(draws,axis=1)
np.savez_compressed(out/'draws.npz',q=q)
r=dict(engine=engine,seed=seed,seconds=time.monotonic()-start,calls_errors=b.counts(),jump_density_evaluations=jump_evaluations,accepted=accepted.tolist(),crossings=crossings.tolist(),primary_fraction=(q[:,:,0]>q[:,:,1]).mean(axis=1).tolist(),mode_history=history,divergences_by_phase=div,depth_hits_by_phase=depth,errors_by_phase=errors,reference_unqualified=True)
(out/'RESULT.json').write_text(json.dumps(r,indent=2)+'\n');b.close();raw.close();print(json.dumps({k:v for k,v in r.items() if k!='mode_history'}))
