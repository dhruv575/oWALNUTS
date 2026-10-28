"""Audit explicit scalar seed inventories; engine-internal streams are excluded."""
import hashlib,json,os,sys,time
from pathlib import Path

def integers(v):
    if type(v)is int:yield v
    elif isinstance(v,dict):
        for x in v.values():yield from integers(x)
    elif isinstance(v,list):
        for x in v:yield from integers(x)

def audit(root,out):
    root=Path(root);out=Path(out);assert not out.exists();start=time.monotonic()
    proposed=set(range(398201000,398249800))|set(range(398300000,398300006));inputs=[];collisions=[]
    for folder,dirs,files in os.walk(root):
        dirs[:]=[d for d in dirs if d not in ['env','.venv','.git','runtime-cache','node_modules','__pycache__','site-packages']]
        if time.monotonic()-start>120:raise TimeoutError('Seed audit deadline')
        for name in files:
            if 'seed' not in name.lower() or not name.lower().endswith('.json'):continue
            p=Path(folder)/name
            if p.resolve()==out.resolve():continue
            if p.stat().st_size>67108864:raise ValueError('Oversized seed inventory')
            raw=p.read_bytes();v=json.loads(raw);shared=sorted(proposed.intersection(integers(v)))
            inputs.append(dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest()))
            if shared:collisions.append(dict(path=str(p),seeds=shared))
    result=dict(root=str(root),reservation_ranges=[[398201000,398249799],[398300000,398300005]],reserved_count=len(proposed),inputs=inputs,collisions=collisions,scope='Explicit integers in seed-named JSON inventories; not unrecorded seeds or opaque engine-internal RNG derivations',elapsed_seconds=time.monotonic()-start)
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(inputs=len(inputs),collisions=len(collisions),reserved_count=len(proposed))))
    if not inputs or collisions:raise ValueError('Seed reservation rejected')

if __name__=='__main__':audit(*sys.argv[1:])
