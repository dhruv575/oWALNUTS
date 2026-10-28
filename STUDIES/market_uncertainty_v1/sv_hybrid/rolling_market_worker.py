"""Six fixed complete-path NUTS comparators; no selective restart."""
import argparse,importlib.metadata,json,sys,time
from pathlib import Path
from literal_reference import sha,load
from rolling_nutpie_adapter import DrawResident

def settings(index):
    if type(index) is not int or not 0<=index<6:raise ValueError('Fixed six paths')
    base=705000000+100000*index
    return index//2,index%2,dict(initial=base,warm=base+10000)

def reserved_seeds():
    result=[]
    for index in range(6):
        month,_,seeds=settings(index);result.extend([seeds['initial'],seeds['initial']+1])
        for tick in range((1488,1488,1344)[month]):result.extend([seeds['warm']+4*tick,seeds['warm']+4*tick+1])
    return result

def validate(path):
    spec=json.loads(Path(path).read_bytes())
    if spec['status']!='frozen_authorized' or spec['paths']!=6:raise ValueError('Fixed campaign')
    for name,digest in spec['sources'].items():
        if sha(name)!=digest:raise ValueError('Frozen source drift')
    parent=json.loads(Path(spec['parent']).read_bytes())
    for name,digest in parent['sources'].items():
        if sha(name)!=digest:raise ValueError('Inherited source drift')
    runtime=parent['runtime']
    if sys.prefix!=runtime['prefix']:raise ValueError('Runtime prefix drift')
    for name,version in runtime['packages'].items():
        if importlib.metadata.version(name)!=version:raise ValueError('Runtime package drift')
    for name,digest in runtime['binaries'].items():
        if sha(name)!=digest:raise ValueError('Runtime binary drift')
    if [m['origins'] for m in parent['months']]!=[1488,1488,1344]:raise ValueError('Fixed path lengths')
    audit=json.loads(Path(spec['audit']).read_bytes())
    if audit['status']!='passed' or audit['collisions'] or audit['reserved_seeds']!=reserved_seeds():raise ValueError('Complete seed schedule audit')
    return spec,parent

def run(manifest,index,out):
    spec,parent=validate(manifest);month_index,replicate,seeds=settings(index);month=parent['months'][month_index]
    sys.path.insert(0,str(Path(parent['worker_path']).parent));sys.path.append(parent['e62_root'])
    import data_contract
    data_contract.configure(month['month']);y=data_contract.load_sealed(parent['acquisition'],month['month'])
    loop=load(spec['linear_runner'],'rolling_fixed_loop');evaluator=load(parent['dependencies']['predictive_density'],'rolling_fixed_density')
    reference=dict(parent['reference']);reference['adapter']=spec['adapter']
    out=Path(out)
    def score(draws,window,label,tick):
        return dict(evaluator.evaluate_observation(draws,label,deadline=time.monotonic()+20),status='ok')
    result=loop.run_lane(y,updates=month['origins'],seeds=seeds,score_ticks=month['reference_ticks'],retain_ticks=month['reference_ticks'],k=400,
        output=out/'lane',score_hook=score,engine_factory=lambda history,seed_map:DrawResident(history,seed_map,reference,out/'nutpie',month['reference_ticks']))
    print(json.dumps(dict(index=index,month=month['month'],replicate=replicate,result=result)),flush=True)
    return 0 if result['status']=='complete' else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('index',type=int);p.add_argument('out');a=p.parse_args()
    raise SystemExit(run(a.manifest,a.index,a.out))
