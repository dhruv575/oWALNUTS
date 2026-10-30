import hashlib,json
from pathlib import Path
study=Path(__file__).resolve().parent
worker=(study/'native_prefix_worker.py').read_text();needle='mass_matrix_gamma=1e-5)';assert worker.count(needle)==1
worker=worker.replace(needle,'mass_matrix_gamma=1e-5,step_size_jitter=0.0)')
runner=(study/'run_native_prefix.py').read_text().replace("'native_prefix01'","'native_prefix02'").replace("'native_prefix_worker.py'","'native_prefix_nojitter_worker.py'")
for name,source in [('native_prefix_nojitter_worker.py',worker),('run_native_prefix_nojitter.py',runner)]:
    p=study/name;assert not p.exists();p.write_text(source)
paths=[study/n for n in ['native_prefix_worker.py','native_prefix_nojitter_worker.py','run_native_prefix.py','run_native_prefix_nojitter.py']]
(study/'local_recovery/NATIVE-PREFIX-NOJITTER-PROVENANCE.json').write_text(json.dumps(dict(only_sampler_change='step_size_jitter=0.0; pinned settings maps this to jitter=None',inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}),indent=2)+'\n')
