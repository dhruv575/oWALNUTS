import hashlib,json,subprocess,sys,time
from pathlib import Path
import numpy as np
study=Path(__file__).resolve().parent;local=study/'local_recovery';parent=local/'recycling_mse01';root=local/'recycling_mse_timing01'
def canonical(path):
    r=json.loads(path.read_text())
    for c in r['chains']:c.pop('seconds')
    return hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest()
if len(sys.argv)>1:
    target=sys.argv[1];index=int(sys.argv[2]);folder=root/target
    builds=json.loads((parent/'SUMMARY.json').read_text())['builds'];rng=np.random.Generator(np.random.PCG64(941330001+index));rows=[]
    expected={};inputs={}
    for batch in range(16):
        for arm in ['original','observed']:
            p=parent/f'{target}-{batch:02d}-{arm}';expected[batch,arm]=canonical(p/'RAW.json');inputs[batch,arm]=p/'INPUT.json'
    for repeat in range(3):
        for batch in range(16):
            for arm in rng.permutation(['original','observed']).tolist():
                binary=Path(builds[arm]['binary']);assert hashlib.sha256(binary.read_bytes()).hexdigest()==builds[arm]['binary_sha256']
                output=folder/f'LAST-{arm}.json';started=time.perf_counter()
                done=subprocess.run([str(binary),str(inputs[batch,arm]),str(output)],check=True,capture_output=True)
                elapsed=time.perf_counter()-started
                assert canonical(output)==expected[batch,arm]
                rows.append(dict(repeat=repeat,batch=batch,arm=arm,seconds=elapsed,canonical_sha256=expected[batch,arm],input_sha256=hashlib.sha256(inputs[batch,arm].read_bytes()).hexdigest()))
        (folder/'TIMINGS.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(target+' timing replays passed');sys.exit(0)
root.mkdir(exist_ok=False);sys.path.insert(0,str(local/'inputs'));from resource_monitor import execute
paths=[Path(__file__),study/'RECYCLING-MSE-TIMING-AUDIT.md'];hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};rows=[]
for i,target in enumerate(['analytic_rotated_gaussian','noncentered','funnel']):
    folder=root/target;folder.mkdir();r=execute([sys.executable,str(Path(__file__).resolve()),target,str(i)],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
    (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained'];rows.append(target);print(target+' timing complete',flush=True)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
(root/'SUMMARY.json').write_text(json.dumps(dict(passed=True,targets=rows,inputs=hashes,unchanged=True),indent=2)+'\n')
