"""Fixed-denominator descriptive fidelity analysis; no qualification threshold."""
import json,math
from pathlib import Path
from linear_runner import exclusive
from data_model import canonical_targets,canonical

def read(path):
    if not path.exists():return None
    return json.loads(path.read_text(encoding='utf-8-sig'))
def finite(x):return isinstance(x,(int,float)) and math.isfinite(x)
def average(values):return sum(values)/len(values) if values and all(finite(x) for x in values) else None

def analyze(root,p):
    root=Path(root);updates=[];checkpoints=[];queries=[];scales=[];references={};targets=canonical_targets(p['checkpoints'])
    for i,key in enumerate(targets):references[key]=read(root/'references'/f'{i:02d}'/'RESULT.json')
    records={}
    for variant in p['variants']:
      for rep in range(2):
        lane=root/'lanes'/f'{variant}-r{rep}'
        for tick in range(1,2001):
            row=read(lane/'records'/f'{tick:06d}.json');native=read(lane/'native'/f'{tick:06d}.json') if row is None and tick in p['checkpoints'] else None;record=row or native;records[(variant,rep,tick)]=record
            updates.append(dict(variant=variant,replicate=rep,tick=tick,native_status=(record or {}).get('native_status','not_observed'),record_complete=row is not None,native_health=(record or {}).get('native_health'),native_wall_seconds=(record or {}).get('native_wall_seconds')))
            if tick not in p['checkpoints']:continue
            score=(row or {}).get('score') or {};reference=references[canonical(variant,tick)];context=(reference or {}).get('contexts',{}).get(variant,{})
            refscore=context.get('score') or {};reliability=context.get('reliability') or {}
            checkpoints.append(dict(variant=variant,replicate=rep,tick=tick,candidate_status=(row or {}).get('score_status','interrupted' if native else 'not_observed'),reference_status=(reference or {}).get('status','not_observed'),reference_primary_reliable=reliability.get('reliable',False)))
            cq={(q['role'],q['index']):q for q in score.get('queries',[])};rq={(q['role'],q['index']):q for q in refscore.get('queries',[])}
            for role,index in [('grid',i) for i in range(5)]+[('observed_label',None)]:
                c=cq.get((role,index),{});r=rq.get((role,index),{});item=dict(variant=variant,replicate=rep,tick=tick,role=role,index=index,status='unavailable',candidate=c,reference=r,reference_reliable=reliability.get('reliable' if role=='grid' else 'observed_label_reliable',False))
                if c.get('status')==r.get('status')=='ok' and c.get('query_sha256')==r.get('query_sha256'):
                    cf=c['forecast'];rf=r['forecast'];item.update(status='available',cdf_error=cf['cdf']-rf['cdf'],logpdf_error=cf['logpdf']-rf['logpdf'])
                queries.append(item)
            c=score.get('scale') or {};r=refscore.get('scale') or {}
            for j,prob in enumerate((.5,.95)):
                item=dict(variant=variant,replicate=rep,tick=tick,probability=prob,status='unavailable')
                if c.get('status')==r.get('status')=='ok':item.update(status='available',relative_error=c['quantiles'][j]/r['quantiles'][j]-1,candidate_relative_mcse=c['relative_mcse'][j],reference_relative_mcse=r['relative_mcse'][j])
                scales.append(item)
    contrasts=[]
    for variant in p['variants']:
      for rep in range(2):
       for index in range(5):
        subset={q['tick']:q for q in queries if q['variant']==variant and q['replicate']==rep and q['role']=='grid' and q['index']==index}
        for metric in ('cdf_error','logpdf_error'):
            early=average([subset[t].get(metric) if subset[t]['reference_reliable'] else None for t in p['early_contrast_ticks']]);late=average([subset[t].get(metric) if subset[t]['reference_reliable'] else None for t in p['late_contrast_ticks']]);contrasts.append(dict(variant=variant,replicate=rep,index=index,metric=metric,early_mean=early,late_mean=late,late_minus_early=late-early if early is not None and late is not None else None))
    paired=[]
    for rep in range(2):
     for index in range(5):
      for metric in ('cdf_error','logpdf_error'):
        v={x['variant']:x['late_minus_early'] for x in contrasts if x['replicate']==rep and x['index']==index and x['metric']==metric};paired.append(dict(replicate=rep,index=index,metric=metric,shift_minus_control_drift=v['shift']-v['control'] if all(x is not None for x in v.values()) else None))
    prefix=[]
    for rep in range(2):
        a=[records[('control',rep,t)] for t in range(1,1001)];b=[records[('shift',rep,t)] for t in range(1,1001)];observed=[(x,y) for x,y in zip(a,b) if x and y and x.get('native_status')==y.get('native_status')=='ok'];mismatches=[i+1 for i,(x,y) in enumerate(zip(a,b)) if x and y and x.get('compact_value_sha256')!=y.get('compact_value_sha256')];prefix.append(dict(replicate=rep,planned=1000,paired_observed=len(observed),mismatch_ticks=mismatches,all_identical=len(observed)==1000 and not mismatches))
    for name,value in [('UPDATE-LEDGER',updates),('CHECKPOINT-LEDGER',checkpoints),('QUERY-COMPARISONS',queries),('SCALE-COMPARISONS',scales),('DRIFT-CONTRASTS',contrasts),('PAIRED-DRIFT-CONTRASTS',paired),('PAIRED-PREFIX',prefix)]:exclusive(root/(name+'.json'),value)
    summary=dict(status='evidence_complete',qualification=None,planned_updates=8000,observed_successful_native=sum(x['native_status']=='ok' for x in updates),planned_checkpoints=44,planned_query_comparisons=264,available_query_comparisons=sum(x['status']=='available' for x in queries),planned_scale_comparisons=88,available_scale_comparisons=sum(x['status']=='available' for x in scales),planned_unique_references=18,completed_unique_references=sum((x or {}).get('status')=='complete' for x in references.values()),limitations='One paired data path and two sampler replicates; common pre-shift targets are duplicates, not independent evidence. MCSE is descriptive; no population drift inference or old scale-qualification rule.')
    exclusive(root/'SUMMARY.json',summary);return dict(status='complete')
