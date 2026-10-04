"""Independent exhaustive-window counts; no fit or transformation estimation."""
import datetime
import hashlib
import json
from pathlib import Path
P=Path(__file__).resolve().parent
protocol=json.loads((P/'protocol.json').read_text())
summary=json.loads((P/'summary.json').read_text())
def ms(s):return int(datetime.datetime.fromisoformat(s).timestamp()*1000)
start=ms(protocol['start_utc']);end=ms(protocol['end_utc_exclusive'])
dev=start+48*3600000;val=dev+24*3600000
trades={name:json.loads((P/summary['field_quality'][name]['file']).read_text()) for name in summary['selected']}
eligible={name:[t for t in rows if not any(t.get(k) is not None for k in protocol['exclude_flags'])] for name,rows in trades.items()}
counts={};origins={};rows=[]
for cutoff in range(start,end,1800000):
    decision=cutoff+60000;finish=decision+1800000
    if finish>=end:continue
    phase='development' if decision<dev else 'validation' if decision<val else 'evaluation'
    boundary={'development':dev,'validation':val,'evaluation':end}[phase]
    origins[phase]=origins.get(phase,0)+1
    for name,events in eligible.items():
        refs=[t for t in events if cutoff-1800000<=t['timestamp']<=cutoff]
        targets=[t for t in events if decision<t['timestamp']<=finish]
        features=[t for t in events if cutoff-900000<t['timestamp']<=cutoff]
        usable=bool(refs and targets and cutoff-900000>=start and finish+60000<=boundary)
        c=counts.setdefault(phase,{}).setdefault(name,dict(scheduled=0,reference_present=0,target_present=0,both_present=0,usable=0,empty_feature_bin=0))
        for key,yes in dict(scheduled=True,reference_present=bool(refs),target_present=bool(targets),both_present=bool(refs and targets),usable=usable,empty_feature_bin=not features).items():c[key]+=int(yes)
        rows.append(dict(cutoff_ms=cutoff,instrument_name=name,phase=phase,usable=usable,
                         reference_trade_id=max(refs,key=lambda t:(t['timestamp'],t['trade_seq']))['trade_id'] if refs else None,
                         target_trade_id=max(targets,key=lambda t:(t['timestamp'],t['trade_seq']))['trade_id'] if targets else None))
result=dict(qualified=False,scheduled_origins=origins,counts=counts,rows=rows,
            source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            limitation='Independent window-count check only; no model fit, imputation, or coverage claim.')
with (P/'observability-audit.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps(dict(origins=origins,usable={phase:sum(c['usable'] for c in groups.values()) for phase,groups in counts.items()})))
