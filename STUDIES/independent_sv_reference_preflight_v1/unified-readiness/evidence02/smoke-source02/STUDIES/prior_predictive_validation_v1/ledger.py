"""Fixed32x32 ledger; independent candidate/baseline/oracle availability."""
import json,math
from pathlib import Path
ARMS=('candidate','baseline','oracle')

def read(path):return json.loads(path.read_text()) if path.exists() else None

def valid_score(score):
    return isinstance(score,dict) and all(isinstance(score.get(k),(int,float)) and math.isfinite(score[k]) for k in ['cdf','logpdf']) and 0<=score['cdf']<=1

def index_rows(value):
    rows={}
    for row in (value or {}).get('rows',[]):
        tick=row['tick']
        if type(tick)is not int or not 1<=tick<=32 or tick in rows:raise ValueError('Invalid or duplicate tick')
        rows[tick]=row
    return rows

def build_ledger(root):
    root=Path(root);ledger=[]
    for stream in range(32):
        directory=root/f'stream-{stream:02d}';candidate=read(directory/'candidate.json');side=read(directory/'side.json');failure=read(directory/'generation-failure.json')
        cr=index_rows(candidate);sr=index_rows(side)
        for tick in range(1,33):
            record=dict(stream=stream,tick=tick,current_index=249+tick,label_index=250+tick,generation='failed' if failure else 'ok' if (directory/'data.json').exists() else 'not_started',arms={})
            for arm in ARMS:
                source=cr.get(tick) if arm=='candidate' else sr.get(tick)
                key='forecast' if arm=='candidate' else arm
                status_key='candidate_status' if arm=='candidate' else arm+'_status'
                state=(source or {}).get(status_key)
                if state=='ok':
                    score=source.get(key)
                    if not valid_score(score):raise ValueError('Invalid status-ok score')
                    entry=dict(status='ok',cdf=score['cdf'],logpdf=score['logpdf'])
                    if 'numerical' in score:entry['numerical']=score['numerical']
                elif state in ('unavailable','failed'):
                    entry=dict(status='unavailable',reason=(source or {}).get(arm+'_error',(source or {}).get('error')))
                else:
                    progress=(candidate or {}).get('in_progress') if arm=='candidate' else ((side or {}).get('in_progress') or {}).get('tick')
                    active=arm=='candidate' or ((side or {}).get('in_progress') or {}).get('arm')==arm
                    interrupted=progress==tick and active
                    reason='generation_failed' if failure else 'stream_stage_ended' if ((candidate if arm=='candidate' else side) or {}).get('status') in ('failed','complete','partial') else None
                    entry=dict(status='interrupted' if interrupted else 'not_started',reason=reason)
                record['arms'][arm]=entry
            ledger.append(record)
    assert len(ledger)==1024
    return ledger

def sentinel_ledger(root):
    from sentinel_adapter import SENTINELS
    out=[]
    for index,(stream,tick) in enumerate(SENTINELS):
        r=read(Path(root)/f'sentinel-{index:02d}'/'reference.json')
        out.append(dict(index=index,stream=stream,tick=tick,status=(r or {}).get('status','not_started'),result=r))
    return out
