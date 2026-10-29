"""Read-only full archive member verification, without filesystem extraction."""
import hashlib,json,sys,tarfile
from pathlib import Path,PurePosixPath


def run(path,expected):
    path=Path(path);digest=hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
    if digest!=expected:raise ValueError('Archive checksum mismatch')
    manifest=None;frozen=None;names=set()
    with tarfile.open(path,'r|gz') as tar:
        for m in tar:
            if m.name in names:raise ValueError('Duplicate members')
            names.add(m.name)
            if not m.isfile() or PurePosixPath(m.name).is_absolute() or '..' in PurePosixPath(m.name).parts:raise ValueError('Unsafe member')
            stream=tar.extractfile(m)
            if m.name=='EVIDENCE-MANIFEST.json':manifest=json.load(stream);continue
            if manifest is None:raise ValueError('Manifest must be first')
            meta=manifest[m.name]
            if m.name=='main-v1/MANIFEST.json':
                data=stream.read();frozen=json.loads(data);member_hash=hashlib.sha256(data).hexdigest()
            else:member_hash=hashlib.file_digest(stream,'sha256').hexdigest()
            if m.size!=meta['bytes'] or member_hash!=meta['sha256']:raise ValueError(m.name)
    if names!=set(manifest)|{'EVIDENCE-MANIFEST.json'}:raise ValueError('Unexpected member set')
    for name,digest in frozen['sources'].items():
        if manifest['source/'+name]['sha256']!=digest:raise ValueError('Executed-source drift')
    result=dict(sha256=expected,bytes=path.stat().st_size,verified_manifest_members=len(manifest),main_sources_match=True,
        s3_status='Not uploaded: local AWS login expired; EC2 originals and this local verified archive retained')
    print(json.dumps(result,indent=2))


if __name__=='__main__':run(*sys.argv[1:])
