"""Fail-closed selected Python runtime identity, before numerical compilation."""
import hashlib,os
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def environment(config):
 env=dict(os.environ)
 # Deliberately replace unrelated PYTHONPATH entries: no fallback package roots.
 env['PYTHONPATH']=config['runtime_identity']['package_root']
 env['PYTHONNOUSERSITE']='1'
 return env

def validate(config,adapter,extension):
 identity=config['runtime_identity'];root=Path(identity['package_root']).resolve();result={}
 for name,module in [('adapter',adapter),('extension',extension)]:
  expected=identity[name];actual=Path(module.__file__).resolve();declared=Path(expected['path']).resolve()
  if actual!=declared or not actual.is_relative_to(root):raise ValueError('Imported runtime path mismatch: '+name)
  value=sha(actual)
  if value!=expected['sha256'] or config['bindings'].get(str(declared))!=value:raise ValueError('Imported runtime hash mismatch: '+name)
  result[name]=dict(path=str(actual),sha256=value)
 return result
