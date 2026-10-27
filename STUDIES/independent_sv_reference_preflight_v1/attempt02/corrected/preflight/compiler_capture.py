"""Explicit compilation-only provenance capture; numerical/sampling APIs untouched."""
from contextlib import contextmanager
from pathlib import Path
import hashlib,shutil

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
@contextmanager
def capture_compiler(module,destination,records):
    original=module.compile_model
    destination=Path(destination);destination.mkdir(exist_ok=False)
    def captured(*args,**kwargs):
        result=original(*args,**kwargs)
        source=Path(result)
        if source.is_symlink() or not source.is_file() or source.suffix!='.so':
            raise ValueError('compiler did not return regular .so')
        target=destination/('model-%d.so'%len(records))
        if target.exists():raise ValueError('capture path exists')
        before=sha(source);shutil.copyfile(source,target);after=sha(source);copied=sha(target)
        if before!=after or before!=copied:raise ValueError('compiled library changed during capture')
        records.append(dict(source_path=str(source),copy_path=str(target),sha256=copied))
        return result
    module.compile_model=captured
    try:yield
    finally:module.compile_model=original
