import hashlib,json,subprocess,sys,time,shutil
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';root=l/'curved_cold_validation01'
def canonical(data):
    for c in data['chains']:c.pop('seconds')
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
if len(sys.argv)>1:
    f=Path(sys.argv[1]);cfg=json.loads((f/'CONFIG.json').read_text());rng=np.random.default_rng(cfg['order_seed']);records=[];expected={}
    for repeat in range(3):
        for arm in rng.permutation(list(cfg['arms'])).tolist():
            out=f/(f'RAW-{arm}.json' if repeat==0 else f'REPLAY-{arm}.json');clock=time.perf_counter();subprocess.run([cfg['arms'][arm]['binary'],str(f/f'INPUT-{arm}.json'),str(out)],check=True,capture_output=True);elapsed=time.perf_counter()-clock;digest=canonical(json.loads(out.read_text()))
            if repeat==0:expected[arm]=digest
            else:assert digest==expected[arm]
            records.append(dict(arm=arm,repeat=repeat,seconds=elapsed,canonical_sha256=digest))
    (f/'TIMINGS.json').write_text(json.dumps(records,indent=2)+'\n');sys.exit(0)
root.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
selection=json.loads((p/'CURVED-COLD-SELECTION.json').read_text());cal=json.loads((l/'curved_cold_calibration01/SUMMARY.json').read_text());assert selection['selection_frozen'] and hashlib.sha256((l/'curved_cold_calibration01/SUMMARY.json').read_bytes()).hexdigest()==selection['calibration_summary_sha256']
exact=json.loads((l/'exact_banana_build02/SUMMARY.json').read_text());assert exact['passed'];arms={c['representation']+'_'+c['engine']+'_'+c['mode']:cal['builds'][c['engine']+'_'+c['mode']] for c in selection['selected']};arms['exact']=exact
for b in arms.values():assert hashlib.sha256(Path(b['binary']).read_bytes()).hexdigest()==b['binary_sha256']
paths=[Path(__file__),p/'analyze_curved_validation.py',p/'CURVED-COLD-SELECTION.json',p/'CURVED-COLD-COMPARISON-PROTOCOL.md',p/'banana_core.rs',p/'native_compact_support.rs',l/'banana_recycling_test01/EXACT-CONTROL.json']+[p/b['package']/'src/main.rs' for b in arms.values()];hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths};(root/'SOURCE-SNAPSHOT.json').write_text(json.dumps(hashes,indent=2)+'\n');starts=np.random.default_rng(942000001).normal(size=(64,24));rows=[]
for batch in range(16):
    assert shutil.disk_usage(root).free>1024**3;f=root/f'batch-{batch:02d}';f.mkdir()
    for choice in selection['selected']:
        rep,engine,mode=choice['representation'],choice['engine'],choice['mode'];arm=rep+'_'+engine+'_'+mode;initial=starts.copy()
        if rep=='direct':initial[:,1::2]+=5*(initial[:,::2]**2-1)
        chains=[dict(start=initial[j].tolist(),seed=942010001+j,**(dict(mass=[1.]*24,step_size=.3) if engine=='wal' else {})) for j in range(batch*4,batch*4+4)]
        spec=dict(target='banana_'+rep,chains=chains,warmup=1000,draws=2000,levels=8,compact=True,observe=mode=='recycled',**choice['config']);(f/f'INPUT-{arm}.json').write_text(json.dumps(spec)+'\n')
    (f/'INPUT-exact.json').write_text(json.dumps(dict(draws=2000,compact=True,chains=[dict(seed=942020001+j) for j in range(4*batch,4*batch+4)]))+'\n');(f/'CONFIG.json').write_text(json.dumps(dict(arms=arms,order_seed=942030001+batch))+'\n')
    r=execute([sys.executable,str(Path(__file__).resolve()),str(f)],str(root),180,f,2*1024**3,64*1024**2,f/'worker.log',output_scan_interval=2);(f/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained'];rows.append(dict(batch=batch,folder=f.name));(root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n');print(f.name+' passed',flush=True)
# Full first-batch replay is outside timing and does not create extra statistical replicates.
for arm,binary in arms.items():
    folder=root/'full'/arm;folder.mkdir(parents=True);spec=json.loads((root/'batch-00'/f'INPUT-{arm}.json').read_text());spec['compact']=False;(folder/'INPUT.json').write_text(json.dumps(spec)+'\n');r=execute([binary['binary'],str(folder/'INPUT.json'),str(folder/'RAW.json')],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained']
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in hashes.items());(root/'SUMMARY.json').write_text(json.dumps(dict(passed=True,rows=rows,inputs=hashes,unchanged=True,builds=arms,selection=selection),indent=2)+'\n')
