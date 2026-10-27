"""One isolated pinned environment preparation, no sampling and no retries."""
import argparse,hashlib,json,os,subprocess,sys,time,traceback,venv
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--requirements',required=True);parser.add_argument('--requirements-sha256',required=True);a=parser.parse_args()
 root=Path(a.root).absolute();root.mkdir(exist_ok=False);record=dict(status='running',started=time.time());path=root/'preparation.json'
 def save():path.write_text(json.dumps(record,indent=2))
 def run(args):return subprocess.run(args,check=True,text=True,capture_output=True)
 try:
  if sys.version_info[:2]!=(3,12):raise RuntimeError('Python3.12 required')
  requirements=Path(a.requirements)
  if sha(requirements)!=a.requirements_sha256:raise RuntimeError('requirements hash mismatch')
  wheel=Path('/home/ubuntu/lanes/resident-predictive-build-20261027/wheels/owalnuts-0.3.0-cp310-abi3-manylinux_2_34_x86_64.whl')
  if sha(wheel)!='b64b1f2aed4bd58e585a9679a67e5840fba971ccf9985cdd85054544e60a1211':raise RuntimeError('native wheel mismatch')
  sdk=Path('/home/ubuntu/.bridgestan/bridgestan-2.9.0')
  if sha(sdk/'Makefile')!='21f9f85c5d2390ba61cfb23015514b4f7dcb678b9f89927ece6bc43ec4eafeee':raise RuntimeError('SDK Makefile mismatch')
  source_suffixes={'.h','.hpp','.hxx','.c','.cc','.cpp','.stan','.py','.mk'}
  sdk_sources={str(p.relative_to(sdk)):sha(p) for p in sorted(sdk.rglob('*')) if p.is_file() and not p.is_symlink() and (p.suffix in source_suffixes or p.name in ('Makefile','local','stanc'))}
  (root/'sdk-source-inventory.json').write_text(json.dumps(sdk_sources,indent=2))
  record.update(requirements_sha256=sha(requirements),wheel_sha256=sha(wheel),sdk_source_inventory_sha256=sha(root/'sdk-source-inventory.json'),sdk_source_files=len(sdk_sources),compiler_version=run(['g++','--version']).stdout,stanc_version=run([str(sdk/'bin/stanc'),'--version']).stdout,phase='create environment');save()
  env=root/'env';venv.EnvBuilder(with_pip=True,symlinks=True).create(env);python=str(env/'bin/python')
  tmp=root/'tmp';tmp.mkdir();os.environ['TMPDIR']=str(tmp);os.environ['PIP_CACHE_DIR']=str(root/'pip-cache');os.environ['PIP_DISABLE_PIP_VERSION_CHECK']='1'
  record['phase']='pinned install';save()
  command=[python,'-m','pip','install','--only-binary=:all:','--no-cache-dir','--report',str(root/'pip-report.json'),'-r',str(requirements),str(wheel)]
  record['install_command']=command;save()
  completed=subprocess.run(command,stdout=(root/'pip.log').open('w'),stderr=subprocess.STDOUT)
  record['pip_exit_code']=completed.returncode
  if completed.returncode:raise RuntimeError('pinned resolver/install failed; no retry')
  record['phase']='identity and imports';save()
  inventory=Path(__file__).with_name('runtime_inventory.py')
  subprocess.run([python,str(inventory),'--output',str(root/'runtime-identity.json'),'--prefix',str(env)],check=True)
  (root/'pip-freeze.txt').write_text(run([python,'-m','pip','freeze','--all']).stdout)
  check=run([python,'-m','pip','check']);(root/'pip-check.txt').write_text(check.stdout)
  for name,digest in sdk_sources.items():
   if sha(sdk/name)!=digest:raise RuntimeError('SDK source drift '+name)
  record.update(status='complete',phase='complete',runtime_identity_sha256=sha(root/'runtime-identity.json'),sdk_sources_unchanged=True)
 except BaseException as exc:record.update(status='failed',error=repr(exc),traceback=traceback.format_exc())
 finally:record['finished']=time.time();save()
 return 0 if record['status']=='complete' else 1
if __name__=='__main__':raise SystemExit(main())
