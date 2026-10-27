"""Atomic evidence helpers. No computations run at import."""
import hashlib,json,math
from pathlib import Path
import numpy as np

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def safe(value):
    if isinstance(value,np.ndarray):return safe(value.tolist())
    if isinstance(value,np.generic):return safe(value.item())
    if isinstance(value,float) and not math.isfinite(value):return dict(nonfinite=repr(value))
    if isinstance(value,dict):return {str(k):safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [safe(v) for v in value]
    return value

def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(safe(value),indent=2,allow_nan=False)+'\n');temp.replace(path)

def save_data(directory,data):
    root=Path(directory);root.mkdir(parents=True,exist_ok=True)
    if (root/'data.json').exists():raise FileExistsError('Never regenerate stream data')
    files={}
    for name in ['y','h']:
        path=root/(name+'.npy')
        if path.exists():raise FileExistsError(path)
        np.save(path,data[name],allow_pickle=False);files[name]=dict(file=path.name,sha256=digest(path))
    atomic(root/'data.json',dict(stream=data['stream'],seeds=data['seeds'],parameters=data['parameters'],files=files))

def load_data(directory):
    root=Path(directory);d=json.loads((root/'data.json').read_text())
    for name,entry in d.pop('files').items():
        path=root/entry['file'];raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise ValueError('Generated data hash mismatch')
        import io
        d[name]=np.load(io.BytesIO(raw),allow_pickle=False)
    if np.asarray(d['y']).shape!=(283,) or np.asarray(d['h']).shape!=(283,):raise ValueError('Stream data shape mismatch')
    return d

def preserve_candidate(directory,result,draws):
    root=Path(directory);root.mkdir(parents=True,exist_ok=True)
    if draws is not None and result['rows']:
        row=result['rows'][-1];p=root/f"tick-{row['tick']:02d}.npy"
        if not p.exists():np.save(p,draws,allow_pickle=False)
        row['compact']=dict(file=p.name,sha256=digest(p),shape=list(np.asarray(draws).shape))
    # Preserve scalar report and separate full-precision evaluator arrays.
    def split(value,prefix,arrays):
        if isinstance(value,np.ndarray):arrays[prefix]=value;return dict(array_key=prefix,shape=list(value.shape),dtype=str(value.dtype))
        if isinstance(value,dict):return {k:split(v,prefix+'__'+k,arrays) for k,v in value.items()}
        if isinstance(value,list):return [split(v,prefix+'__'+str(i),arrays) for i,v in enumerate(value)]
        return value
    copy=dict(result);copy['rows']=[]
    for row in result['rows']:
        arrays={};clean=split(row,'row',arrays)
        if arrays:
            p=root/f"tick-{row['tick']:02d}-score-arrays.npz"
            if not p.exists():np.savez_compressed(p,**arrays)
            clean['score_arrays']=dict(file=p.name,sha256=digest(p))
        copy['rows'].append(clean)
    atomic(root/'candidate.json',copy)
