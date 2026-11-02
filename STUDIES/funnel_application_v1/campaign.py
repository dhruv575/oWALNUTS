import os,json,sys,time,hashlib,shutil,concurrent.futures as cf
from pathlib import Path
from resource_monitor import execute
BASE=Path(__file__).resolve().parent
PY='/home/ubuntu/lanes/unified-readiness-20261027/installation02/work/env/bin/python'
def run(name,script,args):
    root=BASE/name;root.mkdir(parents=True,exist_ok=False)
    result=execute([PY,str(BASE/script),*args],BASE,900,BASE,2*1024**3,28*1024**2,root/'worker.log',output_scan_interval=2.)
    (root/'SUPERVISION.json').write_text(json.dumps(result,indent=2));return result
def cell(case,engine,space,accept,seed,phase):
    name=f'{phase}/{case}-{engine}-{space}-{accept}-{seed}';out=BASE/name/'artifact';r=run(name,'worker.py',[case,engine,space,str(accept),str(seed),phase,str(out)])
    if r['exit_code']==0:return json.loads((out/'SUMMARY.json').read_text())
    return dict(case=case,engine=engine,space=space,accept=accept,seed=seed,phase=phase,failed=r)
def main():
    assert shutil.disk_usage(BASE).free>1024**3+28*1024**2
    sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in BASE.iterdir() if p.is_file() and p.suffix in ['.py','.cpp','.so','.json','.md']}
    (BASE/'FREEZE.json').write_text(json.dumps(sources,indent=2))
    r=run('reference-supervision','reference.py',[])
    if r['exit_code']!=0 or not all(json.loads((BASE/'references'/(c+'.json')).read_text())['passed'] for c in ['weak','mixed']):
        (BASE/'STATUS.json').write_text(json.dumps(dict(status='reference_failed')));return
    run('laplace-supervision','laplace.py',[])
    jobs=[(case,engine,space,a,956100001+i,'calibration') for i,case in enumerate(['weak','mixed']) for space in ['centered','noncentered','hybrid'] for a in [.9,.99] for engine in ['nuts','walnuts']]
    with cf.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(lambda args:cell(*args),jobs))
    selected={}
    for case in ['weak','mixed']:
        for engine in ['nuts','walnuts']:
            candidates=[r for r in rows if r['case']==case and r['engine']==engine and 'summary' in r]
            if not candidates:continue
            def key(r):
                s=r['summary'];values=[v for k in ['bulk','tail'] for v in s['stats'][k] if v is not None];return (s['passed'],min(values)/r['kernel_seconds'] if values else 0.)
            selected[case+'-'+engine]=max(candidates,key=key)
    (BASE/'SELECTION.json').write_text(json.dumps(selected,indent=2))
    validation=[]
    for i,case in enumerate(['weak','mixed']):
        for rep in [1,2]:
            for engine in (['nuts','walnuts'] if rep==1 else ['walnuts','nuts']):
                if case+'-'+engine not in selected:continue
                s=selected[case+'-'+engine];validation.append(cell(case,engine,s['space'],s['accept'],956200000+(i+1)*10+rep,'validation'))
    assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in sources.items())
    (BASE/'STATUS.json').write_text(json.dumps(dict(status='completed',calibration=rows,validation=validation),indent=2))
if __name__=='__main__':main()
