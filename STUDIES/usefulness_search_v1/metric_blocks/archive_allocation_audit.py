import hashlib,io,json,tarfile
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';files={}
for name in ['allocation_audit01','allocation_prefix01']:
    s=json.loads((l/name/'SUMMARY.json').read_text());assert s['passed'] and s['unchanged']
    for f,h in s['inputs'].items():assert hashlib.sha256(Path(f).read_bytes()).hexdigest()==h
audit=json.loads((l/'allocation_audit01/SUMMARY.json').read_text())
for row in audit['rows']:
    stem=row['target']+'-'+row['metric'];old=json.loads((l/'cold_recycling_test01'/(stem+'-original')/'RAW.json').read_text())
    for enabled in [False,True]:
        data=json.loads((l/'allocation_audit01'/f'{stem}-{enabled}'/'RAW.json').read_text())
        for i,(a,b) in enumerate(zip(old['chains'],data['chains'])):
            for k in a:
                if k!='seconds':assert a[k]==b[k]
            c=b['allocation_counts'];events=c['alloc']+c['alloc_zeroed']+c['realloc'];assert sum(c['request_size_bins'])==events
            if enabled:
                for k in c:assert row['chains'][i][k]==c[k]
            else:assert events==c['requested_bytes']==c['dealloc']==c['freed_bytes']==0
prefix=json.loads((l/'allocation_prefix01/SUMMARY.json').read_text())
for row in prefix['rows']:
    stem=row['target']+'-diagonal';full=json.loads((l/'cold_recycling_test01'/(stem+'-full')/'RAW.json').read_text());counts={}
    for n in [1,1000,4000]:
        folder=l/'allocation_audit01'/(stem+'-True') if n==4000 else l/'allocation_prefix01'/f'{stem}-{n}';data=json.loads((folder/'RAW.json').read_text());counts[n]=sum(sum(c['allocation_counts'][k] for k in ['alloc','alloc_zeroed','realloc']) for c in data['chains'])
        if n!=4000:
            for a,b in zip(data['chains'],full['chains']):assert a['draws']==b['draws'][:n]
    assert (counts[4000]-counts[1000])/12000==row['marginal_events_per_retained_draw']
(p/'ALLOCATION-AUDIT-REPLAY.json').write_text(json.dumps(dict(passed=True,scope='Independent counter/parity/prefix replay; no timing or optimization claim'),indent=2)+'\n')
for name in ['allocation_probe_build01','allocation_audit01','allocation_prefix01']:
    for f in (l/name).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for f in (p/'allocation_probe_runner').rglob('*'):
    if f.is_file():files[str(f.relative_to(p))]=f
for pattern in ['*allocation*.py','allocation_probe.rs','ALLOCATION-*','banana_core.rs']:
    for f in p.glob(pattern):
        if f.is_file():files[f.name]=f
for name in ['cold_recycling_archive01','curved_cold_comparison_archive01']:
    f=l/name/'VERIFICATION.json';files[str(f.relative_to(p))]=f
b=audit['build'];binary=Path(b['binary']);assert hashlib.sha256(binary.read_bytes()).hexdigest()==b['binary_sha256'];files['binary/allocation-probe']=binary
out=l/'allocation_audit_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local verified allocation/prefix audit; prior source/evidence archives remain dependencies; not off-device backup');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
