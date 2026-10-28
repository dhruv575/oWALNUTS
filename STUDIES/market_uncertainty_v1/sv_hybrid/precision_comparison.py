"""Descriptive fixed-panel effort comparison; missing/flagged fits stay visible."""
import argparse,json
from pathlib import Path

def compare(short,long):
    if len(short)!=24 or len(long)!=24:raise ValueError('All 24 slots required')
    rows=[]
    for index,(a,b) in enumerate(zip(short,long)):
        if a['index']!=index or b['index']!=index:raise ValueError('Ordered fixed slots required')
        row=dict(index=index,short_status=a['status'],long_status=b['status'],paired=False)
        for label,fit in [('short',a),('long',b)]:
            row[label+'_flags']=fit.get('flagged_coordinates')
            row[label+'_predictive_status']=fit.get('predictive',{}).get('status','missing')
        if a['status']=='complete' and b['status']=='complete':
            if (a['month'],a['tick'],a['method'])!=(b['month'],b['tick'],b['method']):raise ValueError('Window or method mismatch')
            if a['reference']!=b['reference']:raise ValueError('Reference mismatch')
            row.update(month=a['month'],tick=a['tick'],reference_passed=a['reference']['passed'])
            ap,bp=a['predictive'],b['predictive']
            if ap['status']==bp['status']=='available':
                row['paired']=True
                for metric in ('logpdf','pit'):
                    row[metric]=dict(short_difference=ap['difference'][metric],long_difference=bp['difference'][metric],
                        short_mcse=ap[metric+'_mcse'],long_mcse=bp[metric+'_mcse'],
                        absolute_discrepancy_improved=abs(bp['difference'][metric])<abs(ap['difference'][metric]),
                        mcse_reduced=bp[metric+'_mcse']<ap[metric+'_mcse'])
        rows.append(row)
    paired=[r for r in rows if r['paired']]
    return dict(planned=24,available_pairs=len(paired),
        short_passed=sum(r['short_status']=='complete' and r['short_flags']==[] for r in rows),
        long_passed=sum(r['long_status']=='complete' and r['long_flags']==[] for r in rows),
        improvements={m:{k:sum(r[m][k] for r in paired) for k in ('absolute_discrepancy_improved','mcse_reduced')} for m in ('logpdf','pit')},
        scope='Descriptive exposed-window comparison; fresh seeds, both warmup and retention changed. MCSE in flagged fits may be unreliable.',rows=rows)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('short');p.add_argument('long');p.add_argument('out');a=p.parse_args()
    def read(root):
        rows=[]
        for i in range(24):
            path=Path(root)/f'job-{i:02d}/fit/REPORT.json'
            rows.append(json.loads(path.read_bytes()) if path.exists() else dict(index=i,status='missing'))
        return rows
    result=compare(read(a.short),read(a.long))
    with Path(a.out).open('x',encoding='utf8',newline='\n') as f:json.dump(result,f,indent=2,allow_nan=False)
