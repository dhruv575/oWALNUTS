"""Report coverage and diagnostic qualification without displaying forecast scores."""
import json,sys
from pathlib import Path

def status(lane):
    rows=[]
    for folder in sorted(Path(lane).glob('batch-[0-9][0-9][0-9]')):
        final=folder/'FINAL.json';supervision=folder/'SUPERVISION.json'
        if not final.exists() or not supervision.exists():
            rows.append(dict(batch=folder.name,state='no_terminal_receipt'));continue
        s=json.loads(supervision.read_text());jobs=json.loads(final.read_text());qualified={'nuts':0,'walnuts':0};missing=[];failed=[]
        for job in jobs:
            p=folder/f"job-{job['index']}"/'fit/REPORT.json'
            if not p.exists():missing.append(job['index']);continue
            r=json.loads(p.read_text())
            for name in qualified:
                m=r['methods'].get(name,{})
                if m.get('qualified'):qualified[name]+=1
                else:failed.append(dict(index=job['index'],method=name,status=m.get('status','missing'),physical_failures=m.get('failed_physical_coordinates'),predictive_status=m.get('prediction',{}).get('status')))
        rows.append(dict(batch=folder.name,slots=len(jobs),drained=s.get('group_drained'),sources_unchanged=s.get('sources_unchanged'),qualified=qualified,missing=missing,failed=failed,archived=(folder/'ARCHIVE-VERIFIED.json').exists(),cleaned=(folder/'CLEANUP.json').exists()))
    return rows

if __name__=='__main__':print(json.dumps(status(sys.argv[1]),indent=2))
