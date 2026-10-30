import json,subprocess,sys,time
from pathlib import Path
binary,input_path,output_path,timing_path=sys.argv[1:]
t=time.perf_counter();subprocess.run([binary,input_path,output_path],check=True);elapsed=time.perf_counter()-t
Path(timing_path).write_text(json.dumps(dict(seconds=elapsed)))
