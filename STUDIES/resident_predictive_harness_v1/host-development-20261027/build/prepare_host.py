"""Isolated native preparation supervisor; no sampler execution."""
import hashlib,json,os,signal,subprocess,sys,tarfile,time
from pathlib import Path
from datetime import datetime,timezone
root=Path(sys.argv[1]).resolve(); root.mkdir(parents=True,exist_ok=True)
status=root/'status.json'
if status.exists():raise SystemExit('Refusing to overwrite existing preparation')
start=time.monotonic(); state=dict(status='running',start_utc=datetime.now(timezone.utc).isoformat(),supervisor_pid=os.getpid(),deadline_seconds=1200)
def save():status.write_text(json.dumps(state,indent=2))
save();process=None
try:
 manifest=json.loads((root/'source-manifest.json').read_text());archive=root/'native-source.tar.gz'
 if hashlib.sha256(archive.read_bytes()).hexdigest()!=manifest['archive_sha256']:raise ValueError('archive hash mismatch')
 source=root/'source';source.mkdir()
 with tarfile.open(archive) as tar:
  for member in tar.getmembers():
   if not (source/member.name).resolve().is_relative_to(source):raise ValueError('unsafe archive path')
  tar.extractall(source,filter='data')
 for row in manifest['files']:
  if hashlib.sha256((source/row['path']).read_bytes()).hexdigest()!=row['sha256']:raise ValueError('source hash mismatch '+row['path'])
 script=root/'build.sh'
 script.write_text('set -eu\nexport PATH=/home/ubuntu/.cargo/bin:$PATH\nexport CARGO_TARGET_DIR="$PWD/cargo-target"\nexport CARGO_BUILD_JOBS=4\npython3 -c "import subprocess; assert subprocess.check_output([\'rustc\',\'--version\'],text=True).startswith(\'rustc 1.88.0 \'); assert subprocess.check_output([\'cargo\',\'--version\'],text=True).startswith(\'cargo 1.88.0 \')"\npython3 -m venv env\nenv/bin/python -m pip install numpy==2.4.6 scipy==1.18.1 numba==0.67.0 llvmlite==0.49.0 maturin==1.15.0\nenv/bin/python -m pip freeze > dependencies.txt\nrustc --version > toolchain.txt\ncargo --version >> toolchain.txt\nenv/bin/maturin --version >> toolchain.txt\ncargo metadata --manifest-path source/integrations/python/Cargo.toml --locked --no-default-features --format-version 1 > cargo-metadata.json\ncargo tree --manifest-path source/integrations/python/Cargo.toml --locked --no-default-features -e features > cargo-features.txt\nenv/bin/maturin build --release --locked --no-default-features --manifest-path source/integrations/python/Cargo.toml --interpreter env/bin/python --out wheels\nenv/bin/python -m pip install --no-deps wheels/*.whl\nenv/bin/python verify_native.py\n')
 (root/'verify_native.py').write_text("import hashlib,json,importlib.metadata as md,inspect\nfrom pathlib import Path\nimport owalnuts\nassert hasattr(owalnuts,'WarmSession') and hasattr(owalnuts.WarmSession,'refresh_functionals') and hasattr(owalnuts,'from_cfunc_functional')\nassert owalnuts.DEFAULTS['max_refinement_levels']==8\np=Path(owalnuts.__file__);files=[p]+list(p.parent.glob('*.so'))+list(Path('wheels').glob('*.whl'))\nassert list(p.parent.glob('*.so'))\nr=dict(defaults=dict(owalnuts.DEFAULTS),session_signature=str(inspect.signature(owalnuts.WarmSession)),packages={n:md.version(n) for n in ('owalnuts','numpy','scipy','numba','llvmlite','maturin')},files=[dict(path=str(f.resolve()),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),bytes=f.stat().st_size) for f in files])\nPath('native-identity.json').write_text(json.dumps(r,indent=2))\n")
 with (root/'build.log').open('wb') as log:
  process=subprocess.Popen(['taskset','-c','0-3','bash',str(script)],cwd=root,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  state['process_group']=process.pid;save()
  try:rc=process.wait(timeout=max(1,1200-(time.monotonic()-start)));state.update(status='complete' if rc==0 else 'failed',exit_code=rc)
  except subprocess.TimeoutExpired:
   state.update(status='timeout')
except Exception as exc:state.update(status='failed',error=repr(exc))
finally:
 if process is not None:
  pgid=process.pid
  def group_alive():
   try:os.killpg(pgid,0);return True
   except ProcessLookupError:return False
  if group_alive():
   state['cleanup_required']=True
   os.killpg(pgid,signal.SIGTERM)
   grace=time.monotonic()+5
   while group_alive() and time.monotonic()<grace:
    process.poll();time.sleep(.1)
   if group_alive():
    os.killpg(pgid,signal.SIGKILL)
   process.wait()
   grace=time.monotonic()+5
   while group_alive() and time.monotonic()<grace:time.sleep(.1)
  else:process.wait()
  state['owned_process_group_drained']=not group_alive()
  if not state['owned_process_group_drained']:state['status']='cleanup_failed'
 state.update(end_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-start);save()
