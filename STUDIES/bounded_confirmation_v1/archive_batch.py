"""Bind drained-batch archives and verified S3 restoration before reclamation."""
import hashlib,json,tarfile,sys
from pathlib import Path
from supervisor import indices,sha,write

def drained(folder,batch):
    report=json.loads((folder/'SUPERVISION.json').read_text())
    final=json.loads((folder/'FINAL.json').read_text())
    if not report.get('group_drained') or not report.get('sources_unchanged'):raise ValueError('Undrained or changed batch')
    if [r['index'] for r in final]!=indices(batch) or not all(r.get('group_drained') for r in final):raise ValueError('Incomplete denominator')

def pack(lane,batch):
    lane=Path(lane).resolve();folder=lane/f'batch-{batch:03d}';drained(folder,batch)
    archive=lane/f'batch-{batch:03d}.tar.gz';manifest={}
    if archive.exists() or (folder/'ARCHIVE-PACKED.json').exists():raise FileExistsError('Inspect existing archive before retry')
    paths=[lane/'FREEZE.json',*sorted(folder.rglob('*'))]
    paths=[p for p in paths if p.is_file() and 'runtime-cache' not in p.parts]
    for p in paths:
        if p.is_symlink() or not p.resolve().is_relative_to(lane):raise ValueError('Unsafe archive source')
        manifest[p.relative_to(lane).as_posix()]=dict(bytes=p.stat().st_size,sha256=sha(p))
    write(folder/'RAW-MANIFEST.json',manifest)
    with tarfile.open(archive,'w:gz') as tar:
        for p in [*paths,folder/'RAW-MANIFEST.json']:tar.add(p,arcname=p.relative_to(lane).as_posix(),recursive=False)
    # Verify actual stored bytes against pre-pack file hashes; no trust in tar creation.
    seen=set()
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar:
            if member.name not in manifest:continue
            with tar.extractfile(member) as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
            expected=manifest[member.name]
            if digest!=expected['sha256'] or member.size!=expected['bytes']:raise ValueError('Packed content mismatch')
            seen.add(member.name)
    if seen!=set(manifest):raise ValueError('Missing archive members')
    receipt=dict(sha256=sha(archive),bytes=archive.stat().st_size,plan_sha256=sha(folder/'PLAN.json'),manifest_sha256=sha(folder/'RAW-MANIFEST.json'),files=len(manifest))
    write(folder/'ARCHIVE-PACKED.json',receipt);return receipt

def admit(lane,batch,upload_path,restore_path):
    lane=Path(lane).resolve();folder=lane/f'batch-{batch:03d}';drained(folder,batch)
    packed=json.loads((folder/'ARCHIVE-PACKED.json').read_text())
    upload=json.loads(Path(upload_path).read_text());restore=json.loads(Path(restore_path).read_text())
    for key in ['sha256','bytes']:
        if upload.get(key)!=packed[key] or restore.get(key)!=packed[key]:raise ValueError('Archive identity mismatch')
    for key in ['bucket','key','version_id']:
        if not upload.get(key) or upload[key]!=restore.get(key):raise ValueError('S3 version binding mismatch')
    if upload.get('encryption')!='AES256' or restore.get('exact_version_restore_verified') is not True:raise ValueError('Restore/encryption admission')
    if sha(folder/'PLAN.json')!=packed['plan_sha256'] or sha(folder/'RAW-MANIFEST.json')!=packed['manifest_sha256']:raise ValueError('Local record drift')
    receipt=dict(**restore,plan_sha256=packed['plan_sha256'],manifest_sha256=packed['manifest_sha256'])
    write(folder/'ARCHIVE-VERIFIED.json',receipt);return receipt

def reclaim(lane,batch):
    lane=Path(lane).resolve();folder=lane/f'batch-{batch:03d}';drained(folder,batch)
    receipt=json.loads((folder/'ARCHIVE-VERIFIED.json').read_text())
    if receipt.get('exact_version_restore_verified') is not True or not receipt.get('version_id'):raise ValueError('Restore required')
    if sha(folder/'RAW-MANIFEST.json')!=receipt['manifest_sha256'] or sha(folder/'PLAN.json')!=receipt['plan_sha256']:raise ValueError('Evidence binding drift')
    manifest=json.loads((folder/'RAW-MANIFEST.json').read_text());remove=[]
    for name,meta in manifest.items():
        if not name.endswith('.npz'):continue
        p=lane/name
        if p.is_symlink() or not p.resolve().is_relative_to(folder):raise ValueError('Unsafe cleanup target')
        if p.stat().st_size!=meta['bytes'] or sha(p)!=meta['sha256']:raise ValueError('Raw file changed')
        remove.append(p)
    archive=lane/f'batch-{batch:03d}.tar.gz'
    if archive.is_symlink() or sha(archive)!=receipt['sha256']:raise ValueError('Archive changed')
    audit=dict(removed=[str(p.relative_to(lane)) for p in remove],archive=str(archive.relative_to(lane)),verified_version=receipt['version_id'],completed=False)
    write(folder/'CLEANUP-STARTED.json',audit)
    for p in remove:p.unlink()
    archive.unlink();audit['completed']=True;write(folder/'CLEANUP.json',audit);return audit

if __name__=='__main__':
    mode,lane,batch,*extra=sys.argv[1:];batch=int(batch)
    print(json.dumps({'pack':pack,'admit':admit,'reclaim':reclaim}[mode](lane,batch,*extra)))
