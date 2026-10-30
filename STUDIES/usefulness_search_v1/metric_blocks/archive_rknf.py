import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';files={};checks=0
for folder,tuned in [('rknf_leaf_screen01',False),('rknf_tuned01',True)]:
    r=l/folder;s=json.loads((r/'SUMMARY.json').read_text());assert s['completed'];assert not s['passed' if tuned else 'screen_passed']
    for name,h in s['source_hashes'].items():assert hashlib.sha256((p/name).read_bytes()).hexdigest()==h
    for ti,row in enumerate(s['rows']):
        prefix='validation-' if tuned else '';inp=np.load(r/f'{prefix}input-{ti}.npz');arms=[]
        for mode in ['H','RKNF']:
            a=np.load(r/f'{prefix}output-{ti}-{mode}.npz')
            with np.errstate(all='ignore'):score=np.where(a['valid'],np.exp(np.minimum(0,-a['deltaH']))*np.mean((a['q']-inp['q'])**2/inp['variance'],axis=1),0.)
            assert np.array_equal(score,a['score']);assert np.isfinite(score).all();assert float(a['work'].mean())==row['arms'][mode]['mean_calls'];assert float(score.mean())==row['arms'][mode]['mean_score'];arms.append(float(score.mean()/a['work'].mean()));checks+=1
        assert arms[1]/arms[0]==row['ratio' if tuned else 'score_per_call_ratio']
        if tuned:
            cal=json.loads((r/f'CALIBRATION-{ti}.json').read_text())
            for mode in ['H','RKNF']:
                choice=max([x for x in cal['rows'] if x['mode']==mode],key=lambda x:(x['score_per_call'],-x['tolerance']))['tolerance'];assert choice==row['selected'][mode]
    for f in r.rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for folder in ['rknf_leaf_supervision01','rknf_tuned_supervision01']:
    r=l/folder;s=json.loads((r/'SUPERVISION.json').read_text());assert s['exit_code']==0 and s['group_drained']
    for f in r.rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for name in ['rknf_leaf_screen.py','run_rknf_leaf_screen.py','rknf_tuned.py','run_rknf_tuned.py','archive_rknf.py','two_stage_screen.py','RKNF-LEAF-PROTOCOL.md','RKNF-TUNED-PROTOCOL.md','RKNF-LEAF-RESULT.md','ALTERNATIVE-ERROR-SOURCE.json'] :files[name]=p/name
for name in ['inputs/resource_monitor.py','two_stage_screen01/SUMMARY.json','gp_tail_replay_archive01/VERIFICATION.json']:files['local_recovery/'+name]=l/name
out=l/'rknf_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(b);t.addfile(info,io.BytesIO(b))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,arrays_replayed=checks,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local archive, not off-device');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
