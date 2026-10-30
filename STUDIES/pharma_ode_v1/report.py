"""Render descriptive results, including failures and unqualified references."""
import json,sys,statistics
from pathlib import Path
root=Path(sys.argv[1]);s=json.loads((root/'SUMMARY.json').read_text());rows=json.loads((root/'ROWS.json').read_text());initial=json.loads((root/'INITIAL-ROWS.json').read_text())
lines=['# Practical pharmacokinetic ODE pilot','',
       'Observed-data scope: Theoph subjects 1–3 selected by numeric ID; eight post-baseline training observations and two heldout observations per subject. The public Stan fixture is a computational benchmark with unverified clinical provenance.','',
       'Matched-accuracy validation is the primary comparison. An unqualified reference blocks a speed claim; failed seeds remain in the denominator. Speed ratios use only seed pairs that both qualify, so censored comparisons must not be generalized to all attempts.','',
       '| Target | Qualified reference | WALNUTS accuracy /8 | NUTS accuracy /8 | WALNUTS diagnostics /8 | NUTS diagnostics /8 | Paired kernel speedup | Sampler gate |',
       '|---|---|---:|---:|---:|---:|---|---|']
for case,r in s['targets'].items():
    w=r['engines']['walnuts'];n=r['engines']['nuts'];sp=r['kernel_speedup']
    speed='Unavailable' if not sp['pairs'] else f"{sp['geomean']:.2f}x [{sp['bootstrap95'][0]:.2f}, {sp['bootstrap95'][1]:.2f}], {sp['pairs']} pairs"
    lines.append(f"| {case} | {r['reference_qualified']} | {w['accuracy_pass']} | {n['accuracy_pass']} | {w['diagnostic_pass']} | {n['diagnostic_pass']} | {speed} | {r['sampler_gate']} |")
lines+=['','## Reference qualification','','| Target | R-hat max | ESS min | Divergences | Depth hits | Separate means agree | Numerical audit | Qualified |','|---|---:|---:|---:|---:|---|---|---|']
for case,r in s['references'].items():
    d=r.get('summary',{});lines.append(f"| {case} | {d.get('rhat_max')} | {d.get('ess_min')} | {d.get('divergences')} | {d.get('depth_hits')} | {r.get('separate_mean_agreement')} | {r.get('numerical_audit',{}).get('pass')} | {r['qualified']} |")
lines+=['','## Cheap approximation and model checks','','Laplace accuracy is evaluated against the same qualified reference. Its diagnostic pass alone does not establish approximation accuracy. Forecast error ratio >1 exceeds a predeclared forecast bound (including reference Monte Carlo uncertainty).','','| Target | Laplace completed | Full accuracy | Forecast error ratio | MAP + Gaussian draws (s) |','|---|---|---|---:|---:|']
for case,r in s['laplace'].items():lines.append(f"| {case} | {r['status']} | {r['accuracy']['pass_all']} | {r['accuracy'].get('forecast_error_ratio')} | {r['seconds']} |")
lines+=['','The linear model is a different posterior, not a sampler competitor. Heldout predictive log densities below are descriptive only: six observations cannot establish clinical benefit, and unqualified-reference scores must not be treated as converged estimates. Positive nonlinear-minus-linear values favor the nonlinear model.','','| Subject | Nonlinear reference qualified | Linear reference qualified | Nonlinear log score sum | Linear log score sum | Difference |','|---|---|---|---:|---:|---:|']
for i in range(1,4):
    a=s['references'][f'theoph_{i}'];b=s['references'][f'linear_{i}'];x=a.get('heldout');y=b.get('heldout')
    xx=sum(x['log_predictive_density']) if x else None;yy=sum(y['log_predictive_density']) if y else None
    lines.append(f"| {i} | {a['qualified']} | {b['qualified']} | {xx} | {yy} | {xx-yy if xx is not None and yy is not None else None} |")
lines+=['','## Costs and completion','','Unconditional median kernel times below include all successfully measured runs, even those that failed accuracy. They are workload descriptions, not matched-accuracy speedups. Cold totals include shared MAP preparation, Python startup, sampling, forecasting, diagnostics and serialization. Kernel times include warmup and exclude forecast evaluation.','','| Target | Engine | Completed /8 | Median kernel (s) | Median total (s) | Median target calls |','|---|---|---:|---:|---:|---:|']
for case in s['targets']:
    for e in ('walnuts','nuts'):
        rr=[r for r in rows if r['case']==case and r['config'].startswith(e+'_') and r['status']=='ok']
        med=lambda k:round(statistics.median(r[k] for r in rr),3) if rr else None
        lines.append(f"| {case} | {e} | {len(rr)} | {med('seconds')} | {med('total_seconds')} | {med('target_calls')} |")
lines+=['','## Limitations and provenance','',
 'The original direct-concentration forecast implementation produced nonfinite tail forecasts. It is retained separately. The recorded amendment integrates log concentration after the first positive observation, uses forecast tolerance 1e-10 and leaves the fitted likelihood and gradients unchanged. All calibration/reference/Laplace jobs were rerun; no exposed tuning result was reused. A separate aborted path-routing launch is also retained.',
 '', 'The primary training solver still uses tolerance 1e-8. Retained-reference auditing compares tighter BDF and RK45 gradients and predictions; numeric qualification failures block conclusions. Shared multistart local optimization cannot prove all modes were discovered. References use two parameterizations of NUTS, not independent exact truth. Priors are working assumptions, baseline measurement uncertainty is omitted, and subjects are fit individually without population pooling.',
 '', 'One calibration seed per configuration is a limited exploratory tuning budget. Speed bootstrap intervals are descriptive, conditional on matched passing seeds, and do not adjust for target exploration. Positive sampler gates alone do not satisfy the practical-success rule: cheap forecasts/model alternatives must also be inadequate. No clinical decision model, commercial demand test, profitability claim, deployment or trading is established.',
 '', 'See PROTOCOL.md, forecast_fix/AMENDMENT.md, SELECTION.json, REFERENCES.json, SUMMARY.json, compressed all-attempt rows, source-freeze manifests, resource receipts and full evidence archive verification.']
(root/'REPORT.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines[:12]))
