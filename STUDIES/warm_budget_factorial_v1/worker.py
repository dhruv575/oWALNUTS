import argparse,hashlib,importlib.util,json,sys,time
from pathlib import Path
import numpy as np
from linear_runner import run_lane

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,name):
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def settings(j):
    if not 0<=j<12:raise ValueError('Fixed job range')
    m=j//4;r=(j%4)//2;k=(400,1600)[j%2];initial=4072800000000000000+100000*(2*m+r)
    return m,r,k,dict(initial=initial,warm=initial+10000)
def run(parent,j,out,literal=False):
    spec=json.loads(Path(parent).read_bytes());m,r,k,seeds=settings(j)
    sys.path.insert(0,str(Path(spec['worker_path']).parent))
    import data_contract,owalnuts
    month=spec['months'][m];data_contract.configure(month['month'])
    target=load(spec['dependencies']['target'],'factorial_target')
    evaluator=load(spec['dependencies']['predictive_density'],'factorial_density')
    adapter=load(Path(__file__).with_name('resident_adapter.py'),'factorial_resident')
    if literal:
        y=np.resize(np.array([.001,-.002,.0005,0.,.003],dtype=np.float64),253);updates=2;ticks=[1,2];seeds=dict(initial=904028000+j*100,warm=904028010+j*100)
    else:y=data_contract.load_sealed(spec['acquisition'],month['month']);updates=month['origins'];ticks=month['reference_ticks']
    def score(draws,window,label,tick):
        return dict(evaluator.evaluate_observation(draws,label,rho=.95,nu=5,orders=(64,128),chunk=512,deadline=time.monotonic()+20),status='ok')
    result=run_lane(y,updates=updates,seeds=seeds,score_ticks=ticks,retain_ticks=ticks,
        engine_factory=lambda history,s:adapter.DrawResident(owalnuts,target,history,s),score_hook=score,output=Path(out),k=k)
    print(json.dumps(dict(job=j,month=month['month'],replicate=r,k=k,result=result)),flush=True)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('parent');p.add_argument('job',type=int);p.add_argument('out');p.add_argument('--literal',action='store_true');p.add_argument('--manifest');a=p.parse_args()
    if not a.literal:
        if not a.manifest:raise ValueError('Frozen manifest required')
        manifest=json.loads(Path(a.manifest).read_bytes())
        if sha(a.parent)!=manifest['parent_sha256']:raise ValueError('Parent drift')
        for name,want in manifest['new_sources'].items():
            if sha(name)!=want:raise ValueError('New source drift')
    raise SystemExit(0 if run(a.parent,a.job,a.out,a.literal)['status']=='complete' else 1)
