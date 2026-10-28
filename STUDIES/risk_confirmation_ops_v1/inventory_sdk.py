"""Read-only bounded shared build-product inventory; never invokes a compiler."""
import argparse,hashlib,json,time
from pathlib import Path

def inventory(root):
    root=Path(root).resolve();start=time.monotonic();rows=[];counts={};total=0;hash_bytes=0;selected=[]
    for p in sorted(root.rglob('*')):
        if time.monotonic()-start>15:raise TimeoutError('SDK inventory15s budget')
        if not p.is_file() or not (p.suffix in ('.o','.a','.so','.gch','.pch') or p.name.startswith('libtbb.so.')):continue
        s=p.stat();name=p.relative_to(root).as_posix();counts[p.suffix]=counts.get(p.suffix,0)+1;total+=s.st_size
        row=dict(path=name,bytes=s.st_size,mtime_ns=s.st_mtime_ns,symlink=p.is_symlink());rows.append(row)
        if p.suffix=='.a' or name.startswith('src/') or p.name.startswith('libtbb.so'):
            if not p.resolve().is_relative_to(root):raise ValueError('Selected SDK artifact escapes root')
            hash_bytes+=s.st_size
            if hash_bytes>64*1024**2:raise ValueError('Selected SDK hash byte budget')
            selected.append(dict(**row,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    return dict(scope='Read-only pre-readiness shared compiler-product metadata and selected hashes; no compiler invoked',root=str(root),suffix_counts=counts,total_bytes=total,products=rows,selected_hashes=selected,selected_hash_bytes=hash_bytes,elapsed_seconds=time.monotonic()-start,unix_seconds=time.time())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');a=p.parse_args();print(json.dumps(inventory(a.root)))
