from pathlib import Path
import hashlib, io, json, tarfile
import numpy as np
import pandas as pd

archive=Path('target/bounded-multi-full.tar.gz')
expected='9066e526d4a67070a090569f65a25f5379035dfda2ccedd9a0f3ba7f4dbb4c8c'
with archive.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
assert digest==expected
base=Path('STUDIES/amm_accounting_v1/evidence/bounded-multi-20261028')
base.mkdir(exist_ok=False)
manifest={}; small={}; arrays=0
prefix='bounded-multi-20261028/'
with tarfile.open(archive) as t:
    for member in t:
        if not member.isfile(): continue
        assert member.name.startswith(prefix)
        name=member.name[len(prefix):]
        dest=base/name
        assert dest.resolve().is_relative_to(base.resolve())
        with t.extractfile(member) as f:
            raw=f.read()
        manifest[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        if name.endswith('.npz'):
            with np.load(io.BytesIO(raw)) as data:
                for key in data.files: assert np.isfinite(data[key]).all(), (name,key)
                if '/slice-' in name:
                    j=int(name.split('/')[1].split('-')[1]); n=12 if j%3==0 else 250
                    assert data['draws'].shape==(4000,n+3)
                    assert data['warmup'].shape==(1000,n+3)
                    arrays+=1
        if name.endswith(('.npz','.nc')) or '/runtime-cache/' in name: continue
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);small[name]=raw
assert arrays==36
plan=json.loads(small['run01/PLAN.json'])
for name,value in plan['sources'].items(): assert manifest[name]['sha256']==value
outer=json.loads(small['run01/SUPERVISION.json'])
assert outer['exit_code']==0 and outer['group_drained'] and outer['sources_unchanged']
summary=[]
for j in range(9):
    root=f'run01/job-{j}/fit/'
    r=json.loads(small[root+'REPORT.json']);assert r['index']==j
    frames={}
    for method in ['nuts','slice']:
        frame=pd.read_csv(io.BytesIO(small[root+method+'-coordinates.csv']),index_col=0)
        bad=(~np.isfinite(frame[['r_hat','ess_bulk','ess_tail']]).all(axis=1))|(frame.r_hat>1.01)|(frame.ess_bulk<400)|(frame.ess_tail<400)
        assert frame.index[bad].tolist()==r['methods'][method]['failed_coordinates']
        frames[method]=frame
    a,b=frames['slice'],frames['nuts']
    z=(a['mean']-b['mean'])/np.hypot(a.mcse_mean,b.mcse_mean)
    assert np.isclose(abs(z).max(),r['max_abs_mean_z'],rtol=1e-10)
    summary.append(dict(index=j,cap=r['cap'],n=r['n'],case=r['case'],methods=r['methods'],max_abs_mean_z=r['max_abs_mean_z']))
(base/'.gitattributes').write_text('* -text\n')
(base/'FULL-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
receipt=dict(sha256=digest,bytes=archive.stat().st_size,files=len(manifest),sources_verified=True,slice_arrays_verified=arrays,coordinate_csv_diagnostics_reproduced=True,scope='NUTS traces hashed and preserved; diagnostics reproduced from coordinate CSVs, not recomputed from raw NUTS draws')
(base/'ARCHIVE-VERIFIED.json').write_text(json.dumps(receipt,indent=2)+'\n')
(base/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
(base/'verify_archive.py').write_bytes(Path(__file__).read_bytes())
print(json.dumps(receipt))
