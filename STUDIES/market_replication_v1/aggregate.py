"""Fixed descriptive aggregate of all mandatory months; no bootstrap or tests."""
from pathlib import Path
import json,hashlib,math
from data_contract import MONTHS

def summarize(root):
    root=Path(root);months=[]
    for row in MONTHS:
        p=root/row['month']/'summary.json';value=json.loads(p.read_bytes()) if p.exists() else None
        if value and (value.get('month')!=row['month'] or value.get('planned_origins')!=row['origins']):raise ValueError('Month summary identity mismatch')
        months.append(dict(month=row['month'],planned_origins=row['origins'],summary_available=value is not None,summary_sha256=hashlib.sha256(p.read_bytes()).hexdigest() if value is not None else None,summary=value))
    output=dict(scope='Origin-weighted descriptive mean only; adjacent months/context dependent; no pooled CI or significance',planned_origins=4368,planned_forecasts=13104,planned_references=24,months=months,paired={},qualification=None)
    for name in ['candidate_minus_rolling_t5','candidate_minus_ewma_t5']:
        items=[(m['planned_origins'],m['summary']['paired'][name]['full_mean']) for m in months if m['summary']is not None]
        complete=len(items)==3 and all(isinstance(v,(int,float)) and math.isfinite(v) for n,v in items)
        output['paired'][name]=dict(full_origin_weighted_mean=sum(n*v for n,v in items)/4368 if complete else None,all_mandatory_panels_complete=complete)
    return output


def batch_summary(spec,batchroot):
    from worker import exclusive
    result=summarize(batchroot);exclusive(Path(batchroot)/'aggregate.json',result);return result
