"""Read-only bounded-tail status snapshot for a research campaign."""
import argparse,json,os,time
from pathlib import Path
import psutil

def latest(path):
    try:
        with path.open('rb') as f:
            f.seek(0,2);n=f.tell();f.seek(max(0,n-16384));lines=f.read().splitlines()
        for line in reversed(lines):
            try:return json.loads(line)
            except (ValueError,UnicodeDecodeError):continue
    except FileNotFoundError:pass
    return None

def pulse(root):
    root=Path(root).resolve();jobs=[]
    for j in range(12):
        p=root/'campaign01'/f'job-{j:02d}'
        done=p/'candidate/DONE.json';v=json.loads(done.read_bytes()) if done.exists() else None
        progress=latest(p/'candidate/progress.jsonl')
        jobs.append(dict(job=j,started=p.exists(),terminal=None if v is None else v['status'],
                         last_event=None if progress is None else progress.get('event'),
                         tick=None if progress is None else progress.get('tick')))
    processes=[]
    for p in psutil.process_iter(['pid','cmdline','create_time','memory_info','status']):
        try:
            command=' '.join(p.info['cmdline'] or [])
            if p.pid!=os.getpid() and str(root) in command and p.info['status']!=psutil.STATUS_ZOMBIE:
                processes.append(dict(pid=p.pid,created=p.info['create_time'],rss=p.info['memory_info'].rss))
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    util=latest(root/'outer-utilization.jsonl')
    return dict(unix_seconds=time.time(),jobs=jobs,live_matching_processes=processes,
                terminal=(root/'SUPERVISION.json').exists(),disk_free_bytes=psutil.disk_usage(str(root)).free,
                utilization=None if util is None else {k:util.get(k) for k in ('unix_seconds','elapsed_seconds','normalized_reserved_cpu_fraction','reserved_cores')})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');a=p.parse_args();print(json.dumps(pulse(a.root)))
