import collections,json,sys
from pathlib import Path
root=Path(sys.argv[1]);run=root/'initial02';final=json.loads((run/'FINAL.json').read_text());manifest=json.loads((run/'MANIFEST.json').read_text());rows=[]
for i,job in enumerate(manifest['jobs']):
    path=run/f'{i:03d}/result/RESULT.json';r=json.loads(path.read_text()) if path.exists() else dict(status='censored_or_missing')
    rows.append(dict(job=job,result=r,supervision=final['jobs'][i]))
out=dict(role='Preserved failed forecast implementation; not used for tuning or scientific comparisons',attempts=len(rows),statuses=dict(collections.Counter(r['result']['status'] for r in rows)),errors=dict(collections.Counter(r['result'].get('error','none') for r in rows)),sources_unchanged=final['sources_unchanged'],all_groups_drained=all(r['supervision'].get('group_drained') for r in rows),rows=rows)
(root/'LEGACY-SUMMARY.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='rows'},indent=2))
