"""Read-only compact campaign status; invoke outside the frozen source tree."""
import json,sys,collections,time,shutil
from pathlib import Path
root=Path(sys.argv[1]);runs=[]
for folder in ('initial02','validation01'):
    p=root/folder
    if not p.exists():continue
    counts=collections.Counter();results=[]
    for f in p.glob('*/result/RESULT.json'):
        r=json.loads(f.read_text());counts[r['status']]+=1
        results.append(dict(phase=r['phase'],case=r['case'],config=r['config'],status=r['status'],seconds=round(r.get('seconds',0),2),diagnostic=r.get('summary',{}).get('diagnostic_pass'),error=r.get('error')))
    runs.append(dict(folder=folder,status=json.loads((p/'STATUS.json').read_text()) if (p/'STATUS.json').exists() else None,final=(p/'FINAL.json').exists(),counts=dict(counts),recent=results[-5:]))
print(json.dumps(dict(runs=runs,free_bytes=shutil.disk_usage(root).free),indent=2))
