"""Identity and import admission for the new unified runtime only."""
import argparse,hashlib,importlib,importlib.metadata,json,os,sys
from pathlib import Path
PINS={'numpy':'2.4.6','scipy':'1.18.1','numba':'0.67.0','llvmlite':'0.49.0','arviz':'0.23.4','nutpie':'0.16.8','bridgestan':'2.9.0','stanio':'0.5.1','psutil':'7.2.2','owalnuts':'0.3.0'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def inventory(prefix):
 if os.path.abspath(sys.prefix)!=os.path.abspath(prefix):raise ValueError('unified prefix mismatch')
 versions={name:importlib.metadata.version(name) for name in PINS}
 if versions!=PINS:raise ValueError('direct pins mismatch '+repr(versions))
 modules={name:importlib.import_module(name) for name in PINS}
 native={str(p):sha(p) for directory in set(Path(m.__file__).parent for m in modules.values()) for p in directory.rglob('*.so*')}
 owalnuts_native={p:h for p,h in native.items() if Path(modules['owalnuts'].__file__).parent in Path(p).parents}
 if 'db2c445a7a94da67d55d22d3b367c44544630655f07c88068e5456a2c7d93863' not in owalnuts_native.values():raise ValueError('installed native hash differs')
 # All distributions and extension bytes, including transitives, are separately preserved.
 distributions={d.metadata['Name']:d.version for d in importlib.metadata.distributions()}
 sites={Path(d.locate_file('')) for d in importlib.metadata.distributions()}
 all_native={str(p):sha(p) for site in sites for p in site.rglob('*.so*')}
 return dict(prefix=sys.prefix,base_prefix=sys.base_prefix,executable=sys.executable,executable_realpath=str(Path(sys.executable).resolve()),executable_sha256=sha(sys.executable),python_version=sys.version,pinned_versions=versions,distributions=distributions,native_modules=all_native,entry_sources={str(m.__file__):sha(m.__file__) for m in modules.values()})
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--prefix',required=True);a=p.parse_args();Path(a.output).write_text(json.dumps(inventory(a.prefix),indent=2))
