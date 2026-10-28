"""Freeze inherited causal windows and all specialist chain slots, without fitting."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import numpy as np
from development import sha,write


def prepare(root,parent,audit,blocked=False,precision=False):
    if precision and not blocked:raise ValueError('Precision panel requires blocked method')
    root=Path(root).resolve();root.mkdir(exist_ok=False)
    parent=Path(parent).resolve();spec=json.loads(parent.read_bytes())
    for name,digest in spec['sources'].items():
        if sha(name)!=digest:raise ValueError('Inherited source drift')
    sys.path.insert(0,str(Path(spec['worker_path']).parent));sys.path.append(spec['e62_root'])
    import data_contract
    record=json.loads(Path(audit).read_bytes());seeds=record['reserved_seeds']
    methods=[2] if blocked else [0,1];count=96*len(methods)
    if record['status']!='passed' or record['collisions'] or len(seeds)!=count or len(set(seeds))!=count:
        raise ValueError('Complete unique audited seed schedule required')
    shutil.copyfile(parent,root/'PARENT.json');shutil.copyfile(audit,root/'SEED-AUDIT.json')
    windows=[]
    for month in spec['months']:
        data_contract.configure(month['month']);y=data_contract.load_sealed(spec['acquisition'],month['month'])
        for tick in month['reference_ticks']:
            inputs=data_contract.inputs(y,tick);path=root/f'window-{len(windows):02d}.npz'
            np.savez_compressed(path,window=inputs.pop('window'),label=inputs['label'])
            windows.append(dict(month=month['month'],file=str(path),sha256=sha(path),**inputs))
    if len(windows)!=24:raise ValueError('Fixed 24 windows required')
    base=Path(__file__).resolve().parent
    sources={str(p):sha(p) for p in base.glob('*.py')}
    target=base.parent/'sv_prototype/target.py';sources[str(target)]=sha(target)
    write(root/'MANIFEST.json',dict(status='frozen_authorized',windows=windows,seeds=seeds,sources=sources,
                                  parent_path=str(root/'PARENT.json'),parent_sha256=sha(root/'PARENT.json'),
                                  audit_sha256=sha(root/'SEED-AUDIT.json'),runtime=spec['runtime'],
                                  chains=count,methods=methods,warmup=4000 if precision else 1000,retained=8000 if precision else 2000))
    return dict(windows=len(windows),chains=count,manifest_sha256=sha(root/'MANIFEST.json'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('parent');p.add_argument('audit');p.add_argument('--blocked',action='store_true');p.add_argument('--precision',action='store_true');a=p.parse_args()
    print(json.dumps(prepare(a.root,a.parent,a.audit,a.blocked,a.precision)))
