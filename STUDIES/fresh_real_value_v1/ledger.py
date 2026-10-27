"""Fixed full-calendar evidence ledger, including interrupted native/scoring work."""
import hashlib,json
from pathlib import Path
from data_contract import ORIGINS,FIRST_ORIGIN_MS,HALF

ARMS=('candidate','rolling_t5','ewma_t5')

def read(path):return json.loads(path.read_bytes()) if path.exists() else None
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def build(root):
    root=Path(root);candidate=root/'candidate';events={};interrupted=None
    journal=candidate/'progress.jsonl'
    if journal.exists():
        lines=journal.read_bytes().splitlines()
        for i,line in enumerate(lines):
            try:value=json.loads(line)
            except ValueError:
                if i==len(lines)-1:break
                raise
            if 'tick' in value:events[value['tick']]=value
    result=[]
    for tick in range(1,ORIGINS+1):
        origin=FIRST_ORIGIN_MS+(tick-1)*HALF
        row=dict(tick=tick,origin_ms=origin,label_available_ms=origin+HALF,arms={})
        record_path=candidate/'records'/f'{tick:06d}.json';native_path=candidate/'native'/f'{tick:06d}.json'
        record=read(record_path) or read(native_path)
        event=events.get(tick,{})
        if record:
            if record['tick']!=tick or record['current_index']!=249+tick or record['label_index']!=250+tick:raise ValueError('Candidate causal identity mismatch')
            context=record.get('context',{})
            if context.get('origin_ms')!=origin or context.get('label_available_ms')!=origin+HALF:raise ValueError('Candidate timestamp mismatch')
            if record_path.exists() and event.get('event')=='tick_completed' and sha(record_path)!=event['record_sha256']:raise ValueError('Candidate row hash mismatch')
            status=record['score_status'];score=record.get('score',{})
            entry=dict(status='ok' if status=='ok' else 'unavailable' if status in ['unavailable','partial'] else 'interrupted',
                native_status=record['native_status'],reason=record.get('score_error') or record.get('native_error'),
                native_seconds=record.get('native_wall_seconds'),evaluation_seconds=record.get('scoring_seconds'))
            if entry['status']=='ok':entry.update(logpdf=score['logpdf'],pit=score['pit'],numerical=score['numerical'])
            if record_path.exists():entry['forecast_seconds']=record.get('native_wall_seconds',0)+record.get('scoring_seconds',0)
            row['arms']['candidate']=entry
        else:row['arms']['candidate']=dict(status='interrupted' if event.get('event') in ['tick_started','score_started'] else 'not_started')
        for arm in ['rolling_t5','ewma_t5']:
            path=root/'baselines'/arm/f'tick-{tick:04d}.json';entry=read(path)
            if entry:
                if entry['tick']!=tick or entry['arm']!=arm or entry['origin_ms']!=origin or entry['label_available_ms']!=origin+HALF:raise ValueError('Baseline identity mismatch')
                row['arms'][arm]=entry
            else:
                started=root/'baselines/started'/f'{arm}-tick-{tick:04d}.json'
                row['arms'][arm]=dict(status='interrupted' if started.exists() else 'not_started')
        result.append(row)
    return result

def validate_artifacts(root):
    root=Path(root);checked=0;errors=[]
    records={p.name:p for p in (root/'candidate/native').glob('*.json')}
    records.update({p.name:p for p in (root/'candidate/records').glob('*.json')})
    for path in records.values():
        record=read(path)
        for key in ['compact','native_arrays','arrays']:
            if key in record:
                checked+=1
                if sha(root/'candidate'/record[key]['file'])!=record[key]['sha256']:errors.append(str(path)+':'+key)
        if record.get('native_record_sha256'):
            checked+=1
            if sha(root/'candidate/native'/path.name)!=record['native_record_sha256']:errors.append(str(path)+':native_record')
    for path in (root/'references').glob('*/*.json'):
        value=read(path)
        if value.get('candidate_integrity_error'):errors.append(str(path)+':candidate_integrity')
        for key in ['compact','score_arrays']:
            if key in value:
                checked+=1
                if sha(path.parent/value[key]['file'])!=value[key]['sha256']:errors.append(str(path)+':'+key)
    return dict(checked_hashes=checked,integrity_ok=not errors,errors=errors)

def references(root):
    from run_reference import TICKS
    root=Path(root);rows=[]
    for index,tick in enumerate(TICKS):
        path=root/'references'/f'{index:02d}/reference.json';value=read(path)
        if value:
            if value['index']!=index or value['tick']!=tick:raise ValueError('Reference identity mismatch')
            rows.append(value)
        else:
            checkpoints={name:read(path.parent/name) for name in ['compile-checkpoint.json','draws-checkpoint.json','score-checkpoint.json'] if (path.parent/name).exists()}
            rows.append(dict(index=index,tick=tick,status='interrupted' if (root/'jobs'/f'reference-{index:02d}.start.json').exists() else 'not_started',checkpoints=checkpoints))
    return rows
