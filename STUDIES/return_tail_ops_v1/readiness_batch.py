"""Twelve concurrent full-size literal arithmetic checks; no market inputs."""
import argparse,concurrent.futures,json,subprocess
from pathlib import Path
from batch import load_worker,safe
from evidence_io import exclusive
from resource_monitor import execute

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    manifest=Path(a.manifest).absolute();raw=json.loads(manifest.read_bytes());worker=load_worker(raw['worker_path'],raw['sources'][raw['worker_path']]);spec=worker.admit(manifest,expected_status='development_authorized')
    root=Path(a.out);root.mkdir(exist_ok=False);here=Path(__file__).resolve().parent
    # Fixtures are part of the fixed readiness budget, before any literal arithmetic.
    with (root/'fixtures.log').open('xb') as log:
        tested=subprocess.run([spec['python'],'-m','unittest','discover','-s',str(here),'-p','test_*.py','-v'],stdout=log,stderr=subprocess.STDOUT,timeout=45)
    if tested.returncode:raise RuntimeError('Operational fixtures failed')
    def one(i):
        out=root/f'shard-{i:02d}';out.mkdir()
        command=['taskset','-c',str(i),spec['python'],spec['readiness_path'],'--manifest',str(manifest),'--out',str(out/'work'),'--shard',str(i)]
        result=execute(command,Path(spec['readiness_path']).parent,480,out,spec['bounds']['worker_rss_bytes'],spec['bounds']['output_bytes'],out/'worker.log',output_scan_interval=2)
        exclusive(out/'MONITOR.json',result)
        return dict(shard=i,**result)
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:jobs=list(pool.map(one,range(12)))
    complete=all(j.get('status')=='exited' and j.get('exit_code')==0 and safe(j) for j in jobs)
    worker.admit(manifest,expected_status='development_authorized')
    exclusive(root/'READINESS-FINAL.json',dict(jobs=jobs,planned_jobs=12,complete=complete,market_inputs_used=False,source_runtime_postcheck=True))
    return 0 if complete else 1
if __name__=='__main__':raise SystemExit(main())
