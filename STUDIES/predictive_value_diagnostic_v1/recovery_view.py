"""Materialize a separate reporting view without changing either attempt."""
import argparse
import hashlib
import json
from pathlib import Path

def sha(raw):return hashlib.sha256(raw).hexdigest()

def materialize(recovery,destination):
    recovery=Path(recovery).resolve();destination=Path(destination).resolve()
    destination.mkdir(parents=True,exist_ok=False)
    selected={};invalid=[]
    for path in sorted((recovery/'checkpoints').glob('*-tick-*.json')):
        try:
            raw=path.read_bytes();value=json.loads(raw)
        except (OSError,ValueError) as error:
            invalid.append(dict(path=str(path),error=type(error).__name__));continue
        name=f"{value['dataset']}-tick-{value['tick']:03d}.json"
        if path.name.split('-',1)[1]!=name:raise ValueError('Checkpoint origin mismatch')
        selected[name]=(path,raw,'partial_checkpoint')
    for path in recovery.glob('*-tick-*.json'):
        try:raw=path.read_bytes();json.loads(raw)
        except (OSError,ValueError) as error:
            invalid.append(dict(path=str(path),error=type(error).__name__));continue
        selected[path.name]=(path,raw,'completed_origin')
    records=[]
    for name,(source,raw,kind) in sorted(selected.items()):
        path=destination/name
        with path.open('xb') as handle:handle.write(raw)
        if sha(path.read_bytes())!=sha(raw):raise ValueError('Reporting copy mismatch')
        records.append(dict(origin=name,source=str(source),sha256=sha(raw),kind=kind))
    manifest=dict(scope='Amended recovery reporting view; original attempt remains failed and incomplete',
        recovery_directory=str(recovery),origins=records,invalid_files_retained_in_original_location=invalid)
    with (destination/'REPORTING-PROVENANCE.json').open('x',encoding='utf8') as handle:
        json.dump(manifest,handle,indent=2);handle.write('\n')
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('recovery');parser.add_argument('destination')
    args=parser.parse_args();materialize(args.recovery,args.destination)
