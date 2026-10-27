"""Fixed descriptive paired summaries. No qualification or significance decision."""
import argparse
import json
from pathlib import Path
import numpy as np
from evaluate import atomic

BASELINES=['nig_ar1','rolling_t5_mle','ewma_t5']

def summarize(directory):
    directory=Path(directory);answer=dict(scope='Retrospective descriptive diagnostic, already-inspected streams',datasets={})
    for dataset,seeds,bootstrap_seed in [('sim',[971201,971202,971203],27109701),('real',[971301,971302,971303],27109702)]:
        arms=['reference']+[f'warm_K200:{s}' for s in seeds]+BASELINES
        logs=np.full((100,7),np.nan);pits=logs.copy();ledger=[];origin_status=[]
        for tick in range(1,101):
            path=directory/f'{dataset}-tick-{tick:03d}.json'
            if not path.exists():
                ledger.extend(dict(tick=tick,arm=name,status='not_started') for name in arms)
                origin_status.append(dict(tick=tick,status='not_started'));continue
            value=json.loads(path.read_text())
            if value['dataset']!=dataset or value['tick']!=tick:raise ValueError('Origin identity mismatch')
            seen=set();statuses=[]
            for row in value['arms']:
                name=row['arm']+(f":{row['seed']}" if row['seed'] is not None else '')
                if name not in arms or name in seen:raise ValueError('Unknown or duplicate arm: '+name)
                seen.add(name)
                if row['status']!='ok':
                    ledger.append(dict(tick=tick,arm=name,status='unavailable',reason=row.get('reason')))
                    statuses.append('unavailable');continue
                if not np.isfinite(row['logpdf']) or not np.isfinite(row['pit']) or not 0<=row['pit']<=1:
                    raise ValueError('Invalid status-ok score')
                column=arms.index(name);logs[tick-1,column]=row['logpdf'];pits[tick-1,column]=row['pit']
                ledger.append(dict(tick=tick,arm=name,status='ok'));statuses.append('ok')
            active=value.get('active_arm',{})
            active_name=active.get('arm','')+(f":{active['seed']}" if active.get('seed') is not None else '')
            for name in arms:
                if name not in seen:
                    status='interrupted' if name==active_name else 'not_started'
                    ledger.append(dict(tick=tick,arm=name,status=status));statuses.append(status)
            origin_status.append(dict(tick=tick,status='complete' if statuses==['ok']*7 else 'incomplete'))
        report=dict(planned_origins=100,planned_forecasts=700,forecast_status_ledger=ledger,
                    origin_status_ledger=origin_status,arms={},paired_comparisons={})
        for column,name in enumerate(arms):
            good=np.isfinite(logs[:,column]);p=pits[:,column];valid=p[np.isfinite(p)]
            complete=bool(good.all())
            report['arms'][name]=dict(available_origins=int(good.sum()),full_mean_logscore=float(logs[:,column].mean()) if complete else None,
                available_mean_logscore=float(logs[good,column].mean()) if good.any() else None,
                full_total_logscore=float(logs[:,column].sum()) if complete else None,
                pit_counts=np.histogram(valid,bins=np.linspace(0,1,11))[0].tolist(),
                pit_mean=float(valid.mean()) if len(valid) else None,
                pit_below_05=int(np.sum(valid<.05)),pit_above_95=int(np.sum(valid>.95)),
                central90_count=int(np.sum((valid>=.05)&(valid<=.95))),
                pit_acf={str(lag):float(np.corrcoef(p[:-lag],p[lag:])[0,1]) if np.isfinite(p).all() and np.std(p[:-lag])>0 and np.std(p[lag:])>0 else None for lag in [1,5]})
        differences=[];names=[]
        for baseline in BASELINES:
            b=arms.index(baseline)
            names.append(f'reference-minus-{baseline}');differences.append(logs[:,0]-logs[:,b])
            for j,seed in enumerate(seeds,1):
                names.append(f'warm-{seed}-minus-{baseline}');differences.append(logs[:,j]-logs[:,b])
        for j,seed in enumerate(seeds,1):
            names.append(f'warm-{seed}-minus-reference');differences.append(logs[:,j]-logs[:,0])
        matrix=np.array(differences).T
        for j,name in enumerate(names):
            d=matrix[:,j];good=np.isfinite(d);complete=bool(good.all())
            report['paired_comparisons'][name]=dict(available_pairs=int(good.sum()),
                full_mean=float(d.mean()) if complete else None,
                available_mean=float(d[good].mean()) if good.any() else None,
                cumulative=d.cumsum().tolist() if complete else None,
                block10_means=d.reshape(10,10).mean(axis=1).tolist() if complete else None,
                bootstrap={})
        rng=np.random.default_rng(bootstrap_seed)
        for length in [5,10,20]:
            starts=rng.integers(0,100,size=(2000,int(np.ceil(100/length))))
            indices=((starts[:,:,None]+np.arange(length))%100).reshape(2000,-1)[:,:100]
            means=matrix[indices].mean(axis=1)
            for j,name in enumerate(names):
                report['paired_comparisons'][name]['bootstrap'][str(length)]=np.quantile(means[:,j],[.025,.975]).tolist() if np.isfinite(matrix[:,j]).all() else None
        report['warm_reference_absolute_errors']={str(seed):dict(
            available_pairs=int(np.sum(np.isfinite(logs[:,j]-logs[:,0]))),
            mean_absolute_logpdf=float(np.mean(abs(logs[:,j]-logs[:,0]))) if np.isfinite(logs[:,[0,j]]).all() else None,
            mean_absolute_pit=float(np.mean(abs(pits[:,j]-pits[:,0]))) if np.isfinite(pits[:,[0,j]]).all() else None) for j,seed in enumerate(seeds,1)}
        answer['datasets'][dataset]=report
    return answer

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');args=parser.parse_args()
    path=Path(args.directory)/'summary.json'
    if path.exists():raise FileExistsError(path)
    atomic(path,summarize(args.directory))
