"""Bounded terminal analysis of every frozen blocked-market window."""
import concurrent.futures,json,os,sys,time
from pathlib import Path
import psutil
base=Path('/home/ubuntu/lanes/blocked-market-20261028')
source=base/'source/sv_hybrid';sys.path.insert(0,str(source))
from resource_monitor import execute
root=base/'run01';out=base/'analysis';out.mkdir(exist_ok=False)
launch=json.loads((base/'LAUNCH.json').read_bytes())
receipt=root/'SUPERVISION.json'
started=time.monotonic()
if not receipt.exists():
    process=psutil.Process(launch['pid']);identity=process.create_time()
    while not receipt.exists():
        if time.monotonic()-started>4850:raise TimeoutError('Bounded wait exhausted')
        if not process.is_running() or process.create_time()!=identity or process.status()==psutil.STATUS_ZOMBIE:
            raise RuntimeError('Supervisor gone without terminal receipt')
        time.sleep(5)
assert json.loads(receipt.read_bytes()).get('group_drained') is True
assert json.loads((root/'MANIFEST.json').read_bytes())['methods']==[2]
def one(index):
    directory=out/f'job-{index:02d}';directory.mkdir(exist_ok=False)
    command=['taskset','-c',str(index%16),sys.executable,str(source/'market_report.py'),str(root),
             '/home/ubuntu/lanes/reference-precision-extension-20261028-attempt02',str(index),
             '/home/ubuntu/lanes/prior-predictive-validation-20261027/source/STUDIES/predictive_value_diagnostic_v1/predictive_density.py',str(directory/'fit')]
    result=execute(command,str(base),180,directory,1024**3,64*1024**2,directory/'stdout.log',output_scan_interval=5)
    (directory/'MONITOR.json').write_text(json.dumps(result,indent=2))
    return dict(index=index,receipt=result)
def group(core):return [one(index) for index in range(24) if index%16==core]
with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
    records=[r for batch in pool.map(group,range(16)) for r in batch]
(out/'ANALYSIS-LEDGER.json').write_text(json.dumps(dict(planned=24,jobs=sorted(records,key=lambda r:r['index'])),indent=2))
print(json.dumps(dict(planned=24,successful=sum(r['receipt'].get('exit_code')==0 and r['receipt'].get('group_drained') for r in records))),flush=True)
