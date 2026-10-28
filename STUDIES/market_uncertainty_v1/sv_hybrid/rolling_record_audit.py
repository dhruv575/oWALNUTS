"""Terminal lane integrity checks; this is not posterior qualification."""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_lane(lane, planned_updates, supervision):
    lane = Path(lane).resolve()
    if supervision.get('group_drained') is not True:
        raise ValueError('Drained terminal supervision required')
    if type(planned_updates) is not int or planned_updates < 1:
        raise ValueError('Positive planned update count required')
    completed = {}
    truncated_tail = False
    journal = lane / 'progress.jsonl'
    lines = journal.read_bytes().splitlines(keepends=True) if journal.exists() else []
    for index, raw in enumerate(lines):
        try:
            event = json.loads(raw)
        except (ValueError, UnicodeError):
            if index == len(lines)-1 and not raw.endswith(b'\n'):
                truncated_tail = True
                continue
            raise ValueError('Malformed journal entry')
        if event.get('event') == 'tick_completed':
            tick = event['tick']
            if type(tick) is not int or tick != len(completed)+1 or tick > planned_updates:
                raise ValueError('Journal completion gap or duplicate')
            completed[tick] = event
    records = {}
    for path in sorted((lane/'records').glob('*.json')):
        row = json.loads(path.read_bytes())
        tick = row['tick']
        if type(tick) is not int or path.name != f'{tick:06d}.json' or not 1 <= tick <= planned_updates:
            raise ValueError('Record identity mismatch')
        if tick != len(records)+1:
            raise ValueError('Record gap')
        if (row['current_index'], row['label_index'], row['window_start'], row['window_stop']) != (249+tick,250+tick,tick,250+tick):
            raise ValueError('Causal index mismatch')
        if tick in completed:
            event = completed[tick]
            if sha(path) != event['record_sha256']:
                raise ValueError('Journal record hash mismatch')
            if any(row.get(k) != event.get(k) for k in ('native_status','score_status')):
                raise ValueError('Journal status mismatch')
        for key in ('compact', 'arrays', 'native_arrays'):
            if key not in row:
                continue
            artifact = (lane/row[key]['file']).resolve()
            if lane not in artifact.parents:
                raise ValueError('Artifact escapes lane')
            if sha(artifact) != row[key]['sha256']:
                raise ValueError('Artifact hash mismatch')
        records[tick] = row
    if not set(completed) <= set(records):
        raise ValueError('Journal references missing record')
    # A kill between record persistence and journal append can leave one orphan.
    orphans = sorted(set(records)-set(completed))
    if orphans not in ([], [len(completed)+1]):
        raise ValueError('Unexpected unjournaled records')
    return dict(recorded_updates=len(records), journal_completed=len(completed),
                unjournaled_records=orphans, truncated_journal_tail=truncated_tail,
                records=records, scope='Integrity only; no completion or fidelity claim')
