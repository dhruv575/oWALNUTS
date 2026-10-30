import json,shutil,sys
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=Path.home()/'.cache/owalnuts/native-threaded01';root.mkdir(parents=True,exist_ok=False)
assert shutil.disk_usage(root).free>=2*1024**3 and shutil.disk_usage(local).free>=1024**3
sys.path.insert(0,str(local/'inputs'))
from resource_monitor import execute
r=execute([sys.executable,str(study/'build_threaded_native_worker.py'),str(root)],str(root),180,root,2*1024**3,1024**3,root/'worker.log',output_scan_interval=2)
dest=local/'threaded_build01';dest.mkdir(exist_ok=True);shutil.copy2(root/'worker.log',dest/'worker.log')
(dest/'SUPERVISION.json').write_text(json.dumps(dict(r,build_directory=str(root)),indent=2)+'\n');print(json.dumps(r))
