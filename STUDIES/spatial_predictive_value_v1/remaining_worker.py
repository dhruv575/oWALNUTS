import os,sys,time,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,'/home/ubuntu/lanes/spatial-predictive-value-20261101')
from scoring_worker import physical,mixture,analytic,quadrature,summarize,gp_precision,GridGP,Native,GP_PATHS
import numpy as np,nutpie,arviz as az
from scipy.optimize import minimize
from scipy.special import gammaln,logsumexp
from scipy.stats import poisson,nbinom
def main():
    split_index=int(sys.argv[1]);assert split_index in [3,4]
    freeze=json.loads((ROOT/'FREEZE.json').read_text())
    for name,h in freeze.items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
    start=time.perf_counter();out=ROOT/'results';out.mkdir(exist_ok=False)
    source=np.load(ROOT/'SOURCE-AND-SPLIT.npz');px=source['x'];py=source['y'];cell=np.minimum((px/50).astype(int),19)*10+np.minimum((py/50).astype(int),9)
    mask=np.random.default_rng(952000000+split_index).random(len(px))<.2;train=np.bincount(cell[mask],minlength=200);held=np.bincount(cell[~mask],minlength=200)
    assert np.array_equal(train+held,source['full']);np.savez_compressed(out/'SPLIT.npz',mask=mask,train=train,heldout=held)
    d=json.loads((ROOT/'GP-TRAIN-TEMPLATE.json').read_text());d['y']=train.tolist();(out/'GP-TRAIN.json').write_text(json.dumps(d));model=GridGP(d);target=Native(d,955100000+split_index)
    before=time.perf_counter();trace=nutpie.sample(target.compiled,draws=4000,tune=1000,chains=4,cores=4,seed=955100000+split_index,progress_bar=False,save_warmup=False,adaptation='diag',target_accept=.99,maxdepth=12,step_size_jitter=0.)
    q=np.asarray(trace.posterior.q).copy();div=int(trace.sample_stats.diverging.sum());depth=int(trace.sample_stats.maxdepth_reached.sum());trace.close();fit_seconds=time.perf_counter()-before
    np.savez_compressed(out/'DRAWS.npz',q=q);v=physical(q,model);ds=az.convert_to_dataset({'p':v});rhat=np.asarray(az.rhat(ds,method='rank').p);bulk=np.asarray(az.ess(ds,method='bulk').p);tail=np.asarray(az.ess(ds,method='tail').p)
    diagnostic=bool(max(rhat)<=1.01 and min(bulk)>=1000 and min(tail)>=1000 and div==0 and depth==0)
    (out/'DIAGNOSTICS.json').write_text(json.dumps(dict(rhat=rhat.tolist(),bulk=bulk.tolist(),tail=tail.tolist()),indent=2))
    rates=v[:,:,205:].copy();precision=gp_precision(held,rates);flat=rates.reshape(-1,200);pred={'gp':mixture(held,lambda i:flat[:,i],np.ones(len(flat)),955200000+10*split_index)}
    del v,q,ds,rates
    # Exactly the primary training-selection grids and fold generator.
    folds=np.random.default_rng(952400001).multinomial(train,np.full(5,.2)).T;x=np.array(d['x']);distance=((x[:,None]-x[None,:])**2).sum(2)
    bandwidths=[]
    for h in [.25,.5,1.,2.,4.,8.]:
        K=np.exp(-distance/(2*h*h));K/=K.sum(1,keepdims=True);score=sum(float(poisson.logpmf(val,.04*(K@(train-val)/.16)).sum()) for val in folds);bandwidths.append((score,h))
    h=max(bandwidths)[1];K=np.exp(-distance/(2*h*h));K/=K.sum(1,keepdims=True);pred['kernel']=analytic(held,[poisson(.8*r) for r in K@train/.2])
    shapes=[]
    for a in [.1,.25,.5,1.,2.,4.,8.,16.,32.,64.,128.,256.,1000000.]:
        score=0.
        for val in folds:
            yy=train-val;b=a/(yy.mean()/.16)+.16;score+=float(nbinom.logpmf(val,a+yy,b/(b+.04)).sum())
        shapes.append((score,a))
    alpha=max(shapes)[1];b=alpha/(train.mean()/.2)+.2
    pred['empirical_bayes']=analytic(held,[nbinom(a,b/(b+.8)) for a in train+alpha])
    pred['fixed_cell']=analytic(held,[nbinom(a,.225/1.025) for a in train+.5])
    pred['homogeneous']=analytic(held,[nbinom(train.sum()+.5,40.025/40.825)]*200)
    X=np.array(d['design']);prior=1/np.square(d['coef_scale'])
    def objective(beta):
        f=X@beta;mu=.2*np.exp(f);return mu.sum()-train@f+.5*np.sum(beta*beta*prior),X.T@(mu-train)+prior*beta,(X.T*mu)@X+np.diag(prior)
    fit=minimize(lambda b:objective(b)[0],[np.log(train.mean()/.2),0,0],jac=lambda b:objective(b)[1],hess=lambda b:objective(b)[2],method='trust-exact',options={'gtol':1e-8,'maxiter':100});assert max(abs(objective(fit.x)[1]))<=1e-5
    terrain=dict(mode=fit.x.tolist(),covariance=np.linalg.inv(objective(fit.x)[2]).tolist());scores=[]
    for order in [32,48]:
        beta,w=quadrature(order,d,terrain);scores.append(np.array([logsumexp(np.log(w,where=w>0,out=np.full_like(w,-np.inf))+poisson.logpmf(obs,.8*np.exp(beta@X[i]))) for i,obs in enumerate(held)]))
        if order==48:pred['terrain']=mixture(held,lambda i:np.exp(beta@X[i]),w,955200001+10*split_index)
    terrain_error=float(max(abs(scores[1]-scores[0])));summaries={name:summarize(held,rows) for name,rows in pred.items()}
    blocks=np.array([(i//5)*2+j//5 for i in range(20) for j in range(10)]);indices=np.random.default_rng(955000030).integers(0,8,(10000,8));comparisons=[]
    for name,rows in pred.items():
        if name=='gp':continue
        delta=np.array([r['log_score'] for r in pred['gp']])-np.array([r['log_score'] for r in rows]);byblock=np.array([delta[blocks==b].mean() for b in range(8)])
        comparisons.append(dict(competitor=name,gain=float(delta.mean()),lower=float(np.quantile(byblock[indices].mean(1),.05/6))))
    result=dict(split_seed=952000000+split_index,diagnostic_pass=diagnostic,max_rhat=float(max(rhat)),min_bulk=float(min(bulk)),min_tail=float(min(tail)),divergences=div,depth_hits=depth,fit_seconds=fit_seconds,total_seconds=time.perf_counter()-start,terrain_score_error=terrain_error,precision=precision,summaries=summaries,comparisons=comparisons,selected_bandwidth=h,selected_shape=alpha,scope='Exploratory reserved split of same exposed forest; no new reference qualification or independent-site claim')
    (out/'SUMMARY.json').write_text(json.dumps(result,indent=2,allow_nan=False));(out/'CELLS.json').write_text(json.dumps(pred));target.close()
    for name,h in freeze.items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
    print(json.dumps({k:v for k,v in result.items() if k!='precision'}),flush=True)
if __name__=='__main__':main()
