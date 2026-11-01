"""Verify outer deadline cleanup reaches a child with a distinct inner token."""
import json
import sys
import tempfile
from pathlib import Path
from resource_monitor import execute

with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary)
    helper=root/'inner.py'
    helper.write_text('import sys\nfrom pathlib import Path\nsys.path.insert(0,'+repr(str(Path(__file__).resolve().parent))+')\nfrom resource_monitor import execute\np=Path(__file__).resolve().parent\nexecute([sys.executable,"-c","import time;time.sleep(10)"],str(p),5,p,1024**3,1024**2,p/"inner.log",ownership_env="OWALNUTS_PHYSICS_JOB_TOKEN")\n')
    s=execute([sys.executable,str(helper)],str(root),.8,root,1024**3,1024**2,root/'outer.log')
    assert s['reason']=='deadline' and s['group_drained'] and not s['remaining_owned_pids']
    assert (root/'inner.log').exists(), 'Inner monitor did not start before the test deadline'
    result=dict(passed=True,scope='Nested worker killed by outer deadline; distinct inner ownership key preserves outer marker',supervision=s)
    print(json.dumps(result),flush=True)
