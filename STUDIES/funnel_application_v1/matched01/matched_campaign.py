import os,sys,json,hashlib,concurrent.futures as cf,shutil
from pathlib import Path
BASE=Path(__file__).resolve().parent
sys.path.insert(0,'/home/ubuntu/lanes/funnel-application-20261101')
from resource_monitor import execute
PY='/home/ubuntu/venv/bin/python'
def fit(case,engine,accept,seed,draws,phase):
    out=BASE/phase/f'{case}-{engine}-{accept}-{seed}-{draws}';out.mkdir(parents=True,exist_ok=False)
    result=execute([PY,str(BASE/'budget_worker.py'),case,engine,'noncentered',str(accept),str(seed),'budget_'+str(draws),str(out/'artifact')],BASE,900,BASE,2*1024**3,128*1024**2,out/'worker.log',output_scan_interval=2.)
    (out/'SUPERVISION.json').write_text(json.dumps(result,indent=2))
    return json.loads((out/'artifact/SUMMARY.json').read_text()) if result['exit_code']==0 else dict(failed=result,case=case,engine=engine,seed=seed,draws=draws,accept=accept)
def block(case,index,rep,selection,cpu):
    os.sched_setaffinity(0,{cpu});seed=956500000+10*(index+1)+rep;rows=[]
    for draws in [1000,2000,4000]:
        for engine in (['walnuts','nuts'] if rep%2 else ['nuts','walnuts']):rows.append(fit(case,engine,.9 if engine=='walnuts' else selection[case]['accept'],seed,draws,'confirmation'))
    return rows
def lane(jobs,selection,cpu):
    rows=[]
    for case,index,rep in jobs:rows.extend(block(case,index,rep,selection,cpu))
    return rows
if __name__=='__main__':
    assert shutil.disk_usage('/home/ubuntu').free>1024**3
    files=[p for p in BASE.rglob('*') if p.is_file() and p.suffix in ['.py','.cpp','.so','.json','.md']]+[Path('/home/ubuntu/lanes/funnel-application-20261101/model.so')]
    freeze={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files};(BASE/'FREEZE.json').write_text(json.dumps(freeze,indent=2))
    cpu_ids=sorted(os.sched_getaffinity(0))[:4]
    calibration=[];selection={}
    for index,case in enumerate(['weak','mixed']):
        rows=[fit(case,'nuts',a,956600001+index,4000,'calibration') for a in [.9,.99,.999]];calibration.extend(rows);passed=[r for r in rows if 'summary' in r and r['summary']['passed']]
        selected=min(passed,key=lambda r:r['kernel_seconds']) if passed else dict(accept=.999)
        selection[case]=dict(accept=selected['accept'],qualified=bool(passed))
    (BASE/'SELECTION.json').write_text(json.dumps(dict(selection=selection,calibration=calibration),indent=2))
    jobs=[(case,index,rep) for index,case in enumerate(['weak','mixed']) for rep in range(1,9)]
    with cf.ProcessPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(lane,jobs[i::4],selection,cpu_ids[i]) for i in range(4)];rows=[r for f in futures for r in f.result()]
    assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in freeze.items())
    (BASE/'STATUS.json').write_text(json.dumps(dict(status='completed',selection=selection,confirmation=rows),indent=2))
