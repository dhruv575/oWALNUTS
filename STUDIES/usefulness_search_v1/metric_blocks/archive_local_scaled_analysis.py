import hashlib,io,json,os,subprocess,sys,tarfile
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';dest=local/'scaled_analysis_archive';dest.mkdir(exist_ok=False)
files={}
for n in ['analyze_local_scaled.py','report_local_scaled.py','archive_local_scaled_analysis.py','LOCAL-SCALED-COMPARISON.json','LOCAL-SCALED-REPORT.md','SCALED-VALIDATION.md','LOCAL-SCALED-VALIDATION.md','RELATED-WORK-CHECK.md','SCORE-GATE-METHODS.md']:
    files[n]=study/n
resource_rows=[];receipts=[]
for i in range(1,9):
    name=f'localscaled{i:02d}';root=local/name;receipt=local/(name+'_archive')/'VERIFICATION.json';r=json.loads(receipt.read_text());archive=receipt.parent/'evidence.tar.gz'
    assert r['passed'] and hashlib.sha256(archive.read_bytes()).hexdigest()==r['sha256']
    with tarfile.open(archive) as tar:
        manifest=json.load(tar.extractfile('EVIDENCE-MANIFEST.json'))
        for n in ['SUMMARY.json','VERIFICATION.json','LOCAL-ADAPTATION.json','REFERENCES.json']:
            raw=tar.extractfile(n).read();assert hashlib.sha256(raw).hexdigest()==manifest[n]['sha256'] and raw==(root/n).read_bytes()
            files[f'local_recovery/{name}/{n}']=root/n
    files[f'local_recovery/{name}_archive/VERIFICATION.json']=receipt;receipts.append(r)
    for p in (root/'runs').glob('*/SUPERVISION.json'):
        sup=json.loads(p.read_text());assert sup['exit_code']==0 and sup['group_drained'] and sup['peak_rss']<=2*1024**3 and sup['final_output_bytes']<=64*1024**2
        resource_rows.append(sup)
assert len(resource_rows)==672
audit=dict(jobs=len(resource_rows),max_peak_rss=max(r['peak_rss'] for r in resource_rows),max_final_output_bytes=max(r['final_output_bytes'] for r in resource_rows),max_elapsed_seconds=max(r['elapsed_seconds'] for r in resource_rows),all_drained=True,archive_sha256s=[r['sha256'] for r in receipts],scope='Terminal supervisor checks and current local archive hash/summary correspondence. Workspace free-space floor was observed separately; old runner checked WSL root rather than workspace filesystem.')
(dest/'RESOURCE-AUDIT.json').write_text(json.dumps(audit,indent=2)+'\n');files['RESOURCE-AUDIT.json']=dest/'RESOURCE-AUDIT.json'
manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()}
archive=dest/'evidence.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
    raw=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('EVIDENCE-MANIFEST.json');info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
    for n,p in files.items():tar.add(p,arcname=n,recursive=False)
replay=dest/'replay';replay.mkdir()
with tarfile.open(archive) as tar:
    for n,e in manifest.items():
        raw=tar.extractfile(n).read();assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256']
        p=replay/n;assert p.resolve().is_relative_to(replay.resolve());p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
subprocess.run([sys.executable,str(replay/'analyze_local_scaled.py')],check=True,env=env,stdout=subprocess.DEVNULL)
a=json.loads((study/'LOCAL-SCALED-COMPARISON.json').read_text());b=json.loads((replay/'LOCAL-SCALED-COMPARISON.json').read_text())
assert {k:v for k,v in a.items() if k!='inputs'}=={k:v for k,v in b.items() if k!='inputs'}
receipt=dict(passed=True,members=len(manifest),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),exact_numeric_analysis_replay=True,continuation_gate=a['continuation_gate'],resource_audit=audit)
(dest/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
