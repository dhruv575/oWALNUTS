"""Bounded terminal reporting using immutable source and reference bindings."""
import argparse
import importlib.metadata
import json
import sys
from pathlib import Path
from rolling_record_audit import sha
from rolling_inventory import read


def validate(plan_path):
    plan=read(plan_path)
    for path,digest in plan['bindings'].items():
        if sha(Path(path))!=digest:raise ValueError('Analysis binding drift: '+path)
    if sys.prefix!=plan['runtime']['prefix']:raise ValueError('Analysis runtime prefix drift')
    for package,version in plan['runtime']['packages'].items():
        if importlib.metadata.version(package)!=version:raise ValueError('Analysis package drift')
    root=Path(plan['root'])
    if read(root/'SUPERVISION.json').get('group_drained') is not True:
        raise ValueError('Sampling must be terminal and drained')
    return plan


def write(path,value):
    with Path(path).open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2,allow_nan=False)


def run(plan_path):
    plan=validate(plan_path);out=Path(plan['output'])
    from rolling_scores import run as scores
    from rolling_diagnostics import run as diagnostics
    from rolling_compare import run as compare
    result=scores(plan['root'],plan['reference'],plan['reference_sha256'])
    write(out/'SCORES.json',result)
    diagnostics(plan['root'],plan['reference'],plan['reference_sha256'],out/'diagnostics')
    comparison=compare(out/'SCORES.json',plan['walnuts_report'],plan['walnuts_root'])
    write(out/'COMPARISON.json',comparison)
    write(out/'COMPLETE.json',dict(plan_sha256=sha(Path(plan_path)),
          report_hashes={str(p.relative_to(out)):sha(p) for p in out.rglob('*.json')},
          planned_pairs=comparison['planned_pairs'],available_pairs=comparison['available_pairs']))


def supervise(plan_path):
    plan=validate(plan_path);out=Path(plan['output']);out.mkdir(exist_ok=False)
    from resource_monitor import execute
    receipt=execute(['taskset','-c','0-3',sys.executable,str(Path(__file__).resolve()),str(Path(plan_path).resolve()),'--worker'],
                    str(out),900,out,8*1024**3,512*1024**2,out/'worker.log',
                    ownership_env='OWALNUTS_ROLLING_ANALYSIS',utilization_path=out/'utilization.jsonl',
                    phase_reserved_cores={'startup':4},output_scan_interval=5)
    write(out/'SUPERVISION.json',receipt)
    return 0 if receipt.get('exit_code')==0 and receipt.get('group_drained') else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('plan');p.add_argument('--worker',action='store_true');a=p.parse_args()
    if a.worker:run(a.plan)
    else:raise SystemExit(supervise(a.plan))
