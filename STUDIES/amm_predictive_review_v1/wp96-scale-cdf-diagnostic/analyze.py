"""All-scored-origin WP96 scale-CDF diagnostic; immutable archived inputs."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import arviz as az
import numpy as np
import scipy

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent/'scale-cdf-diagnostic'/'analyze.py'
spec = importlib.util.spec_from_file_location('scale_cdf', SHARED)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
STREAMS = ('shift','control')
POLICIES = ('frozen','m100','m500','trig')
SEEDS = (960101,960102)
ESTIMATORS = ('original','noise_vs_cdf','cdf_vs_cdf')


def uncertainty(a, idx, tick, proto, computed):
    m = a[...,0]+proto['model']['rho']*(a[...,2]-a[...,0])
    sigma = np.exp(a[...,1])
    eps = np.random.default_rng(proto['quantities']['eps_seed_base']+tick).normal(size=(4,20000))[idx,:a.shape[1]]
    predictive_scale = np.exp((m+sigma*eps)/2)
    analytic, noisy = [], []
    for p,h,q,nq in zip(base.PS,computed['deterministic']['logvol_roots'],
                       (computed['deterministic']['p50'],computed['deterministic']['p95']),
                       (computed['original_noise']['p50'],computed['original_noise']['p95'])):
        z = (h-m)/sigma
        f = float(np.mean(2*np.exp(-z*z/2)/(np.sqrt(2*np.pi)*q*sigma)))
        analytic.append(float(az.mcse(base.ndtr(z),method='mean'))/f/q)
        noisy.append(float(az.mcse(predictive_scale,method='quantile',prob=p))/nq)
    if not np.isfinite(analytic+noisy).all():
        raise ValueError('nonfinite MCSE diagnostic')
    return dict(analytic_relative=analytic,original_relative=noisy,
                caveat='Asymptotic chain-aware diagnostic; no stationarity or automatic stopping guarantee')


def load(cell,rec,tick,reference,sources):
    p = cell/rec['file'] if reference else cell/f'tick-{tick:04}.f32'
    sources[str(p.resolve())] = base.identity(p)
    raw = np.frombuffer(p.read_bytes(),dtype='<f4')
    if raw.size != rec['chains']*rec['draws']*3:
        raise ValueError('compact draw shape mismatch')
    a = raw.reshape(rec['chains'],rec['draws'],3).astype(float)
    idx = rec['kept'] if reference else rec.get('kept',list(range(rec['chains'])))
    if reference:
        a = a[idx]
    if a.shape[0]!=len(idx) or not np.isfinite(a).all():
        raise ValueError('invalid draws or original chain identities')
    return a,idx


def pair(computed,reference,stuck):
    values = {k:np.array([computed[k]['p50'],computed[k]['p95']]) for k in ('original_noise','deterministic')}
    refs = {k:np.array([reference[k]['p50'],reference[k]['p95']]) for k in ('original_noise','deterministic')}
    out = {}
    for name,num,den in [('original','original_noise','original_noise'),
                         ('noise_vs_cdf','original_noise','deterministic'),
                         ('cdf_vs_cdf','deterministic','deterministic')]:
        errors = values[num]/refs[den]-1
        out[name] = dict(errors=errors.tolist(),within_bands=bool(np.all(np.abs(errors)<=base.TOL)),
                         accurate_no_stuck=bool(np.all(np.abs(errors)<=base.TOL) and not stuck))
    return out


def group(rows,stream,policy,half,seed=None):
    selected = [r for r in rows if r['stream']==stream and r['policy']==policy and r['half']==half
                and (seed is None or r['seed']==seed)]
    good = [r for r in selected if r['status']=='ok']
    out = dict(stream=stream,policy=policy,half=half,seed=seed,planned=len(selected),processed=len(good))
    for estimator in ESTIMATORS:
        mcse_key = 'analytic_relative' if estimator=='cdf_vs_cdf' else 'original_relative'
        per_seed = {str(s):sum(r['comparisons'][estimator]['accurate_no_stuck'] for r in good if r['seed']==s)
                    for s in SEEDS if seed is None or s==seed}
        passed = sum(per_seed.values())
        out[estimator] = dict(within_bands=sum(r['comparisons'][estimator]['within_bands'] for r in good),
            accurate_no_stuck=passed,share=passed/len(selected),per_seed_counts=per_seed,
            descriptive_95pooled_90perseed=(passed>=76 and all(n>=36 for n in per_seed.values())) if seed is None else None,
            mean_signed_errors=[float(np.mean([r['comparisons'][estimator]['errors'][i] for r in good])) for i in (0,1)] if good else None,
            median_absolute_errors=[float(np.median([abs(r['comparisons'][estimator]['errors'][i]) for r in good])) for i in (0,1)] if good else None,
            median_own_relative_mcse=[float(np.median([r['uncertainty'][mcse_key][i] for r in good])) for i in (0,1)] if good else None)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,required=True,help='WP96 source directory with protocol/analyze.py')
    parser.add_argument('--artifacts',type=Path,required=True,help='Immutable recovered artifacts directory')
    parser.add_argument('--out',type=Path,default=HERE)
    args = parser.parse_args()
    start = time.perf_counter()
    deadline = start+300
    result = dict(kind='post-hoc all-scored-tick estimator diagnostic; original WP96 verdict unchanged',
        created_utc=datetime.now(timezone.utc).isoformat(),planned_references=160,planned_warm_rows=1280,
        plan=base.identity(HERE/'PLAN.md'),source=base.identity(Path(__file__)),shared_source=base.identity(SHARED),
        environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,arviz=az.__version__,platform=platform.platform()),
        reference_caveat=base.CAVEAT,numerical_fixtures=base.fixtures(deadline),origins=[],rows=[])
    study,art = args.study.resolve(),args.artifacts.resolve()
    proto = json.loads((study/'protocol.json').read_text())
    sources = {str(p.resolve()):base.identity(p) for p in (study/'protocol.json',study/'analyze.py')}
    archived = {}
    report_path = art/'per-tick.json'
    if report_path.exists():
        sources[str(report_path)] = base.identity(report_path)
        for key,rows in json.loads(report_path.read_text()).items():
            cell_id,half = key.split(':')
            for row in rows:
                archived[(cell_id,row['tick'])] = row
    logs = {}
    def records(cell):
        if cell not in logs:
            logs[cell] = base.records(cell,sources)
        return logs[cell]
    for stream in STREAMS:
        for tick in range(25,2001,25):
            origin_start = time.perf_counter()
            key = f'{stream}:{tick}'
            half = 'half1' if tick<=1000 else 'half2'
            origin = dict(key=key,stream=stream,tick=tick,half=half,status='pending')
            reference = None
            try:
                base.check_deadline(deadline)
                cell = art/'cells'/f'ref-{stream}'
                rec = records(cell).get(tick)
                if rec is None or rec.get('status')!='ok':
                    raise ValueError('reference missing or original gate failed')
                a,idx = load(cell,rec,tick,True,sources)
                reference = base.compute(a,idx,tick,proto,deadline,reference=True)
                ref_medians = [float(np.median(a[...,1])),float(np.median(a[...,2]))]
                origin.update(status='ok',reference=reference,reference_medians_log_sigma_h_last=ref_medians,
                              original_gate={k:rec.get(k) for k in ('status','kept','flagged','seed','attempt','rhat_h_next')})
            except (OSError,ValueError,KeyError,IndexError,TimeoutError) as exc:
                origin.update(status='budget_exhausted' if isinstance(exc,TimeoutError) else 'invalid_or_missing',error=str(exc))
            for policy in POLICIES:
                for seed in SEEDS:
                    cell_id = f'warm-{policy}-{stream}-s{seed}'
                    row = dict(cell=cell_id,stream=stream,tick=tick,policy=policy,seed=seed,half=half,reference_key=key,status='pending')
                    try:
                        base.check_deadline(deadline)
                        if reference is None:
                            raise ValueError('reference unavailable')
                        cell = art/'cells'/cell_id
                        rec = records(cell).get(tick)
                        if rec is None or rec.get('status')!='ok':
                            raise ValueError('warm record missing or not ok')
                        a,idx = load(cell,rec,tick,False,sources)
                        computed = base.compute(a,idx,tick,proto,deadline)
                        stuck = [c for c in range(len(a)) if abs(np.median(a[c,:,1])-ref_medians[0])>1 or abs(np.median(a[c,:,2])-ref_medians[1])>2]
                        comparisons = pair(computed,reference,stuck)
                        old = archived.get((cell_id,tick))
                        reproduction = None
                        if old:
                            e = comparisons['original']['errors']
                            delta = max(abs(e[0]-old['e50']),abs(e[1]-old['e95']))
                            reproduction = dict(max_absolute_error_difference=delta,
                                accuracy_matches=comparisons['original']['accurate_no_stuck']==old['accurate'],stuck_matches=stuck==old['stuck'])
                            if delta>1e-12 or not reproduction['accuracy_matches'] or not reproduction['stuck_matches']:
                                raise ValueError('original frozen score reproduction mismatch')
                        row.update(status='ok',quantiles={name:{k:computed[name][k] for k in ('p50','p95','processing_seconds')} for name in ('original_noise','deterministic')},
                            numerical=dict(logvol_bracket=computed['deterministic']['logvol_bracket'],residuals=computed['deterministic']['residuals']),
                            comparisons=comparisons,uncertainty=uncertainty(a,idx,tick,proto,computed),
                            original_frozen_gate=dict(stuck=stuck,accurate=comparisons['original']['accurate_no_stuck'],
                                tolerance_p50=.02,tolerance_p95=.05,latency_is_not_gated=True),
                            original_warm_metadata={k:rec.get(k) for k in ('chains','draws','kept','divergences','readapt','wall_seconds')},
                            original_noise_chain_rows=idx,original_score_reproduction=reproduction)
                    except (OSError,ValueError,KeyError,IndexError,TimeoutError) as exc:
                        row.update(status='budget_exhausted' if isinstance(exc,TimeoutError) else 'invalid_or_missing',error=str(exc))
                    result['rows'].append(row)
            origin['local_total_processing_seconds'] = time.perf_counter()-origin_start
            result['origins'].append(origin)
    result['input_identities'] = list(sources.values())
    result['input_integrity_after'] = all(base.identity(Path(p))['sha256']==v['sha256'] for p,v in sources.items())
    if not result['input_integrity_after']:
        raise ValueError('input changed during read-only analysis')
    result['processed_references'] = sum(r['status']=='ok' for r in result['origins'])
    result['processed_warm_rows'] = sum(r['status']=='ok' for r in result['rows'])
    result['total_local_processing_seconds'] = time.perf_counter()-start
    result['groups'] = [group(result['rows'],s,p,h) for s in STREAMS for p in POLICIES for h in ('half1','half2')]
    result['seed_groups'] = [group(result['rows'],s,p,h,n) for s in STREAMS for p in POLICIES for h in ('half1','half2') for n in SEEDS]
    args.out.mkdir(parents=True,exist_ok=True)
    raw = json.dumps(result,allow_nan=False,separators=(',',':')).encode()
    (args.out/'results.json.gz').write_bytes(gzip.compress(raw,mtime=0))
    summary = {k:v for k,v in result.items() if k not in ('rows','origins','input_identities')}
    summary['detailed_results_sha256'] = hashlib.sha256((args.out/'results.json.gz').read_bytes()).hexdigest()
    (args.out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(processed_references=result['processed_references'],processed_warm_rows=result['processed_warm_rows'],
                         seconds=result['total_local_processing_seconds'],groups=[{k:g[k] for k in ('stream','policy','half','original','cdf_vs_cdf')} for g in result['groups']]),indent=2))


if __name__=='__main__':
    main()
