from pathlib import Path
study=Path(__file__).resolve().parent;source=(study/'analyze_refinement_ablation.py').read_text()
old="study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'refinement_ablation01';s=json.loads((root/'SUMMARY.json').read_text());assert len(s['rows'])==15 and s['unchanged']\nfor p,h in s['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h"
new="""study=Path(__file__).resolve().parent;local=study/'local_recovery';entries=[]
for name,count in [('refinement_ablation01',15),('refinement_ablation02',10)]:
    root=local/name;s=json.loads((root/'SUMMARY.json').read_text());assert len(s['rows'])==count and s['unchanged']
    for p,h in s['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
    entries.extend((root,r) for r in s['rows'])
for root,r in entries:
    if r['levels']==8 and r['max_error']==1:assert r['completed'], 'Baseline parity must pass before interpretation'
"""
assert source.count(old)==1;source=source.replace(old,new).replace("for entry in s['rows']:","for root,entry in entries:")
source=source.replace('(m,2,1000.)','(m,8,1000.)').replace('outputs[m,2,1000.]','outputs[m,8,1000.]')
source=source.replace('REFINEMENT-ABLATION-ANALYSIS.json','REFINEMENT-CORRECTED-ANALYSIS.json').replace('REFINEMENT-ABLATION-REPORT.md','REFINEMENT-CORRECTED-REPORT.md')
source=source.replace("'Exposed one-seed factorial, not independent validation or standard-NUTS equivalence.'","'Corrected one-versus-eight-level exposed factorial; two-level rows are auxiliary. Not independent validation or standard-NUTS equivalence.'")
dest=study/'analyze_refinement_correction.py';assert not dest.exists();dest.write_text(source)
