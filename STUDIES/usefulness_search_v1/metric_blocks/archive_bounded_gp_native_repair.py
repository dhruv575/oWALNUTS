import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'bounded_gp_native_repair01';s=json.loads((r/'SUMMARY.json').read_text());assert s['completed'] and len(s['rows'])==32;files={}
for n,h in s['source_hashes'].items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h
for row in s['rows']:
    for name,h in row.get('inputs',{}).items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
    if 'functionals' in row:
        f=row['functionals'];assert all(np.isfinite(v).all() for v in f.values())
        assert min(f['bulk'])==row['bulk'] and min(f['tail'])==row['tail'] and max(f['rhat'])==row['rhat']
        passed=row['rhat']<=1.01 and row['bulk']>=400 and row['tail']>=400 and row['divergences']==0 and row['max_z']<=4.5 and row['max_mean_sd']<=.1 and row['max_sd_error']<=.1
        assert passed==row['passed']
expected={(fold,t,m,a) for fold in range(4) for t in ['raw','bounded'] for m in ['diag','low_rank'] for a in [.999,.9999]}
assert {(x['fold'],x['transform'],x['mode'],x['target_accept']) for x in s['rows']}==expected
for selection in s['selected']:
    candidates=[]
    for mode in ['diag','low_rank']:
        for accept in [.999,.9999]:
            subset=[x for x in s['rows'] if x['transform']==selection['transform'] and x['mode']==mode and x['target_accept']==accept]
            if all(x['passed'] for x in subset):
                score=float(np.exp(np.mean(np.log([x['calls']['gradient']/x['bulk'] for x in subset]))))
                candidates.append((score,-accept,mode!='diag',mode,accept))
    candidates.sort()
    if not candidates:assert selection['selection'] is None
    else:
        chosen=selection['selection'];best=candidates[0]
        assert chosen['mode']==best[3] and chosen['target_accept']==best[4]
        assert np.isclose(chosen['calls_per_min_bulk_ess_geomean'],best[0],rtol=1e-12)
lines=['# Direct bounded-map full-chain calibration','','Separate native calibration after the failed bounded validation. Four configurations per transform, all four fresh seeds,8000 retained draws per chain. Earlier failures remain unchanged. No WALNUTS competitive claim follows from this additional baseline search.','','| Transform | Mode | Target acceptance | Qualified folds | Retained divergences | Geometric calls/minimum bulk ESS |','|---|---|---|---|---|---|']
for transform in ['raw','bounded']:
    for mode in ['diag','low_rank']:
        for accept in [.999,.9999]:
            rows=[x for x in s['rows'] if x['transform']==transform and x['mode']==mode and x['target_accept']==accept]
            if not rows:continue
            assert len(rows)==4;v=float(np.exp(np.mean(np.log([x['calls_per_min_bulk_ess'] for x in rows])))) if all('calls_per_min_bulk_ess' in x for x in rows) else None;lines.append(f"| {transform} | {mode} | {accept} | {sum(x['passed'] for x in rows)}/4 | {sum(x.get('divergences',0) for x in rows)} | {v} |")
cost={engine:sum(x.get('calls',{}).get('gradient',0) for x in s['rows'] if x['mode'].startswith('walnuts')==(engine=='walnuts')) for engine in ['walnuts','native']};lines+=['','Selections: '+json.dumps(s['selected']),'','All-fit calibration gradient costs: '+json.dumps(cost), '','Costs above exclude full pilot generation and fitting; retain the original map-pilot ledger for both transformed engines. Unqualified rows are diagnostic only. No competitive ratio or generality claim is justified by calibration selection. Fresh validation with strong raw/affine/native controls and original-space gates is required, along with complete pilot/fitting expense and serial timing before any practical-value claim. No production change, novelty claim or goal completion.']
(p/'BOUNDED-GP-NATIVE-REPAIR-RESULT.md').write_text('\n'.join(lines)+'\n')
for dirname in ['bounded_gp_native_repair01','bounded_gp_counter01']:
    for f in (l/dirname).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for name in ['BOUNDED-GP-NATIVE-REPAIR-PROTOCOL.md','BOUNDED-GP-NATIVE-REPAIR-RESULT.md','prepare_bounded_gp_native_repair.py','bounded_gp_native_repair_worker.py','run_bounded_gp_native_repair.py','archive_bounded_gp_native_repair.py','native_common.py','local_recovery/bounded_gp_target_archive01/VERIFICATION.json','local_recovery/gp_transport_calibration01/COST-LEDGER.json','local_recovery/localscaled01/REFERENCES.json']:files[name]=p/name
auditpath=l/'native_repair_mixing_audit01/SUMMARY.json';audit=json.loads(auditpath.read_text())
for name,h in audit['inputs'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
for f in [auditpath,p/'audit_native_repair_mixing.py']:files[str(f.relative_to(p))]=f
out=l/'bounded_gp_native_repair_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    raw=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        raw=t.extractfile(n).read();assert len(raw)==m['bytes'] and hashlib.sha256(raw).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local archive, depends on preserved target/input archives; not off-device');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
