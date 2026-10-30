"""Bounded eight-chunk local queue; audit and archive before proceeding."""
import json,os,subprocess,sys,time
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery'
start=int(sys.argv[1]);assert 1<=start<=8
env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',LD_LIBRARY_PATH=str(local/'venv/lib'))
log=local/f'QUEUE-{start:02d}.jsonl';assert not log.exists()
def run(args):
    with (local/f'QUEUE-{start:02d}.log').open('a') as out:
        subprocess.run([sys.executable,*map(str,args)],check=True,env=env,stdout=out,stderr=subprocess.STDOUT)
for i in range(start,9):
    if i>1:
        receipt=json.loads((local/f'localscaled{i-1:02d}_archive/VERIFICATION.json').read_text());assert receipt['passed']
    run([study/'prepare_local_scaled.py',i])
    root=local/f'localscaled{i:02d}'
    run([root/'run_scaled.py',i]);run([root/'verify_scaled.py']);run([study/'archive_local_research.py',root.name])
    with log.open('a') as out:out.write(json.dumps(dict(chunk=i,completed_unix=time.time(),verified=True))+'\n')
