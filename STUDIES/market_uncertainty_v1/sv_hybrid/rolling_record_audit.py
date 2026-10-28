"""Terminal lane integrity checks; this is not posterior qualification."""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_packed(value, arrays):
    """Verify every retained leaf and reject unreferenced array members."""
    seen=set()
    def visit(node):
        if isinstance(node,dict) and 'array_key' in node:
            key=node['array_key']
            if key in seen or key not in arrays:raise ValueError('Packed array key mismatch')
            a=arrays[key];seen.add(key)
            if list(a.shape)!=node['shape'] or a.dtype.str!=node['dtype'] or hashlib.sha256(a.tobytes(order='C')).hexdigest()!=node['sha256']:
                raise ValueError('Packed array identity mismatch')
        elif isinstance(node,dict):
            for child in node.values():visit(child)
        elif isinstance(node,list):
            for child in node:visit(child)
    visit(value)
    if seen!=set(arrays):raise ValueError('Unreferenced array members')


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
        if 'native_record_sha256' in row:
            native_record=lane/'native'/f'{tick:06d}.json'
            if sha(native_record)!=row['native_record_sha256']:
                raise ValueError('Pre-score native record mismatch')
        if any(k in row for k in ('compact','arrays','native_arrays')):
            import numpy as np
            if 'compact' in row:
                compact=np.load(lane/row['compact']['file'],allow_pickle=False)
                if compact.dtype!=np.float64 or compact.shape!=(4,400,4) or not np.isfinite(compact).all():
                    raise ValueError('Compact draw axes or values')
                if hashlib.sha256(compact.tobytes(order='C')).hexdigest()!=row['compact_value_sha256']:
                    raise ValueError('Compact value identity mismatch')
            for artifact_key,payload_key in (('arrays','score'),('native_arrays','native')):
                if artifact_key in row:
                    with np.load(lane/row[artifact_key]['file'],allow_pickle=False) as arrays:
                        verify_packed(row[payload_key],arrays)
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
