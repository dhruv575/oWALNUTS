import hashlib,json,sys
from pathlib import Path
import numpy as np
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'compact_original_test01';root.mkdir(exist_ok=False);parent=local/'recycling_mse01'
build=json.loads((local/'compact_original_build01/SUMMARY.json').read_text());binary=Path(build['binary']);assert hashlib.sha256(binary.read_bytes()).hexdigest()==build['binary_sha256']
sys.path.insert(0,str(local/'inputs'));from resource_monitor import execute
paths=[Path(__file__),study/'COMPACT-RECYCLING-PROTOCOL.md',study/'compact_original_runner/src/main.rs',local/'recycling_source03/src/recycling.rs'];hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};(root/'SOURCE-SNAPSHOT.json').write_text(json.dumps(hashes,indent=2)+'\n')
rows=[]
for target in ['analytic_rotated_gaussian','noncentered','funnel']:
    for batch in range(16):
        for arm in ['original']:
            source=parent/f'{target}-{batch:02d}-{arm}';old=json.loads((source/'RAW.json').read_text());spec=json.loads((source/'INPUT.json').read_text());spec['compact']=True
            folder=root/source.name;folder.mkdir();inp=folder/'INPUT.json';inp.write_text(json.dumps(spec)+'\n')
            r=execute([str(binary),str(inp),str(folder/'RAW.json')],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained']
            new=json.loads((folder/'RAW.json').read_text())
            for a,b in zip(old['chains'],new['chains']):
                x=np.asarray(a['draws'],dtype='<f8');assert hashlib.sha256(x.tobytes()).hexdigest()==b['draw_sha256'];assert b['draws']==[] and b['recycled']==[]
                for k in a:
                    if k not in ['draws','recycled','seconds']:assert a[k]==b[k]
                v=np.asarray(a['recycled']) if arm=='observed' else np.concatenate([x,x*x,x<0,x<-2],axis=1)
                s=b['summary'];assert s['count']==len(x) and s['block_sizes']==[50]*20
                assert np.allclose(s['mean'],v.mean(axis=0),rtol=2e-13,atol=1e-10)
                assert np.allclose(s['block_means'],v.reshape(20,50,-1).mean(axis=1),rtol=2e-13,atol=1e-10)
            rows.append(dict(folder=folder.name,passed=True,original_bytes=(source/'RAW.json').stat().st_size,compact_bytes=(folder/'RAW.json').stat().st_size))
    print(target+' all original-kernel compact checks passed',flush=True)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
(root/'SUMMARY.json').write_text(json.dumps(dict(passed=True,rows=rows,inputs=hashes,unchanged=True,full_mode_exact_cases=0,binary=build),indent=2)+'\n')
