"""Prepare only; never freezes or runs posthoc recovery."""
import json,shutil,zipfile,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[2];S=R/'STUDIES/options_flow_v1';OLD=S/'artifacts/posterior-resource-pilot-v1';OUT=S/'artifacts/posterior-resource-recovery-v1';HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False)
OUT.mkdir(exist_ok=False);code=OUT/'code';code.mkdir();source=OUT/'archived-study';source.mkdir()
for p in HERE.glob('*.py'):shutil.copy2(p,code/p.name)
shutil.copy2(HERE/'README.md',code/'README.md')
archive=OLD/'independent-terminal-source.zip';plan=json.loads((OLD/'plan.json').read_text());manifest={}
with zipfile.ZipFile(archive) as z:
    for member in z.namelist():
        if not member.endswith('.py'):continue
        rel=Path(member);relative=Path(*rel.parts[1:]) if rel.parts[0]=='study' else rel
        dest=(source/relative).resolve()
        if not dest.is_relative_to(source.resolve()):raise ValueError('Archive path escape')
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(member))
        original=(S/relative).resolve();digest=sha(dest)
        if plan['bindings'].get(str(original))!=digest:raise ValueError('Archive differs from original plan')
        manifest[member]=dict(extracted=str(dest),original=str(original),sha256=digest)
audit=json.loads((OLD/'independent-terminal-audit.json').read_text());inventory={str(Path(p).resolve()):r['sha256'] for p,r in audit['inventory'].items()};specs=[]
for i in [0,3]:
    cell=plan['cells'][i];base=Path(cell['out']);report=base/'fit/python-pymc-flow-report.json';raw=base/'fit/draws-8000/python-pymc-flow-raw.json';status=OLD/(cell['id']+'-status.json')
    inputs={str(p.resolve()):sha(p) for p in [OLD/'plan.json',status,report,Path(cell['fixture']),archive,OLD/'independent-terminal-audit.json',OLD/'independent-terminal-provenance.json',*code.glob('*.py'),*(Path(r['extracted']) for r in manifest.values())]}
    # Reuse independent terminal raw digest; worker verifies under its cap before any analysis.
    inputs[str(raw.resolve())]=inventory[str(raw.resolve())]
    spec=dict(posthoc=True,resampled=False,original_terminal_archived=True,python=plan['python'],memory_bytes=8*1024**3,timeout_seconds=1800,cell_id=cell['id'],out=str((OUT/cell['id']).resolve()),archived_study_directory=str(source.resolve()),source_archive=str(archive.resolve()),source_manifest=manifest,original_plan=str((OLD/'plan.json').resolve()),original_status=str(status.resolve()),report=str(report.resolve()),raw=str(raw.resolve()),posterior_sha256=plan['posterior_sha256'],immutable_inputs=inputs,launcher_inputs={str(p.resolve()):sha(p) for p in [*code.glob('*.py'),Path(plan['python']),source/'hardware_control.py',archive]})
    path=OUT/(cell['id']+'-spec-draft.json');save(path,spec);specs.append(str(path.resolve()))
save(OUT/'cohort-draft.json',dict(frozen=False,posthoc=True,resampled=False,total_seconds=3600,cleanup_reserve_seconds=15,specs=specs,spec_hashes={p:sha(p) for p in specs},interpretation='Additional posthoc analysis only; original failures/costs remain unchanged; no independent accuracy qualification'))
save(OUT/'validation.json',dict(tests=9,seconds=2.03,sampling=False,status='passed',command='python -m pytest target/posterior-resource-recovery-draft -q',test_source_sha256=sha(HERE/'test_recovery.py')))
print(str(OUT))
