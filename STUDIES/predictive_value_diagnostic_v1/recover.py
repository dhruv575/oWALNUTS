"""Separately authorized infrastructure recovery; frozen evaluator is unchanged."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import traceback
import numpy as np
import evaluate as original

HERE=Path(__file__).resolve().parent

def exclusive(path,value):
    with path.open('x',encoding='utf8') as handle:
        json.dump(value,handle,indent=2,allow_nan=False)
        handle.write('\n');handle.flush();os.fsync(handle.fileno())

def verify(audit):
    if original.digest(HERE/'FREEZE.json')!=audit['original_freeze_sha256']:raise ValueError('Original FREEZE changed')
    for name,expected in audit['original_files'].items():
        if original.digest(Path(audit['original_directory'])/name)!=expected:raise ValueError('Original output changed')
    freeze=json.loads((HERE/'FREEZE.json').read_bytes())
    for name,expected in freeze['files'].items():
        if original.digest(HERE/name)!=expected:raise ValueError('Frozen implementation changed')
    if original.digest(original.EXACT_PATH)!=freeze['exact_cdf_sha256']:raise ValueError('CDF changed')
    inventory=json.loads((HERE/'ORIGIN-INVENTORY.json').read_bytes())
    for dataset in inventory['datasets']:
        if original.digest(original.SOURCE/dataset['data_file_relative_to_wp97'])!=dataset['data_sha256']:raise ValueError('Data changed')
        for entry in dataset['origins']:
            for source in entry['sources']:
                if original.digest(original.SOURCE/source['file_relative_to_wp97'])!=source['sha256']:raise ValueError('Draw changed')
    return inventory

def run(out):
    audit=json.loads((HERE/'RECOVERY-AUDIT.json').read_bytes())
    started=time.monotonic();deadline=started+audit['remaining_seconds']
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    state=dict(pid=os.getpid(),status='running',started_unix=time.time(),hard_seconds=audit['remaining_seconds'],
        original_status='failed',original_completed_count=len(audit['completed']),new_completed=[],new_sha256={},
        recovery_script_sha256=original.digest(Path(__file__)),audit_sha256=original.digest(HERE/'RECOVERY-AUDIT.json'))
    exclusive(out/'recovery-start.json',state)
    journal=out/'checkpoints';journal.mkdir()
    sequence=0
    def checkpoint(path,value):
        nonlocal sequence
        original.check_deadline(deadline);sequence+=1
        exclusive(journal/f'{sequence:06d}-{path.name}',value)
    try:
        inventory=verify(audit)
        environment=json.loads((HERE/'ENVIRONMENT.json').read_bytes())
        actual=dict(python=original.sys.version,executable=original.sys.executable,numpy=np.__version__,
            scipy=original.scipy.__version__,arviz=original.az.__version__,numba=original.numba.__version__)
        if any(environment[k]!=v for k,v in actual.items()):raise ValueError('Runtime mismatch')
        failed=json.loads((Path(audit['original_directory'])/'full.json').read_bytes())
        expected=[f'{d}-tick-{t:03d}.json' for t in range(1,101) for d in ['sim','real']]
        if audit['completed']+audit['remaining']!=expected or len(audit['remaining'])!=79:raise ValueError('Schedule mismatch')
        for name in audit['completed']:
            raw=(Path(audit['original_directory'])/name).read_bytes()
            with (out/name).open('xb') as handle:handle.write(raw)
            if original.digest(out/name)!=audit['original_files'][name]:raise ValueError('Copied evidence hash mismatch')
        streams={}
        for dataset in inventory['datasets']:
            raw=(original.SOURCE/dataset['data_file_relative_to_wp97']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=dataset['data_sha256']:raise ValueError('Data changed')
            streams[dataset['dataset']]=(dataset,np.asarray(json.loads(raw)['y'],dtype=float))
        original.atomic=checkpoint
        for name in audit['remaining']:
            original.check_deadline(deadline)
            dataset=name.split('-')[0];tick=int(name.split('-')[2].split('.')[0]);data,y=streams[dataset]
            result=original.origin(dataset,data['origins'][tick-1],y,failed['initial_fits'][dataset],deadline,out/name)
            exclusive(out/name,result)
            state['new_completed'].append(name);state['new_sha256'][name]=original.digest(out/name)
            checkpoint(Path('progress.json'),state)
        verify(audit);original.check_deadline(deadline)
        for name in audit['completed']:
            if original.digest(out/name)!=audit['original_files'][name]:raise ValueError('Copied evidence changed')
        for name,expected_hash in state['new_sha256'].items():
            if original.digest(out/name)!=expected_hash:raise ValueError('Recovery evidence changed')
        if original.digest(Path(__file__))!=state['recovery_script_sha256'] or original.digest(HERE/'RECOVERY-AUDIT.json')!=state['audit_sha256']:
            raise ValueError('Recovery source changed')
        state['status']='recovered_complete'
    except BaseException as error:
        state.update(status='failed',error=type(error).__name__,reason=str(error),traceback=traceback.format_exc())
        raise
    finally:
        state.update(ended_unix=time.time(),elapsed_seconds=time.monotonic()-started)
        exclusive(out/'recovery-final.json',state)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args();run(args.out)
