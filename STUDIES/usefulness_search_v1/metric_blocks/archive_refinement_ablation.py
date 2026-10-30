import hashlib,io,json,tarfile
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';files={}
for name in ['refinement_ablation01','refinement_ablation02','refinement_ablation_build01','refinement_ablation_test01']:
    for p in (local/name).rglob('*'):
        if p.is_file():files[str(p.relative_to(study))]=p
for name in ['refinement_ablation01','refinement_ablation02']:
    s=json.loads((local/name/'SUMMARY.json').read_text());assert s['unchanged']
    for p,h in s['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
    for r in s['rows']:assert json.loads((local/name/r['folder']/'SUPERVISION.json').read_text())['group_drained']
for p in (study/'refinement_ablation_runner').rglob('*'):
    if p.is_file():files[str(p.relative_to(study))]=p
for name in ['prepare_refinement_ablation.py','build_refinement_ablation.py','prepare_refinement_tests.py','test_refinement_ablation.py','run_refinement_ablation.py','analyze_refinement_ablation.py','prepare_refinement_correction.py','run_refinement_correction.py','prepare_corrected_analysis.py','analyze_refinement_correction.py','archive_refinement_ablation.py','REFINEMENT-ABLATION-PROTOCOL.md','REFINEMENT-ABLATION-CORRECTION.md','REFINEMENT-CORRECTED-REPORT.md','REFINEMENT-CORRECTED-ANALYSIS.json','REFINEMENT-CORRECTED-INTERPRETATION.md','local_recovery/REFINEMENT-ABLATION-PROVENANCE.json']:files[name]=study/name
build=json.loads((local/'refinement_ablation_build01/SUMMARY.json').read_text());binary=Path(build['binary']);assert hashlib.sha256(binary.read_bytes()).hexdigest()==build['binary_sha256'];files['binary/runner']=binary
dest=local/'refinement_ablation_archive01';dest.mkdir(exist_ok=False);archive=dest/'evidence.tar.gz';manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()}
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for n,p in files.items():t.add(p,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,r in manifest.items():
        data=t.extractfile(n).read();assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local evidence/source/binary read-back including original setup error and correction; not off-device backup.')
(dest/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
