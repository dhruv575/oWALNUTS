"""Hourly Agent Comms consultations from operational evidence only."""
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timezone

BASE = Path('/home/ubuntu/.cache/owalnuts-transfer')
LANE = Path('/home/ubuntu/lanes/bounded-confirmation-20261028')
CONFIG = BASE / 'hourly-updates-secret.json'
STATE = BASE / 'hourly-updates'


def request_id(machine, thread, key):
    h = hashlib.sha256(json.dumps([machine, thread, key], separators=(',', ':')).encode()).hexdigest()
    return f'{h[:8]}-{h[8:12]}-4{h[13:16]}-a{h[17:20]}-{h[20:32]}'


def summary():
    import psutil
    from operational_status import status
    rows = status(LANE)
    complete = [r for r in rows if 'slots' in r]
    slots = sum(r['slots'] for r in complete)
    archived = sum(r['slots'] for r in complete if r['archived'])
    nuts = sum(r['qualified']['nuts'] for r in complete)
    walnuts = sum(r['qualified']['walnuts'] for r in complete)
    missing = sum(len(r['missing']) for r in complete)
    control_path = BASE / 'cloud-controller/status.json'
    control = json.loads(control_path.read_text())
    live = False
    try:
        p = psutil.Process(control['pid'])
        live = any(Path(x).name == 'cloud_controller.py' for x in p.cmdline()) and p.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    launches = {}; durations = []
    for line in (BASE / 'cloud-controller/events.jsonl').read_text().splitlines():
        event = json.loads(line)
        if event['state'] == 'launch':
            launches[event['batch']] = datetime.fromisoformat(event['time_utc'].replace('Z', '+00:00'))
        elif event['state'] == 'batch_preserved' and event['batch'] in launches:
            duration = (datetime.fromisoformat(event['time_utc'].replace('Z', '+00:00')) - launches[event['batch']]).total_seconds()
            if duration > 0:
                durations.append(duration)
    remaining = 255 - sum(r['archived'] for r in complete)
    estimate = remaining * statistics.median(durations[-10:]) / 3600 if durations else None
    import shutil
    free = shutil.disk_usage(LANE).free / 1024**3
    phase = control['state']
    state = f"controller live, phase {phase}, batch {control.get('batch', 'n/a')}" if live else f'controller not running (last phase: {phase})'
    eta = f' Estimated remaining: {estimate:.1f} hours at the recent pace, excluding future interruptions.' if live and estimate is not None and phase not in ['blocked','stopped_at_safe_boundary'] else ' No reliable ETA while stopped.'
    if slots == 3050:
        eta = ' All planned slots have finished; final analysis and broader research remain separate.'
    return (f'oWALNUTS hourly update: {slots}/3,050 planned slots finished; {archived} archived and verified. '
            f'{state}. Diagnostic-qualified fits: NUTS {nuts}, WALNUTS {walnuts}; missing case reports: {missing}. '
            f'Free disk: {free:.1f} GiB.{eta} Predictive scores remain sealed; these counts are not evidence of profitability.')


def main():
    import fcntl
    STATE.mkdir(mode=0o700, exist_ok=True)
    with (STATE / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if '--preview' in sys.argv:
            print(summary()); return 0
        config = json.loads(CONFIG.read_text())
        if not config['relayUrl'].startswith('https://'):
            raise ValueError('HTTPS required')
        pending = STATE / 'pending.json'
        if pending.exists():
            job = json.loads(pending.read_text())
        else:
            slot = max(0, int((time.time() - config['anchor_epoch']) // 3600))
            marker = STATE / f'sent-{slot}.json'
            if marker.exists():
                return 0
            key = f"owalnuts-hourly-{int(config['anchor_epoch'])}-{slot}"
            job = dict(slot=slot, body=dict(machineId=config['machineId'],
                sessionId=f"{config['machineId']}:{config['thread_id']}",
                requestId=request_id(config['machineId'], config['thread_id'], key), text=summary()))
            temporary = STATE / 'pending.tmp'
            temporary.write_text(json.dumps(job))
            temporary.replace(pending)
        req = urllib.request.Request(config['relayUrl'].rstrip('/') + '/bridge/consult',
            data=json.dumps(job['body']).encode(), method='POST',
            headers={'Authorization':'Bearer ' + config['bridgeKey'], 'Content-Type':'application/json'})
        with urllib.request.urlopen(req, timeout=20) as response:
            if response.status != 202:
                raise ValueError('Consultation not accepted')
            result = json.load(response)
        receipt = dict(slot=job['slot'], accepted_at_utc=datetime.now(timezone.utc).isoformat(), consultation_id=result['id'])
        (STATE / f"sent-{job['slot']}.json").write_text(json.dumps(receipt, indent=2)+'\n')
        pending.unlink()
        print(json.dumps(receipt))
        return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps(dict(error_type=type(exc).__name__)))
        sys.exit(1)
