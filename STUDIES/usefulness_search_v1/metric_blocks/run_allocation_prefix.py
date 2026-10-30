import hashlib,json,sys
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'allocation_prefix01';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
s=json.loads((l/'allocation_audit01/SUMMARY.json').read_text());assert s['passed'];b=s['build'];assert hashlib.sha256(Path(b['binary']).read_bytes()).hexdigest()==b['binary_sha256'];files=[Path(__file__),p/'ALLOCATION-PREFIX-PROTOCOL.md'];hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files};rows=[]
for target in ['banana_direct','banana_latent']:
    stem=target+'-diagonal';full=json.loads((l/'cold_recycling_test01'/(stem+'-full')/'RAW.json').read_text());prior=json.loads((l/'allocation_audit01'/(stem+'-True')/'RAW.json').read_text());data={4000:prior}
    for draws in [1,1000]:
        f=r/f'{stem}-{draws}';f.mkdir();spec=json.loads((l/'allocation_audit01'/(stem+'-True')/'INPUT.json').read_text());spec.update(draws=draws,compact=False);(f/'INPUT.json').write_text(json.dumps(spec)+'\n');result=execute([b['binary'],str(f/'INPUT.json'),str(f/'RAW.json')],str(r),180,f,2*1024**3,64*1024**2,f/'worker.log',output_scan_interval=2);(f/'SUPERVISION.json').write_text(json.dumps(result,indent=2)+'\n');assert result['exit_code']==0 and result['group_drained'];data[draws]=json.loads((f/'RAW.json').read_text())
        for a,c,reference in zip(prior['chains'],data[draws]['chains'],full['chains']):
            assert c['draws']==reference['draws'][:draws];assert c['draw_sha256']==hashlib.sha256(np.array(c['draws'],dtype='<f8').tobytes()).hexdigest()
            for k in ['step_size','mass','discarded']:assert a[k]==c[k]
            assert a['target_calls']-a['work']['target_calls_total']==c['target_calls']-c['work']['target_calls_total']
    counts={n:sum(sum(c['allocation_counts'][k] for k in ['alloc','alloc_zeroed','realloc']) for c in v['chains']) for n,v in data.items()};slope=(counts[4000]-counts[1000])/(4*3000);residual=counts[1000]-4*1000*slope;row=dict(target=target,exact_prefix_and_nonretained_calls=True,total_events=counts,marginal_events_per_retained_draw=slope,estimated_fixed_event_residual=residual,fixed_residual_fraction_at4000=residual/counts[4000]);rows.append(row);print(json.dumps(row),flush=True)
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in hashes.items());(r/'SUMMARY.json').write_text(json.dumps(dict(passed=True,rows=rows,inputs=hashes,unchanged=True,build=b,scope='Prefix differences, not exact warmup attribution or timing'),indent=2)+'\n')
