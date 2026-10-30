import hashlib,json,subprocess,sys,time,shutil
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';root=l/'curved_cold_calibration01'
def canonical(data):
    for c in data['chains']:c.pop('seconds')
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
if len(sys.argv)>1:
    f=Path(sys.argv[1]);config=json.loads((f/'CONFIG.json').read_text());rng=np.random.default_rng(config['order_seed']);records=[];expected={}
    for repeat in range(3):
        for arm in rng.permutation(list(config['arms'])).tolist():
            output=f/(f'RAW-{arm}.json' if repeat==0 else f'REPLAY-{arm}.json');clock=time.perf_counter();subprocess.run([config['arms'][arm]['binary'],str(f/f'INPUT-{arm}.json'),str(output)],check=True,capture_output=True);elapsed=time.perf_counter()-clock;digest=canonical(json.loads(output.read_text()))
            if repeat==0:expected[arm]=digest
            else:assert digest==expected[arm]
            records.append(dict(arm=arm,repeat=repeat,seconds=elapsed,canonical_sha256=digest))
    for engine in ['wal','native']:
        for i in range(4):
            a=json.loads((f/f'RAW-{engine}_ordinary_{i}.json').read_text());b=json.loads((f/f'RAW-{engine}_recycled_{i}.json').read_text())
            for x,y in zip(a['chains'],b['chains']):
                for k in ['draw_sha256','target_calls','retained_divergences']+(['metadata','telemetry','work'] if engine=='wal' else ['warmup_calls','total_steps','ordinary_summary']):assert x[k]==y[k],(engine,i,k)
    (f/'TIMINGS.json').write_text(json.dumps(records,indent=2)+'\n');sys.exit(0)
assert json.loads((l/'tuned_native_test01/SUMMARY.json').read_text())['passed'] and json.loads((l/'cold_recycling_test01/SUMMARY.json').read_text())['passed']
root.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
builds={}
for engine,folder in [('wal','cold_recycling_build03'),('native','tuned_native_build01')]:
    b=json.loads((l/folder/'SUMMARY.json').read_text());assert b['passed'] and b['compiler']=='rustc 1.99.1 (58cf8f9c3 2026-10-13)'
    for row in b['rows']:
        mode='recycled' if 'recycling' in row['package'] else 'ordinary';builds[engine+'_'+mode]=row;assert hashlib.sha256(Path(row['binary']).read_bytes()).hexdigest()==row['binary_sha256']
configs={'wal':[dict(target_accept=accept,max_error=err,metric='diagonal') for accept in [.9,.99] for err in [1.,10.]],'native':[dict(target_accept=accept,adaptation=metric) for accept in [.9,.99] for metric in ['diag','low_rank']]}
paths=[Path(__file__),p/'select_curved_calibration.py',p/'CURVED-COLD-COMPARISON-PROTOCOL.md',p/'banana_core.rs',l/'banana_recycling_test01/EXACT-CONTROL.json']+[p/b['package']/'src/main.rs' for b in builds.values()];hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths};(root/'SOURCE-SNAPSHOT.json').write_text(json.dumps(hashes,indent=2)+'\n')
starts=np.random.default_rng(941900001).normal(size=(16,24));rows=[]
for ri,rep in enumerate(['direct','latent']):
    initial=starts.copy()
    if rep=='direct':initial[:,1::2]+=5*(initial[:,::2]**2-1)
    for batch in range(4):
        assert shutil.disk_usage(root).free>1024**3;f=root/f'{rep}-{batch:02d}';f.mkdir();arms={}
        for engine in configs:
            for mode in ['ordinary','recycled']:
                for i,cfg in enumerate(configs[engine]):
                    arm=f'{engine}_{mode}_{i}';arms[arm]=builds[engine+'_'+mode];chains=[dict(start=initial[j].tolist(),seed=941910001+j,**(dict(mass=[1.]*24,step_size=.3) if engine=='wal' else {})) for j in range(4*batch,4*batch+4)];spec=dict(target='banana_'+rep,chains=chains,warmup=1000,draws=2000,levels=8,compact=True,observe=mode=='recycled',**cfg);(f/f'INPUT-{arm}.json').write_text(json.dumps(spec)+'\n')
        (f/'CONFIG.json').write_text(json.dumps(dict(arms=arms,order_seed=941920001+100*ri+batch))+'\n');r=execute([sys.executable,str(Path(__file__).resolve()),str(f)],str(root),180,f,2*1024**3,64*1024**2,f/'worker.log',output_scan_interval=2);(f/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained'];rows.append(dict(representation=rep,batch=batch,folder=f.name));(root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n');print(f.name+' calibration completed',flush=True)
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in hashes.items());(root/'SUMMARY.json').write_text(json.dumps(dict(passed=True,rows=rows,inputs=hashes,unchanged=True,builds=builds,configs=configs),indent=2)+'\n')
