"""Explicit preparation only after sourcefinal. NEVER launches fitting/analysis."""
from pathlib import Path
import sys,json,argparse
R=Path('C:/dev/owalnuts').resolve();S=R/'STUDIES/options_flow_v1';O=S/'artifacts/posterior-reference-bank-v1';sys.path.insert(0,str(S))
p=argparse.ArgumentParser();p.add_argument('--source-final',required=True);p.add_argument('--freeze-fitting',action='store_true');args=p.parse_args()
import subprocess
if subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()!=args.source_final:raise ValueError('Explicit sourcefinal HEAD differs')
from posterior_resource.bank_controller import prepare,freeze
from posterior_resource.bank_analysis_preparation import prepare_intent
A=O/'final-preparation';audit=json.loads((A/'fit-seed-audit.json').read_text());rows=[dict(backend=['public','reference','reference','public'][i%4],init_seed=199010001+i,seed=199110001+i,predictive_seed=199240001+i) for i in range(64)]
assert {r[k] for r in rows for k in ['init_seed','seed','predictive_seed']}==set(audit['seeds'])
streams=A/'streams.json'
with streams.open('x') as f:json.dump(rows,f,indent=2)
plan=prepare(O/'run',S,S/'artifacts/python-flow-long-v1/fixture.json',(R/'target/python-workflow-env/Scripts/python.exe').resolve(),R/'target/python-flow-worktree/integrations/python/python',S/'artifacts/continuation-release-attested-v1.json',streams,A/'fit-seed-audit.json',S/'artifacts/posterior-resource-pilot-v1/plan.json')
if args.freeze_fitting:
 freeze(O/'run');prepare_intent(O/'run/plan.json',A/'bootstrap-seed-audit.json',O/'analysis',199370001)
print(json.dumps(dict(fits=64,fitting_frozen=args.freeze_fitting,analysis_frozen=False,launched=False)))
