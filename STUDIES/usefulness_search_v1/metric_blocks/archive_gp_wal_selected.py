import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np,arviz as az
p=Path(__file__).resolve().parent;l=p/'local_recovery';cal=json.loads((l/'gp_wal_calibration01/SUMMARY.json').read_text());val=json.loads((l/'gp_wal_selected_validation01/SUMMARY.json').read_text());assert cal['completed'] and val['completed'];selected=cal['selected'];verified=0
for root,s in [(l/'gp_wal_calibration01',cal),(l/'gp_wal_selected_validation01',val)]:
    for row in s['rows']:
        if row.get('completed') is False:continue
        folder=root/(f"{row['mode']}-{row['target_accept']}-{row['seed']}" if root.name=='gp_wal_calibration01' else f"{row['mode']}-{row['seed']}")
        for f,h in row['inputs'].items():assert hashlib.sha256(Path(f).read_bytes()).hexdigest()==h
        with np.load(folder/'FUNCTIONALS.npz') as z:x=z['values']
        ds=az.convert_to_dataset({'p':x});assert float(np.min(np.asarray(az.ess(ds,method='bulk').p)))==row['bulk'];assert float(np.min(np.asarray(az.ess(ds,method='tail').p)))==row['tail'];assert float(np.max(np.asarray(az.rhat(ds,method='rank').p)))==row['rhat'];assert row['calls_per_min_bulk_ess']==row['calls']['gradient']/row['bulk'];verified+=1
lines=['# Equal-budget GP tuning and fresh selected-workflow validation','','Both engines received six configurations and two calibration seeds (equal fit counts, not equal realized target calls). WALNUTS selected '+selected['mode']+' at target acceptance '+str(selected['target_accept'])+'. Dense.8 failed the calibration accuracy gate on both seeds and remains failed. Other candidate configurations qualified both fits. Native selection remains low_rank,.99 from the previous frozen calibration.','','The isolated driver preserves original, omitted-default and explicit.8 draws/calls/divergence/revision outputs exactly for auto and dense at1100 warmup/100 retained. The first build lacked the existing research feature, and the first100-warmup preflight was rejected by the automatic slow-window schedule; both failures and their repairs are preserved. No kernel or production edits.','','| Fresh workflow | Qualified fits | Retained divergences | Median minimum bulkESS | Median total gradients |','|---|---:|---:|---:|---:|']
for mode in ['low_rank',selected['mode']]:
    subset=[x for x in val['rows'] if x['mode']==mode];good=[x for x in subset if 'bulk' in x];lines.append(f"| {mode} | {sum(x['passed'] for x in subset)}/8 | {sum(x['divergences'] for x in good)} | {np.median([x['bulk'] for x in good]):.1f} | {np.median([x['calls']['gradient'] for x in good]):.0f} |")
if val['comparison']:
    c=val['comparison'];lines+=['',f"WALNUTS/native minimum-bulkESS per total actual target call: **{c['walnuts_native_efficiency_ratio']:.4f}**, paired95% bootstrap interval **[{c['interval'][0]:.4f},{c['interval'][1]:.4f}]**. Frozen >1.2 lower-bound signal gate: **{val['signal_passed']}**."]
else:lines+=['','At least one validation fit failed; the all-pair efficiency ratio is withheld by the frozen rule.']
native=json.loads((l/'gp_native_repair01/SUMMARY.json').read_text());lines+=['',f"Calibration gradient calls: WALNUTS {sum(x['calls']['gradient'] for x in cal['rows'] if 'calls' in x):,}; native {sum(x['calls']['gradient'] for x in native['rows'] if 'calls' in x):,}. Reported separately because settings on both sides have prior research history. No asymmetric calibration charge supports a performance claim.",'','Eight new seed sets, unchanged reference/accuracy gates and all numerical diagnostics replayed independently. Initializers, metric estimators and implementation/compiler stacks differ. This is a narrow workflow/target-call result, not matched-kernel causality, full end-to-end runtime or general superiority. The prior default-WALNUTS ratio.7001 remains a valid negative result. No thresholds or seeds were revised.','','If the signal passes, next isolate the contribution of refinement versus metric/step adaptation using the selected metric and frozen step, with exact-reference checks and matched native geometry. Also test centered GP and approximate-inference controls before practical application claims. If it fails, do not promote the selected arm or reinterpret calibration as validation. The model has only11 counts and13 parameters; novelty, generality, a useful real application and goal completion remain unproven.','','Evidence includes all28 fits,builds,both failed attempts,driver parity,selection hash and sources. A verified local archive preserves raw draws,models and executables. No off-device-backup or production-change claim.']
(p/'GP-WAL-SELECTED-RESULT.md').write_text('\n'.join(lines)+'\n');(l/'gp_wal_selected_validation01/REPLAY.json').write_text(json.dumps(dict(passed=True,verified_fits=verified),indent=2)+'\n');files={}
for name in ['gp_wal_build01','gp_wal_build02','gp_wal_driver_test01','gp_wal_driver_test02','gp_wal_calibration01','gp_wal_selected_validation01']:
    for f in (l/name).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for pattern in ['*gp_wal*.py','GP-WAL-*']:
    for f in p.glob(pattern):
        if f.is_file():files[f.name]=f
for name in ['gp_wal_pristine_runner','gp_wal_tuned_runner']:
    for f in (p/name).rglob('*'):
        if f.is_file() and 'target' not in f.relative_to(p/name).parts:files[str(f.relative_to(p))]=f
for row in val['rows']:
    if 'inputs' in row:
        for f in row['inputs']:
            f=Path(f)
            try:n=str(f.relative_to(p))
            except ValueError:n='binary/'+f.name
            files[n]=f
for row in json.loads((l/'gp_wal_build02/SUMMARY.json').read_text())['rows']:
    f=Path(row['binary']);assert hashlib.sha256(f.read_bytes()).hexdigest()==row['binary_sha256'];files['binary/'+f.name]=f
repo=p.parents[2]
for folder in [repo/'src',repo/'integrations/bridgestan/src']:
    for f in folder.rglob('*'):
        if f.is_file():files['repository/'+str(f.relative_to(repo))]=f
for n in ['Cargo.toml','Cargo.lock','integrations/bridgestan/Cargo.toml']:files['repository/'+n]=repo/n
f=l/'gp_repair_comparison_archive01/VERIFICATION.json';files[str(f.relative_to(p))]=f
out=l/'gp_wal_selected_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(b);t.addfile(info,io.BytesIO(b))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local selected-GP evidence including sources/models/binaries and failures; parent archive remains a dependency; not off-device backup');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
