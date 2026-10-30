import hashlib,json,subprocess,sys,time,shutil
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';root=l/'recycled_baseline_screen01'
def canonical(data):
    for c in data['chains']:c.pop('seconds')
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
if len(sys.argv)>1:
    f=Path(sys.argv[1]);config=json.loads((f/'CONFIG.json').read_text());rng=np.random.default_rng(config['order_seed']);records=[];expected={}
    for repeat in range(3):
        for arm in rng.permutation(list(config['builds'])).tolist():
            out=f/(f'RAW-{arm}.json' if repeat==0 else f'REPLAY-{arm}.json');clock=time.perf_counter()
            subprocess.run([config['builds'][arm]['binary'],str(f/f'INPUT-{arm}.json'),str(out)],check=True,capture_output=True)
            elapsed=time.perf_counter()-clock;digest=canonical(json.loads(out.read_text()))
            if repeat==0:expected[arm]=digest
            else:assert digest==expected[arm]
            records.append(dict(arm=arm,repeat=repeat,seconds=elapsed,canonical_sha256=digest))
    for prefix in ['wal','diag','low_rank']:
        a=json.loads((f/f'RAW-{prefix}_ordinary.json').read_text());b=json.loads((f/f'RAW-{prefix}_recycled.json').read_text())
        for x,y in zip(a['chains'],b['chains']):
            for k in ['draw_sha256','target_calls','retained_divergences']:assert x[k]==y[k]
            for k in (['work'] if prefix=='wal' else ['warmup_calls','total_steps','ordinary_summary']):assert x[k]==y[k]
    (f/'TIMINGS.json').write_text(json.dumps(records,indent=2)+'\n');sys.exit(0)
assert json.loads((l/'native_compact_test01/SUMMARY.json').read_text())['passed']
assert json.loads((l/'compact_wal_stable_test01/SUMMARY.json').read_text())['passed']
root.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
wal=json.loads((l/'compact_wal_stable_build01/SUMMARY.json').read_text());native=json.loads((l/'native_compact_build01/SUMMARY.json').read_text());assert wal['passed'] and native['passed'] and wal['compiler']==native['compiler']
wb={b['package']:b for b in wal['rows']};nb={b['package']:b for b in native['rows']}
builds={'wal_ordinary':wb['compact_original_runner'],'wal_recycled':wb['compact_recycling_runner']}
for adaptation in ['diag','low_rank']:
    for mode,package in [('ordinary','native_compact_pristine_runner'),('recycled','native_compact_recycling_runner')]:builds[adaptation+'_'+mode]=nb[package]
for b in builds.values():assert hashlib.sha256(Path(b['binary']).read_bytes()).hexdigest()==b['binary_sha256']
files=[Path(__file__),p/'RECYCLED-BASELINE-SCREEN-PROTOCOL.md',p/'analyze_recycled_baseline_screen.py']+[p/b['package']/'src/main.rs' for b in builds.values()]
hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files};(root/'SOURCE-SNAPSHOT.json').write_text(json.dumps(hashes,indent=2)+'\n')
rows=[]
for ti,target in enumerate(['noncentered','analytic_rotated_gaussian']):
    d=10 if ti==0 else 2;rng=np.random.default_rng(941600001+ti);starts=rng.normal(size=(64,d))
    if ti==0:starts[:,0]*=3
    else:starts=starts@np.linalg.cholesky([[2.,1.],[1.,2.]]).T
    for batch in range(16):
        assert shutil.disk_usage(root).free>1024**3;f=root/f'{target}-{batch:02d}';f.mkdir()
        chains=[dict(start=starts[i].tolist(),seed=941610001+1000*ti+i) for i in range(4*batch,4*batch+4)]
        for arm in builds:
            if arm.startswith('wal'):
                wc=[dict(c,mass=[1.]*d if ti==0 else [2/3,-1/3,-1/3,2/3],step_size=.3) for c in chains]
                spec=dict(target=target,chains=wc,metric='diagonal' if ti==0 else 'dense',draws=1000,levels=8,max_error=1.,compact=True,observe=arm.endswith('recycled'))
            else:spec=dict(target=target,chains=chains,adaptation='low_rank' if arm.startswith('low_rank') else 'diag',warmup=1000,draws=1000,compact=True,observe=arm.endswith('recycled'))
            (f/f'INPUT-{arm}.json').write_text(json.dumps(spec)+'\n')
        (f/'CONFIG.json').write_text(json.dumps(dict(builds=builds,order_seed=941630001+100*ti+batch))+'\n')
        r=execute([sys.executable,str(Path(__file__).resolve()),str(f)],str(root),180,f,2*1024**3,64*1024**2,f/'worker.log',output_scan_interval=2);(f/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained']
        rows.append(dict(target=target,batch=batch,folder=f.name));(root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n')
        print(f.name+' passed',flush=True)
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in hashes.items())
(root/'SUMMARY.json').write_text(json.dumps(dict(passed=True,rows=rows,inputs=hashes,unchanged=True,builds=builds,compiler=wal['compiler']),indent=2)+'\n')
