import hashlib,io,json,tarfile
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_intensity_coverage01'
s=json.loads((r/'SUMMARY.json').read_text());assert len(s['rows'])==48
for name,h in s['inputs'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
supervision=json.loads((l/'gp_intensity_coverage_supervision01/SUMMARY.json').read_text());assert supervision['exit_code']==0 and supervision['group_drained']
lines=['# Posthoc intensity coverage audit','','Saved draws from the failed bounded validation were re-evaluated on24 quantities: rho,alpha,11 log intensities and11 intensities. This is not fresh validation and does not change the original all-fit failure.','','Both reference summaries agree exactly on shared means/SDs, with maximum MCSE difference1.40e-14. The24-quantity reference passes its stored convergence thresholds. The stricter descriptive accuracy rule uses mean error<=.1 reference SD, relative SD error<=.1 and combined-MCSE z<=4.','','| Workflow | All checks | Accuracy checks |','|---|---|---|']
for transform,mode in [('raw','walnuts_dense'),('raw','low_rank'),('affine','walnuts_dense'),('affine','diag'),('bounded','walnuts_dense'),('bounded','low_rank')]:
    rows=[x for x in s['rows'] if x['transform']==transform and x['mode']==mode];assert len(rows)==8
    accuracy=sum(all(x['gates'][k] for k in ['mean_error','sd_error','combined_z']) for x in rows)
    lines.append(f"| {transform}/{mode} | {sum(x['passed'] for x in rows)}/8 | {accuracy}/8 |")
lines+=['','Only the two previously recorded native divergence failures remain. No intensity accuracy or convergence failures were added. This does not establish practical advantage, fresh predictive validity, novelty or end-to-end speed. No original outcome or threshold is overwritten.']
(p/'GP-INTENSITY-COVERAGE-RESULT.md').write_text('\n'.join(lines)+'\n')
names=['audit_gp_intensity_coverage.py','run_gp_intensity_coverage.py','archive_gp_intensity_coverage.py','GP-INTENSITY-COVERAGE-RESULT.md','GP-COMPARISON-COVERAGE-AUDIT.md','local_recovery/gp_intensity_coverage01/SUMMARY.json','local_recovery/gp_intensity_coverage_supervision01/SUMMARY.json','local_recovery/gp_intensity_coverage_supervision01/worker.log','local_recovery/bounded_gp_validation_archive01/VERIFICATION.json','../gp_count/REFERENCE.json','local_recovery/localscaled01/REFERENCES.json']
files={name.replace('../','parent/'):p/name for name in names};out=l/'gp_intensity_coverage_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz'
manifest={name:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for name,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    raw=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
    for name,f in files.items():t.add(f,arcname=name,recursive=False)
with tarfile.open(archive) as t:
    for name,m in manifest.items():
        raw=t.extractfile(name).read();assert len(raw)==m['bytes'] and hashlib.sha256(raw).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local derived evidence; raw draws depend on preserved bounded validation archive; not off-device')
(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
