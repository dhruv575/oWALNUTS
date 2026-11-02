"""Two native spatial baselines (8 CPUs) and two physics workers (2 CPUs).
The original dispatcher may still have two dense controls: combined cap 12.
"""
import os,json,hashlib,concurrent.futures as cf
from pathlib import Path
from resource_monitor import execute
BASE=Path(__file__).resolve().parent
os.environ['LD_LIBRARY_PATH']='/home/ubuntu/lanes/gp-portable-runtime-20261030/models'
PY='/home/ubuntu/venv/bin/python'
PHYS='/home/ubuntu/lanes/unified-readiness-20261027/installation02/work/env/bin/python'
def run(script,method,seed,parent,python):
    out=BASE/parent/f'{method}-{seed}' if method!='prepare' else BASE/parent/'prepare'
    out.mkdir(parents=True,exist_ok=False)
    result=execute([python,str(BASE/script),method,str(seed),str(out/'artifact')],BASE,900,out,2*1024**3,24*1024**2,out/'worker.log',output_scan_interval=2.)
    (out/'SUPERVISION.json').write_text(json.dumps(result,indent=2));return dict(method=method,seed=seed,**result)
def physics():
    pre=run('physics_worker.py','prepare',954200000,'physics',PHYS)
    if pre['exit_code']!=0:return [pre]
    methods=['mh_affine','da_affine','mh_transport','da_transport','nuts_raw','nuts_affine','nuts_transport','walnuts_raw','walnuts_affine','walnuts_transport']
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(run,'physics_worker.py',m,s,'physics',PHYS) for m in methods for s in [954200001,954200002]]
        return [pre]+[f.result() for f in jobs]
def main():
    (BASE/'FOLLOWUP-SOURCES.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in BASE.iterdir() if p.suffix in ['.py','.cpp','.md','.so']},indent=2))
    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        jobs=[pool.submit(run,'spatial_worker.py','nuts',s,'repair01',PY) for s in [954100001,954100002]]
        physics_job=pool.submit(physics)
        rows=[f.result() for f in jobs]+physics_job.result()
    (BASE/'FOLLOWUP-STATUS.json').write_text(json.dumps(rows,indent=2))
if __name__=='__main__':main()
