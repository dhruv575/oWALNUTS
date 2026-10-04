from pathlib import Path
import json,hashlib,sys
R=Path('C:/dev/owalnuts');S=R/'STUDIES/options_flow_v1';O=S/'artifacts/persistent-comparison-v1';sys.path.insert(0,str(S))
from persistent_comparison_plan import reviewed_seeds
from asof_market_fixture import attach_archived_anchors,prepare
from continuation_comparison import save,sha
au=json.loads((O/'seed-audit-compact.json').read_text());reviewed_seeds(au['sampler_rows'],O/'seed-audit-compact.json',au['initialization_seeds'])
for p,h in au['supplemental_evidence'].items():assert sha(p)==h
panelpath=S/'artifacts/deribit-features-v1/panel.json';archive=S/'artifacts/deribit-access-panel-v3';protocolpath=S/'DERIBIT_HISTORY_ACCESS_PROTOCOL_V3.json'
panel=json.loads(panelpath.read_text());protocol=json.loads(protocolpath.read_text());anchored=attach_archived_anchors(panel,archive);save(O/'anchored-panel.json',anchored)
rows=[]
for origin,seed in zip([168,216],au['initialization_seeds']):
 f=prepare(anchored,protocol,origin_index=origin,window=128,init_seed=seed);path=O/f'fixture-{origin}.json';save(path,f)
 rows.append(dict(origin=origin,path=str(path),sha256=sha(path),initialization_seed=seed,observed_count=sum(map(sum,f['data']['observation_mask'])),forecast_cells=f['precision_family'],canonical_dimension=len(f['data']['initial_positions'][0])))
assert rows[0]['observed_count']!=rows[1]['observed_count']
save(O/'fixture-preparation.json',dict(status='prepared_not_frozen',fixtures=rows,expected_processes=4,expected_fits=12,sequence=[168,216,168],seed_audit_sha256=sha(O/'seed-audit-compact.json'),original_panel_sha256=sha(panelpath),anchored_panel_sha256=sha(O/'anchored-panel.json'),protocol_sha256=sha(protocolpath),archive_trade_bindings=panel['acquisition_binding']['trade_files'],qualified=False))
print(json.dumps(rows))
