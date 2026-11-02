"""Bounded, CPU-weighted dispatcher for existing EC2 capacity only."""
import concurrent.futures as cf
import hashlib,json,os,shutil,sys,time
from pathlib import Path
from resource_monitor import execute

BASE=Path(__file__).resolve().parent
PYTHON='/home/ubuntu/venv/bin/python'

def write(name,value):
    temporary=BASE/(name+'.tmp');temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.replace(BASE/name)

def main():
    sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in BASE.iterdir() if p.suffix in ['.py','.json','.md'] and p.name not in ['STATUS.json','LIVE.json']}
    write('SPATIAL-SOURCES.json',sources)
    pre=BASE/'results/grid_preflight';pre.mkdir(exist_ok=False)
    status=execute([PYTHON,str(BASE/'grid_preflight.py'),str(BASE/'GP-TRAIN.json'),str(pre/'SUMMARY.json')],BASE,120,pre,2*1024**3,4*1024**2,pre/'worker.log',output_scan_interval=2.)
    write('GRID-SUPERVISION.json',status)
    if status.get('exit_code')!=0 or not json.loads((pre/'SUMMARY.json').read_text())['passed']:
        write('STATUS.json',dict(status='preflight_failed'));return
    jobs=[]
    for method in ['nuts','blocked_grid1','blocked_grid4','blocked_dense']:
        for seed in [954100001,954100002]:jobs.append(dict(method=method,seed=seed,cores=4 if method=='nuts' else 1))
    rows=[];running={};used=0
    with cf.ThreadPoolExecutor(max_workers=12) as pool:
        while jobs or running:
            for job in jobs[:]:
                if used+job['cores']>12:continue
                total=sum(p.stat().st_size for p in BASE.rglob('*') if p.is_file())
                if shutil.disk_usage(BASE).free<1024**3 or total>200*1024**2:
                    rows.extend(dict(**j,status='not_launched_resource_floor') for j in jobs);jobs.clear();break
                name=f"{job['method']}-{job['seed']}";out=BASE/'results'/name;out.mkdir(exist_ok=False)
                future=pool.submit(execute,[PYTHON,str(BASE/'spatial_worker.py'),job['method'],str(job['seed']),str(out/'artifact')],BASE,900,out,2*1024**3,24*1024**2,out/'worker.log',output_scan_interval=2.)
                running[future]=(job,out);used+=job['cores'];jobs.remove(job)
            for future in list(running):
                if not future.done():continue
                job,out=running.pop(future);used-=job['cores'];result=future.result()
                (out/'SUPERVISION.json').write_text(json.dumps(result,indent=2)+'\n');rows.append(dict(**job,**result,path=str(out)))
            write('LIVE.json',dict(time=time.time(),used_cores=used,pending=jobs,running=[j for j,_ in running.values()],completed=rows,disk_free=shutil.disk_usage(BASE).free))
            time.sleep(2)
    write('STATUS.json',dict(status='completed',rows=rows))

if __name__=='__main__':main()
