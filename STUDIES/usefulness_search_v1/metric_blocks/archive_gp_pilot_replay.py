import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_pilot_replay01';s=json.loads((r/'SUMMARY.json').read_text());assert s['completed'] and len(s['rows'])==4
lines=['# Pilot and bounded-map replay','','All four archived pilots were rerun serially. The preflight checks exact retained draws, total target calls and fitted map parameters; it is not new-map validation or an end-to-end speed comparison.','','| Fold | Passed | Pilot gradients | Sampling seconds | Map fit seconds | JSON seconds |','|---|---|---|---|---|---|']
for row in s['rows']:
    fold=row['fold'];d=r/f'fold-{fold}';old=l/f"gp_fresh_comparison01/low_rank-{row['seed']}"
    for name,h in row.get('inputs',{}).items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
    supervision=json.loads((d/'SUPERVISION.json').read_text());assert supervision['exit_code']==0 and supervision['group_drained']
    checks=dict(draws_bit_identical=np.array_equal(np.load(d/'DRAWS.npz')['q'],np.load(old/'DRAWS-STATS.npz')['sample_stats__unconstrained_draw'],equal_nan=True),calls_identical=row['calls']==json.loads((old/'SUMMARY.json').read_text())['calls'],map_identical=json.loads((d/'MAP.json').read_text())==json.loads((l/f'bounded_transport01/fold-{fold}/MAP.json').read_text()))
    assert checks==row['checks'] and all(checks.values())==row['passed']
    lines.append(f"| {fold} | {row['passed']} | {row['calls']['gradient']} | {row['sampling_seconds']:.6f} | {row['map_fit_seconds']:.6f} | {row['map_serialization_seconds']:.6f} |")
assert s['passed']==all(x['passed'] for x in s['rows'])
lines+=['','Sampling time includes model construction and sampling after imports. Map fitting uses the prescribed400 positions but the complete pilot is charged. JSON timing includes only map serialization, not compiled target-data construction. Process supervision also includes imports, output and comparisons; its polling clock is not a precise short-duration timer. No clocks here establish superiority or replace prospective full-workflow timing.']
(p/'GP-PILOT-REPLAY-RESULT.md').write_text('\n'.join(lines)+'\n')
files={str(f.relative_to(p)):f for f in r.rglob('*') if f.is_file()}
for name in ['GP-PILOT-REPLAY-PROTOCOL.md','GP-PILOT-REPLAY-RESULT.md','gp_pilot_replay_worker.py','run_gp_pilot_replay.py','archive_gp_pilot_replay.py','bounded_transport.py','local_recovery/bounded_transport_archive01/VERIFICATION.json']:files[name]=p/name
out=l/'gp_pilot_replay_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    raw=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        raw=t.extractfile(n).read();assert len(raw)==m['bytes'] and hashlib.sha256(raw).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local replay archive; archived original pilot and target dependencies retained separately; not off-device')
(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
