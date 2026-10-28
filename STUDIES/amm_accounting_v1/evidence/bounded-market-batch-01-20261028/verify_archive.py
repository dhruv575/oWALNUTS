"""Verify full batch archive, bind summaries, preserve small reviewable evidence."""
from pathlib import Path
import hashlib,io,json,sys,tarfile
import numpy as np
from bounded_market_common import physical_draws,differences

def run(archive,batch,expected,destination):
    archive=Path(archive);base=Path(destination);batch=int(batch)
    with archive.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    if digest!=expected:raise ValueError('Archive SHA256')
    base.mkdir(exist_ok=False);manifest={};small={};joints={};observed_joint={};draw_counts={}
    with tarfile.open(archive) as tar:
        for member in tar:
            if not member.isfile():continue
            name=member.name;dest=base/name
            if not dest.resolve().is_relative_to(base.resolve()):raise ValueError('Unsafe archive member')
            raw=tar.extractfile(member).read();manifest[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            if name.endswith('.npz'):
                with np.load(io.BytesIO(raw)) as data:
                    if not all(np.isfinite(data[k]).all() for k in data.files):raise ValueError('Nonfinite array '+name)
                    key=Path(name).parent.as_posix()
                    if name.endswith('/draws.npz'):
                        a=data['draws'];assert a.shape==(4,4000,253)
                        j=int(Path(name).parts[1].split('-')[1]);cap=[.5,1.,2.][j%3]
                        joints[key]=physical_draws(a,cap)[1];draw_counts[key]=len(a)*a.shape[1]
                        if '/nuts/' in name:assert data['warmup'].shape==(4,2000,253)
                        if '/walnuts/' in name:assert data['divergent'].shape==(4,6000) and data['depth'].shape==(4,6000)
                    elif name.endswith('/joint.npz'):observed_joint[key]=data['draws'].copy()
                continue
            dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);small[name]=raw
    assert joints.keys()==observed_joint.keys()
    for key in joints:np.testing.assert_allclose(joints[key],observed_joint[key],rtol=1e-12,atol=1e-13)
    freeze=json.loads(small['FREEZE.json']);assert manifest['SEED-AUDIT.json']['sha256']==freeze['seed_audit_sha256']
    prefix=f'batch-{batch:02d}/';plan=json.loads(small[prefix+'PLAN.json'])
    assert plan['freeze_sha256']==manifest['FREEZE.json']['sha256']
    assert plan['indices']==list(range(12*batch,12*batch+12))
    outer=json.loads(small[prefix+'SUPERVISION.json']);assert outer['group_drained'] and outer['sources_unchanged']
    finals=json.loads(small[prefix+'FINAL.json']);assert [r['index'] for r in finals]==plan['indices']
    rows=[]
    for j in plan['indices']:
        name=prefix+f'job-{j}/fit/REPORT.json'
        if name not in small:
            rows.append(dict(index=j,status='missing_report'));continue
        r=json.loads(small[name]);assert r['index']==j
        for method,result in r['methods'].items():
            receipt=json.loads(small[prefix+f'job-{j}/fit/{method}/SUPERVISION.json']);assert receipt['group_drained']
            if result['status']=='sampled':assert draw_counts[prefix+f'job-{j}/fit/{method}']==16000
        for comparison in r['comparisons']:
            assert abs(comparison['model']+comparison['inference']-comparison['total'])<1e-12
        rows.append(dict(index=j,cap=r['cap'],fixture_index=r['fixture']['index'],month=r['fixture']['month'],tick=r['fixture']['tick'],methods={k:dict(status=v['status'],qualified=v['qualified'],prediction=v.get('prediction')) for k,v in r['methods'].items()},comparisons=r['comparisons']))
    (base/'.gitattributes').write_text('* -text\n');(base/'FULL-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    receipt=dict(sha256=digest,bytes=archive.stat().st_size,files=len(manifest),batch=batch,raw_joint_reconstruction_verified=True,source_freeze_and_seed_audit_bound=True,method_draw_sets=len(joints),scope='Array and provenance verification; coordinate/functional diagnostics are preserved reports, not newly recomputed ArviZ estimates')
    (base/'ARCHIVE-VERIFIED.json').write_text(json.dumps(receipt,indent=2)+'\n');(base/'SUMMARY.json').write_text(json.dumps(rows,indent=2)+'\n')
    (base/'verify_archive.py').write_bytes(Path(__file__).read_bytes());print(json.dumps(receipt))

if __name__=='__main__':run(*sys.argv[1:])
