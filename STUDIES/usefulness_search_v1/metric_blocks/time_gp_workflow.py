import json,subprocess,sys,time
from pathlib import Path
out=Path(sys.argv[1]);t=time.perf_counter()
result=subprocess.run(sys.argv[2:],check=False)
elapsed=time.perf_counter()-t
(out/'PROCESS-TIME.json').write_text(json.dumps(dict(seconds=elapsed,returncode=result.returncode,scope='Blocking child subprocess: imports, setup, sampling, diagnostics and writes; excludes wrapper startup and precompiled libraries.'),indent=2)+'\n')
sys.exit(result.returncode)
