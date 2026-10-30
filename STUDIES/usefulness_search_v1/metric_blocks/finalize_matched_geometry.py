import hashlib,io,json,tarfile
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'matched_geometry01';s=json.loads((root/'SUMMARY.json').read_text());rows=[]
for entry in s['rows']:
    folder=root/entry['model'];sup=json.loads((folder/'SUPERVISION.json').read_text());assert sup['group_drained']
    if entry['completed']:
        r=json.loads((folder/'SUMMARY.json').read_text())
        for p,h in r['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
        ratios=None
        if r['native']['passed'] and r['walnuts']['passed']:
            ratios={k:r['walnuts']['bulk']/r['walnuts'][cost]/(r['native']['bulk']/r['native'][cost]) for k,cost in [('efficiency','continuation_calls'),('workflow_efficiency','workflow_calls')]}
            assert ratios==r['qualified_ratios']
        rows.append(dict(model=entry['model'],native_pass=r['native']['passed'],walnuts_pass=r['walnuts']['passed'],ratios=ratios))
    else:rows.append(dict(model=entry['model'],failure='Worker failed; preserved log identifies reconstruction-gate assertion. No continuation comparison.'))
lines=['# Matched-geometry diagnostic','', 'Exposed single-seed diagnostic; no fresh efficacy or application claim.','', '| Target | Native pass | WALNUTS pass | ESS/call ratio, continuation | ESS/call ratio, full workflow |','|---|---|---|---|---|']
for r in rows:
    ratio=r.get('ratios');lines.append('| '+r['model']+' | '+str(r.get('native_pass','unavailable'))+' | '+str(r.get('walnuts_pass','unavailable'))+' | '+(f"{ratio['efficiency']:.3f} | {ratio['workflow_efficiency']:.3f}" if ratio else 'unqualified | unqualified')+' |')
lines+=['','ARMA failed the reconstruction gate before WALNUTS sampling; retain this failure. All other workers completed. The three qualified pairs favor native NUTS at these shared geometries and native-tuned fixed steps. This does not establish native superiority under WALNUTS-specific step tuning. Do not use wall time: parallelism differs.','', 'Default native step-size jitter caused the first prefix qualification to fail its fixed-step requirement. A separate no-jitter batch passed all six prefix, geometry/step and actual-call difference checks. Original benchmark settings and results were not changed.','', 'Next diagnostic: a prespecified bounded WALNUTS step-size ladder on these exposed metrics, followed by fresh whole-pilot replication only if a meaningful qualified signal emerges. No selection on these data can count as confirmation.']
(study/'MATCHED-GEOMETRY-REPORT.md').write_text('\n'.join(lines)+'\n')
(study/'MATCHED-GEOMETRY-ANALYSIS.json').write_text(json.dumps(dict(rows=rows,scope='Exposed diagnostic; qualified point-ratio replay only.'),indent=2)+'\n')
files={str(p.relative_to(local)):p for p in root.rglob('*') if p.is_file()}
for name in ['matched_geometry_worker.py','run_matched_geometry.py','finalize_matched_geometry.py','MATCHED-GEOMETRY-DIAGNOSTIC.md','MATCHED-GEOMETRY-REPORT.md','MATCHED-GEOMETRY-ANALYSIS.json']:
    files['source/'+name]=study/name
dest=local/'matched_geometry_archive01';dest.mkdir(exist_ok=False);manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()};archive=dest/'evidence.tar.gz'
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for n,p in files.items():t.add(p,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,r in manifest.items():
        data=t.extractfile(n).read();assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
out=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local evidence read-back, not statistical success or off-device backup.')
(dest/'VERIFICATION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
