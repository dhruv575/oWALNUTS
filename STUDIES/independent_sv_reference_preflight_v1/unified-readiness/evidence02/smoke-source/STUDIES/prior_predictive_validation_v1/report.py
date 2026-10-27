"""Stream-cluster summaries. Never treats1024dependent origins as iid."""
import numpy as np
from ledger import ARMS,valid_score
GRID=np.arange(1,20)/20

def bootmeans(values,indices):
    result=np.empty((len(indices),values.shape[1]))
    for start in range(0,len(indices),500):result[start:start+500]=values[indices[start:start+500]].mean(axis=1)
    return result

def scalar_summary(values,indices):
    good=np.isfinite(values);counts=good.sum(axis=1);complete=bool(good.all());stream_means=np.divide(np.nansum(values,axis=1),counts,out=np.full(32,np.nan),where=counts>0)
    out=dict(planned_origins=1024,available_origins=int(good.sum()),complete_streams=int(np.sum(counts==32)),available_origin_mean=float(values[good].mean()) if good.any() else None,stream_available_means=[float(x) if np.isfinite(x) else None for x in stream_means],full_mean=float(values.mean()) if complete else None,cluster_interval95=None)
    out['leave_one_stream_out_means']=None
    if complete:
        out['cluster_interval95']=np.quantile(bootmeans(stream_means[:,None],indices)[:,0],[.025,.975]).tolist()
        out['leave_one_stream_out_means']=((stream_means.sum()-stream_means)/31).tolist()
    return out

def summarize(ledger,sentinels=None,replicates=10000,bootstrap_seed=2026102705000000):
    if type(replicates)is not int or replicates<1:raise ValueError('positive replicate count required')
    ids=[(r['stream'],r['tick']) for r in ledger]
    if len(ids)!=1024 or set(ids)!={(s,t) for s in range(32) for t in range(1,33)}:raise ValueError('Complete unique1024-row ledger required')
    log={a:np.full((32,32),np.nan) for a in ARMS};pit={a:np.full((32,32),np.nan) for a in ARMS};status={a:{} for a in ARMS}
    for row in ledger:
        s,t=row['stream'],row['tick']-1
        for arm in ARMS:
            entry=row['arms'][arm];name=entry['status'];status[arm][name]=status[arm].get(name,0)+1
            if name=='ok':
                if not valid_score(entry):raise ValueError('Invalid ledger score')
                log[arm][s,t]=entry['logpdf'];pit[arm][s,t]=entry['cdf']
    rng=np.random.default_rng(bootstrap_seed);indices=rng.integers(0,32,size=(replicates,32))
    out=dict(planned_streams=32,planned_origins=1024,status_counts=status,bootstrap=dict(seed=bootstrap_seed,replicates=replicates,unit='whole independent stream; all32ticks kept together',same_resamples_for_all_arms=True),arms={},paired={})
    for arm in ARMS:
        p=pit[arm];valid=p[np.isfinite(p)];r=dict(negative_logscore=scalar_summary(-log[arm],indices),pit_mean=scalar_summary(p,indices),pit_second_moment=scalar_summary(p*p,indices),pit_histogram=np.histogram(valid,np.linspace(0,1,11))[0].tolist(),pit_below05=int(np.sum(valid<.05)),pit_above95=int(np.sum(valid>.95)),pit_exact_zero=int(np.sum(valid==0)),pit_exact_one=int(np.sum(valid==1)),pit_ecdf=None)
        if np.isfinite(p).all():
            stream_ecdf=np.stack([(p<=q).mean(axis=1) for q in GRID],axis=1);mean=stream_ecdf.mean(axis=0);resamples=bootmeans(stream_ecdf,indices)
            radius=float(np.quantile(np.max(abs(resamples-mean),axis=1),.95))
            r['pit_ecdf']=dict(grid=GRID.tolist(),estimate=mean.tolist(),uniform_target=GRID.tolist(),centered_bootstrap_supnorm_radius95=radius,lower=np.maximum(0,mean-radius).tolist(),upper=np.minimum(1,mean+radius).tolist(),scope='descriptive32-stream bootstrap simultaneous grid envelope')
        out['arms'][arm]=r
    for other in ['baseline','oracle']:
        # Positive value means candidate has better logscore; all32complete streams needed for interval.
        out['paired']['candidate_logscore_minus_'+other]=scalar_summary(log['candidate']-log[other],indices)
    out['sentinels']=sentinels or []
    for item in out['sentinels']:
        r=item.get('result') or {};score=r.get('score');s,t=item['stream'],item['tick']-1
        item['reference_diagnostics_pass']=r.get('reference_diagnostics_pass') is True
        item['candidate_minus_reference']=None
        if item['reference_diagnostics_pass'] and valid_score(score) and np.isfinite(log['candidate'][s,t]):
            item['candidate_minus_reference']=dict(logpdf=float(log['candidate'][s,t]-score['logpdf']),pit=float(pit['candidate'][s,t]-score['cdf']))
    out['all_candidate_origins_valid']=bool(np.isfinite(log['candidate']).all())
    out['qualification']=None
    return out
