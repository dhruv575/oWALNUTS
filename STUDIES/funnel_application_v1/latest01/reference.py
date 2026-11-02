"""Independent conditional quadrature; no sampler draws used as a reference."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import json,time
from pathlib import Path
import numpy as np
from scipy.special import expit,logit,logsumexp
from numpy.polynomial.hermite import hermgauss
from numpy.polynomial.legendre import leggauss
BASE=Path(__file__).resolve().parent
def integrate(data,orders,bounds=(-16.,3.),width=1.):
    nh,nm,nt=orders;n=np.array(data['n']);y=np.array(data['y']);pseudo=(y+.5)/(n+1);observed=logit(pseudo);variance=1/(n*pseudo*(1-pseudo))
    ln,lw=leggauss(nh);hn,hw=hermgauss(nm);tn,tw=hermgauss(nt);z=tn*np.sqrt(2);logtw=np.log(tw)-.5*np.log(np.pi)
    hs=[];hweights=[]
    edges=[bounds[0],np.log(.1),np.log(.5),bounds[1]]
    for low,high in zip(edges[:-1],edges[1:]):hs.extend((low+high)/2+(high-low)*ln/2);hweights.extend(lw*(high-low)/2)
    h=np.array(hs);tau=np.exp(h);prec=1/(tau[:,None]**2+variance);v=1/(.25+prec.sum(1));m=v*(prec@observed);s=np.sqrt(v)*width
    mu=m[:,None]+s[:,None]*np.sqrt(2)*hn;tt=np.broadcast_to(tau[:,None],mu.shape);hh=np.broadcast_to(h[:,None],mu.shape)
    logweights=np.log(np.array(hweights))[:,None]+np.log(hw)[None,:]-.5*np.log(np.pi)
    logq=-.5*(np.sqrt(2)*hn[None,:])**2-np.log(s[:,None])-.5*np.log(2*np.pi)
    outer=logweights-logq-mu*mu/8+hh-tt*tt/2
    mu=mu.ravel();tt=tt.ravel();outer=outer.ravel();first=[];second=[];joint=[];max_step=0.
    for lo in range(0,len(mu),256):
        mm=mu[lo:lo+256,None];t=tt[lo:lo+256,None];t2=t*t;mode=np.broadcast_to(mm,(len(mm),12)).copy()
        for iteration in range(40):
            p=expit(mode);gradient=y-n*p-(mode-mm)/t2;H=n*p*(1-p)+1/t2;step=gradient/H;mode+=np.clip(step,-5,5)
            if np.max(abs(step))<1e-10:break
        max_step=max(max_step,float(np.max(abs(step))));p=expit(mode);scale=1/np.sqrt(n*p*(1-p)+1/t2)
        theta=mode[:,:,None]+scale[:,:,None]*z;prob=expit(theta)
        likelihood=y[None,:,None]*theta-n[None,:,None]*np.logaddexp(0,theta)
        ratios=likelihood-.5*((theta-mm[:,:,None])/t[:,:,None])**2-np.log(t[:,:,None])+.5*z*z+np.log(scale[:,:,None])
        weights=ratios+logtw;normalizer=logsumexp(weights,axis=2);w=np.exp(weights-normalizer[:,:,None]);mt=(w*theta).sum(2);st=(w*theta*theta).sum(2);mp=(w*prob).sum(2);sp=(w*prob*prob).sum(2)
        small=(t<.1).astype(float);medium=(t<.5).astype(float)
        first.append(np.c_[mm,t,mt,mp,small,medium]);second.append(np.c_[mm*mm,t*t,st,sp,small,medium]);joint.extend(outer[lo:lo+256]+normalizer.sum(1))
    joint=np.array(joint);w=np.exp(joint-logsumexp(joint));first=np.concatenate(first);second=np.concatenate(second);mean=w@first;sd=np.sqrt(np.maximum(0,w@second-mean*mean))
    return dict(orders=list(orders),bounds=list(bounds),width=width,log_normalizer=float(logsumexp(joint)),mean=mean.tolist(),sd=sd.tolist(),max_conditional_newton_step=max_step)
def differences(a,b):
    mean=np.array(a['mean']);sd=np.array(a['sd']);delta=abs(mean-b['mean']);return dict(log_normalizer=abs(a['log_normalizer']-b['log_normalizer']),mean_sd=float(max(delta[:26]/sd[:26])),relative_sd=float(max(abs(sd[:26]-np.array(b['sd'])[:26])/sd[:26])),probability=float(max(delta[26:])))
def qualified(d):return d['log_normalizer']<=1e-4 and d['mean_sd']<=.002 and d['relative_sd']<=.005 and d['probability']<=.001
def main():
    out=BASE/'references';out.mkdir(exist_ok=False)
    for case in ['mixed','mixed10','mixed100']:
        start=time.perf_counter();data=json.loads((BASE/(case+'.json')).read_text());levels=[integrate(data,o) for o in [(32,32,24),(48,48,40),(72,64,64)]]
        expanded=integrate(data,(72,64,64),(-20.,3.5),1.25);conv=differences(levels[-1],levels[-2]);domain=differences(levels[-1],expanded)
        result=dict(passed=qualified(conv) and qualified(domain),levels=levels,expanded=expanded,convergence=conv,domain_check=domain,mean=levels[-1]['mean'],sd=levels[-1]['sd'],seconds=time.perf_counter()-start)
        (out/(case+'.json')).write_text(json.dumps(result,indent=2));print(json.dumps(dict(case=case,passed=result['passed'],convergence=conv,domain=domain,seconds=result['seconds'])),flush=True)
if __name__=='__main__':main()
