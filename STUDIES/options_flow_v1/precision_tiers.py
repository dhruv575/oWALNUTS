"""Run one arm to a declared interval precision, charging every attempted tier.

This is an exploratory execution mechanism. A passing precision screen is not
calibration, predictive usefulness, or scientific qualification.
"""
import time
CONTROLLER_STARTED = time.perf_counter()
import argparse
import json
import math
from pathlib import Path


def precision_screen(report, relative_mcse=.02, names=None, require_forecast=True):
    if not 0 < relative_mcse < 1:
        raise ValueError('relative_mcse must be in (0,1)')
    reasons=[];ratios={}
    if report.get('status')!='completed' or not report.get('healthy',False):
        reasons.append('fit is missing, failed or unhealthy')
    evaluation=report.get('evaluation',{})
    functionals=evaluation.get('functionals',{})
    selected=list(functionals) if names is None else list(names)
    if not selected:reasons.append('no selected parameter functionals')
    def check(key,lower,upper,mcse):
        try:
            width=float(upper)-float(lower)
            errors=[float(v) for v in mcse]
            if len(errors)!=2 or width<=0 or not math.isfinite(width) or any(v<0 or not math.isfinite(v) for v in errors):
                raise ValueError()
            ratio=max(errors)/width;ratios[key]=ratio
            if ratio>relative_mcse:reasons.append(f'{key}: endpoint MCSE exceeds threshold')
        except (TypeError,ValueError):reasons.append(f'{key}: invalid interval precision')
    for name in selected:
        entry=functionals.get(name,{})
        interval=entry.get('interval_90',[])
        if len(interval)!=2:
            reasons.append(f'{name}: missing interval');continue
        check(name,*interval,entry.get('endpoint_mcse',[]))
    rows=evaluation.get('forecast',{}).get('rows',[])
    if require_forecast and not rows:reasons.append('missing predictive intervals')
    for i,row in enumerate(rows):
        check(f'forecast_{i}',row.get('lower'),row.get('upper'),row.get('endpoint_mcse',[]))
    return {'pass':not reasons,'reasons':reasons,'max_endpoint_mcse_over_width':max(ratios.values(),default=None),
            'ratios':ratios,'threshold':relative_mcse,'parameter_functionals':selected,
            'forecast_rows':len(rows),'qualified':False}


def run_tiers(fixture,out,arm,executable,seed,warmup,tiers,chains,timeout,model='flow',
              relative_mcse=.02,names=None,require_attestation=False,executor=None,cpus=None,reference_script=None):
    if not tiers or any(v<4 for v in tiers) or any(b<=a for a,b in zip(tiers,tiers[1:])):
        raise ValueError('Retained tiers must be strictly increasing integers >=4')
    if model not in ('flow','local_level'):raise ValueError('Unknown model')
    out=Path(out)
    # Refuse all existing directories so no historical failed attempt is replaced.
    out.mkdir(parents=True,exist_ok=False)
    if executor is None:
        if model=='flow':
            from run import execute as executor
        else:
            from run_local_level import execute as executor
    if require_attestation and not arm.startswith('numpyro'):
        from build import verify_attestation
        verify_attestation(executable=executable)
    plan={'model':model,'fixture':str(Path(fixture).resolve()),'arm':arm,'seed':seed,
          'warmup':warmup,'tiers':list(tiers),'chains':chains,'timeout_per_tier':timeout,
          'relative_mcse':relative_mcse,'names':names,'cpus':cpus,'reference_script':str(reference_script) if reference_script else None,'phase':'exploratory',
          'restart_policy':'Independent full run per tier, same declared seed; all costs charged'}
    (out/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    attempts=[];start=time.perf_counter()
    for draws in tiers:
        path=out/f'draws-{draws}'
        call_start=time.perf_counter()
        options={}
        if require_attestation:options['require_attestation']=True
        if cpus is not None:options['cpus']=cpus
        if reference_script is not None:
            if model!='flow':raise ValueError('Reference override is currently supported only for the flow model')
            options['reference_script']=reference_script
        try:
            report=executor(fixture,path,arm,executable,seed,warmup,draws,chains,timeout,**options)
        except Exception as exc:
            # Preserve controller-level failures too; never overwrite an
            # existing worker report, including a partial/running report.
            report={'status':'failed','healthy':False,'arm':arm,'seed':seed,
                    'error':f'{type(exc).__name__}: {exc}',
                    'failed_elapsed_seconds':time.perf_counter()-call_start,
                    'phase':'exploratory','qualified':False,'controller_exception':True}
            path.mkdir(parents=True,exist_ok=True)
            with (path/'controller-exception.json').open('x',encoding='utf-8') as handle:
                json.dump(report,handle,indent=2,allow_nan=False)
        call_seconds=time.perf_counter()-call_start
        screen=precision_screen(report,relative_mcse,names)
        attempts.append({'draws':draws,'report':str((path/f'{arm}-report.json').resolve()),
                         'call_seconds_including_reporting':call_seconds,'screen':screen,
                         'status':report.get('status'),
                         'controller_exception':report.get('controller_exception',False)})
        if screen['pass'] or report.get('status')!='completed':break
    passed=bool(attempts and attempts[-1]['screen']['pass'])
    result={'plan':plan,'attempts':attempts,'precision_pass':passed,'qualified':False,
            'attempted_draws_per_chain':sum(a['draws'] for a in attempts),
            'selected_draws_per_chain':attempts[-1]['draws'] if passed else None,
            'cumulative_fit_and_report_seconds':sum(a['call_seconds_including_reporting'] for a in attempts),
            'tier_controller_seconds':time.perf_counter()-start,
            'timing_scope':'All full-restart fits, diagnostics, prediction and per-cell report writes. CLI total separately includes controller imports/setup; package install/build reported separately.'}
    (out/'precision-result.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fixture',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--arm',required=True);p.add_argument('--exe',type=Path)
    p.add_argument('--model',choices=['flow','local_level'],default='flow')
    p.add_argument('--seed',type=int,required=True);p.add_argument('--warmup',type=int,default=1000)
    p.add_argument('--tiers',type=int,nargs='+',default=[1000,2000,4000,8000])
    p.add_argument('--chains',type=int,default=4);p.add_argument('--timeout',type=float,default=1800)
    p.add_argument('--relative-mcse',type=float,default=.02);p.add_argument('--names',nargs='+')
    from hardware_control import parse_cpus
    p.add_argument('--cpus',type=parse_cpus);p.add_argument('--reference-script',type=Path)
    p.add_argument('--require-attestation',action='store_true');a=p.parse_args()
    if not a.arm.startswith('numpyro') and not a.exe:p.error('--exe required for Rust arms')
    result=run_tiers(a.fixture,a.out,a.arm,a.exe,a.seed,a.warmup,a.tiers,a.chains,a.timeout,
                     a.model,a.relative_mcse,a.names,a.require_attestation,cpus=a.cpus,reference_script=a.reference_script)
    # Includes the written precision-result, excludes only this tiny clock sidecar.
    clock={'controller_invocation_seconds':time.perf_counter()-CONTROLLER_STARTED,
           'precision_pass':result['precision_pass'],'qualified':False}
    (a.out/'invocation-timing.json').write_text(json.dumps(clock,indent=2),encoding='utf-8')
    print(json.dumps(clock))
    return 0 if result['precision_pass'] else 2


if __name__=='__main__':raise SystemExit(main())
