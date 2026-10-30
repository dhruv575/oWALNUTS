import hashlib,json,shutil,sys
from pathlib import Path
import numpy as np
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'recycling_mse01';root.mkdir(exist_ok=False)
assert json.loads((local/'recycling_test02/SUMMARY.json').read_text())['passed']
builds={arm:json.loads((local/name/'SUMMARY.json').read_text()) for arm,name in [('original','funnel_cross_build01'),('observed','recycling_build03')]}
for b in builds.values():assert hashlib.sha256(Path(b['binary']).read_bytes()).hexdigest()==b['binary_sha256']
sys.path.insert(0,str(local/'inputs'));from resource_monitor import execute
paths=[Path(__file__),study/'RECYCLING-MSE-PROTOCOL.md',study/'analyze_recycling_mse.py',study/'recycling_runner/src/main.rs',local/'recycling_source02/src/recycling.rs',local/'recycling_source02/src/kernel.rs',local/'recycling_source02/src/walnutpie.rs']
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};(root/'SOURCE-SNAPSHOT.json').write_text(json.dumps(hashes,indent=2)+'\n')
rows=[]
for t,target in enumerate(['analytic_rotated_gaussian','noncentered','funnel']):
    rng=np.random.Generator(np.random.PCG64(941300001+t));d=2 if t==0 else 10
    if t==0:starts=rng.normal(size=(64,d))@np.linalg.cholesky([[2.,1.],[1.,2.]]).T;mass=[2/3,-1/3,-1/3,2/3]
    else:
        starts=rng.normal(size=(64,d));starts[:,0]*=3;mass=[1.]*d
        if t==2:starts[:,1:]*=np.exp(starts[:,:1]/2)
    for batch in range(16):
        chains=[dict(start=starts[i].tolist(),mass=mass,step_size=.3,seed=941310001+1000*t+i) for i in range(4*batch,4*batch+4)]
        for arm in (['original','observed'] if batch%2==0 else ['observed','original']):
            assert shutil.disk_usage(root).free>1024**3
            folder=root/f'{target}-{batch:02d}-{arm}';folder.mkdir();spec=dict(target=target,metric='dense' if t==0 else 'diagonal',draws=1000,levels=8,max_error=1.,observe=arm=='observed',chains=chains)
            inp=folder/'INPUT.json';inp.write_text(json.dumps(spec)+'\n')
            r=execute([builds[arm]['binary'],str(inp),str(folder/'RAW.json')],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
            (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n')
            row=dict(target=target,batch=batch,arm=arm,folder=folder.name,completed=r['exit_code']==0 and r['group_drained']);rows.append(row)
            (root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n')
        print(f'{target} batch {batch+1}/16 complete',flush=True)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
(root/'SUMMARY.json').write_text(json.dumps(dict(rows=rows,inputs=hashes,unchanged=True,builds=builds),indent=2)+'\n')
