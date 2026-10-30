from pathlib import Path
study=Path(__file__).resolve().parent
source=(study/'run_refinement_ablation.py').read_text().replace("'refinement_ablation01'","'refinement_ablation02'").replace('REFINEMENT-ABLATION-PROTOCOL.md','REFINEMENT-ABLATION-CORRECTION.md')
needle='[(1,1.),(1,1000.),(2,1000.)]';assert source.count(needle)==1;source=source.replace(needle,'[(8,1.),(8,1000.)]')
needle="worker=root/'worker.py';worker.write_text(source)";assert source.count(needle)==1
insert='''source += "\\nif spec['levels']==8 and spec['max_error']==1:\\n    old=json.loads((LOCAL/'matched_geometry01'/model/'OUTPUT.json').read_text())\\n    assert result['target_calls']==old['target_calls']\\n    for a,b in zip(result['chains'],old['chains']):\\n        for key in ['draws','target_calls','retained_divergences','step_size','mass','seed','revision']:assert a[key]==b[key]\\n"
'''
source=source.replace(needle,insert+needle)
path=study/'run_refinement_correction.py';assert not path.exists();path.write_text(source)
