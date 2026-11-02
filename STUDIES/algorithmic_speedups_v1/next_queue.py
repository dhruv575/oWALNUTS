import concurrent.futures as cf,json,shutil,hashlib
from followup_campaign import BASE,PY
from resource_monitor import execute
def run(name,script,args,limit):
    out=BASE/'next01'/name;out.mkdir(parents=True,exist_ok=False)
    result=execute([PY,str(BASE/script),*args,str(out/'artifact')],BASE,900,out,2*1024**3,limit*1024**2,out/'worker.log',output_scan_interval=2.)
    (out/'SUPERVISION.json').write_text(json.dumps(result,indent=2));return dict(name=name,**result)
if __name__=='__main__':
    assert shutil.disk_usage(BASE).free>1024**3
    assert sum(f.stat().st_size for f in BASE.rglob('*') if f.is_file())+30*1024**2<200*1024**2
    (BASE/'NEXT-SOURCES.json').write_text(json.dumps({f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in BASE.iterdir() if f.suffix in ['.py','.cpp','.so','.md']},indent=2))
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(run,'confirmation-954100005','grid_precision_worker.py',['nuts_grid','954100005'],28),pool.submit(run,'scaling','scaling_worker.py',[],2)]
        rows=[f.result() for f in jobs]
    (BASE/'NEXT-STATUS.json').write_text(json.dumps(rows,indent=2))
