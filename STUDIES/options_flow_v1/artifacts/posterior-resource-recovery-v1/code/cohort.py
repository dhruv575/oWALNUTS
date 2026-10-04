"""Fixed two-public recovery denominator and3600s additional budget."""
import argparse,json,time
from pathlib import Path
from launch import launch,sha,save

def run(path):
    path=Path(path).resolve();digest=sha(path);plan=json.loads(path.read_text());out=path.parent
    if path.with_suffix('.sha256').read_text().strip()!=digest:raise ValueError('Frozen cohort required')
    if plan['total_seconds']!=3600 or plan['cleanup_reserve_seconds']!=15 or len(plan['specs'])!=2:raise ValueError('Fixed two-recovery resource policy required')
    if (out/'recovery-terminal.json').exists():raise ValueError('Never retry completed cohort')
    specs=[json.loads(Path(p).read_text()) for p in plan['specs']]
    if [s['cell_id'] for s in specs]!=['fit-0-public','fit-3-public']:raise ValueError('Exact original public denominator required')
    for spec in specs:
        if any(Path(str(spec['out'])+suffix).exists() for suffix in ['', '-started.json','-status.json','-hardware.json','-exit.json','.log']):raise ValueError('Never retry started recovery')
    tick=time.perf_counter();results=[]
    for spec_path,spec in zip(plan['specs'],specs):
        try:
            if sha(path)!=digest or any(sha(p)!=h for p,h in plan['spec_hashes'].items()):raise ValueError('Frozen cohort/spec changed')
            remaining=3600-(time.perf_counter()-tick)-15
            if remaining<=0:
                record=dict(cell_id=spec['cell_id'],status='unattempted_global_budget',posthoc=True,resampled=False,additional_outer_seconds=0)
                save(str(spec['out'])+'-status.json',record)
            else:record=launch(spec_path,min(1800,remaining))
        except Exception as exc:
            record=dict(cell_id=spec['cell_id'],status='controller_failed',error=str(exc),posthoc=True,resampled=False)
            status=Path(str(spec['out'])+'-status.json')
            if not status.exists():save(status,record)
        results.append(record)
    save(out/'recovery-terminal.json',dict(expected=2,recorded=len(results),results=results,additional_outer_seconds=time.perf_counter()-tick,qualified=False,posthoc=True,resampled=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);a=p.parse_args();run(a.plan)
