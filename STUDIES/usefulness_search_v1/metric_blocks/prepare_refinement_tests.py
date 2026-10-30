from pathlib import Path
study=Path(__file__).resolve().parent
source=(study/'test_fixed_metric_runner.py').read_text().replace("'fixed_metric_test01'","'refinement_ablation_test01'").replace("'fixed_metric_build02/SUMMARY.json'","'refinement_ablation_build01/SUMMARY.json'")
needle="result=run('combined',spec);q=";assert source.count(needle)==1
replacement='''control=run('control',spec)
    old=json.loads((local/'fixed_metric_test01/combined-OUTPUT.json').read_text())
    for a,b in zip(control['chains'],old['chains']):
        for key in ['draws','target_calls','retained_divergences','step_size','mass','seed','revision']:assert a[key]==b[key]
        assert a['levels']==2 and a['max_error']==1
    spec.update(levels=1,max_error=1000.)
    result=run('combined',spec)
    for r in result['chains']:
        assert r['levels']==1 and r['max_error']==1000 and r['work']['target_calls_reverse']==0
        assert r['work']['all_phase_calls']==r['target_calls']
    q='''
source=source.replace(needle,replacement)
dest=study/'test_refinement_ablation.py';assert not dest.exists();dest.write_text(source)
