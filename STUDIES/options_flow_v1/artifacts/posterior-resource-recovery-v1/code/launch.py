"""One immutable, contained posthoc analysis attempt; never retries."""
import argparse,hashlib,json,os,subprocess,time,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def save(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False)

def launch(path,timeout=1800):
    path=Path(path).resolve();digest=sha(path);spec=json.loads(path.read_text());base=Path(spec['out'])
    if path.with_suffix('.sha256').read_text().strip()!=digest:raise ValueError('Frozen recovery spec required')
    for suffix in ['', '-started.json','-hardware.json','-status.json','-exit.json','.log']:
        if Path(str(base)+suffix).exists():raise ValueError('Never overwrite/retry recovery')
    tick=time.perf_counter();record=dict(status='failed',posthoc=True,resampled=False,qualified=False,spec_sha256=digest)
    hp=Path(str(base)+'-hardware.json');args=[spec['python'],str(Path(spec['archived_study_directory'])/'hardware_control.py'),'--cpus','0','--record',str(hp),'--timeout',str(timeout),'--',spec['python'],str(HERE/'recover.py'),'--spec',str(path)]
    save(str(base)+'-started.json',dict(record,command=args,original_status=spec['original_status']))
    try:
        if not 0<timeout<=1800:raise ValueError('Bounded remaining deadline required')
        if spec['timeout_seconds']!=1800 or spec['memory_bytes']!=8*1024**3:raise ValueError('Resource policy mismatch')
        if any(sha(p)!=v for p,v in spec['launcher_inputs'].items()):raise ValueError('Recovery launcher/source changed')
        with Path(str(base)+'.log').open('x') as log:r=subprocess.run(args,cwd=HERE,env=dict(os.environ,PYTHONPATH=spec['archived_study_directory']),stdout=log,stderr=subprocess.STDOUT)
        record['returncode']=r.returncode;save(str(base)+'-exit.json',dict(returncode=r.returncode,spec_sha256=digest))
        h=json.loads(hp.read_text())
        sys.path.insert(0,spec['archived_study_directory'])
        from asof_rolling_execute import validate_hardware
        validate_hardware(h,args,r.returncode,timeout)
        if h['command']!=args[args.index('--')+1:] or h['returncode']!=r.returncode or h['job_active_processes_after_cleanup']!=0 or h['realized_cpus']!=[0] or h['containment']['assigned_before_worker_execution'] is not True:raise ValueError('Containment evidence mismatch')
        if h['status'] not in ['completed','worker-failed','worker-timeout']:raise ValueError('Unknown hardware status')
        if h['status']=='completed' and r.returncode!=0 or h['status']=='worker-failed' and r.returncode==0:raise ValueError('Inconsistent exit status')
        if h['status']=='worker-timeout':
            if r.returncode!=124 or h['elapsed_seconds']<timeout:raise ValueError('Timeout evidence mismatch')
            record['status']='budgeted_timeout'
        else:
            rp=base/'recovery-result.json';result=json.loads(rp.read_text());record.update(status=result['status'],result_sha256=sha(rp))
            if result['status'] not in ['failed','posthoc_analysis_completed']:raise ValueError('Unknown recovery status')
            if result['status']=='posthoc_analysis_completed' and r.returncode!=0:raise ValueError('Completed recovery has failed exit')
            if result['cell_id']!=spec['cell_id'] or result['posthoc'] is not True or result['resampled'] is not False:raise ValueError('Recovery identity mismatch')
        if sha(path)!=digest:raise ValueError('Recovery spec changed')
        if any(sha(p)!=v for p,v in spec['launcher_inputs'].items()):raise ValueError('Postworker launcher/source changed')
        from recover import verify
        verify(spec)
    except Exception as exc:record.update(status='failed',error=f'{type(exc).__name__}: {exc}')
    record['additional_outer_seconds']=time.perf_counter()-tick;save(str(base)+'-status.json',record)
    return record

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--spec',required=True);a=p.parse_args();launch(a.spec)
