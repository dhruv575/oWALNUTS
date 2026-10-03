"""Pure audit of full-restart time-to-precision results, including all attempts.

bundle={'result': precision_result, 'reports': {absolute_report_path: report},
        'invocation': invocation_timing_json}. No disk reads or runs are implied.
expected cells follow qualification.py, with settings excluding retained draws;
draw count is bound separately to each recorded attempted tier. Exploratory
bundles may be comparable but are never scientific qualification evidence.
"""
from __future__ import annotations

import copy
import math

from qualification import cell_gate, finite
from precision_tiers import precision_screen


PLAN_MATCH = ('model','seed','warmup','chains','timeout_per_tier',
              'relative_mcse','names','cpus','restart_policy')
RESTART_POLICY = 'Independent full run per tier, same declared seed; all costs charged'
SCOPES = ('cold_controller_invocation','cold_fit_and_report')


def audit_tiers(bundle, expected, model, timing_scope='cold_controller_invocation'):
    if timing_scope not in SCOPES:
        raise ValueError('This full-restart adapter cannot substantiate reused/warm-process timing')
    result = bundle.get('result', {}); plan = result.get('plan', {})
    reasons=[]; attempts=result.get('attempts',[]); rows=[]
    if plan.get('restart_policy') != RESTART_POLICY: reasons.append('unsupported or missing restart policy')
    if plan.get('relative_mcse') != .02: reasons.append('requires declared .02 endpoint MCSE/width threshold')
    for key in ('arm','seed'):
        if plan.get(key) != expected.get(key): reasons.append('plan identity mismatch: '+key)
    for key in ('warmup','chains'):
        if plan.get(key) != expected['settings'].get(key): reasons.append('plan settings mismatch: '+key)
    required = sorted(p['key'] for p in model['primary'] if p['kind']=='functional')
    selected = plan.get('names')
    if selected is not None and (len(selected)!=len(set(selected)) or not set(required).issubset(selected)):
        reasons.append('declared parameter functionals omit frozen primary or contain duplicates')
    tiers=plan.get('tiers',[])
    if not tiers or any(not isinstance(t,int) or isinstance(t,bool) or t<4 for t in tiers) or any(b<=a for a,b in zip(tiers,tiers[1:])):
        reasons.append('invalid tier schedule')
    if not attempts or [a.get('draws') for a in attempts] != tiers[:len(attempts)]:
        reasons.append('missing/reordered/skipped attempted tier')
    if len(attempts)>len(tiers): reasons.append('more attempts than planned tiers')
    total=0.; draws=0; final_report=None
    for index, attempt in enumerate(attempts):
        cost=attempt.get('call_seconds_including_reporting')
        if not finite(cost) or cost<=0:
            reasons.append(f'attempt {index}: missing positive charged elapsed cost')
        else: total+=cost
        draws+=attempt.get('draws',0) if isinstance(attempt.get('draws'),int) else 0
        report=bundle.get('reports',{}).get(attempt.get('report'))
        if report is None:
            reasons.append(f'attempt {index}: missing report');continue
        final_report=report
        expected_attempt=copy.deepcopy(expected)
        expected_attempt['settings']=dict(expected['settings'],draws=attempt['draws'])
        gate=cell_gate(report,expected_attempt,model,None,require_qualification=False)
        # All reported intervals are checked. Frozen primary selector metadata
        # prevents a report replacing next observed uncertainty by latent width.
        screen=precision_screen(report,.02,selected)
        passes=gate['pass'] and screen['pass']
        if attempt.get('status')!=report.get('status'):
            reasons.append(f'attempt {index}: status differs from report')
        # precision_tiers stops on its screen even if the stricter audit finds
        # additional provenance/diagnostic failures. No later attempt can hide it.
        if index<len(attempts)-1 and (screen['pass'] or report.get('status')!='completed'):
            reasons.append(f'attempt {index}: restarted after terminal/passing attempt')
        if report.get('status')=='completed':
            measured=report.get('end_to_end_seconds')
        else:
            measured=report.get('failed_elapsed_seconds',report.get('process_seconds'))
        if not finite(measured) or measured<=0 or not finite(cost) or cost+1e-6<measured:
            reasons.append(f'attempt {index}: elapsed cost missing or undercounted')
        # Identity/source failures on intermediate tiers are always fatal. Poor
        # convergence/precision may legitimately trigger a fully charged restart.
        for key in ('arm','seed','fixture_sha256','source_sha256','settings'):
            if report.get(key)!=expected_attempt.get(key):
                reasons.append(f'attempt {index}: identity mismatch {key}')
        rows.append({'draws':attempt['draws'],'pass':passes,'gate':gate,'screen':screen})
    if not rows or len(rows)!=len(attempts) or not rows[-1]['pass']:
        reasons.append('no audited healthy final precision pass')
    if result.get('precision_pass') is not True: reasons.append('controller did not pass')
    if attempts and result.get('selected_draws_per_chain')!=attempts[-1].get('draws'):
        reasons.append('selected retained count mismatch')
    if result.get('attempted_draws_per_chain')!=draws: reasons.append('total attempted retained count mismatch')
    stored=result.get('cumulative_fit_and_report_seconds')
    if not finite(stored) or not math.isclose(stored,total,rel_tol=1e-10,abs_tol=1e-6):
        reasons.append('cumulative attempt costs do not reconcile')
    controller=result.get('tier_controller_seconds')
    if not finite(controller) or controller+1e-6<total: reasons.append('controller elapsed undercounts attempts')
    clock=bundle.get('invocation',{}).get('controller_invocation_seconds')
    if timing_scope=='cold_controller_invocation':
        if not finite(clock) or not finite(controller) or clock+1e-6<controller:
            reasons.append('missing/undercounted controller invocation clock')
        elapsed=clock
    else: elapsed=stored
    if final_report is not None:
        effective_names=sorted(final_report.get('evaluation',{}).get('functionals',{})) if selected is None else sorted(selected)
        forecast_keys=[(r.get('horizon'),r.get('group')) for r in final_report.get('evaluation',{}).get('forecast',{}).get('rows',[])]
        if len(forecast_keys)!=len(set(forecast_keys)): reasons.append('duplicate forecast identities')
    else: effective_names=[];forecast_keys=[]
    return {'pass':not reasons,'reasons':reasons,'attempts':rows,'elapsed_seconds':elapsed,
            'timing_scope':timing_scope,'effective_names':effective_names,
            'forecast_keys':sorted(forecast_keys,key=repr),'plan':plan,
            'qualification_eligible':bool(not reasons and expected.get('protocol_sha256') and all(
                         bundle['reports'][a['report']].get('phase')=='qualification' and
                         bundle['reports'][a['report']].get('protocol_sha256')==expected['protocol_sha256']
                         for a in attempts)),'qualified':False}


def compare_precision(candidate,reference,candidate_expected,reference_expected,model,
                      timing_scope='cold_controller_invocation'):
    a=audit_tiers(candidate,candidate_expected,model,timing_scope)
    b=audit_tiers(reference,reference_expected,model,timing_scope)
    mismatch=[key for key in PLAN_MATCH if a['plan'].get(key)!=b['plan'].get(key)]
    tiers_a=a['plan'].get('tiers',[]);tiers_b=b['plan'].get('tiers',[])
    shared=[]
    for left,right in zip(tiers_a,tiers_b):
        if left!=right:break
        shared.append(left)
    selected_a=candidate.get('result',{}).get('selected_draws_per_chain')
    selected_b=reference.get('result',{}).get('selected_draws_per_chain')
    if selected_a not in shared or selected_b not in shared:
        mismatch.append('realized first-pass tier schedules differ')
    for key in ('fixture_sha256','dimension'):
        if candidate_expected.get(key)!=reference_expected.get(key):mismatch.append(key)
    # Retained draws may differ; all other run settings must match.
    settings_a={k:v for k,v in candidate_expected['settings'].items() if k!='draws'}
    settings_b={k:v for k,v in reference_expected['settings'].items() if k!='draws'}
    if settings_a!=settings_b:mismatch.append('settings other than retained count')
    if a['effective_names']!=b['effective_names']:mismatch.append('effective parameter functionals')
    if a['forecast_keys']!=b['forecast_keys']:mismatch.append('forecast horizons/groups')
    sources_a=candidate_expected.get('source_sha256',{})
    sources_b=reference_expected.get('source_sha256',{})
    shared_source_differences=sorted(k for k in sources_a.keys() & sources_b.keys()
                                     if sources_a[k]!=sources_b[k])
    if shared_source_differences:mismatch.append('shared source revisions differ')
    comparable=a['pass'] and b['pass'] and not mismatch
    return {'comparable':comparable,'mismatches':mismatch,'candidate':a,'reference':b,
            'time_to_precision_speedup':b['elapsed_seconds']/a['elapsed_seconds'] if comparable else None,
            'tier_schedule_comparison':{'candidate':tiers_a,'reference':tiers_b,'common_prefix':shared,
                 'unused_cap_difference':tiers_a!=tiers_b,
                 'note':'Different unused caps are allowed only when both first passes lie inside the identical shared prefix.'},
            'source_comparison':{'shared_differences':shared_source_differences,
                                 'candidate_only':sorted(sources_a.keys()-sources_b.keys()),
                                 'reference_only':sorted(sources_b.keys()-sources_a.keys())},
            'timing_scope':timing_scope,'qualified':False,
            'interpretation':'Diagnostic equal-precision comparison only. Requires fresh frozen replication, uncertainty analysis, calibration and market evidence.'}
