"""Bounded spatial reference attempt with a durable heartbeat and terminal state."""
import concurrent.futures
import hashlib
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path
import psutil
from resource_monitor import execute

base = Path(__file__).resolve().parent
runtime = Path('/home/ubuntu/lanes/gp-portable-runtime-20261030')
smoke = Path('/home/ubuntu/lanes/spatial-counts-preflight-20261030')

def write(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)

def main():
    assert shutil.disk_usage(base).free > 1.6 * 1024**3
    assert json.loads((smoke/'SUPERVISION.json').read_text())['group_drained']
    assert json.loads((smoke/'evidence/SUMMARY.json').read_text())['passed']
    expected = json.loads((base/'SOURCE-HASHES.json').read_text())
    for name, digest in expected.items():
        assert hashlib.sha256((base/name).read_bytes()).hexdigest() == digest, name
    paths = [base/name for name in expected] + [base/'SOURCE-HASHES.json']
    paths += [smoke/n for n in ['spatial_gp_model.so','spatial_gp.stan','evidence/counted_model.so']]
    paths += [runtime/n for n in ['gp-wal-tuned-runner','native_common.py','models/libtbb.so.2']]
    hashes = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    write(base/'INPUT-HASHES.json',hashes)
    root = base/'results';root.mkdir(exist_ok=False)
    stopped = threading.Event()
    rows = []
    started = time.time()
    def heartbeat():
        with (base/'HEARTBEAT.jsonl').open('x') as log:
            while not stopped.is_set():
                record = dict(unix_seconds=time.time(),elapsed_seconds=time.time()-started,
                              cpu_percent=psutil.cpu_percent(interval=1),
                              available_memory=psutil.virtual_memory().available,
                              free_disk=shutil.disk_usage(base).free,completed_groups=len(rows))
                log.write(json.dumps(record)+'\n');log.flush()
                write(base/'LIVE.json',record)
                stopped.wait(14)
    watcher = threading.Thread(target=heartbeat,daemon=True);watcher.start()
    write(base/'STATUS.json',dict(status='running',pid=os.getpid(),started=started))
    def run(g):
        out=root/str(g);out.mkdir()
        command=['taskset','-c',f'{g*4}-{g*4+3}',sys.executable,str(base/'reference_worker_repair.py'),str(g)]
        s=execute(command,str(base),2400,out,4*1024**3,128*1024**2,out/'worker.log',output_scan_interval=2)
        write(out/'SUPERVISION.json',s)
        complete=s['status']=='exited' and s['exit_code']==0 and s['group_drained'] and (out/'SUMMARY.json').exists()
        return json.loads((out/'SUMMARY.json').read_text()) if complete else dict(group=g,passed=False,supervision=s)
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for future in concurrent.futures.as_completed([pool.submit(run,g) for g in (1,2,3)]):
                row=future.result();rows.append(row);write(root/'PROGRESS.json',rows)
                print(json.dumps(dict(group=row['group'],passed=row['passed'])),flush=True)
        original=Path('/home/ubuntu/lanes/spatial-counts-reference-20261031')
        original_start=json.loads((original/'LAUNCH.json').read_text())['launched']
        while not (original/'results/0/SUPERVISION.json').exists() and time.time()<original_start+2440:
            time.sleep(5)
        write(base/'GROUP-SOURCES.json',{str(g):str(original/'results/0' if g==0 else root/str(g)) for g in range(4)})
        out=base/'summary-supervision';out.mkdir()
        s=execute([sys.executable,str(base/'reference_summary_repair.py')],str(base),300,out,4*1024**3,16*1024**2,out/'worker.log',output_scan_interval=2)
        write(out/'SUPERVISION.json',s)
        intact=all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        complete=s['status']=='exited' and s['exit_code']==0 and s['group_drained'] and intact
        summary=json.loads((root/'SUMMARY.json').read_text()) if (root/'SUMMARY.json').exists() else {}
        write(base/'STATUS.json',dict(status='completed' if complete else 'failed',source_hashes_intact=intact,
              reference_qualified=complete and summary.get('passed',False),independent_audit_pending=True,
              elapsed_seconds=time.time()-started,completed_groups=len(rows)))
    except BaseException as exc:
        write(base/'STATUS.json',dict(status='failed',error=repr(exc),elapsed_seconds=time.time()-started))
        raise
    finally:
        stopped.set();watcher.join(timeout=20)

if __name__=='__main__':
    main()
