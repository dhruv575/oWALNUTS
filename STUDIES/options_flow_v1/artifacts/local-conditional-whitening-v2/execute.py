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
    plan_path=HERE/'plan.json';original_digest=digest(plan_path);plan=json.loads(plan_path.read_text())
    if plan.get('frozen') is not True:raise ValueError('Plan must be frozen before execution')
    if digest(plan_path)!=(HERE/'plan.sha256').read_text().strip():raise ValueError('Plan digest changed')
    if digest(__file__)!=plan['runner_sha256']:raise ValueError('Runner changed')
    selected=set(args.cell or [c['id'] for c in plan['cells']])
    if selected-{c['id'] for c in plan['cells']}:raise ValueError('Unknown cell')
    for cell in plan['cells']:
        if cell['id'] not in selected:continue
        started=HERE/(cell['id']+'.started.json');terminal=HERE/(cell['id']+'.status.json')
        if started.exists() or terminal.exists():raise FileExistsError('Already attempted: '+cell['id'])
        save(started,dict(id=cell['id'],utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
        ts=time.perf_counter();record=dict(id=cell['id'],phase='exploratory',qualified=False,plan_sha256=original_digest,accepted=False,precision_pass=False,returncode=None)
        try:
            if digest(plan_path)!=original_digest or (HERE/'plan.sha256').read_text().strip()!=original_digest:raise ValueError('Original plan or sidecar changed')
            for bound_path,expected in plan['bound_files'].items():
                if digest(bound_path)!=expected:raise ValueError('Bound file changed: '+bound_path)
            if {p.name:digest(p) for p in ROOT.glob('*.py')}!=plan['source_sha256']:raise ValueError('Study source changed')
            for path,expected in plan['bound_files'].items():
                if digest(path)!=expected:raise ValueError('Bound file changed: '+path)
            if digest(cell['fixture'])!=cell['fixture_sha256']:raise ValueError('Fixture changed')
            with (HERE/(cell['id']+'.log')).open('x',encoding='utf-8') as log:
                result=subprocess.run(cell['command'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=False)
            record['returncode']=result.returncode
            if digest(plan_path)!=original_digest or (HERE/'plan.sha256').read_text().strip()!=original_digest:raise ValueError('Original plan or sidecar changed')
            for bound_path,expected in plan['bound_files'].items():
                if digest(bound_path)!=expected:raise ValueError('Bound file changed: '+bound_path)
            if {p.name:digest(p) for p in ROOT.glob('*.py')}!=plan['source_sha256']:raise ValueError('Study source changed during worker')
            if digest(cell['fixture'])!=cell['fixture_sha256']:raise ValueError('Fixture changed during worker')
            affinity_path=cell['command'][cell['command'].index('--record')+1]
            affinity=json.loads(Path(affinity_path).read_text())
            containment=affinity.get('containment',{})
            if containment.get('kind')!='windows-job-object' or containment.get('assigned_before_worker_execution') is not True or affinity.get('job_active_processes_after_cleanup')!=0:
                raise ValueError('Worker process containment not confirmed')
            record['hardware_record']=affinity_path
            record['hardware_sha256']=digest(affinity_path)
            record['hardware_status']=affinity['status']
            if affinity.get('status')=='worker-timeout':
                record.update(worker_status='operational_timeout',failure_category='timeout',healthy=False)
                record['elapsed_seconds']=time.perf_counter()-ts
                save(terminal,record);print(json.dumps(record),flush=True)
                continue
            report=json.loads(Path(cell['report']).read_text())
            if report.get('fixture_sha256')!=cell['fixture_sha256'] or report.get('source_sha256')!=plan['source_sha256'] or report.get('seed')!=cell['seed'] or report.get('coordinates')!=cell['coordinates']:
                raise ValueError('Worker report provenance mismatch')
            record.update(returncode=result.returncode,worker_status=report.get('status'),
                          precision_pass=(result.returncode==0 and affinity.get('returncode')==0 and affinity.get('status')=='completed' and report.get('status')=='completed' and report.get('healthy') is True and report.get('precision_pass') is True),healthy=report.get('healthy',False),
                          report=cell['report'],report_sha256=digest(cell['report']))
            record['accepted']=record['precision_pass']
            record['failure_category']=None if record['accepted'] else 'worker_health_precision_or_exit_failure'
        except Exception as exc:record.update(worker_status='executor_failed',accepted=False,precision_pass=False,failure_category='operational_provenance_or_executor',error=f'{type(exc).__name__}: {exc}')
        record['elapsed_seconds']=time.perf_counter()-ts
        save(terminal,record);print(json.dumps(record),flush=True)

if __name__=='__main__':main()
