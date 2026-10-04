"""Execute an externally generated, frozen local residual breadth plan.

Standard library only: this controller never generates fixtures or imports a
numerical stack. Plan creation and freezing are deliberately separate.
Required plan keys: frozen, python, source_sha256, bound_files, runner_sha256,
cells (flat execution order). Each cell has id, arm=candidate|reference,
fixture, fixture_sha256, chain_seed. The adjacent plan.sha256 binds the plan.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent
FUNCTIONALS = {'h_terminal','h_initial','h_mean','sigma_obs','sigma_rw'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_new(path, value):
    # Exclusive creation prevents accidental replacement of attempts/evidence.
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def verify_sources(plan):
    if {p.name:digest(p) for p in ROOT.glob('*.py')} != plan['source_sha256']:
        raise ValueError('Study source set or contents changed')
    if digest(__file__) != plan['runner_sha256']:
        raise ValueError('Executor changed')
    for path, expected in plan['bound_files'].items():
        if digest(path) != expected:
            raise ValueError('Bound dependency changed: '+path)


def worker_command(plan, cell, out):
    shared = ['--fixture', cell['fixture'], '--out', str(out), '--seed',
              str(cell['chain_seed']), '--warmup', '1000', '--chains', '4',
              '--tiers', '1000', '2000', '4000', '8000',
              '--coordinates', 'observation_residual']
    if cell['arm'] == 'candidate':
        worker = [plan['python'], str(ROOT/'pymc_workflow.py'), *shared]
        report = out/'python-pymc-report.json'
    elif cell['arm'] == 'reference':
        worker = [plan['python'], str(ROOT/'continuation_precision.py'),
                  *shared, '--model', 'local_level', '--batch-size', '1000',
                  '--target-accept', '0.9']
        report = out/'numpyro-continuation-report.json'
    else:
        raise ValueError('Unknown arm')
    # Wrapper sets affinity before launching/importing the numerical worker,
    # enforces its timeout and kills/reaps the direct worker on timeout.
    command = [plan['python'], str(ROOT/'hardware_control.py'), '--cpus', '0',
               '--record', str(out.parent/(cell['id']+'.hardware.json')),
               '--timeout', '1800', '--', *worker]
    return command, report


def verify_plan(plan_path, original_digest):
    if digest(plan_path) != original_digest or plan_path.with_suffix('.sha256').read_text().strip() != original_digest:
        raise ValueError('Plan or sidecar changed')


def run_cell(plan, plan_path, cell, directory, original_digest):
    started = directory/(cell['id']+'.started.json')
    terminal = directory/(cell['id']+'.status.json')
    output = directory/cell['id']
    if started.exists() or terminal.exists() or output.exists():
        raise FileExistsError('Already attempted; never restart automatically: '+cell['id'])
    start = time.perf_counter()
    save_new(started, dict(id=cell['id'], utc=utc(), plan_sha256=original_digest,
                          fixture_sha256=cell['fixture_sha256'], cell=cell))
    record = dict(id=cell['id'], arm=cell['arm'], phase='exploratory', qualified=False,
                  precision_pass=False, accepted=False, status='executor_failed')
    try:
        verify_plan(plan_path,original_digest)
        verify_sources(plan)
        if digest(cell['fixture']) != cell['fixture_sha256']:
            raise ValueError('Fixture changed')
        command, report_path = worker_command(plan, cell, output)
        record['command'] = command
        with (directory/(cell['id']+'.log')).open('x', encoding='utf-8') as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log,
                                    stderr=subprocess.STDOUT, check=False)
        record.update(returncode=result.returncode, report=str(report_path))
        # Recheck after the worker, including failed workers. Source mutation
        # invalidates this cell without hiding its cost or erasing its output.
        verify_sources(plan)
        verify_plan(plan_path,original_digest)
        if digest(cell['fixture']) != cell['fixture_sha256']:
            raise ValueError('Fixture changed during worker')
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding='utf-8'))
            if report.get('status') == 'completed':
                if report.get('coordinates') != 'observation_residual':
                    raise ValueError('Unexpected reported coordinates')
                if set(report.get('evaluation',{}).get('functionals',{})) != FUNCTIONALS:
                    raise ValueError('Reported functional name set differs from plan')
            record.update(worker_status=report.get('status'),
                          precision_pass=report.get('precision_pass', False),
                          healthy=report.get('healthy', False),
                          retained_divergences=report.get('retained_divergences'),
                          report_sha256=digest(report_path))
            record['accepted'] = (result.returncode == 0 and
                report.get('status') == 'completed' and report.get('precision_pass') is True
                and report.get('healthy') is True and report.get('retained_divergences') == 0)
        record['status'] = 'passed' if record['accepted'] else 'failed'
    except Exception as exc:
        record['error'] = f'{type(exc).__name__}: {exc}'
    record.update(terminal_utc=utc(), elapsed_seconds=time.perf_counter()-start)
    save_new(terminal, record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--cell', action='append')
    args = parser.parse_args()
    plan_path = args.plan.resolve()
    original_digest=digest(plan_path)
    verify_plan(plan_path,original_digest)
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    if plan.get('frozen') is not True:
        raise ValueError('Execution requires an explicitly frozen plan')
    ids = [cell['id'] for cell in plan['cells']]
    if len(ids) != 30 or len(set(ids)) != 30:
        raise ValueError('Require exactly 30 unique planned cells')
    if sum(c['arm']=='candidate' for c in plan['cells']) != 24 or sum(c['arm']=='reference' for c in plan['cells']) != 6:
        raise ValueError('Require 24 candidate and 6 reference cells')
    if any(Path(v).name != v or v in ('.','..') for v in ids):
        raise ValueError('Cell identifiers must be simple names')
    selected = set(args.cell or ids)
    if selected-set(ids):
        raise ValueError('Unknown selected cell')
    for cell in plan['cells']:
        if cell['id'] in selected:
            print(json.dumps(run_cell(plan, plan_path, cell, plan_path.parent,original_digest)), flush=True)


if __name__ == '__main__':
    main()
