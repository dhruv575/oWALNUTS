import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'curved_cold_validation01';s=json.loads((r/'SUMMARY.json').read_text());a=json.loads((p/'CURVED-COLD-VALIDATION-ANALYSIS.json').read_text());assert s['passed'] and a['full_replays_verified']==9
for folder in ['curved_cold_calibration01','curved_cold_validation01']:
    sm=json.loads((l/folder/'SUMMARY.json').read_text());assert sm['passed']
    for f,h in sm['inputs'].items():assert hashlib.sha256(Path(f).read_bytes()).hexdigest()==h
selection=json.loads((p/'CURVED-COLD-SELECTION.json').read_text())
for candidate in selection['candidates']:
    arm=candidate['engine']+'_'+candidate['mode']+'_'+str(candidate['index']);values=[];times=[];div=0;variance=np.tile([1.,51.],12)
    for batch in range(4):
        folder=l/'curved_cold_calibration01'/f'{candidate["representation"]}-{batch:02d}';data=json.loads((folder/f'RAW-{arm}.json').read_text());ts=json.loads((folder/'TIMINGS.json').read_text());times.append(np.mean([t['seconds'] for t in ts if t['arm']==arm]))
        for chain in data['chains']:
            sm=chain['summary'] if candidate['engine']=='wal' else chain['conditional_summary' if candidate['mode']=='recycled' else 'ordinary_summary'];values.append(sm['mean'][24:48]);div+=chain['retained_divergences']
    mse=float(np.mean(((np.array(values)-variance)/variance)**2));assert np.isclose(mse,candidate['mse']) and np.isclose(np.mean(times),candidate['mean_batch_seconds']) and np.isclose(mse*np.mean(times),candidate['objective']) and div==candidate['divergences'] and candidate['eligible']==(div==0)
for chosen in selection['selected']:
    group=[c for c in selection['candidates'] if all(c[k]==chosen[k] for k in ['representation','engine','mode'])];best=min(group,key=lambda c:(not c['eligible'],c['divergences'] if not c['eligible'] else 0,c['objective'],c['index']));assert chosen['index']==best['index']
truth=np.array(json.loads((l/'banana_recycling_test01/EXACT-CONTROL.json').read_text())['truth']);var=np.tile([1.,51.],12);scale=np.r_[np.sqrt(var),var,np.ones(48)];est={arm:[] for arm in s['builds']};cost={arm:[] for arm in s['builds']}
for batch in range(16):
    f=r/f'batch-{batch:02d}';ts=json.loads((f/'TIMINGS.json').read_text())
    for arm in est:
        data=json.loads((f/f'RAW-{arm}.json').read_text())
        for c in data['chains']:
            sm=c['summary'] if arm=='exact' or '_wal_' in arm else c['conditional_summary' if arm.endswith('_recycled') else 'ordinary_summary'];est[arm].append(sm['mean']);c.pop('seconds')
        digest=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest();t=[v for v in ts if v['arm']==arm];assert len(t)==3 and all(v['canonical_sha256']==digest for v in t);cost[arm].append(np.mean([v['seconds'] for v in t]))
for j,family in enumerate(a['families']):
    sl=slice(24*j,24*(j+1));mse={arm:float(np.mean(((np.array(v)[:,sl]-truth[sl])/scale[sl])**2)) for arm,v in est.items()}
    for arm in mse:assert np.isclose(mse[arm],family['mse'][arm],rtol=1e-13,atol=1e-16)
    for c in family['comparisons']:
        base='direct_wal_recycled';mr=mse[c['control']]/mse[base];assert np.isclose(c['mse_ratio'],mr)
        for label,flag in [('single_fit',False),('calibration_amortized',True)]:
            ac=a['diagnostics'][c['control']]['calibration_one_pass_seconds']/16 if flag else 0;bc=a['diagnostics'][base]['calibration_one_pass_seconds']/16 if flag else 0;cr=(np.mean(cost[c['control']])+ac)/(np.mean(cost[base])+bc);assert np.isclose(c['costs'][label]['cost_ratio'],cr) and np.isclose(c['costs'][label]['adjusted_ratio'],mr*cr)
checks={c['control']:all(v['descriptive_endpoint_range'][0]>1.2 for v in c['costs'].values()) for c in a['families'][1]['comparisons'] if c['control']!='direct_wal_ordinary'};assert checks==a['checks'];assert a['efficiency_gate_passed']==(all(checks.values()) and a['z_gate'] and a['zero_divergence_gate'] and a['eligible_gate'])
(p/'CURVED-COLD-REPLAY.json').write_text(json.dumps(dict(passed=True,scope='Independent selection-rule, canonical timing-output, MSE and cost-ratio/gate replay; bootstrap interval implementation not duplicated'),indent=2)+'\n')
files={}
for name in ['tuned_native_build01','tuned_native_test01','exact_banana_build01','exact_banana_build02','curved_cold_calibration01','curved_cold_validation01']:
    for f in (l/name).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for name in ['tuned_native_pristine_runner','tuned_native_recycling_runner','exact_banana_runner']:
    for f in (p/name).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for pattern in ['*tuned_native.py','*exact_banana*.py','*curved_calibration.py','*curved_validation.py','diagnose_curved_work.py','archive_curved_comparison.py','CURVED-COLD-*','banana_core.rs','native_compact_support.rs']:
    for f in p.glob(pattern):
        if f.is_file():files[f.name]=f
for name in ['cold_recycling_archive01','banana_recycling_archive01','native_recycling_archive01']:
    f=l/name/'VERIFICATION.json';files[str(f.relative_to(p))]=f
for arm,b in s['builds'].items():
    f=Path(b['binary']);assert hashlib.sha256(f.read_bytes()).hexdigest()==b['binary_sha256'];files['binary/'+arm]=f
out=l/'curved_cold_comparison_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local readback-verified tuned cold calibration/validation and binaries; prior source archives remain dependencies; not off-device backup');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
