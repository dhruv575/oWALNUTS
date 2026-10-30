import hashlib,json,sys,tomllib
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';root=l/'native_compact_test01';root.mkdir(exist_ok=False)
sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
build=json.loads((l/'native_compact_build01/SUMMARY.json').read_text());assert build['passed'];binaries={b['package']:b for b in build['rows']}
for b in binaries.values():assert hashlib.sha256(Path(b['binary']).read_bytes()).hexdigest()==b['binary_sha256']
locks=[]
for name in binaries:
    data=tomllib.loads((p/name/'Cargo.lock').read_text());locks.append({x['name']:(x['version'],x.get('source'),x.get('checksum')) for x in data['package'] if x.get('source')})
assert locks[0]==locks[1]
files=[Path(__file__),p/'NATIVE-COMPACT-PROTOCOL.md',p/'native_compact_support.rs']+[p/n/'src/main.rs' for n in binaries]
hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files};(root/'SOURCE-SNAPSHOT.json').write_text(json.dumps(hashes,indent=2)+'\n')
def features(x):return np.concatenate([x,x*x,(x<0).astype(float),(x< -2).astype(float)],axis=1)
def check_summary(s,v):
    assert s['count']==len(v)
    if len(v)==0:assert s['mean']==s['block_means']==s['block_sizes']==[];return
    np.testing.assert_allclose(s['mean'],v.mean(0),rtol=2e-13,atol=1e-10)
    blocks=[v[i:i+50] for i in range(0,len(v),50)];assert s['block_sizes']==[len(x) for x in blocks]
    np.testing.assert_allclose(s['block_means'],[x.mean(0) for x in blocks],rtol=2e-13,atol=1e-10)
rows=[]
for folder in sorted((l/'native_recycling_test02').iterdir()):
    if not folder.is_dir():continue
    spec=json.loads((folder/'INPUT.json').read_text());prior=json.loads((folder/'RAW.json').read_text());name='native_compact_pristine_runner' if folder.name.endswith('-pristine') else 'native_compact_recycling_runner'
    modes=[True,False] if folder.name=='analytic_rotated_gaussian-diag-enabled' else [True]
    for compact in modes:
        out=root/(folder.name+('-compact' if compact else '-full'));out.mkdir();spec['compact']=compact;(out/'INPUT.json').write_text(json.dumps(spec)+'\n')
        r=execute([binaries[name]['binary'],str(out/'INPUT.json'),str(out/'RAW.json')],str(root),180,out,2*1024**3,64*1024**2,out/'worker.log',output_scan_interval=2);(out/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained']
        data=json.loads((out/'RAW.json').read_text())
        for a,b in zip(prior['chains'],data['chains']):
            x=np.array(a['all_draws'],dtype='<f8');assert hashlib.sha256(x.tobytes()).hexdigest()==b['draw_sha256']
            for k in ['warmup','draws','target_calls','warmup_calls']:assert a[k]==b[k]
            assert b['total_steps']==sum(v['num_steps'] for v in a['all_progress'])
            assert b['retained_divergences']==sum(v['diverging'] for v in a['all_progress'][a['warmup']:])
            check_summary(b['ordinary_summary'],features(x[a['warmup']:]))
            check_summary(b['conditional_summary'],np.array(a['recycled'][a['warmup']:]))
            for k in ['all_draws','all_progress','recycled']:assert b[k]==([] if compact else a[k])
        rows.append(dict(case=out.name,passed=True,prior_bytes=(folder/'RAW.json').stat().st_size,output_bytes=(out/'RAW.json').stat().st_size));print(json.dumps(rows[-1]),flush=True)
assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in hashes.items())
(root/'SUMMARY.json').write_text(json.dumps(dict(passed=True,rows=rows,inputs=hashes,unchanged=True,binaries=binaries,registry_dependencies_identical=True),indent=2)+'\n')
