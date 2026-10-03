"""Execute only the cells in the adjacent frozen exploratory plan."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    with path.open('x',encoding='utf-8') as handle:json.dump(value,handle,indent=2,allow_nan=False)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cell',action='append');args=parser.parse_args()
    plan_path=HERE/'plan.json';plan=json.loads(plan_path.read_text())
    if digest(plan_path)!=(HERE/'plan.sha256').read_text().strip():raise ValueError('Plan digest changed')
    if digest(__file__)!=plan['runner_sha256']:raise ValueError('Runner changed')
    selected=set(args.cell or [c['id'] for c in plan['cells']])
    if selected-{c['id'] for c in plan['cells']}:raise ValueError('Unknown cell')
    for cell in plan['cells']:
        if cell['id'] not in selected:continue
        started=HERE/(cell['id']+'.started.json');terminal=HERE/(cell['id']+'.status.json')
        if started.exists() or terminal.exists():raise FileExistsError('Already attempted: '+cell['id'])
        save(started,dict(id=cell['id'],utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
        ts=time.perf_counter();record=dict(id=cell['id'],phase='exploratory',qualified=False)
        try:
            if {p.name:digest(p) for p in ROOT.glob('*.py')}!=plan['source_sha256']:raise ValueError('Study source changed')
            for path,expected in plan['bound_files'].items():
                if digest(path)!=expected:raise ValueError('Bound file changed: '+path)
            if digest(cell['fixture'])!=cell['fixture_sha256']:raise ValueError('Fixture changed')
            with (HERE/(cell['id']+'.log')).open('x',encoding='utf-8') as log:
                result=subprocess.run(cell['command'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=False)
            report=json.loads(Path(cell['report']).read_text())
            record.update(returncode=result.returncode,worker_status=report.get('status'),
                          precision_pass=report.get('precision_pass',False),healthy=report.get('healthy',False),
                          report=cell['report'],report_sha256=digest(cell['report']))
        except Exception as exc:record.update(worker_status='executor_failed',error=f'{type(exc).__name__}: {exc}')
        record['elapsed_seconds']=time.perf_counter()-ts
        save(terminal,record);print(json.dumps(record),flush=True)

if __name__=='__main__':main()
