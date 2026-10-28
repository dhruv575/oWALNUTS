"""Match complete-path implementation evidence, retaining missing score pairs."""
import argparse
import json
from pathlib import Path
from rolling_inventory import read
from rolling_record_audit import sha


def pair_rows(nuts,walnuts,walnuts_root):
    if nuts['inventory']['reference_sha256']!=walnuts['inventory']['reference_sha256']:
        raise ValueError('Different reference evidence')
    lookup={(r['job'],r['tick']):r for r in walnuts['rows']}
    if len(nuts['rows'])!=48 or len({(r['job'],r['tick']) for r in nuts['rows']})!=48:
        raise ValueError('NUTS score denominator')
    pairs=[]
    for n in nuts['rows']:
        w=lookup[2*n['job'],n['tick']]
        if n['month']!=w['month'] or n['reference_pass']!=w['reference_pass'] or n['reference']!=w['reference']:
            raise ValueError('Reference or month identity mismatch')
        available=n['metrics_status']==w['metrics_status']=='available'
        pair=dict(nuts_job=n['job'],walnuts_job=w['job'],month=n['month'],tick=n['tick'],
                  reference_pass=n['reference_pass'],available=available,
                  nuts_status=n['metrics_status'],walnuts_status=w['metrics_status'])
        if available:
            path=Path(walnuts_root)/'campaign01'/f"job-{w['job']:02d}"/'candidate/records'/f"{w['tick']:06d}.json"
            if sha(path)!=w['record_sha256']:raise ValueError('WALNUTS record identity mismatch')
            record=read(path)
            if record['window_sha256']!=n['window_sha256'] or record['label_index']!=n['label_index']:
                raise ValueError('Causal window or label mismatch')
            pair['nuts_minus_walnuts_absolute_reference_discrepancy']={k:abs(n['difference'][k])-abs(w['difference'][k]) for k in ('logpdf','pit')}
            pair['nuts_minus_walnuts_mcse']={k:n['candidate'][k+'_mcse']-w['candidate'][k+'_mcse'] for k in ('logpdf','pit')}
            pair['nuts_minus_walnuts_score']={k:n['candidate'][k]-w['candidate'][k] for k in ('logpdf','pit')}
        pairs.append(pair)
    return pairs


def run(nuts_path,walnuts_path,walnuts_root):
    nuts,walnuts=read(nuts_path),read(walnuts_path)
    pairs=pair_rows(nuts,walnuts,walnuts_root);timings=[]
    wjobs={j['job']:j for j in walnuts['inventory']['jobs']}
    for n in nuts['inventory']['jobs']:
        w=wjobs[2*n['job']];both=n['complete'] and w['complete']
        ne=(n['monitor'] or {}).get('elapsed_seconds');we=(w['monitor'] or {}).get('elapsed_seconds')
        if both and (ne is None or we is None or min(ne,we)<=0):raise ValueError('Complete-path timing missing')
        timings.append(dict(nuts_job=n['job'],walnuts_job=w['job'],both_complete=both,
                            nuts_observed_seconds=ne,walnuts_observed_seconds=we,
                            nuts_over_walnuts_full_path_seconds=ne/we if both else None))
    return dict(scope='Descriptive implementation contrast, not isolated algorithm or confirmatory predictive effect',
                nuts_report_sha256=sha(Path(nuts_path)),walnuts_report_sha256=sha(Path(walnuts_path)),
                planned_pairs=48,available_pairs=sum(p['available'] for p in pairs),pairs=pairs,timings=timings,
                uncertainty='No independence-based contrast intervals; shared references and overlapping windows remain dependent.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('nuts');p.add_argument('walnuts');p.add_argument('walnuts_root');p.add_argument('out');a=p.parse_args()
    result=run(a.nuts,a.walnuts,a.walnuts_root)
    with Path(a.out).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False)
