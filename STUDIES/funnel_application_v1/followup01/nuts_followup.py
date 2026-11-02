import sys,json,hashlib,shutil
from pathlib import Path
BASE=Path('/home/ubuntu/lanes/funnel-application-20261101');OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE))
from resource_monitor import execute
PY='/home/ubuntu/lanes/unified-readiness-20261027/installation02/work/env/bin/python'
if __name__=='__main__':
    assert shutil.disk_usage(BASE).free>1024**3
    files=[BASE/n for n in ['worker.py','backend.py','model.so','model.cpp','reference.py','weak.json','mixed.json']]+[OUT/'nuts_followup.py',OUT/'NUTS-FOLLOWUP.md']
    freeze={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files};(OUT/'FREEZE.json').write_text(json.dumps(freeze,indent=2));rows=[]
    for i,case in enumerate(['weak','mixed']):
        for rep in [1,2]:
            arms=[('nuts',space,accept) for space in ['noncentered','hybrid'] for accept in [.99,.999]]
            if rep==1:arms.insert(0,('walnuts','noncentered',.9))
            else:arms.append(('walnuts','noncentered',.9))
            seed=956400000+(i+1)*10+rep
            for engine,space,accept in arms:
                root=OUT/f'{case}-{engine}-{space}-{accept}-{seed}';root.mkdir(exist_ok=False)
                result=execute([PY,str(BASE/'worker.py'),case,engine,space,str(accept),str(seed),'followup',str(root/'artifact')],BASE,900,OUT,2*1024**3,64*1024**2,root/'worker.log',output_scan_interval=2.)
                (root/'SUPERVISION.json').write_text(json.dumps(result,indent=2));rows.append(dict(case=case,engine=engine,space=space,accept=accept,seed=seed,**result))
                (OUT/'LIVE.json').write_text(json.dumps(rows,indent=2))
    assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in freeze.items())
    (OUT/'STATUS.json').write_text(json.dumps(dict(status='completed',rows=rows),indent=2))
