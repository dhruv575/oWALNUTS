from pathlib import Path
import sys,json
R=Path('C:/dev/owalnuts');S=R/'STUDIES/options_flow_v1';O=S/'artifacts/persistent-comparison-v1';sys.path.insert(0,str(S))
from persistent_comparison_plan import prepare,validate_plan
python=(R/'target/python-workflow-env/Scripts/python.exe').resolve();package=R/'target/python-flow-worktree/integrations/python/python'
p=prepare(O/'run',python,package,S/'artifacts/continuation-release-attested-v1.json',S/'artifacts/deribit-features-v1/panel.json',O/'anchored-panel.json',S/'DERIBIT_HISTORY_ACCESS_PROTOCOL_V3.json',[O/'fixture-168.json',O/'fixture-216.json'],[[106510001,106510002,106510003],[106510004,106510005,106510006]],O/'seed-audit-compact-v2.json',S/'artifacts/deribit-access-panel-v3')
validate_plan(p,O/'run');print(json.dumps(dict(processes=p['expected_processes'],fits=p['expected_fits'],frozen=p['frozen'],bound_files=len(p['bound_files']))))
