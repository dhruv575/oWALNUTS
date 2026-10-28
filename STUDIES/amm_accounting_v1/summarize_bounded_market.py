"""Descriptive fixed-denominator summary; caps are not independent markets."""
import json,math,statistics,sys
from pathlib import Path

def summarize(root):
    rows={}
    for path in sorted(Path(root).glob('bounded-market-batch-*-20261028/SUMMARY.json')):
        for row in json.loads(path.read_text()):
            j=row['index']
            if j in rows or not 0<=j<72:raise ValueError('Duplicate or invalid cell')
            rows[j]=row
    groups=[]
    for cap in [.5,1.,2.]:
        for month in ['2025-12','2026-01','2026-02','all']:
            selected=[r for r in rows.values() if r.get('cap')==cap and (month=='all' or r.get('month')==month)]
            for baseline in ['rolling_t5','ewma_t5','nig_ar1']:
                qualified=[]
                for r in selected:
                    matches=[c for c in r.get('comparisons',[]) if c['baseline']==baseline]
                    if len(matches)>1:raise ValueError('Duplicate comparison')
                    if matches and matches[0]['qualified']:qualified.append(matches[0])
                fields={}
                for field in ['model','inference','total']:
                    values=[c[field] for c in qualified]
                    if not all(math.isfinite(x) for x in values):raise ValueError('Nonfinite qualified score')
                    fields[field]=dict(mean=statistics.mean(values) if values else None,median=statistics.median(values) if values else None,minimum=min(values) if values else None,maximum=max(values) if values else None,positive=sum(x>0 for x in values))
                groups.append(dict(cap=cap,month=month,baseline=baseline,planned=24 if month=='all' else 8,reported=len(selected),qualified=len(qualified),scores=fields))
    return dict(planned_cells=72,reported_cells=len(rows),missing_indices=sorted(set(range(72))-rows.keys()),groups=groups,limitations='Development origins; descriptive scores only. Caps share observations. No independent-market replication, holdout claim, precision-matched speed comparison, or economic claim.')

if __name__=='__main__':
    result=summarize(sys.argv[1]);Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+'\n')
