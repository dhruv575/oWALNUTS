from common import *
import time
os.environ['XDG_CACHE_HOME']=str(BASE/'cache-scoring')
import arviz as az
from scipy.special import logsumexp,gammaln
from scipy.stats import poisson,nbinom
from numpy.polynomial.hermite import hermgauss

def empirical(y,draws,weights):
    order=np.argsort(draws,kind='stable');x=draws[order];w=weights[order];cdf=np.cumsum(w)
    quantiles=[int(x[min(np.searchsorted(cdf,p),len(x)-1)]) for p in [.05,.25,.75,.95]]
    crps=float(weights@abs(draws-y)-np.sum(w*x*(2*cdf-w-1)))
    return crps,quantiles
def mixture(y,rate_function,weights,seed):
    rng=np.random.default_rng(seed);weights=np.asarray(weights);weights=weights/weights.sum();lw=np.log(weights,where=weights>0,out=np.full_like(weights,-np.inf));rows=[]
    for i,obs in enumerate(y):
        rates=.8*rate_function(i);assert np.isfinite(rates).all() and (rates>0).all()
        lp=float(logsumexp(lw+poisson.logpmf(obs,rates)));mean=float(weights@rates);variance=float(weights@(rates+(rates-mean)**2))
        draw=rng.poisson(rates);crps,quantiles=empirical(obs,draw,weights)
        rows.append(dict(log_score=lp,mean=mean,variance=variance,crps=crps,q05=quantiles[0],q25=quantiles[1],q75=quantiles[2],q95=quantiles[3]))
    return rows
def analytic(y,distributions):
    rows=[]
    for obs,dist in zip(y,distributions):
        upper=max(int(obs),int(dist.ppf(1-1e-11)));assert upper<100000 and dist.sf(upper)<=1e-10
        k=np.arange(upper+1);crps=float(np.sum((dist.cdf(k)-(k>=obs))**2));qu=dist.ppf([.05,.25,.75,.95]).astype(int)
        rows.append(dict(log_score=float(dist.logpmf(obs)),mean=float(dist.mean()),variance=float(dist.var()),crps=crps,q05=int(qu[0]),q25=int(qu[1]),q75=int(qu[2]),q95=int(qu[3])))
    return rows
def quadrature(order,d,terrain):
    nodes,w=hermgauss(order);z=np.stack(np.meshgrid(nodes,nodes,nodes,indexing='ij'),axis=-1).reshape(-1,3)*np.sqrt(2)
    lw=sum(np.meshgrid(np.log(w),np.log(w),np.log(w),indexing='ij')).ravel()-1.5*np.log(np.pi)
    L=np.linalg.cholesky(terrain['covariance']);beta=np.array(terrain['mode'])+z@L.T
    logq=-1.5*np.log(2*np.pi)-np.log(np.diag(L)).sum()-.5*(z*z).sum(1);x=np.array(d['design']);counts=np.array(d['y']);precision=1/np.square(d['coef_scale'])
    lp=[]
    for j in range(0,len(beta),2048):
        b=beta[j:j+2048];f=b@x.T;lp.extend(f@counts-d['exposure']*np.exp(f).sum(1)-.5*(b*b*precision).sum(1))
    corrected=lw+np.array(lp)-logq;weights=np.exp(corrected-logsumexp(corrected));return beta,weights
def gp_precision(y,rates):
    # rates: four chains x 4000 retained x 200; delta-method log probability MCSE.
    logp=poisson.logpmf(y[None,None,:],.8*rates);shift=logp.max((0,1));prob=np.exp(logp-shift)
    mcse=np.asarray(az.mcse(az.convert_to_dataset({'p':prob}),method='mean').p)/prob.mean((0,1))
    rate_mcse=np.asarray(az.mcse(az.convert_to_dataset({'p':rates}),method='mean').p)/rates.mean((0,1))
    score=np.log(prob.mean((0,1)))+shift
    return dict(log_score=score.tolist(),log_score_mcse=mcse.tolist(),mean_rate_relative_mcse=rate_mcse.tolist())
def summarize(y,rows):
    arr={k:np.array([r[k] for r in rows]) for k in rows[0]}
    return dict(mean_log_score=float(arr['log_score'].mean()),mean_crps=float(arr['crps'].mean()),rmse=float(np.sqrt(np.mean((arr['mean']-y)**2))),coverage50=float(np.mean((y>=arr['q25'])&(y<=arr['q75']))),coverage90=float(np.mean((y>=arr['q05'])&(y<=arr['q95']))),width50=float(np.mean(arr['q75']-arr['q25'])),width90=float(np.mean(arr['q95']-arr['q05'])))
def main():
    verify_freeze();frozen=json.loads((BASE/'SCORING-FREEZE.json').read_text())
    for name,h in frozen.items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
    assert json.loads((BASE/'training/REFERENCE.json').read_text())['passed']
    out=BASE/'scoring';out.mkdir(exist_ok=False);start=time.perf_counter()
    # First scientific access to heldout outcomes is here, after all freezes/gates.
    held=json.loads((BASE/'inputs/HELDOUT.json').read_text());assert held['exposure']==.8
    y=np.array(held['y']);d=data();assert y.shape==(200,) and (y>=0).all()
    model=GridGP(d);gp_rates=[]
    for root in GP_PATHS:
        q=np.load(root/'DRAWS.npz')['q'];v=physical(q,model);gp_rates.append(v[:,:,205:].copy());del v,q
    precision=[gp_precision(y,r) for r in gp_rates]
    a,b=precision;score_diff=abs(np.array(a['log_score'])-b['log_score']);se=np.sqrt(np.array(a['log_score_mcse'])**2+np.array(b['log_score_mcse'])**2)
    gp_checks=dict(log_score_mcse=all(max(r['log_score_mcse'])<=.02 for r in precision),rate_mcse=all(max(r['mean_rate_relative_mcse'])<=.01 for r in precision),replicate_scores=bool(np.all(score_diff<=np.maximum(.05,4*se))))
    rates=np.concatenate(gp_rates).reshape(-1,200);results={};failures={}
    results['gp']=mixture(y,lambda i:rates[:,i],np.ones(len(rates)),955000020)
    del rates,gp_rates
    terrain=json.loads((BASE/'inputs/TERRAIN.json').read_text());x=np.array(d['design']);terrain_scores={}
    for order in [32,48]:
        beta,w=quadrature(order,d,terrain)
        terrain_scores[order]=[float(logsumexp(np.log(w,where=w>0,out=np.full_like(w,-np.inf))+poisson.logpmf(obs,.8*np.exp(beta@x[i])))) for i,obs in enumerate(y)]
        if order==48:results['terrain']=mixture(y,lambda i:np.exp(beta@x[i]),w,955000021)
    difference=abs(np.array(terrain_scores[32])-terrain_scores[48]);terrain_ok=bool(max(difference)<=.02 and difference.mean()<=.005)
    cheap=json.loads((BASE/'inputs/CHEAP.json').read_text())
    for name in ['homogeneous','fixed_cell','empirical_bayes']:
        c=cheap[name];shapes=np.broadcast_to(c['shape'],(200,));b=c['rate'];results[name]=analytic(y,[nbinom(a,b/(b+.8)) for a in shapes])
    results['kernel']=analytic(y,[poisson(.8*r) for r in cheap['kernel']['rate']])
    approx=json.loads((BASE/'approximation_repair01/APPROXIMATION.json').read_text())
    if approx['valid']:
        try:
            q=np.load(BASE/'approximation_repair01/LAPLACE-DRAWS.npz')['q'];rates=physical(q.reshape(1,-1,205),model)[0,:,205:]
            results['laplace_gp']=mixture(y,lambda i:rates[:,i],np.ones(len(rates)),955000026)
        except (ValueError,OverflowError,AssertionError) as error:failures['laplace_gp']=str(error)
    else:failures['laplace_gp']='Training fit failed validity gate'
    summaries={name:summarize(y,rows) for name,rows in results.items()}
    blocks=np.array([(i//5)*2+j//5 for i in range(20) for j in range(10)]);rng=np.random.default_rng(955000030);bootstrap=rng.integers(0,8,size=(10000,8));comparisons=[]
    gp=np.array([r['log_score'] for r in results['gp']])
    for name,rows in results.items():
        if name=='gp':continue
        delta=gp-np.array([r['log_score'] for r in rows]);means=np.array([delta[blocks==b].mean() for b in range(8)]);boot=means[bootstrap].mean(1)
        comparisons.append(dict(competitor=name,gain=float(delta.mean()),lower=float(np.quantile(boot,.05/6)),upper=float(np.quantile(boot,1-.05/6)),block_means=means.tolist()))
    numerical=all(gp_checks.values()) and terrain_ok
    best_crps=min(v['mean_crps'] for k,v in summaries.items() if k!='gp');crps_improvement=1-summaries['gp']['mean_crps']/best_crps
    positive=numerical and all(r['gain']>=.05 and r['lower']>0 for r in comparisons) and crps_improvement>=.05
    result=dict(positive_predictive_value_pilot=bool(positive),numerical_pass=bool(numerical),gp_checks=gp_checks,terrain_quadrature_pass=terrain_ok,terrain_max_score_difference=float(max(difference)),summaries=summaries,comparisons=comparisons,crps_improvement_over_best=float(crps_improvement),unavailable_predictors=failures,precision=precision,seconds=time.perf_counter()-start,heldout_sha256=hashlib.sha256((BASE/'inputs/HELDOUT.json').read_bytes()).hexdigest(),scope='Historical same-site partial-census prediction; descriptive spatial-block uncertainty, no independent-site, decision or profit claim')
    write(out/'CELLS.json',dict(heldout=y.tolist(),predictors=results));write(out/'SUMMARY.json',result)
    verify_freeze()
    for name,h in frozen.items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
    print(json.dumps({k:v for k,v in result.items() if k not in ['precision']}),flush=True)
if __name__=='__main__':main()
