"""One-shot admission on E72 job 04's drained, exhausted worker group."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import psutil
from literal_reference import validate,write,sha


def launch(base,campaign):
    base=Path(base).resolve();campaign=Path(campaign).resolve()
    spec=validate(json.loads((base/'MANIFEST.json').read_bytes()))
    if any(not (campaign/'campaign01'/f'job-{j:02d}').is_dir() for j in range(12)):
        return dict(status='not_ready',reason='Campaign queue not exhausted')
    job=campaign/'campaign01/job-04';receipt=job/'MONITOR.json'
    if not receipt.exists():return dict(status='not_ready',reason='Job 04 still active')
    monitor=json.loads(receipt.read_bytes())
    if monitor.get('group_drained') is not True:raise ValueError('Job ownership did not drain')
    cores=None;created=None
    for line in (job/'utilization.jsonl').read_text().splitlines():
        for p in json.loads(line)['processes']:
            if p['pid']==monitor['pid']:cores=p['affinity'];created=p['created']
    if cores is None or len(set(cores))!=4:raise ValueError('Missing original four-core allocation')
    token=(monitor['ownership_env']+'='+monitor['ownership_token']).encode()
    workers=[]
    for p in psutil.process_iter(['pid','cmdline','create_time']):
        try:
            if p.uids().real!=os.getuid():continue
            if p.create_time()<created:continue
            env=Path('/proc')/str(p.pid)/'environ'
            try:environment=env.read_bytes()
            except PermissionError:
                # Privilege-separated SSH session helpers are not job children.
                parent=p.parent()
                if p.name()=='sshd' and parent is not None and parent.uids().real==0:continue
                raise
            if token in environment.split(b'\0'):raise ValueError('Old owned process remains')
            cmd=p.info['cmdline'] or []
            if str(campaign/'worker.py') in cmd:
                affinity=p.cpu_affinity()
                workers.append(dict(pid=p.pid,created=p.info['create_time'],affinity=affinity))
                if set(cores)&set(affinity):raise ValueError('Campaign worker overlaps released cores')
        except (FileNotFoundError,ProcessLookupError,psutil.NoSuchProcess):pass
    if shutil.disk_usage(base).free<6*1024**3:raise ValueError('Disk admission')
    if (base/'attempt01').exists():raise FileExistsError('Reference attempt already exists')
    admission=dict(status='admitted',cores=cores,drained_job_sha256=sha(receipt),
                   manifest_sha256=sha(base/'MANIFEST.json'),active_campaign_workers=workers,
                   launcher_sha256=sha(__file__))
    # Exclusive receipt prevents duplicate launch even if observation disconnects.
    write(base/'ADMISSION.json',admission)
    with (base/'launch.log').open('xb') as log:
        child=subprocess.Popen(['taskset','-c',','.join(map(str,cores)),sys.executable,
                                str(base/'literal_reference.py'),str(base/'MANIFEST.json'),str(base/'attempt01')],
                               cwd=base,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
    record=dict(status='launched',pid=child.pid,cores=cores)
    write(base/'LAUNCH.json',record)
    return record


if __name__=='__main__':print(json.dumps(launch(*sys.argv[1:])))
