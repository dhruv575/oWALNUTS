"""One fixed specialist market chain; outer containment is mandatory."""
import argparse
import json
from pathlib import Path
import sys
import time
import numpy as np
from development import Target,Priors,EvaluationBudget,sweep,sweep_interwoven,sha,write
from blocked_path import sweep_blocked


def decode(index,methods=(0,1)):
    if tuple(methods) not in ((0,1),(2,)):raise ValueError('Declared method panel')
    width=4*len(methods)
    if type(index) is not int or not 0<=index<24*width:raise ValueError('Chain index')
    return index//width,methods[(index%width)//4],index%4


def sample(window,method,seed,*,warmup=1000,retained=2000,cap=295,function=None):
    if np.asarray(window).shape!=(250,) or not np.isfinite(window).all():raise ValueError('Finite T250 window required')
    if method not in (0,1,2):raise ValueError('Method')
    model=Target(window,np.ones((250,1)),np.empty((250,0)),np.ones(250,dtype=bool),rho=.95,nu=5.,
                 priors=Priors(2*np.log(.005),1.,np.log(.2),.5,.002,.03))
    q=np.r_[model.priors.mu_mean,model.priors.log_sigma_mean,0.,np.zeros(250)]
    rng=np.random.default_rng(seed);budget=EvaluationBudget(2000000)
    function=function or (sweep,sweep_interwoven,sweep_blocked)[method]
    full=[];compact=[];started=time.monotonic();result=dict(status='incomplete',completed_sweeps=0)
    try:
        for step in range(warmup+retained):
            if time.monotonic()-started>cap:raise TimeoutError('Fixed chain time cap')
            q,_=function(model,q,rng,budget=budget)
            if q.shape!=(253,) or not np.isfinite(q).all():raise ValueError('Invalid sampler state')
            result['completed_sweeps']=step+1
            if step>=warmup:
                full.append(q.copy());compact.append(np.r_[q[:3],model.path(q)[-1]])
        result['status']='complete'
    except Exception as exc:result['error']=repr(exc)
    result.update(seconds=time.monotonic()-started,retained=len(full),evaluations=budget.calls)
    return result,np.asarray(full).reshape(-1,253),np.asarray(compact).reshape(-1,4)


def run(manifest,index,out):
    manifest=Path(manifest);spec=json.loads(manifest.read_bytes())
    if spec.get('status')!='frozen_authorized':raise ValueError('Frozen campaign required')
    for name,digest in spec['sources'].items():
        if sha(name)!=digest:raise ValueError('Frozen source drift')
    methods=spec.get('methods',[0,1]);spot,method,chain=decode(index,methods);item=spec['windows'][spot]
    if len(spec['windows'])!=24 or len(spec['seeds'])!=96*len(methods):raise ValueError('Fixed denominators')
    path=Path(item['file'])
    if sha(path)!=item['sha256']:raise ValueError('Window drift')
    with np.load(path,allow_pickle=False) as data:window=data['window'].copy()
    root=Path(out);root.mkdir(exist_ok=False)
    write(root/'STARTED.json',dict(index=index,spot=spot,method=method,chain=chain,seed=spec['seeds'][index],manifest_sha256=sha(manifest),window_sha256=item['sha256']))
    result,full,compact=sample(window,method,spec['seeds'][index])
    np.savez_compressed(root/'draws.npz',full=full,compact=compact)
    result.update(index=index,spot=spot,method=method,chain=chain,arrays_sha256=sha(root/'draws.npz'))
    write(root/'FINAL.json',result)
    return 0 if result['status']=='complete' else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('index',type=int);p.add_argument('out');a=p.parse_args()
    raise SystemExit(run(a.manifest,a.index,a.out))
