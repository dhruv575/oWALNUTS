"""Terminal six-path inventory with fixed 48-slot denominator."""
import argparse
import json
from pathlib import Path
from rolling_record_audit import audit_lane, sha


def read(path):
    return json.loads(Path(path).read_bytes())


def inventory(root, reference, reference_sha256):
    root=Path(root);outer=read(root/'SUPERVISION.json')
    if outer.get('group_drained') is not True:
        raise ValueError('Terminal process drain required')
    plan=read(root/'PLAN.json');parent=read(root/'PARENT.json')
    if plan.get('paths')!=6 or sha(root/'PARENT.json')!=plan['sources'][plan['parent']]:
        raise ValueError('Frozen parent mismatch')
    months=parent['months']
    if [m['origins'] for m in months]!=[1488,1488,1344] or len({m['month'] for m in months})!=3:
        raise ValueError('Fixed path dimensions')
    if any(len(m['reference_ticks'])!=8 or len(set(m['reference_ticks']))!=8 or
           any(type(t) is not int or not 1<=t<=m['origins'] for t in m['reference_ticks']) for m in months):
        raise ValueError('Fixed score dimensions')
    if sha(Path(reference))!=reference_sha256:
        raise ValueError('Reference hash mismatch')
    refs=read(reference)['rows'];lookup={(r['month'],r['tick']):r['extended'] for r in refs}
    expected={(m['month'],t) for m in months for t in m['reference_ticks']}
    if len(refs)!=24 or set(lookup)!=expected:
        raise ValueError('Reference identity mismatch')
    jobs=[];spots=[]
    for j in range(6):
        month=months[j//2];job=root/'campaign01'/f'job-{j:02d}';lane=job/'fit/lane'
        monitor=read(job/'SUPERVISION.json') if (job/'SUPERVISION.json').exists() else None
        done=read(lane/'DONE.json') if (lane/'DONE.json').exists() else None
        evidence=audit_lane(lane,month['origins'],outer);records=evidence.pop('records')
        native_ok=sum(r.get('native_status')=='ok' for r in records.values())
        available=0
        for tick in month['reference_ticks']:
            row=records.get(tick);ok=bool(row and row.get('native_status')=='ok' and row.get('score_status')=='ok' and
                                       tick<=evidence['journal_completed'])
            if ok and any(k not in row for k in ('arrays','compact','native_arrays','window_sha256')):
                raise ValueError('Successful score missing retained evidence')
            available+=ok
            spots.append(dict(job=j,e72_k400_job=2*j,month=month['month'],replicate=j%2,tick=tick,
                              available=ok,reference_pass=lookup[month['month'],tick]['passed'],
                              score_status=row.get('score_status') if row else 'missing_record',
                              record_sha256=sha(lane/'records'/f'{tick:06d}.json') if row else None,
                              window_sha256=row.get('window_sha256') if row else None,
                              label_index=row.get('label_index') if row else None))
        complete=bool(monitor and monitor.get('exit_code')==0 and monitor.get('group_drained') is True and
                      done and done.get('status')=='complete' and done.get('native_completed')==month['origins'] and
                      native_ok==evidence['journal_completed']==month['origins'] and available==8 and
                      not evidence['truncated_journal_tail'])
        jobs.append(dict(job=j,month=month['month'],replicate=j%2,started=job.exists(),complete=complete,
                         planned_updates=month['origins'],native_ok=native_ok,available_scores=available,
                         recorded_divergences=sum(c['divergences'] for r in records.values() for c in r.get('native_health',[])),
                         integrity=evidence,monitor=monitor,done=done))
    return dict(scope='Terminal structural inventory, not posterior qualification',planned_jobs=6,planned_spots=48,
                completed_jobs=sum(j['complete'] for j in jobs),available_spots=sum(s['available'] for s in spots),
                reference_sha256=reference_sha256,plan_sha256=sha(root/'PLAN.json'),supervision=outer,jobs=jobs,spots=spots)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('reference');p.add_argument('reference_sha256');p.add_argument('out');a=p.parse_args()
    result=inventory(a.root,a.reference,a.reference_sha256)
    with Path(a.out).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False)
