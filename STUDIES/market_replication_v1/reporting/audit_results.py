"""Post-terminal descriptive evidence audit only; no fitting, RNG or score rerun."""
import argparse,collections,hashlib,json,math,time
from pathlib import Path
MONTHS=[('2026-04',1440),('2026-05',1488),('2026-06',1440)]
ARMS=['candidate','rolling_t5','ewma_t5']

def paired_check(rows,summary,n):
    if len(rows)!=n or {r['tick'] for r in rows}!=set(range(1,n+1)):raise ValueError('Nonunique/incomplete ledger identities')
    scores={a:[] for a in ARMS};counts={a:collections.Counter() for a in ARMS}
    for row in rows:
        if set(row['arms'])!=set(ARMS):raise ValueError('Arm identity mismatch')
        for a in ARMS:
            v=row['arms'][a];counts[a][v['status']]+=1
            if v['status']=='ok':
                if not math.isfinite(v['logpdf']) or not math.isfinite(v['pit']) or not 0<=v['pit']<=1:raise ValueError('Invalid status-ok score')
                scores[a].append(v['logpdf'])
    result=dict(status_counts={a:dict(c) for a,c in counts.items()},arm_means={},paired_means={})
    for a in ARMS:
        mean=math.fsum(scores[a])/n if len(scores[a])==n else None;result['arm_means'][a]=mean
        if summary:
            if summary['status_counts'][a]!=dict(counts[a]):raise ValueError('Frozen status counts mismatch')
            want=summary['arms'][a]['logscore']['full_mean']
            if want is not None and (type(want)not in (int,float) or not math.isfinite(want)):raise ValueError('Nonfinite/nonnumeric frozen mean')
            if (mean is None)!=(want is None) or mean is not None and abs(mean-want)>1e-12:raise ValueError('Frozen arm mean mismatch')
    for baseline in ARMS[1:]:
        pairs=[r['arms']['candidate']['logpdf']-r['arms'][baseline]['logpdf'] for r in rows if r['arms']['candidate']['status']=='ok' and r['arms'][baseline]['status']=='ok']
        mean=math.fsum(pairs)/n if len(pairs)==n else None;name='candidate_minus_'+baseline;result['paired_means'][name]=dict(available_pairs=len(pairs),full_mean=mean)
        if summary:
            want=summary['paired'][name]['full_mean']
            if want is not None and (type(want)not in (int,float) or not math.isfinite(want)):raise ValueError('Nonfinite/nonnumeric frozen mean')
            if (mean is None)!=(want is None) or mean is not None and abs(mean-want)>1e-12:raise ValueError('Frozen paired mean mismatch')
    return result

def initialization_summary(value):
    telemetry=value.get('telemetry') or (value.get('failure') or {}).get('payload') or {}
    config=telemetry.get('config') or {};warmup=config.get('warmup');draws=config.get('draws');chains=[]
    totals={k:collections.Counter() for k in ['work_discarded','work_retained','work_total']};guards=[]
    for i,c in enumerate(telemetry.get('chains') or []):
        row=dict(chain=i,guard_checks=c.get('trapped_chain_checks'),warmup_end=c.get('warmup_end'),sampling_end=c.get('sampling_end'),array_health_available=False)
        divergence=c.get('divergent');depth=c.get('depth');stop=c.get('stop')
        if type(warmup)is int and type(draws)is int and isinstance(divergence,list) and len(divergence)==warmup+draws and all(v in [0,1,False,True] for v in divergence):
            row.update(array_health_available=True,warmup_array_divergences=sum(divergence[:warmup]),retained_array_divergences=sum(divergence[warmup:]))
            if isinstance(depth,list) and len(depth)==warmup+draws:row.update(warmup_maximum_depth=max(depth[:warmup],default=None),retained_maximum_depth=max(depth[warmup:],default=None))
            if isinstance(stop,list) and len(stop)==warmup+draws:row.update(warmup_stop_counts=dict(collections.Counter(map(str,stop[:warmup]))),retained_stop_counts=dict(collections.Counter(map(str,stop[warmup:]))))
        for key in totals:
            row[key]=c.get(key)
            if isinstance(c.get(key),dict):totals[key].update({k:v for k,v in c[key].items() if type(v)in(int,float)})
        guards.extend(c.get('trapped_chain_checks') or []);chains.append(row)
    return dict(status=value.get('status'),failure=value.get('failure'),engine_factory_seconds=value.get('engine_factory_seconds'),config=config,
        chain_warnings=telemetry.get('chain_warnings'),chains=chains,recorded_chains=len(chains),work_totals={k:dict(v) for k,v in totals.items()},
        guard_checks=len(guards),guard_restarts=sum(g.get('restarted')is True for g in guards),
        scope='Initial warmup/retained/guard telemetry is separate from per-update health; discarded work may include abandoned attempts and must not be called retained sampling')

def audit(root):
    root=Path(root).resolve();start=time.monotonic();hashes={};bytes_read=0
    def read(path):
        nonlocal bytes_read
        if time.monotonic()-start>120:raise TimeoutError('Postrun audit120second bound')
        if len(hashes)>=50000:raise ValueError('Postrun audit file bound')
        if path.stat().st_size>16*1024**2:raise ValueError('Postrun audit per-file byte bound')
        raw=path.read_bytes();bytes_read+=len(raw)
        if len(raw)>16*1024**2 or bytes_read>1024**3:raise ValueError('Postrun audit byte bound')
        hashes[str(path.relative_to(root))]=hashlib.sha256(raw).hexdigest();return json.loads(raw)
    outer=read(root/'BATCH-SUPERVISION.json')
    if outer.get('group_drained')is not True or outer.get('remaining_owned_pids')!=[]:raise ValueError('Terminal drained supervisor required before interpretation')
    batch=root/'batch';state=read(batch/'BATCH-FINAL.json');result=dict(scope='Existing frozen summaries and metadata only; no new inference',planned_origins=4368,planned_forecasts=13104,planned_references=24,outer=outer,all_original_jobs=state['jobs'],months=[])
    for month,n in MONTHS:
        folder=batch/month;sp=folder/'summary.json';summary=read(sp) if sp.exists() else None
        lp=folder/'ledger.json'
        if not lp.exists():lp=folder/'terminal-ledger.json'
        item=dict(month=month,planned_origins=n,ledger_missing=not lp.exists(),summary_missing=summary is None)
        initial=folder/'candidate/INITIAL.json';item['initialization']=initialization_summary(read(initial)) if initial.exists() else dict(status='not_recorded')
        if lp.exists():item['ledger_check']=paired_check(read(lp),summary,n)
        if summary:
            item['paired']=summary['paired'];item['arms']=summary['arms'];item['references']=summary['references'];item['artifact_integrity']=summary['artifact_integrity']
        else:
            rp=folder/'terminal-references.json';item['references']=read(rp) if rp.exists() else None
        health=dict(recorded_ticks=0,recorded_chain_updates=0,transitions=0,divergences=0,nonfinite_energy_errors=0,zero_density_evaluations=0,maximum_depth=None,maximum_finite_abs_energy_error=None,stop_counts={},missing_field_counts={});stops=collections.Counter();missing=collections.Counter();numeric=dict(recorded_scores=0,max_logpdf_order_difference=None,max_pit_order_difference=None,roundoff_clips=0)
        records={p.name:p for p in (folder/'candidate/native').glob('*.json')};records.update({p.name:p for p in (folder/'candidate/records').glob('*.json')})
        for path in sorted(records.values()):
            value=read(path);health['recorded_ticks']+=1
            for h in (value.get('native_health') or []):
                health['recorded_chain_updates']+=1
                for key in ['transitions','divergences','nonfinite_energy_errors','zero_density_evaluations']:
                    if h.get(key)is None:missing[key]+=1
                    else:health[key]+=h[key]
                for key in ['maximum_depth','maximum_finite_abs_energy_error']:
                    if h.get(key)is not None:health[key]=max(health[key] if health[key]is not None else h[key],h[key])
                stops.update(h.get('stop_counts',{}))
            num=(value.get('score') or {}).get('numerical')
            if num:
                numeric['recorded_scores']+=1
                for dest,src in [('max_logpdf_order_difference','logpdf_absolute_difference'),('max_pit_order_difference','pit_absolute_difference')]:numeric[dest]=max(numeric[dest] or 0,num[src])
                numeric['roundoff_clips']+=sum(x['cdf_roundoff_clip_count'] for x in num['aggregate_by_order'])
        health['stop_counts']=dict(stops);health['missing_field_counts']=dict(missing);item.update(native_health=health,numerical=numeric);result['months'].append(item)
    ap=batch/'aggregate.json';result['frozen_aggregate']=read(ap) if ap.exists() else None
    result.update(input_hashes=hashes,files_read=len(hashes),bytes_read=bytes_read,elapsed_seconds=time.monotonic()-start,qualification=None)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    result=audit(args.root)
    with Path(args.out).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
