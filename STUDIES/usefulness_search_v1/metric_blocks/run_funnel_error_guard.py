import hashlib,json,shutil,sys
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery'
build=json.loads((local/'funnel_error_guard_build02/SUMMARY.json').read_text());assert build['passed']
binary=Path(build['binary']);assert hashlib.sha256(binary.read_bytes()).hexdigest()==build['binary_sha256']
root=local/'funnel_error_guard01';root.mkdir(exist_ok=False)
sys.path.insert(0,str(local/'inputs'));from resource_monitor import execute
paths=[Path(__file__),study/'FUNNEL-ERROR-GUARD-PROTOCOL.md',study/'funnel_error_guard_runner/src/main.rs',study/'funnel_error_guard_runner/Cargo.lock',study/'analyze_funnel_error_guard.py']
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
(root/'SOURCE-SNAPSHOT.json').write_text(json.dumps(hashes,indent=2)+'\n')
rows=[]
for seed in range(941000001,941000005):
    for target in ['noncentered','centered']:
        for arm in ['default','permissive']:
            assert shutil.disk_usage(root).free>1024**3
            folder=root/f'{target}-{arm}-{seed}';folder.mkdir()
            r=execute([str(binary),target,arm,'2000','20000',str(seed),str(folder/'RAW.json')],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
            (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n')
            rows.append(dict(target=target,arm=arm,seed=seed,folder=folder.name,completed=r['exit_code']==0 and r['group_drained']))
            (root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n')
            print(json.dumps(rows[-1]),flush=True)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
(root/'SUMMARY.json').write_text(json.dumps(dict(rows=rows,inputs=hashes,unchanged=True,binary=build),indent=2)+'\n')
