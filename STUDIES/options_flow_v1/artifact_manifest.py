"""Hash terminal-cell raw draws without mistaking a running output for evidence."""
import argparse
import hashlib
import json
from pathlib import Path


def manifest(root):
    root=Path(root).resolve(); entries=[]; skipped=[]
    for path in sorted(root.rglob('*-raw.json')):
        report=path.with_name(path.name.replace('-raw.json','-report.json'))
        if not report.exists() and path.name=='python-pymc-raw.json':
            # Compile-once PyMC tiers store each immutable fit under this name.
            report=path.with_name('fit-report.json')
        if not report.exists():
            skipped.append({'path':str(path.relative_to(root)),'reason':'no report'})
            continue
        result=json.loads(report.read_text())
        if result.get('status') not in ('completed','failed'):
            skipped.append({'path':str(path.relative_to(root)),'reason':'cell not terminal'})
            continue
        before=path.stat(); digest=hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda:handle.read(1024*1024),b''): digest.update(chunk)
        after=path.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise RuntimeError(f'Artifact changed while hashing: {path}')
        entries.append({'path':str(path.relative_to(root)).replace('\\','/'),
            'bytes':after.st_size,'sha256':digest.hexdigest(),'cell_status':result['status'],
            'report_path':str(report.relative_to(root)).replace('\\','/'),
            'report_sha256':hashlib.sha256(report.read_bytes()).hexdigest()})
    return {'schema':'options-flow-raw-artifacts-v1','entries':entries,'skipped':skipped,
        'scope':'Local raw-array integrity only; does not establish scientific qualification.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path)
    args=p.parse_args()
    # A new snapshot name preserves earlier manifests as more cells finish.
    with args.output.open('x',encoding='utf-8') as handle:
        json.dump(manifest(args.root),handle,indent=2,allow_nan=False)
