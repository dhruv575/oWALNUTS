"""Frozen full-calendar descriptive scoring; never acquires data or samples models."""
import numpy as np

ARMS=('candidate','rolling_t5','ewma_t5')
N=1488
BLOCKS=(24,48,96)
BOOTSTRAP_SEED=2026102713000000

def available(values):
    mask=np.isfinite(values);complete=bool(mask.all())
    return dict(planned_origins=N,available_origins=int(mask.sum()),
        full_mean=float(values.mean()) if complete else None,
        available_mean=float(values[mask].mean()) if mask.any() else None,
        daily_means=[float(day.mean()) if np.isfinite(day).all() else None for day in values.reshape(N//48,48)],
        cumulative=values.cumsum().tolist() if complete else None,
        leave_one_day_out_means=((values.sum()-values.reshape(N//48,48).sum(axis=1))/(N-48)).tolist() if complete else None,
        block_intervals={})

def timing(values):
    a=np.asarray([v for v in values if isinstance(v,(int,float)) and np.isfinite(v) and v>=0],dtype=float)
    return dict(measured_origins=len(a),median=float(np.median(a)) if len(a) else None,
        p95=float(np.quantile(a,.95)) if len(a) else None,maximum=float(a.max()) if len(a) else None,
        total=float(a.sum()) if len(a) else None,scope='All recorded attempts, including unavailable scores; excludes unattempted origins')

def summarize(ledger,*,replicates=10000,seed=BOOTSTRAP_SEED,starts_provider=None):
    if len(ledger)!=N or {r['tick'] for r in ledger}!=set(range(1,N+1)):raise ValueError('Fixed unique full-month ledger required')
    logs=np.full((N,3),np.nan);pits=logs.copy();counts={a:{} for a in ARMS};costs={a:{k:[] for k in ['forecast_seconds','fit_seconds','score_seconds','native_seconds','evaluation_seconds']} for a in ARMS}
    for row in ledger:
        if type(row['tick'])is not int or not 1<=row['tick']<=N:raise ValueError('Invalid tick')
        if set(row['arms'])!=set(ARMS):raise ValueError('Missing/extra arm')
        for j,arm in enumerate(ARMS):
            r=row['arms'][arm];status=r['status'];counts[arm][status]=counts[arm].get(status,0)+1
            if status not in ['ok','unavailable','not_started','interrupted']:raise ValueError('Unknown status')
            if status=='ok':
                if not np.isfinite([r['logpdf'],r['pit']]).all() or not 0<=r['pit']<=1:raise ValueError('Invalid status-ok score')
                logs[row['tick']-1,j]=r['logpdf'];pits[row['tick']-1,j]=r['pit']
            for key in costs[arm]:costs[arm][key].append(r.get(key))
    result=dict(scope='Historical heldout-by-project-access, not prospective live or profit evidence',planned_origins=N,
        planned_forecasts=3*N,status_counts=counts,primary='candidate_minus_rolling_t5',practical_reference_nats=.01,
        bootstrap=dict(seed=seed,replicates=replicates,primary_block=48,blocks=list(BLOCKS),unit='paired origin vector; circular time blocks',scope='descriptive dependent-series uncertainty'),arms={},paired={},qualification=None)
    vectors=[];summaries=[]
    for j,arm in enumerate(ARMS):
        p=pits[:,j];valid=p[np.isfinite(p)]
        r=dict(logscore=available(logs[:,j]),pit_mean=available(p),pit_second_moment=available(p*p),
            pit_histogram=np.histogram(valid,np.linspace(0,1,11))[0].tolist(),pit_available=len(valid),
            pit_below05=int(np.sum(valid<.05)),pit_above95=int(np.sum(valid>.95)),
            central90_count=int(np.sum((valid>=.05)&(valid<=.95))),pit_exact_zero=int(np.sum(valid==0)),pit_exact_one=int(np.sum(valid==1)),
            pit_acf={str(lag):float(np.corrcoef(p[:-lag],p[lag:])[0,1]) if np.isfinite(p).all() and np.std(p[:-lag])>0 and np.std(p[lag:])>0 else None for lag in [1,48]},
            costs={key:timing(value) for key,value in costs[arm].items()})
        result['arms'][arm]=r
        for key,vector in [('logscore',logs[:,j]),('pit_mean',p),('pit_second_moment',p*p)]:vectors.append(vector);summaries.append(r[key])
    for j,arm in [(1,'rolling_t5'),(2,'ewma_t5')]:
        vector=logs[:,0]-logs[:,j];summary=available(vector)
        result['paired']['candidate_minus_'+arm]=summary;vectors.append(vector);summaries.append(summary)
    matrix=np.stack(vectors,axis=1)
    if starts_provider is None:
        rng=np.random.default_rng(seed)
        starts_provider=lambda length,count:rng.integers(0,N,size=(count,int(np.ceil(N/length))))
    for length in BLOCKS:
        starts=np.asarray(starts_provider(length,replicates))
        if starts.shape!=(replicates,int(np.ceil(N/length))) or not np.issubdtype(starts.dtype,np.integer) or np.any((starts<0)|(starts>=N)):
            raise ValueError('Invalid block starts')
        means=np.empty((replicates,matrix.shape[1]))
        for begin in range(0,replicates,100):
            indices=((starts[begin:begin+100,:,None]+np.arange(length))%N).reshape(-1,starts.shape[1]*length)[:,:N]
            means[begin:begin+len(indices)]=matrix[indices].mean(axis=1)
        for j,summary in enumerate(summaries):
            summary['block_intervals'][str(length)]=np.quantile(means[:,j],[.025,.975]).tolist() if np.isfinite(matrix[:,j]).all() else None
    return result
