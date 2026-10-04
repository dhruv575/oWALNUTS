"""Read-only exploratory correlated-control outcome analysis; never runs workers."""
import json,math,sys,hashlib
from pathlib import Path
import numpy as np
from scipy.stats import beta,norm

def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def interval(k,n):
    return [0. if k==0 else float(beta.ppf(.025,k,n-k+1)),1. if k==n else float(beta.ppf(.975,k+1,n-k))] if n else None

def summarize(plan,records,diagnostics):
    expected={c['id']:c for c in plan['cells']}
    if len(expected)!=28 or len(records)!=28 or {r['id'] for r in records}!=set(expected):raise ValueError('Exact28 distinct terminal cells required')
    if any(type(r['seconds']) not in (int,float) or not math.isfinite(r['seconds']) or r['seconds']<0 for r in records):raise ValueError('Invalid cost')
    groups={};truth=norm.ppf([.05,.95])
    for name,rho,shift in [('correlated_null',.9,0.),('iid_null',0.,0.),('shift_01',.9,.1),('shift_05',.9,.5)]:
        rows=[r for r in records if expected[r['id']]['phase']=='main' and expected[r['id']]['rho']==rho and expected[r['id']]['backend_b_shift']==shift]
        policy=plan['progression'][name];n=len(rows)
        if n!=policy['intended']:raise ValueError('Group denominator mismatch')
        complete=[r for r in rows if r['status']=='completed'];resolved=sum(r['result']['bank_status']=='numerically_resolved_under_declared_checks' for r in complete)
        covered=sum(r['result']['both_endpoints_cover_truth'] for r in complete);miss=sum(r['result']['bank_status']=='numerically_resolved_under_declared_checks' and not r['result']['both_endpoints_cover_truth'] for r in complete)
        passed=len(complete)==n and resolved>=policy.get('minimum_resolved',0) and resolved<=policy.get('maximum_resolved',n) and covered>=policy.get('minimum_both_covered',0) and miss<=policy.get('maximum_resolved_miss',n)
        group=dict(intended=n,completed=len(complete),failed_or_unstarted=n-len(complete),resolved=resolved,both_covered=covered,resolved_misses=miss,progression_pass=passed,seconds=sum(r['seconds'] for r in rows),resolved_fraction_of_intended=resolved/n,covered_fraction_of_intended=covered/n,evaluable_completed_only_resolved_ci95=interval(resolved,len(complete)),evaluable_completed_only_coverage_ci95=interval(covered,len(complete)),variance_scaling=[])
        if shift==0:
            for length in plan['prefixes']:
                for backend in range(2):
                    vectors=[diagnostics[r['id']]['estimates'][str(length)][backend] for r in complete]
                    if len(vectors)<2:continue
                    values=np.asarray(vectors);emp=np.cov(values,rowvar=False,ddof=1)
                    predicted=np.mean([next(v for v in diagnostics[r['id']]['covariance'] if v['n']==length)['quantile_delta_covariance'] for r in complete],axis=0)
                    group['variance_scaling'].append(dict(length=length,backend=backend,independent_replicates=len(values),empirical_covariance=emp.tolist(),mean_bias=(values.mean(axis=0)-truth).tolist(),delta_covariance=predicted.tolist(),variance_ratio=(np.diag(emp)/np.diag(predicted)).tolist()))
        groups[name]=group
    return dict(expected=28,groups=groups,all_progression_pass=all(g['progression_pass'] for g in groups.values()),sentinels=[r for r in records if expected[r['id']]['phase']=='sentinel'],total_seconds=sum(r['seconds'] for r in records),qualified=False,scope='Exploratory analytic controls, not posterior accuracy. Pointwise binomial intervals use completed evaluable cells only, condition on computational success, and have no simultaneous guarantee; null with no evaluable cells. Intended-denominator fractions are descriptive, not Bernoulli accuracy trials. Failed/unstarted cells retain the progression denominator. Variance comparisons condition on completed cells; paired prefixes and backends are not extra independent replicates. GaussianAR indicator covariance is independently derived; quantile delta covariance is an asymptotic approximation. Small replicate counts imply substantial unquantified variance-ratio uncertainty.')

def analyze(plan_path,out):
    plan=load(plan_path);sys.path.insert(0,plan['study'])
    from correlated_reference_study import read_frozen,validate_outputs
    plan=read_frozen(plan_path);out=Path(out);summary=load(out/'summary.json')
    if summary.get('integrity_error'):raise ValueError('Campaign integrity failure')
    if load(out/'expected.json')['plan_sha256']!=sha(plan_path):raise ValueError('Outcome plan mismatch')
    records=[];diagnostics={}
    byid={c['id']:c for c in plan['cells']}
    for r in summary['rows']:
        row=dict(r)
        if row['status']=='completed':
            directory=out/row['id'];validate_outputs(directory,byid[row['id']],plan)
            result=load(directory/'result.json');bank=load(directory/'bank.json');actual=norm.ppf([.05,.95])
            if not np.allclose(result['truth'],actual,rtol=0,atol=1e-14):raise ValueError('Analytic truth mismatch')
            coverage=all(bank['endpoints'][name]['lower']<=actual[i]<=bank['endpoints'][name]['upper'] for i,name in enumerate(['lo','hi']))
            if coverage!=result['both_endpoints_cover_truth']:raise ValueError('Coverage flag mismatch')
            row['result']=result;diagnostics[row['id']]=load(directory/'prefix-diagnostic.json')
        records.append(row)
    result=summarize(plan,records,diagnostics);result.update(plan_sha256=sha(plan_path),analysis_sha256=sha(__file__),campaign_outer_seconds=summary['seconds'])
    return result
if __name__=='__main__':
    result=analyze(sys.argv[1],sys.argv[2])
    with Path(sys.argv[3]).open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
