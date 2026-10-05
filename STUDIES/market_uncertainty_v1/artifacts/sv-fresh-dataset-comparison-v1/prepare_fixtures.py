"""Create declared fixtures without selecting on outcomes; source pinning is separate."""
import json,hashlib,sys,time
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;R=P.parents[1];S=R/'STUDIES/market_uncertainty_v1/sv_prototype';sys.path.insert(0,str(S))
from synthetic import simulate,covariates,ILLUSTRATIVE_PRIORS
start=time.perf_counter();out=P/'prepared';out.mkdir(exist_ok=False)
protocol=dict(status='prepared_not_authorized_to_run',qualified=False,fixtures=6,periods=512,ablation='both',rho=.9,nu=5.,chains=4,warmup=1000,tiers=[1000,2000,4000],cpus=[0,1,2,3],timeout_seconds_per_fit=1800,global_seconds=21600,disk_floor_bytes=12*1024**3,threshold=.02,priors=vars(ILLUSTRATIVE_PRIORS),streams=[dict(id=f'fixture{i}',fixture=7201+i,mask=7301+i,sampler=7401+i,starts=7501+i,predictive=7601+i,order=['public','reference'] if i%2==0 else ['reference','public']) for i in range(6)],scope='Six declared unseen prior-generated development fixtures; all intended failures retained; no calibration or speed qualification')
(out/'protocol.json').write_text(json.dumps(protocol,indent=2));rows=[]
for role in protocol['streams']:
 record=dict(id=role['id'],status='preparation_failed')
 try:
  mask=np.random.default_rng(role['mask']).random(512)>=.1;f=simulate(512,role['fixture'],'both',priors=ILLUSTRATIVE_PRIORS,rho=.9,nu=5.,observed=mask);pr=ILLUSTRATIVE_PRIORS
  mean=np.r_[pr.mu_mean,pr.log_sigma_mean,np.zeros(516)];sd=np.r_[pr.mu_sd,pr.log_sigma_sd,np.full(2,pr.beta_sd),np.full(2,pr.gamma_sd),np.ones(512)]
  f['starts']=mean+.25*sd*np.random.default_rng(role['starts']).normal(size=(4,518));f['predictive_seed']=role['predictive'];f['stream_roles']=role;x,w=covariates(513,'both');f['future']=dict(x=x[-1],w=w[-1],index=512,scope='Fixed known deterministic forcing, not realized future flow');f['data']['y'][~mask]=0.
  path=out/(role['id']+'.json');path.write_text(json.dumps(f,indent=2,allow_nan=False,default=lambda x:x.tolist()));record.update(status='prepared',path=str(path.resolve()),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
 except Exception as exc:record['error']=repr(exc)
 rows.append(record)
(out/'fixture-manifest.json').write_text(json.dumps(dict(fixtures=rows,preparation_seconds=time.perf_counter()-start),indent=2));print('Prepared manifest with all six intended fixture identities; outcomes not summarized')
