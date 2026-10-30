import hashlib,json,sys,shutil
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'allocation_audit01';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
build=json.loads((l/'allocation_probe_build01/SUMMARY.json').read_text());assert build['passed'];b=build['rows'][0];assert hashlib.sha256(Path(b['binary']).read_bytes()).hexdigest()==b['binary_sha256']
files=[Path(__file__),p/'allocation_probe.rs',p/'ALLOCATION-AUDIT-PROTOCOL.md',p/'allocation_probe_runner/src/main.rs',p.parents[2]/'src/kernel.rs',p.parents[2]/'src/walnutpie.rs',p.parents[2]/'src/sampler.rs'];hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files};(r/'SOURCE-SNAPSHOT.json').write_text(json.dumps(hashes,indent=2)+'\n');rows=[]
cases=[(t,m) for t in ['banana_direct','banana_latent'] for m in ['identity','diagonal']]+[('funnel','diagonal')]
for target,metric in cases:
    old=l/'cold_recycling_test01'/f'{target}-{metric}-original';prior=json.loads((old/'RAW.json').read_text());spec=json.loads((old/'INPUT.json').read_text());counts=[]
    for enabled in [False,True]:
        assert shutil.disk_usage(r).free>1024**3;folder=r/f'{target}-{metric}-{enabled}';folder.mkdir();spec['profile_allocations']=enabled;(folder/'INPUT.json').write_text(json.dumps(spec)+'\n');result=execute([b['binary'],str(folder/'INPUT.json'),str(folder/'RAW.json')],str(r),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(result,indent=2)+'\n');assert result['exit_code']==0 and result['group_drained'];data=json.loads((folder/'RAW.json').read_text())
        for ci,(a,c) in enumerate(zip(prior['chains'],data['chains'])):
            for k in a:
                if k!='seconds':assert a[k]==c[k],(target,metric,k)
            allocation=c['allocation_counts'];events=allocation['alloc']+allocation['alloc_zeroed']+allocation['realloc'];assert sum(allocation['request_size_bins'])==events
            if not enabled:assert events==allocation['requested_bytes']==allocation['dealloc']==allocation['freed_bytes']==0
            else:
                assert events>0 and allocation['requested_bytes']>0;counts.append(dict(chain=ci,actual_target_calls=c['target_calls'],transitions=c['discarded']+spec['draws'],events_per_call=events/c['target_calls'],events_per_transition=events/(c['discarded']+spec['draws']),**allocation))
    row=dict(target=target,metric=metric,exact_pristine_disabled_enabled_parity=True,chains=counts);rows.append(row);print(json.dumps(dict(target=target,metric=metric,total_events=sum(c['alloc']+c['alloc_zeroed']+c['realloc'] for c in counts),events_per_call=sum(c['alloc']+c['alloc_zeroed']+c['realloc'] for c in counts)/sum(c['actual_target_calls'] for c in counts))),flush=True)
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in hashes.items());(r/'SUMMARY.json').write_text(json.dumps(dict(passed=True,rows=rows,inputs=hashes,unchanged=True,build=b,scope='Gross allocations during Sampler::run, not speed or live memory'),indent=2)+'\n')
