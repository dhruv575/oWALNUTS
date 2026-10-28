import json,statistics
from pathlib import Path
base=Path('/home/ubuntu/lanes/blocked-market-20261028')
rows=[]
for index in range(24):
    p=base/f'analysis/job-{index:02d}/fit/REPORT.json'
    row=json.loads(p.read_bytes()) if p.exists() else dict(index=index,status='missing')
    if row['status']=='complete':assert row['index']==index and row['spot']==index and row['method']==2
    rows.append(row)
complete=[r for r in rows if r['status']=='complete']
result=dict(planned=24,completed=len(complete),flagged_fits=sum(bool(r['flagged_coordinates']) for r in complete),
 compact_flags={n:sum(n in r['flagged_coordinates'] for r in complete) for n in ('mu','log_sigma','beta','h_last')},
 worst_bulk_ess={n:min((r['coordinates'][n]['bulk_ess'] for r in complete),default=None) for n in ('mu','log_sigma','beta','h_last')},
 subsets={})
references=json.loads(Path('/home/ubuntu/lanes/reference-precision-extension-20261028-attempt02/COMPARISON.json').read_bytes())['rows']
passing={i for i,r in enumerate(references) if r['extended']['passed']}
assert len(references)==24 and len(passing)==22
for name,subset in [('all',rows),('reference_passing',[r for r in rows if r['index'] in passing])]:
    available=[r for r in subset if r.get('predictive',{}).get('status')=='available']
    result['subsets'][name]=dict(planned=len(subset),available=len(available),
      max_abs_logpdf=max((abs(r['predictive']['difference']['logpdf']) for r in available),default=None),
      max_abs_pit=max((abs(r['predictive']['difference']['pit']) for r in available),default=None),
      median_logpdf_mcse=statistics.median(r['predictive']['logpdf_mcse'] for r in available) if available else None)
result['rows']=[dict(index=r['index'],month=r.get('month'),tick=r.get('tick'),status=r['status'],flagged_coordinates=r.get('flagged_coordinates'),predictive=r.get('predictive'),reference=r.get('reference')) for r in rows]
(base/'analysis/SUMMARY.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
