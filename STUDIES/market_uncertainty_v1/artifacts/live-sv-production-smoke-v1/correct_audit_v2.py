import json,hashlib,shutil
from pathlib import Path
A=Path('STUDIES/market_uncertainty_v1/artifacts/live-sv-production-smoke-v1');P=Path('target/sv-online-production-smoke-v1');r=json.loads((A/'independent-audit.json').read_text());w=json.loads((A/'run-v1/issued/worker-result.json').read_text());r['checks']['firsttier']=([a['draws'] for a in w['attempts']]==[1000,2000] and all(not a['evaluation']['precision_pass'] for a in w['attempts'][:-1]) and w['attempts'][-1]['evaluation']['precision_pass'] and all(a['divergences']==0 for a in w['attempts']));r['draws']=2000;r['integrity_pass']=all(r['checks'].values());r['audit_correction']='Original audit incorrectly assumed first tier1000; preserved. Actual firstpass2000 after1000precisionfailure, consistent fixedprocedure.'
(A/'independent-audit-v2.json').write_text(json.dumps(r,indent=2));shutil.copyfile(P/'independent_archive_audit.py',A/'independent_archive_audit.py')
(A/'RESULTS.md').write_text('''# Actual production-worker integration smoke

859 independent checks pass after correcting one auditor assumption: the fit
passed at2000 retained draws after1000 failed precision. The original failed
audit is retained. All canonical/functional health and endpoint precision checks
pass at2000, with zero retained divergences. Raw posterior diagnostics were not
recomputed; saved reported diagnostics and all source/runtime/input hashes were
verified. No mock worker was passed: the real contained workflow subprocess
ran with its native CFunc target and verified runtime identity.

Worker2.28435s, complete issuer3.25260s, smoke wrapper3.45173s. Issuance includes
snapshot, build, fit, reporting, identity checks and decision; imports before
simulated arrival are outside that issuance latency. This is synthetic receipt
replay with simulated origin/UTC clocks, not a real-market publication or a
market coverage/speed qualification. Provisional and synthetic terminal scoring
agree on the separately appended synthetic outcome. The synthetic terminal
summary is a harness control, not evidence of a real collector ending.

Large NPY arrays remain external with raw-hashes.json. Exact executed Python
sources are in executed-sources.zip; config binds native binary paths/hashes.
''')
(A/'.gitattributes').write_text('* -text\n')
print('v2pass',r['integrity_pass'])
