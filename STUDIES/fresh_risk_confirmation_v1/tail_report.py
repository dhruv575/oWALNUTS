"""Fixed paired monthly summaries; terminal accounting never rescores or draws RNG."""
import hashlib,json
from pathlib import Path
import numpy as np
from tail_inputs import MONTHS,origins,references

ARMS=('candidate','rolling_t5','ewma_t5')
SIDES=('long','short')

def write(path,value):
    from tail_worker import exclusive
    exclusive(path,value)

def valid(value):
    if not isinstance(value,dict) or value.get('status')!='ok':return False
    try:
        if not np.isfinite([value['q05'],value['q95'],value['width']]).all() or not value['q05']<value['q95']:return False
        for side in SIDES:
            r=value['risk'][side]
            if not np.isfinite([r['limit'],r['pinball']]).all() or r['pinball']<0 or type(r['exceedance'])is not int or r['exceedance']not in (0,1):return False
        return True
    except (KeyError,TypeError,ValueError):return False

def load_rows(root,month):
    root=Path(root);n=dict(MONTHS)[month];rows=[]
    for tick in range(1,n+1):
        path=root/'rows'/month/f'{tick:06d}.json'
        if path.exists():
            row=json.loads(path.read_bytes())
            if row.get('month')!=month or row.get('tick')!=tick:raise ValueError('Origin identity mismatch')
            if set(row.get('arms',{}))-set(ARMS):raise ValueError('Unexpected arm')
        else:row=dict(month=month,tick=tick,arms={})
        for arm in ARMS:
            value=row['arms'].get(arm)
            if value is None:
                entered=(root/'started'/'candidate'/month/f'{tick:06d}.json').exists()
                row['arms'][arm]=dict(status='interrupted' if entered else 'not_started')
            elif value.get('status')=='ok' and not valid(value):raise ValueError('Invalid successful arm')
        rows.append(row)
    return rows

def bootstrap(matrix,seed,repetitions=10000):
    """One index stream per month; all columns share each circular resample."""
    n=len(matrix);rng=np.random.default_rng(seed);out={}
    for length in (24,48,96):
        means=[]
        for _ in range(repetitions):
            starts=rng.integers(0,n,size=int(np.ceil(n/length)))
            indices=((starts[:,None]+np.arange(length))%n).ravel()[:n]
            means.append(matrix[indices].mean(axis=0))
        out[str(length)]=np.quantile(np.asarray(means),[.025,.975],axis=0).T.tolist()
    return out

def run(spec,root,month):
    root=Path(root);rows=load_rows(root,month);n=len(rows);summary=dict(status='complete',month=month,planned_origins=n,arms={},comparisons={},references=[])
    vectors=[];names=[]
    for arm in ARMS:
        good=[r['arms'][arm] for r in rows if valid(r['arms'][arm])]
        item=dict(available=len(good),planned=n,full_panel=len(good)==n,tails={})
        if len(good)==n:
            item['mean_width']=float(np.mean([v['width'] for v in good]));item['postprocess_seconds']={k:float(f([v['postprocess_seconds'] for v in good])) for k,f in [('min',np.min),('median',np.median),('max',np.max),('sum',np.sum)]}
        for side in SIDES:
            item['tails'][side]=None
            if len(good)==n:
                r=[v['risk'][side] for v in good];exc=np.array([x['exceedance'] for x in r]);loss=np.array([x['pinball'] for x in r])
                item['tails'][side]=dict(mean_pinball=float(loss.mean()),mean_limit=float(np.mean([x['limit'] for x in r])),exceedance_count=int(exc.sum()),exceedance_rate=float(exc.mean()),signed_exceedance_minus_05=float(exc.mean()-.05))
                vectors.append(exc);names.append(('arm',arm,side))
        summary['arms'][arm]=item
    for arm in ARMS[1:]:
        for side in SIDES:
            key=arm+'_'+side;pair=[r for r in rows if valid(r['arms'][arm]) and valid(r['arms']['candidate'])];item=dict(available=len(pair),planned=n,mean_advantage=None,mean_exceedance_difference=None,block_intervals=None)
            if len(pair)==n:
                loss=np.array([r['arms'][arm]['risk'][side]['pinball']-r['arms']['candidate']['risk'][side]['pinball'] for r in pair]);exc=np.array([r['arms'][arm]['risk'][side]['exceedance']-r['arms']['candidate']['risk'][side]['exceedance'] for r in pair]);daily=loss.reshape(-1,48).mean(axis=1)
                denominator=summary['arms'][arm]['tails'][side]['mean_pinball']
                item.update(mean_advantage=float(loss.mean()),relative_mean_loss_reduction=float(loss.mean()/denominator) if np.isfinite(denominator) and denominator>0 else None,comparison_role='primary' if arm=='ewma_t5' else 'secondary',mean_exceedance_difference=float(exc.mean()),daily_mean_advantage=daily.tolist(),cumulative_advantage=np.cumsum(loss).tolist(),leave_one_day_out_mean=((loss.sum()-daily*48)/(n-48)).tolist())
                vectors.extend([loss,exc]);names.extend([('loss',key,None),('exceedance',key,None)])
            summary['comparisons'][key]=item
    if vectors:
        intervals=bootstrap(np.stack(vectors,axis=1),spec['bootstrap_seeds'][month])
        for j,(kind,key,side) in enumerate(names):
            ci={length:value[j] for length,value in intervals.items()}
            if kind=='arm':summary['arms'][key]['tails'][side]['exceedance_rate_intervals']=ci
            else:summary['comparisons'][key][kind+'_block_intervals']=ci
    for m,index,tick in references():
        if m==month:
            path=root/'references'/month/f'{tick:06d}.json'
            summary['references'].append(json.loads(path.read_bytes()) if path.exists() else dict(month=month,index=index,tick=tick,status='not_started'))
    summary['full_scientific_panel']=all(x['available']==n for x in summary['arms'].values())
    destination=root/'reports'/month;write(destination/'ledger.json',rows);write(destination/'summary.json',summary);return summary

def terminal_accounting(spec,root,jobs):
    root=Path(root);ledgers={m:load_rows(root,m) for m,_ in MONTHS};errors=[];valid_count=sum(valid(row['arms'][a]) for rows in ledgers.values() for row in rows for a in ARMS)
    allowed={f'rows/{m}/{t:06d}.json' for m,t in origins()}|{f'references/{m}/{t:06d}.json' for m,i,t in references()}
    actual={p.relative_to(root).as_posix() for folder in ('rows','references') for p in (root/folder).glob('*/*.json')}
    if actual-allowed:errors.append('Unexpected origin output')
    output_hashes={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sorted(actual)}
    for phase in ('candidate','reference'):
        for shard in range(12):
            path=root/'jobs'/f'{phase}-{shard:02d}.json'
            if not path.exists():continue
            state=json.loads(path.read_bytes())
            for name,want in state.get('output_hashes',{}).items():
                target=root/name
                if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=want:errors.append('Output hash: '+name)
            for name,want in state.get('input_integrity',{}).get('hashes',{}).items():
                target=Path(spec['input']['root'])/name
                if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=want:errors.append('Input hash: '+name)
    reference_ledger=[]
    for m,index,tick in references():
        path=root/'references'/m/f'{tick:06d}.json'
        row=json.loads(path.read_bytes()) if path.exists() else dict(month=m,index=index,tick=tick,status='interrupted' if (root/'started'/'reference'/m/f'{tick:06d}.json').exists() else 'not_started')
        if (row.get('month'),row.get('index'),row.get('tick'))!=(m,index,tick):errors.append('Reference identity')
        if 'candidate_row_sha256'in row and output_hashes.get(f'rows/{m}/{tick:06d}.json')!=row['candidate_row_sha256']:errors.append('Reference candidate binding')
        reference_ledger.append(row)
    result=dict(accounting_complete=True,planned_candidate_origins=4320,planned_reference_origins=24,planned_arm_origins=12960,valid_arm_origins=valid_count,valid_reference_origins=sum(r.get('status')=='ok' for r in reference_ledger),artifact_integrity=dict(integrity_ok=not errors,errors=errors),operational_jobs=jobs)
    write(root/'terminal-output-hashes.json',output_hashes);write(root/'terminal-ledger.json',dict(months=ledgers,references=reference_ledger));write(root/'evidence-validation.json',result);return result

def batch_summary(spec,root):
    root=Path(root);summaries={};result=dict(status='incomplete',months={},origin_weighted_comparisons=None,interpretation='Retrospective descriptive aggregate only; no pooled interval')
    for m,n in MONTHS:
        path=root/'reports'/m/'summary.json'
        if path.exists():summaries[m]=json.loads(path.read_bytes());result['months'][m]=dict(summary_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),full_panel=summaries[m]['full_scientific_panel'])
        else:result['months'][m]=dict(full_panel=False)
    if len(summaries)==3 and all(v['full_scientific_panel'] for v in summaries.values()):
        result.update(status='complete',origin_weighted_comparisons={key:sum(summaries[m]['comparisons'][key]['mean_advantage']*n for m,n in MONTHS)/4320 for key in summaries['2026-04']['comparisons']})
        result['origin_weighted_arms']={arm:dict(mean_width=sum(summaries[m]['arms'][arm]['mean_width']*n for m,n in MONTHS)/4320,tails={side:{key:sum(summaries[m]['arms'][arm]['tails'][side][key]*n for m,n in MONTHS)/4320 for key in ('mean_pinball','mean_limit','exceedance_rate','signed_exceedance_minus_05')} for side in SIDES}) for arm in ARMS}
    write(root/'aggregate.json',result);return result
