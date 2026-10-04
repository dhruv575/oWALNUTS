"""Posthoc adapter verification only; no sampling or extraction."""
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
study = root / 'STUDIES/options_flow_v1'
sys.path.insert(0, str(study))
from posterior_resource.resource_worker import validate_report

pilot = study / 'artifacts/posterior-resource-pilot-v1'
plan = json.loads((pilot / 'plan.json').read_text())
rows = []
for cell in plan['cells']:
    if cell['backend'] != 'public':
        continue
    fit = Path(cell['out']) / 'fit'
    report = json.loads((fit / 'python-pymc-flow-report.json').read_text())
    fixture = json.loads(Path(cell['fixture']).read_text())
    validate_report(report, cell, fixture, plan,
                    fit / 'draws-8000/python-pymc-flow-raw.json')
    rows.append({'cell_id': cell['id'], 'adapter_pass': True,
                 'original_status': json.loads(
                     (pilot / (cell['id'] + '-status.json')).read_text())['status']})
print(json.dumps({'posthoc': True, 'resampled': False, 'rows': rows,
    'adapter_sha256': hashlib.sha256(
        (study / 'posterior_resource/resource_worker.py').read_bytes()).hexdigest()}))
