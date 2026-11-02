import time
START=time.monotonic()
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import arviz as az
from scipy.special import logsumexp,ndtr,roots_legendre,roots_hermitenorm
from backend import Backend,ROOT,physical,linear_prediction
from sampling import CONFIGS,fit

def features(q,pred):return np.column_stack([q,np.exp(q),pred])
def moment(q,pred,lw):
    w=np.exp(lw-logsumexp(lw));f=features(q,pred);mean=w@f;variance=w@((f-mean)**2)
    return dict(mean=mean.tolist(),sd=np.sqrt(variance).tolist(),probability=float(w@ndtr(pred[:,2]/.05)))
def diagnose(q,pred,info):
    f=features(q.reshape(-1,2),pred.reshape(-1,5)).reshape(*q.shape[:2],9)
    ds=az.convert_to_dataset({'p':f});st={k:np.asarray(fn(ds).p) for k,fn in [('rhat',lambda d:az.rhat(d,method='rank')),('bulk',lambda d:az.ess(d,method='bulk')),('tail',lambda d:az.ess(d,method='tail')),('mcse',lambda d:az.mcse(d,method='mean'))]}
    mean=f.mean((0,1));sd=f.reshape(-1,9).std(0,ddof=1);p=ndtr(pred[:,:,2]/.05)
    pmcse=0. if np.var(p)==0 else float(np.asarray(az.mcse(az.convert_to_dataset({'p':p}),method='mean').p))
    finite=all(np.isfinite(v).all() for v in st.values()) and np.isfinite(pmcse)
    passed=bool(finite and max(st['rhat'])<=1.01 and min(st['bulk'])>=400 and min(st['tail'])>=400 and info['divergences']==0 and info['depth_hits']==0)
    return dict(diagnostic_pass=passed,mean=mean.tolist(),sd=sd.tolist(),probability=float(p.mean()),probability_mcse=pmcse,
                max_mcse_sd=float(max(st['mcse']/sd)),**{k:v.tolist() for k,v in st.items()})

def grid(data,out):
    b=Backend(data);alltimes=np.r_[data['times'],data['future_times']];levels=[];start=time.monotonic()
    for n in [96,160,256]:
        nodes,weights=roots_legendre(n)
        a=-2+3*nodes;d=2*nodes
        q=np.stack(np.meshgrid(a,d,indexing='ij'),axis=-1).reshape(-1,2)
        lw=(np.log(weights)[:,None]+np.log(weights)[None,:]+np.log(6)).ravel()
        if data['linear']:trajectory=linear_prediction(q,alltimes,data['theta'])
        else:trajectory=b.predict_batch(q,alltimes)
        pred=trajectory[:,6:];lp=-.5*np.sum(((trajectory[:,:6]-data['observed'])/.05)**2,axis=1)-.5*np.sum(((q-np.log([.2,2.]))/[.8,.5])**2,axis=1)
        lw=lw+lp;r=moment(q,pred,lw);r.update(order=n,log_normalizer=float(logsumexp(lw)));levels.append(r)
        print(json.dumps(dict(event='grid',order=n)),flush=True)
    last,previous=levels[-1],levels[-2];sd=np.array(last['sd'])
    differences=dict(log_normalizer=abs(last['log_normalizer']-previous['log_normalizer']),
                     mean_sd=float(max(abs(np.array(last['mean'])-previous['mean'])/sd)),
                     sd_relative=float(max(abs(sd-previous['sd'])/sd)),
                     angle_mean=float(max(abs(np.array(last['mean'][4:])-previous['mean'][4:]))),
                     probability=abs(last['probability']-previous['probability']))
    passed=differences['log_normalizer']<=1e-4 and differences['mean_sd']<=.002 and differences['sd_relative']<=.005 and differences['angle_mean']<=1e-4 and differences['probability']<=1e-4
    np.savez_compressed(out/'draws.npz',q=q,pred=pred,logweights=lw)
    b.close();return dict(reference_pass=bool(passed),levels=levels,summary=last,differences=differences,seconds=time.monotonic()-start,shared_preparation_seconds=0.)

def main(phase,case,config,rep,destination):
    out=Path(destination);out.mkdir(exist_ok=False);case=int(case);rep=int(rep)
    frozen=json.loads((ROOT/'CAMPAIGN-MANIFEST.json').read_text())['sources']
    assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in frozen.items())
    data=json.loads((ROOT/'data'/f'case{case}.json').read_text());data['linear']=config=='linear'
    tag=f'case{case}'+('-linear' if data['linear'] else '')
    result=dict(phase=phase,case=case,config=config,rep=rep,import_seconds=time.monotonic()-START)
    if phase=='grid':result.update(grid(data,out))
    elif phase=='laplace_grid':
        prep=json.loads((ROOT/'prepared'/(tag+'.json')).read_text());before=time.monotonic();b=Backend(data);levels=[]
        for order in [24,40]:
            nodes,weights=roots_hermitenorm(order)
            z=np.stack(np.meshgrid(nodes,nodes,indexing='ij'),axis=-1).reshape(-1,2)@np.array(prep['L']).T+prep['mode']
            q=physical(z);lw=(np.log(weights)[:,None]+np.log(weights)[None,:]-np.log(2*np.pi)).ravel()
            pred=linear_prediction(q,data['future_times'],data['theta']) if data['linear'] else b.predict_batch(q)
            row=moment(q,pred,lw);row['order']=order;levels.append(row)
        b.close();a,c=levels;sd=np.array(c['sd'])
        differences=dict(mean_sd=float(max(abs(np.array(c['mean'])-a['mean'])/sd)),sd_relative=float(max(abs(sd-a['sd'])/sd)),angle_mean=float(max(abs(np.array(c['mean'][4:])-a['mean'][4:]))),probability=abs(c['probability']-a['probability']))
        ok=differences['mean_sd']<=.002 and differences['sd_relative']<=.005 and differences['angle_mean']<=1e-4 and differences['probability']<=1e-4
        np.savez_compressed(out/'draws.npz',z=z,q=q,pred=pred,logweights=lw)
        result.update(approximation_quadrature_pass=bool(ok),levels=levels,summary=c,differences=differences,seconds=time.monotonic()-before,shared_preparation_seconds=prep['seconds'])
    else:
        prep=json.loads((ROOT/'prepared'/(tag+'.json')).read_text());before=time.monotonic()
        if phase=='laplace':
            seed=953300000+2*case+int(data['linear']);z=np.random.default_rng(seed).normal(size=(4,16384,2))@np.array(prep['L']).T+prep['mode']
            info=dict(seconds=time.monotonic()-before,target_calls=0,solver_errors=0,divergences=0,depth_hits=0)
        else:
            seed=953100000+100*case+list(CONFIGS).index(config) if phase=='calibrate' else 953200000+100*case+rep
            draws,warmup=(400,300) if phase=='calibrate' else (1000,500)
            z,info=fit(data,prep,config,seed,draws,warmup)
        q=physical(z);b=Backend(data);pred=b.predict_batch(q.reshape(-1,2)).reshape(*q.shape[:2],5);b.close()
        summary=diagnose(q,pred,info)
        np.savez_compressed(out/'draws.npz',z=z,q=q,pred=pred)
        result.update(seed=seed,**info,summary=summary,postprocess_seconds=time.monotonic()-before-info['seconds'],shared_preparation_seconds=prep['seconds'])
    result['worker_seconds']=time.monotonic()-START
    result['total_seconds']=result['worker_seconds']+result['shared_preparation_seconds']
    assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in frozen.items())
    (out/'RESULT.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ['phase','case','config','total_seconds']}),flush=True)
if __name__=='__main__':main(*sys.argv[1:])
