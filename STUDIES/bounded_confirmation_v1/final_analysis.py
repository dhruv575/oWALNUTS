"""Final audit and explicitly descriptive summaries, retaining calendar gaps.

Run with a verified compact-evidence directory and a new output directory.
Missing/unqualified cases never admit the frozen primary confirmation analysis.
Exploratory bootstrap samples the original calendar (including missing positions),
then averages qualified observations in each resample; it does not close gaps.
"""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
from primary_analysis import analyze
from confirmation_calendar import schedule
from confirmation_bootstrap import circular_indices


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def describe(x, seed):
    valid = np.isfinite(x).all(axis=1)
    available = x[valid]
    if not len(available):
        return dict(planned=len(x), qualified=0)
    blocks = []
    for offset, block in enumerate([96, 48, 336]):
        rng = np.random.Generator(np.random.PCG64(seed + offset))
        draws = []
        for lo in range(0, 20000, 64):
            starts = rng.integers(0, len(x), size=(min(64, 20000-lo), (len(x)+block-1)//block))
            ix = circular_indices(starts, len(x), block)
            counts = valid[ix].sum(axis=1)
            if np.any(counts == 0):
                raise ValueError('No qualified data in resample')
            draws.append(np.where(valid[ix, None], x[ix], 0.).sum(axis=1)/counts[:, None])
        draws = np.concatenate(draws)
        blocks.append(dict(block=block, seed=seed+offset, replicates=20000,
            lower_9875=np.quantile(draws, .0125, axis=0).tolist(),
            interval_95=np.quantile(draws, [.025, .975], axis=0).T.tolist()))
    return dict(planned=len(x), qualified=len(available), missing_or_unqualified=int((~valid).sum()),
        mean=available.mean(axis=0).tolist(), median=np.median(available, axis=0).tolist(),
        positive_fraction=(available > 0).mean(axis=0).tolist(), blocks=blocks,
        tail_influence=dict(removed_largest_count=int(np.ceil(.01*len(available))),
            mean_without_largest_one_percent=np.sort(available,axis=0)[:-int(np.ceil(.01*len(available)))].mean(axis=0).tolist(),
            scope='Separate per-column descriptive trimming; not a replacement endpoint'),
        scope='Descriptive available-case analysis; calendar gaps retained in resampling; no confirmation or missing-data correction')


def run(lane, output):
    lane, output = Path(lane), Path(output)
    calendar = schedule()['cells']; reports=[]; bindings=[]
    freeze = json.loads((lane/'FREEZE.json').read_text())
    for name in ['confirmation_calendar.py', 'confirmation_bootstrap.py', 'CONFIRMATION-ANALYSIS-PROTOCOL.md']:
        path = Path(__file__).parent.parent/'amm_accounting_v1'/name
        assert sha(path) == freeze['sources']['source/STUDIES/amm_accounting_v1/'+name]
    for batch in range(255):
        folder=lane/f'batch-{batch:03d}'
        receipt=json.loads((folder/'ARCHIVE-VERIFIED.json').read_text())
        packed=json.loads((folder/'ARCHIVE-PACKED.json').read_text())
        assert receipt['exact_version_restore_verified'] and receipt['version_id']
        for key in ['sha256','bytes','plan_sha256','manifest_sha256']:
            assert receipt[key] == packed[key]
        for name,key in [('PLAN.json','plan_sha256'),('RAW-MANIFEST.json','manifest_sha256')]:
            assert sha(folder/name)==receipt[key]
        manifest=json.loads((folder/'RAW-MANIFEST.json').read_text())
        plan=json.loads((folder/'PLAN.json').read_text())
        assert plan['indices']==list(range(batch*12,min(batch*12+12,3050)))
        assert plan['freeze_sha256']==sha(lane/'FREEZE.json')
        def checked(path):
            meta=manifest[str(path.relative_to(lane)).replace('\\','/')]
            assert path.stat().st_size==meta['bytes'] and sha(path)==meta['sha256']
            return json.loads(path.read_text())
        supervision=checked(folder/'SUPERVISION.json')
        assert supervision['group_drained'] and supervision['sources_unchanged']
        final=checked(folder/'FINAL.json')
        assert sorted(r['index'] for r in final)==plan['indices']
        for index in plan['indices']:
            path=folder/f'job-{index}'/'fit/REPORT.json'
            if path.exists():
                report=checked(path); assert report['index']==index
                reports.append(report)
            else:
                assert str(path.relative_to(lane)).replace('\\','/') not in manifest
        bindings.append(dict(batch=batch, **receipt))
    result=analyze(calendar,reports)
    by_index={r['index']:r for r in reports}
    result['descriptive_months']=[]
    for mi,month in enumerate(['2025-09','2025-10']):
        cells=[c for c in calendar if c['month']==month and c['primary']]
        x=np.full((len(cells),4),np.nan); discrepancy=[]; pits={m:[] for m in ['nuts','walnuts']}
        for pos,c in enumerate(cells):
            r=by_index.get(c['index'])
            if not r:continue
            comparisons={v['baseline']:v for v in r['comparisons']}
            if all(comparisons.get(b,{}).get('qualified') for b in ['rolling_t5','ewma_t5','nig_ar1']):
                x[pos]=[comparisons[b]['model'] for b in ['rolling_t5','ewma_t5','nig_ar1']]+[comparisons['rolling_t5']['inference']]
            methods=r['methods']
            if all(methods[m].get('qualified') for m in pits):
                a,b=(methods[m]['prediction'] for m in ['nuts','walnuts'])
                mcse=float(np.hypot(a['logpdf_mcse'],b['logpdf_mcse']))
                discrepancy.append(dict(index=c['index'],difference=b['logpdf']-a['logpdf'],combined_mcse=mcse,standardized=(b['logpdf']-a['logpdf'])/mcse if mcse else None))
            for m in pits:
                if methods[m].get('qualified'):pits[m].append(methods[m]['prediction']['pit'])
        summary=describe(x,398300000+3*mi)
        summary.update(month=month, columns=['nuts_minus_rolling_t5','nuts_minus_ewma_t5','nuts_minus_nig_ar1','walnuts_minus_nuts'],
            pit={m:dict(n=len(v),mean=float(np.mean(v)),below_005=int(np.sum(np.array(v)<.05)),above_095=int(np.sum(np.array(v)>.95))) for m,v in pits.items()},
            sampler_discrepancies=discrepancy)
        result['descriptive_months'].append(summary)
    result['sensitivity']=[]
    for month in ['2025-09','2025-10']:
        for cap in [.5,2.]:
            cells=[c for c in calendar if c['month']==month and c['cap']==cap]
            selected=[by_index[c['index']] for c in cells if c['index'] in by_index]
            result['sensitivity'].append(dict(month=month,cap=cap,planned=len(cells),reported=len(selected),qualified={m:sum(r['methods'][m]['qualified'] for r in selected) for m in ['nuts','walnuts']},
                comparisons={b:dict(n=len(v),mean=float(np.mean(v)) if v else None) for b in ['rolling_t5','ewma_t5','nig_ar1'] for v in [[q['model'] for r in selected for q in r['comparisons'] if q['baseline']==b and q.get('qualified')]]}))
    result['costs']={m:{k:dict(n=len(v),median=float(np.median(v)),total=float(np.sum(v))) for k in ['setup_seconds','sampling_seconds','diagnostics_seconds'] for v in [[r['methods'][m][k] for r in reports if k in r['methods'][m]]]} for m in ['nuts','walnuts']}
    result['qualification']={m:sum(r['methods'][m].get('qualified',False) for r in reports) for m in ['nuts','walnuts']}
    output.mkdir(parents=True,exist_ok=False)
    for name,value in [('RESULTS.json',result),('ARCHIVE-BINDINGS.json',bindings)]:
        (output/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(status=result['status'],admission=result['admission'],qualification=result['qualification'])))


if __name__=='__main__':run(*sys.argv[1:])
