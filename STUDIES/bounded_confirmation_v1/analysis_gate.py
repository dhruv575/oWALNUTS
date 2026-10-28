"""Full-denominator admission for the frozen primary confirmation analysis."""
import math

def assess(calendar,reports):
    expected={r['index']:r for r in calendar}
    if len(expected)!=3050 or sorted(expected)!=list(range(3050)):raise ValueError('Fixed calendar required')
    observed={}
    for r in reports:
        j=r['index']
        if j not in expected or j in observed:raise ValueError('Duplicate or unexpected report')
        c=expected[j]
        if r['cap']!=c['cap'] or any(r['fixture'][k]!=c[k] for k in ['month','tick','origin_ms','label_available_ms']):raise ValueError('Report/calendar drift')
        observed[j]=r
    missing=sorted(set(expected)-set(observed));failures=[];primary_bad=[]
    for j,r in observed.items():
        primary=expected[j]['primary']
        for method in ['nuts','walnuts']:
            m=r.get('methods',{}).get(method,{})
            if not m.get('qualified'):
                failures.append(dict(index=j,method=method,primary=primary))
                if primary:primary_bad.append(j)
        if primary:
            comparisons={}
            for comparison in r.get('comparisons',[]):
                name=comparison['baseline']
                if name in comparisons:raise ValueError('Duplicate baseline')
                comparisons[name]=comparison
            for name in ['rolling_t5','ewma_t5']:
                c=comparisons.get(name,{})
                if not c.get('qualified') or not all(type(c.get(k)) in (int,float) and math.isfinite(c[k]) for k in ['model','inference','total']):primary_bad.append(j)
                elif abs(c['model']+c['inference']-c['total'])>1e-10:raise ValueError('Score identity')
    return dict(planned=3050,reported=len(observed),missing=missing,diagnostic_failures=failures,unqualified_primary_indices=sorted(set(primary_bad)),primary_analysis_admitted=not missing and not primary_bad,scope='No complete-case substitution; sensitivity failures disclosed separately; gate does not itself establish confirmation')
