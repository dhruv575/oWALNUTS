"""Post-run descriptive as-of replay outcomes; no sampling or qualification.

All32 intended fits and all8x4 origin/group forecasts remain explicit. Sparse,
serially dependent outcomes do not justify independent-binomial coverage claims.
"""
import math
from pathlib import Path
from continuation_comparison import load,save,sha
from asof_rolling_protocol import ORIGINS,ARMS,delayed_join
from asof_rolling_execute import gate
from asof_market_fixture import delayed_scores


def summarize(directory,*,as_of_ms):
    directory=Path(directory).resolve();path=directory/'plan.json';plan=load(path);digest=sha(path)
    if plan.get('frozen') is not True or path.with_suffix('.sha256').read_text().strip()!=digest or plan['expected']!=32:
        raise ValueError('Frozen complete32-cell intent required')
    cells=plan['cells']
    expected={(o,a) for o in ORIGINS for a in ARMS}
    if len(cells)!=32 or {(c['origin'],c['comparison_arm']) for c in cells}!=expected:raise ValueError('Intended origin/arm denominator differs')
    panel=load(plan['panel_path'])
    if sha(plan['panel_path'])!=plan['bound_files'][str(Path(plan['panel_path']).resolve())]:raise ValueError('Scoring panel changed')
    outcomes=[];by_key={}
    for c in cells:
        sp=directory/(c['id']+'-status.json');item=dict(id=c['id'],origin=c['origin'],arm=c['comparison_arm'],success=False,
            status='missing_terminal_record',elapsed_seconds=None,forecasts=[dict(group=g,forecast_usable=False,scoring_eligible=None,observed=None,covered=None,interval_score=None) for g in range(4)])
        try:
            status=load(sp);item['status']=status['status'];elapsed=status['elapsed_seconds']
            if type(elapsed) not in (int,float) or not math.isfinite(elapsed) or elapsed<0:raise ValueError('Invalid charged elapsed')
            item['elapsed_seconds']=elapsed;item['terminal_sha256']=sha(sp)
            fixture=load(c['fixture'])
            if sha(c['fixture'])!=c['fixture_sha256']:raise ValueError('Fixture changed')
            labels=delayed_scores(fixture,panel,as_of_ms=as_of_ms)
            item['forecasts']=[dict(label,forecast_usable=False,covered=None,interval_score=None) for label in sorted(labels,key=lambda r:r['group'])]
            if status.get('success') is True:
                rp=directory/c['id']/('python-pymc-flow-report.json' if c['arm']=='owalnuts_continuation' else 'report.json')
                if sha(rp)!=status['report_sha256']:raise ValueError('Report changed after terminal commitment')
                report=load(rp)
                if not gate(report,c):raise ValueError('Claimed success fails full precision gate')
                fixture=load(c['fixture']);joined=delayed_join(fixture,panel,rp,status['report_sha256'],cell=c,as_of_ms=as_of_ms)
                intervals={(r['horizon'],r['group']):r for r in report['evaluation']['forecast']['rows']}
                rows=[]
                for label in sorted(joined['labels'],key=lambda r:r['group']):
                    row=dict(label,forecast_usable=bool(label['forecast_available']),covered=None,interval_score=None)
                    interval=intervals[(1,label['group'])];lo=interval['lower'];hi=interval['upper']
                    row.update(lower=lo,upper=hi,width=hi-lo if label['forecast_available'] else None)
                    if label['scoring_eligible'] and label['forecast_available']:
                        y=label['observed'];row.update(covered=lo<=y<=hi,interval_score=hi-lo+20*max(lo-y,0)+20*max(y-hi,0))
                    rows.append(row)
                item.update(success=True,forecasts=rows,report_sha256=status['report_sha256'])
        except Exception as exc:item.update(success=False,validation_error=str(exc))
        outcomes.append(item);by_key[(c['origin'],c['comparison_arm'])]=item
    summaries={}
    for arm in ARMS:
        subset=[r for r in outcomes if r['arm']==arm];scored=[f for r in subset if r['success'] for f in r['forecasts'] if f['covered'] is not None]
        known=[r['elapsed_seconds'] for r in subset if r['elapsed_seconds'] is not None]
        summaries[arm]=dict(intended_fits=8,intended_forecasts=32,successful_fits=sum(r['success'] for r in subset),failed_or_unverified_fits=sum(not r['success'] for r in subset),
            no_forecast_eligible_fits=sum(r['status']=='no_forecast_eligible' for r in subset),
            known_anchor_cells=sum(f.get('anchor_available') is True for r in subset for f in r['forecasts']),
            missing_anchor_cells=sum(f.get('anchor_available') is False for r in subset for f in r['forecasts']),
            missing_covariate_cells=sum(f.get('feature_available') is False for r in subset for f in r['forecasts']),
            future_unobserved_cells=sum(f.get('future_outcome_unobserved') is True for r in subset for f in r['forecasts']),
            eligible_observed_cells=sum(f.get('scoring_eligible') is True for r in subset for f in r['forecasts']),
            missing_or_purged_cells=sum(f.get('scoring_eligible') is False for r in subset for f in r['forecasts']),
            unknown_label_eligibility_cells=sum(f.get('scoring_eligible') is None for r in subset for f in r['forecasts']),
            scored_forecasts=len(scored),unscored_forecasts=32-len(scored),known_elapsed_seconds=sum(known),missing_cost_records=8-len(known),
            coverage=sum(r['covered'] for r in scored)/len(scored) if scored else None,
            coverage_scope='Conditional on scored, protocol-eligible observations with successful precision-gated forecasts; not all-origin coverage',
            usable_and_covering_count=sum(r['covered'] for r in scored),usable_and_covering_over_all_intended=sum(r['covered'] for r in scored)/32,
            usable_and_covering_over_eligible_observed=(sum(r['covered'] for r in scored)/sum(f.get('scoring_eligible') is True for r in subset for f in r['forecasts']) if all(f.get('scoring_eligible') is not None for r in subset for f in r['forecasts']) and any(f.get('scoring_eligible') is True for r in subset for f in r['forecasts']) else None),
            mean_interval_score=sum(r['interval_score'] for r in scored)/len(scored) if scored else None)
    ratios=[];ablations=[]
    for origin in ORIGINS:
        for kind in ['flow','no-flow']:
            public=by_key[(origin,'public-'+kind)];reference=by_key[(origin,'reference-'+kind)]
            eligible=public['success'] and reference['success'] and public['elapsed_seconds']>0
            ratios.append(dict(origin=origin,kind=kind,paired_success=bool(eligible),reference_over_public_seconds=reference['elapsed_seconds']/public['elapsed_seconds'] if eligible else None))
        for backend in ['public','reference']:
            flow=by_key[(origin,backend+'-flow')];zero=by_key[(origin,backend+'-no-flow')]
            for g in range(4):
                a=flow['forecasts'][g];b=zero['forecasts'][g]
                usable=flow['success'] and zero['success'] and a['covered'] is not None and b['covered'] is not None and a['observed']==b['observed']
                ablations.append(dict(origin=origin,backend=backend,group=g,paired_score_available=bool(usable),flow_minus_zero_interval_score=a['interval_score']-b['interval_score'] if usable else None))
    return dict(qualified=False,plan_sha256=digest,intended_fits=32,intended_origins=8,intended_origin_group_cells=32,
        outcomes=outcomes,arms=summaries,paired_sampler_costs=ratios,paired_ablation_scores=ablations,
        interpretation='Descriptive sparse dependent rolling-window outcomes only; no coverage/alpha/trading qualification. Zero-x same-model ablation retains nuisance priors and is not a best-performance no-flow baseline.',
        failure_policy='All intended fits/cells retained. Missing terminal costs are unknown, never silently zero; ratios require paired precision success. Scoring never conditions inference or stopping.')
