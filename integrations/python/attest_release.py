"""Build an isolated release extension with before/after provenance (stdlib only).

Invoke only in a coordinated quiet window. This script cannot establish that
other host processes are idle; its manifest records the operator's quiet claim.
It never installs the extension or overwrites an existing output directory.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tomllib


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_paths(root):
    """Conservatively bind every local path dependency, including optional ones."""
    pending=[root/'integrations/python']; seen=set(); paths=set()
    while pending:
        crate=pending.pop().resolve()
        if crate in seen: continue
        seen.add(crate)
        manifest=crate/'Cargo.toml'; paths.add(manifest)
        paths.update(crate.glob('Cargo.lock')); paths.update(crate.glob('build.rs'))
        paths.update((crate/'src').rglob('*.rs'))
        doc=tomllib.loads(manifest.read_text())
        def walk(value):
            if isinstance(value,dict):
                if isinstance(value.get('path'),str) and (crate/value['path']/'Cargo.toml').is_file():
                    pending.append(crate/value['path'])
                for item in value.values():walk(item)
            elif isinstance(value,list):
                for item in value:walk(item)
        walk(doc)
    paths.update((root/'integrations/python/python').rglob('*.py'))
    paths.add(Path(__file__).resolve())
    for parent in [root,*root.parents]:
        for name in ['config','config.toml']:
            candidate=parent/'.cargo'/name
            if candidate.is_file():paths.add(candidate)
    cargo_home=Path(os.environ.get('CARGO_HOME',Path.home()/'.cargo'))
    for name in ['config','config.toml']:
        if (cargo_home/name).is_file():paths.add(cargo_home/name)
    return sorted(paths,key=str)


def snapshot(root): return {str(p):sha(p) for p in source_paths(root)}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--python',type=Path,required=True)
    parser.add_argument('--toolchain',default='1.88.0-x86_64-pc-windows-gnu')
    parser.add_argument('--quiet-window-note',required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    interpreter=args.python.resolve(strict=True); out=args.out.resolve()
    out.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter()
    env=os.environ.copy(); env['PYO3_PYTHON']=str(interpreter)
    # Isolated target directory avoids claiming historical cached binaries were rebuilt.
    command=['cargo','+'+args.toolchain,'build','--release','--locked','--manifest-path',
             str(root/'integrations/python/Cargo.toml'),'--target-dir',str(out/'build')]
    record=dict(status='started',utc_started=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        command=command,cwd=str(root),quiet_window_note=args.quiet_window_note,
        quiet_window_evidence='Operator coordination; no autonomous host-idleness guarantee',
        environment={key:env[key] for key in ['PYO3_PYTHON','RUSTFLAGS','CARGO_ENCODED_RUSTFLAGS',
            'RUSTC','RUSTC_WRAPPER','RUSTC_WORKSPACE_WRAPPER','CARGO_BUILD_TARGET','CC','CXX','AR',
            'PYO3_CONFIG_FILE','PYO3_CROSS','PYO3_CROSS_LIB_DIR','PYO3_CROSS_PYTHON_VERSION'] if key in env})
    record['source_before']=snapshot(root)
    record['python']=dict(path=str(interpreter),sha256=sha(interpreter),description=subprocess.check_output(
        [str(interpreter),'-c','import sys,sysconfig,json;print(json.dumps(dict(version=sys.version,executable=sys.executable,platform=sysconfig.get_platform())))'],text=True).strip())
    record['rustc']=subprocess.check_output(['rustup','run',args.toolchain,'rustc','-vV'],text=True)
    record['cargo']=subprocess.check_output(['rustup','run',args.toolchain,'cargo','-V'],text=True)
    (out/'started.json').write_text(json.dumps(record,indent=2))
    try:
        with (out/'build.log').open('w') as log:
            result=subprocess.run(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
        record['returncode']=result.returncode
        record['source_after']=snapshot(root)
        if record['source_after']!=record['source_before']:raise RuntimeError('Source changed during build')
        if sha(interpreter)!=record['python']['sha256']:raise RuntimeError('Python executable changed during build')
        if result.returncode:raise RuntimeError('Cargo release build failed')
        binary=out/'build/release'/('_owalnuts.dll' if os.name=='nt' else 'lib_owalnuts.dylib' if sys.platform=='darwin' else 'lib_owalnuts.so')
        record['binary']=dict(path=str(binary),sha256=sha(binary),bytes=binary.stat().st_size)
        record['status']='attested'
    except Exception as exc:
        record.update(status='failed',error=str(exc))
    record['seconds']=time.perf_counter()-started
    temporary=out/'manifest.tmp';temporary.write_text(json.dumps(record,indent=2))
    temporary.replace(out/'manifest.json')
    print(json.dumps({key:record.get(key) for key in ['status','seconds','error']}))
    return int(record['status']!='attested')


if __name__=='__main__':raise SystemExit(main())
