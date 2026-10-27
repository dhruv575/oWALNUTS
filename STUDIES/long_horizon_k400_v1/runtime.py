"""Pinned-runtime admission and immutable array helpers, no study work on import."""
import hashlib,importlib.util,importlib.metadata,json,sys,io
from pathlib import Path
import numpy as np

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def module(path,name):
    p=Path(path);sys.path.insert(0,str(p.parent))
    try:
        spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    finally:sys.path.pop(0)
def admit(path):
    spec=json.loads(Path(path).read_text());runtime=spec['runtime']
    if spec.get('status')!='frozen_authorized':raise ValueError('No data/sampling authorization')
    if sys.prefix!=runtime['prefix']:raise ValueError('Runtime prefix mismatch')
    for name,v in runtime['packages'].items():
        if importlib.metadata.version(name)!=v:raise ValueError('Runtime package mismatch '+name)
    for name,v in {**spec['sources'],**runtime['binaries']}.items():
        if sha(name)!=v:raise ValueError('Source/runtime bytes changed '+name)
    return spec

def save_array(path,a):
    import os
    path=Path(path)
    with path.open('xb') as f:np.save(f,a,allow_pickle=False);f.flush();os.fsync(f.fileno())
    return dict(file=path.name,sha256=sha(path),shape=list(a.shape),dtype=a.dtype.str)

def load_data(root,variant):
    root=Path(root)/'data';meta=json.loads((root/'DATA.json').read_text());entry=meta['arrays'][variant+'_y'];raw=(root/entry['file']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise ValueError('Data hash mismatch')
    a=np.load(io.BytesIO(raw),allow_pickle=False)
    if a.dtype!=np.dtype('float64') or a.shape!=(2251,) or not np.isfinite(a).all():raise ValueError('Data schema')
    return a

def evaluator(spec):
    d=spec['dependencies'];m=module(d['evaluator_adapter'],'bound_e61_evaluator_adapter')
    return m.Evaluator(d['predictive_density'],spec['sources'][d['predictive_density']],5.)
