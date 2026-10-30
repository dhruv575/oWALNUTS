import hashlib,io,json,tarfile
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';files={}
q=json.loads((l/'momentum_pool_test02/SUMMARY.json').read_text());assert q['passed']
s=json.loads((l/'momentum_pool_timing02/SUMMARY.json').read_text());assert s['completed']
for target in ['banana_direct','banana_latent','funnel']:
    for i in range(20):
        pair=[json.loads((l/'momentum_pool_timing02'/f'{target}-{i:02d}-{a}/RAW.json').read_text()) for a in range(2)]
        assert len(pair[0]['chains'])==len(pair[1]['chains'])==4
        for a,b in zip(pair[0]['chains'],pair[1]['chains']):
            assert {k:v for k,v in a.items() if k!='seconds'}=={k:v for k,v in b.items() if k!='seconds'}
for name in ['allocation_attribution_source01','allocation_attribution_build01','allocation_attribution01','momentum_pool_source01','momentum_pool_build01','momentum_pool_test01','momentum_pool_test02','momentum_pool_timing01','momentum_pool_timing02']:
    for f in (l/name).rglob('*'):
        if f.is_file() and 'target' not in f.relative_to(l/name).parts:files[str(f.relative_to(p))]=f
for pattern in ['*momentum*.py','*allocation_attribution*.py','allocation_attribution_probe.rs','momentum_pool_fragment.rs','MOMENTUM-*','ALLOCATION-ATTRIBUTION-*']:
    for f in p.glob(pattern):
        if f.is_file():files[f.name]=f
for name in ['allocation_attribution_runner','momentum_pool_runner','momentum_pool_probe_runner']:
    for f in (p/name).rglob('*'):
        if f.is_file() and 'target' not in f.relative_to(p/name).parts:files[str(f.relative_to(p))]=f
for name in ['allocation_attribution_build01','momentum_pool_build01','cold_recycling_build03']:
    for row in json.loads((l/name/'SUMMARY.json').read_text())['rows']:
        binary=Path(row['binary']);assert hashlib.sha256(binary.read_bytes()).hexdigest()==row['binary_sha256'];files['binaries/'+binary.name]=binary
for name in ['allocation_audit_archive01','cold_recycling_archive01']:
    f=l/name/'VERIFICATION.json';files[str(f.relative_to(p))]=f
out=l/'momentum_pool_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local archive with isolated sources, binaries, failures and all timings; prior archives remain dependencies; not off-device backup');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
