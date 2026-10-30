import json,runpy,sys,time
from pathlib import Path
p=Path(__file__).resolve().parent;out=Path(sys.argv[1]);seed=int(sys.argv[2]);package=out/'package';package.mkdir()
for name in ['common.py','conditional_v3.py','prepare_conditional_v3.py']:
    text=(p/'local_recovery/gp_conditional_local01'/name).read_text()
    if name=='common.py':text=text.replace("Path(__file__).resolve().parents[2]",repr(str(p)))
    (package/name).write_text(text)
sys.path.insert(0,str(package));t=time.perf_counter();runpy.run_path(str(package/'prepare_conditional_v3.py'),run_name='__main__');setup=time.perf_counter()-t
from conditional_v3 import COUNTS
for k in COUNTS:COUNTS[k]=0
# The original fresh-confirmation worker's package insertion is removed so imports
# resolve to this run's newly rebuilt grid, never the historical cached grid.
source=(p/'gp_conditional_confirmation_worker.py').read_text()
line="sys.path.insert(0,str(Path(__file__).resolve().parent/'local_recovery/gp_conditional_local01'))"
assert line in source;source=source.replace(line,'')
source=source.replace("Path(__file__).resolve().parent.parent/'gp_count/REFERENCE.json'","Path("+repr(str(p.parent/'gp_count/REFERENCE.json'))+")")
sys.argv=[str(p/'gp_conditional_confirmation_worker.py'),str(seed),str(out)]
exec(compile(source,'fresh_importance_worker','exec'),dict(__name__='__main__',__file__=str(p/'gp_conditional_confirmation_worker.py')))
(out/'SETUP.json').write_text(json.dumps(dict(seconds=setup,preflight=json.loads((package/'CONDITIONAL-PREFLIGHT.json').read_text())),indent=2)+'\n')
