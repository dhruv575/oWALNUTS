"""Fixed bounded-loss comparisons; no market access or new scoring in reports."""
import hashlib,json
from pathlib import Path
import numpy as np
from inputs import MONTHS,origins,references
from bounded_loss import COST
ARMS=('candidate','rolling_t5','ewma_t5')
COMPARISONS=[('decision',x) for x in ('ewma_t5','rolling_t5','always_retain','always_convert')]+[('forecast',x) for x in ('ewma_t5','rolling_t5')]
def write(path,value):
    from worker import exclusive
    exclusive(path,value)
def valid(v):
    try:return v.get('status')=='ok' and np.isfinite([v['mean_downside'],v['score']['squared_error'],v['score']['decision_cost']]).all() and 0<=v['mean_downside']<=1 and 0<=v['score']['squared_error']<=1 and 0<=v['score']['decision_cost']<=1 and v['score']['action']in ('retain','convert')
    except (TypeError,KeyError):return False
def load_rows(root,m):
    root=Path(root);rows=[]
    for t in range(1,dict(MONTHS)[m]+1):
        path=root/'rows'/m/f'{t:06d}.json';row=json.loads(path.read_bytes()) if path.exists() else dict(month=m,tick=t,arms={})
        if (row.get('month'),row.get('tick'))!=(m,t) or set(row['arms'])-set(ARMS):raise ValueError('Row identity mismatch')
        for arm in ARMS:
            if arm not in row['arms']:row['arms'][arm]=dict(status='interrupted' if (root/'started/candidate'/m/f'{t:06d}.json').exists() else 'not_started')
            elif row['arms'][arm].get('status')=='ok' and not valid(row['arms'][arm]):raise ValueError('Invalid successful bounded score')
        rows.append(row)
    return rows
def bootstrap(matrix,seed,repetitions=10000):
    rng=np.random.default_rng(seed);n=len(matrix);result={}
    for length in (24,48,96):
        means=[]
        for _ in range(repetitions):
            starts=rng.integers(0,n,size=int(np.ceil(n/length)));indices=((starts[:,None]+np.arange(length))%n).ravel()[:n];means.append(matrix[indices].mean(axis=0))
        result[str(length)]=np.quantile(means,[.025,.975],axis=0).T.tolist()
    return result
def pair(row,kind,control):
    c=row['arms']['candidate']
    if not valid(c):return None
    if control.startswith('always_'):return c['score'][control+'_cost']-c['score']['decision_cost']
    other=row['arms'][control]
    if not valid(other):return None
    field='decision_cost' if kind=='decision' else 'squared_error';return other['score'][field]-c['score'][field]
def run(spec,root,m):
    root=Path(root);rows=load_rows(root,m);n=len(rows);result=dict(status='complete',month=m,planned_origins=n,arms={},comparisons={},references=[]);vectors=[];names=[]
    for arm in ARMS:
        good=[r['arms'][arm] for r in rows if valid(r['arms'][arm])];item=dict(planned=n,available=len(good),means=None)
        if len(good)==n:
            item['means']=dict(mean_downside=float(np.mean([x['mean_downside'] for x in good])),squared_error=float(np.mean([x['score']['squared_error'] for x in good])),decision_cost=float(np.mean([x['score']['decision_cost'] for x in good])),conversion_rate=sum(x['score']['action']=='convert' for x in good)/n)
            item['postprocess_seconds']={key:float(fun([x['postprocess_seconds'] for x in good])) for key,fun in [('min',np.min),('median',np.median),('max',np.max),('sum',np.sum)]}
        item['numerical_ambiguity_count']=sum(bool(x.get('numerical',{}).get('estimated_threshold_ambiguity')) for x in good);result['arms'][arm]=item
    for kind,control in COMPARISONS:
        key=kind+'_'+control;available=[v for row in rows if (v:=pair(row,kind,control))is not None];item=dict(planned=n,available=len(available),mean_advantage=None,block_intervals=None,role='primary' if (kind,control)==('decision','ewma_t5') else 'secondary')
        if len(available)==n:
            values=np.array(available);daily=values.reshape(-1,48).mean(axis=1);item.update(mean_advantage=float(values.mean()),daily_mean_advantage=daily.tolist(),cumulative_advantage=np.cumsum(values).tolist(),leave_one_day_out_mean=((values.sum()-daily*48)/(n-48)).tolist());vectors.append(values);names.append(key)
        result['comparisons'][key]=item
    if vectors:
        ci=bootstrap(np.stack(vectors,axis=1),spec['bootstrap_seeds'][m])
        for i,key in enumerate(names):result['comparisons'][key]['block_intervals']={length:v[i] for length,v in ci.items()}
    for month,i,t in references():
        if month==m:
            path=root/'references'/m/f'{t:06d}.json';result['references'].append(json.loads(path.read_bytes()) if path.exists() else dict(month=m,index=i,tick=t,status='not_started'))
    result['full_scientific_panel']=all(v['available']==n for v in result['arms'].values());write(root/'reports'/m/'ledger.json',rows);write(root/'reports'/m/'summary.json',result);return result
def terminal_accounting(spec,root,jobs):
    root=Path(root);rows={m:load_rows(root,m) for m,n in MONTHS};errors=[];hashes={};reference_rows=[]
    for folder in ('rows','references'):
        for path in (root/folder).glob('*/*.json'):hashes[path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    allowed={f'rows/{m}/{t:06d}.json' for m,t in origins()}|{f'references/{m}/{t:06d}.json' for m,i,t in references()}
    if set(hashes)-allowed:errors.append('Unexpected output origin')
    records=[r['arms']['candidate'] for rs in rows.values() for r in rs]
    for m,i,t in references():
        path=root/'references'/m/f'{t:06d}.json';r=json.loads(path.read_bytes()) if path.exists() else dict(month=m,index=i,tick=t,status='interrupted' if (root/'started/reference'/m/f'{t:06d}.json').exists() else 'not_started')
        if (r.get('month'),r.get('index'),r.get('tick'))!=(m,i,t):errors.append('Reference identity mismatch')
        if 'candidate_row_sha256'in r and hashes.get(f'rows/{m}/{t:06d}.json')!=r['candidate_row_sha256']:errors.append('Reference candidate binding changed')
        reference_rows.append(r);records.append(r.get('reference',{}))
    for r in records:
        if 'functional'in r:
            value=r['functional'];path=root/value['file']
            if not path.resolve().is_relative_to(root.resolve()) or not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=value['sha256']:errors.append('Functional array integrity')
    for path in (root/'jobs').glob('*.json'):
        if '.start.'in path.name:continue
        job=json.loads(path.read_bytes())
        for name,want in job.get('output_hashes',{}).items():
            if hashes.get(name)!=want:errors.append('Output changed: '+name)
        for name,want in job.get('input_integrity',{}).get('hashes',{}).items():
            if hashlib.sha256((Path(spec['input']['root'])/name).read_bytes()).hexdigest()!=want:errors.append('Input changed: '+name)
    result=dict(accounting_complete=True,planned_candidate_origins=4368,planned_reference_origins=24,planned_arm_origins=13104,valid_arm_origins=sum(valid(r['arms'][a]) for rs in rows.values() for r in rs for a in ARMS),valid_reference_origins=sum(r['status']=='ok' for r in reference_rows),artifact_integrity=dict(integrity_ok=not errors,errors=errors),operational_jobs=jobs)
    write(root/'terminal-ledger.json',dict(months=rows,references=reference_rows));write(root/'terminal-output-hashes.json',hashes);write(root/'evidence-validation.json',result);return result
def batch_summary(spec,root):
    root=Path(root);summaries={};result=dict(status='incomplete',months={},origin_weighted_comparisons=None,interpretation='Descriptive exposed-data aggregate; no pooled interval or profit qualification')
    for m,n in MONTHS:
        path=root/'reports'/m/'summary.json'
        if path.exists():summaries[m]=json.loads(path.read_bytes());result['months'][m]=dict(full_panel=summaries[m]['full_scientific_panel'],summary_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        else:result['months'][m]=dict(full_panel=False)
    if len(summaries)==3 and all(s['full_scientific_panel'] for s in summaries.values()):result.update(status='complete',origin_weighted_comparisons={key:sum(summaries[m]['comparisons'][key]['mean_advantage']*n for m,n in MONTHS)/4368 for key in summaries[MONTHS[0][0]]['comparisons']})
    write(root/'aggregate.json',result);return result
