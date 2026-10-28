"""All planned retained fits, including unavailable scores and initial fits."""
import argparse
import json
from pathlib import Path
from rolling_inventory import inventory, read
from rolling_record_audit import sha
from rolling_trace_report import report_trace


def run(root,reference,reference_sha256,out):
    root=Path(root);out=Path(out);audit=inventory(root,reference,reference_sha256)
    out.mkdir(exist_ok=False)
    rows=[]
    for job in audit['jobs']:
        j=job['job'];fit=root/'campaign01'/f'job-{j:02d}'/'fit';lane=fit/'lane'
        ticks=[0]+[s['tick'] for s in audit['spots'] if s['job']==j]
        for tick in ticks:
            row=dict(job=j,month=job['month'],replicate=job['replicate'],tick=tick,
                     scope='initialization' if tick==0 else 'retained_update',status='unavailable')
            path=lane/'INITIAL.json' if tick==0 else lane/'records'/f'{tick:06d}.json'
            payload=read(path) if path.exists() else None
            telemetry=None;compact=None
            if payload is not None:
                row['record_sha256']=sha(path)
                if tick==0 and payload.get('status')=='complete':
                    telemetry=payload['telemetry']['fit']
                elif tick>0 and payload.get('native_status')=='ok':
                    telemetry=payload['native'];compact=lane/payload['compact']['file']
            if telemetry is not None:
                expected=telemetry['artifacts']
                result=report_trace(fit/'nutpie'/f'tick-{tick:06d}',expected,compact,200 if tick==0 else 400)
                if result['metadata']!=telemetry['metadata']:
                    raise ValueError('Trace and recorded metadata disagree')
                report=out/f'job-{j:02d}-tick-{tick:06d}.json'
                report.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
                row.update(status='available',report=report.name,report_sha256=sha(report),
                           diagnostic_passed=result['diagnostic_passed'],flagged_coordinates=result['flagged_coordinates'],
                           divergences=result['metadata']['divergences'])
            rows.append(row)
    result=dict(scope='Retained-fit diagnostics; no unretained-window qualification',planned_initializations=6,
                planned_updates=48,rows=rows,inventory=audit)
    (out/'SUMMARY.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('reference');p.add_argument('reference_sha256');p.add_argument('out');a=p.parse_args()
    run(a.root,a.reference,a.reference_sha256,a.out)
