import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
import arviz as az
p=Path(__file__).resolve().parent;l=p/'local_recovery';cal=json.loads((l/'gp_native_repair01/SUMMARY.json').read_text());val=json.loads((l/'gp_fresh_comparison01/SUMMARY.json').read_text());assert cal['completed'] and val['completed'];verified=0
for root,s in [(l/'gp_native_repair01',cal),(l/'gp_fresh_comparison01',val)]:
    for row in s['rows']:
        if row.get('completed') is False:continue
        folder=root/(f"{row['mode']}-{row['target_accept']}-{row['seed']}" if root.name=='gp_native_repair01' else f"{row['mode']}-{row['seed']}")
        for f,h in row['inputs'].items():assert hashlib.sha256(Path(f).read_bytes()).hexdigest()==h
        with np.load(folder/'FUNCTIONALS.npz') as z:x=z['values']
        ds=az.convert_to_dataset({'p':x});bulk=np.asarray(az.ess(ds,method='bulk').p);tail=np.asarray(az.ess(ds,method='tail').p);rh=np.asarray(az.rhat(ds,method='rank').p);assert float(min(bulk))==row['bulk'] and float(min(tail))==row['tail'] and float(max(rh))==row['rhat'];assert row['calls_per_min_bulk_ess']==row['calls']['gradient']/row['bulk'];verified+=1
lines=['# GP qualification repair and fresh workflow comparison','','The native baseline is repairable without changing the model. Target acceptance.9 retains divergences on both calibration seeds for both metric modes. All four diagonal/low-rank configurations at.99 or.999 pass both seeds. The frozen calibration criterion selects low_rank,.99 at786.6 actual gradient calls per minimum bulkESS. This replaces the inadequate.8 default baseline for this target; earlier native failures must not be described as an inherent WALNUTS advantage.','','Eight fresh paired seed sets use4 chains,1100 warmup,2000 retained draws with the selected native configuration and existing WALNUTS automatic adaptation. Initializers differ, so this compares workflows. Actual target calls include initialization/warmup and retained sampling; calibration cost is reported separately. Same accuracy gates and qualified reference, no discarded fits.','','| Workflow | Qualified fits | Divergences total | Median minimum bulkESS | Median total gradient calls |','|---|---:|---:|---:|---:|']
for mode in ['low_rank','walnuts_auto']:
    subset=[x for x in val['rows'] if x['mode']==mode];good=[x for x in subset if 'bulk' in x];lines.append(f"| {mode} | {sum(x['passed'] for x in subset)}/8 | {sum(x['divergences'] for x in good)} | {np.median([x['bulk'] for x in good]):.1f} | {np.median([x['calls']['gradient'] for x in good]):.0f} |")
if val['comparison']:
    c=val['comparison'];lines+=['',f"WALNUTS/native minimum-bulkESS-per-total-call geometric ratio: **{c['walnuts_native_efficiency_ratio']:.4f}**, paired95% bootstrap interval **[{c['interval'][0]:.4f},{c['interval'][1]:.4f}]**. Above1 favors WALNUTS. Frozen signal gate passed: **{val['signal_passed']}**."]
else:lines+=['','At least one fit failed qualification; the frozen all-pair efficiency ratio is withheld. No performance credit from excluding failed fits.']
cal_calls=sum(x['calls']['gradient'] for x in cal['rows'] if 'calls' in x);lines+=['',f'Native calibration expense: {cal_calls:,} actual gradient calls across12 fits. This is not selectively charged to native for a steady-workflow claim; WALNUTS settings also benefited from earlier research. Post-import operation clocks are preserved but are not end-to-end timing and are not the primary gate.','','All recorded functionals were independently replayed through the bulk/tailESS and rank R-hat computations; target/source/reference hashes match. Counter receipts and raw arrays remain archived. There is no default change, application-value result, uniqueness claim, or goal completion. The target has only11 observed counts and13 parameters, and model-rewrite and approximate-inference controls are not yet tested.','','Next reviewed step: before any further GP superiority claim, give WALNUTS equal bounded calibration over metric and acceptance settings, then validate only the frozen selection on new seeds against this repaired native control. If the calibrated comparison remains negative, close this benchmark route rather than weakening reference or divergence gates. Centered GP/model rewrites and approximate controls remain necessary for practical usefulness even if a later sampler screen passes.']
(p/'GP-REPAIR-COMPARISON-RESULT.md').write_text('\n'.join(lines)+'\n');(l/'gp_fresh_comparison01/REPLAY.json').write_text(json.dumps(dict(passed=True,verified_fits=verified),indent=2)+'\n');files={}
for folder in [l/'gp_native_repair01',l/'gp_fresh_comparison01']:
    for f in folder.rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for pattern in ['*gp*repair*.py','*gp*comparison*.py','GP-NATIVE-*','GP-FRESH-*','GP-REPAIR-*']:
    for f in p.glob(pattern):
        if f.is_file():files[f.name]=f
for n in ['native_common.py','model_online.rs']:files[n]=p/n
for row in val['rows']:
    if 'inputs' in row:
        for f in row['inputs']:
            f=Path(f);files[str(f.relative_to(p))]=f
out=l/'gp_repair_comparison_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(b);t.addfile(info,io.BytesIO(b))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local archive with executed binary/models, raw fits and calibration; not off-device backup');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
