from pathlib import Path
import sys,json,shutil
R=Path('C:/dev/owalnuts');S=R/'STUDIES/options_flow_v1';O=S/'artifacts/correlated-reference-study-v1';sys.path.insert(0,str(S))
from correlated_reference_study import make_plan,validate,verify,save,sha
seeds=list(range(1970000000,1970003612));audit=O/'historical-seed-inventory.json';a=json.loads(audit.read_text());assert seeds==a['candidate_seeds'];assert not set(seeds)&set(a['reserved_seeds'])
p=make_plan(seeds,S,(R/'target/python-workflow-env/Scripts/python.exe').resolve(),audit);validate(p);verify(p,require_frozen=False)
actual=[seed for c in p['cells'] for seed in c['fit_seeds']+c['init_seeds']+[c['bootstrap_seed']]];assert actual==seeds
save(O/'plan-draft.json',p)
print(json.dumps(dict(path=str(O/'plan-draft.json'),sha256=sha(O/'plan-draft.json'),audit_sha256=sha(audit),cells=len(p['cells']),streams=len(actual),frozen=p['frozen'],source_files=len(p['source']))))
