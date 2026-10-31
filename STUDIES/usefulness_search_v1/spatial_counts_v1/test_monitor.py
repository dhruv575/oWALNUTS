"""Exercise successful drain, deadline and the added disk admission guard."""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from resource_monitor import execute

checks = {}
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    for name, script, cap in [('success','print(42)',5),('deadline','import time;time.sleep(10)',.3)]:
        out = root/name;out.mkdir()
        s = execute([sys.executable,'-c',script],str(out),cap,out,256*1024**2,1024**2,out/'log')
        assert s['group_drained'] and not s['remaining_owned_pids']
        if name=='success':assert s['status']=='exited' and s['exit_code']==0
        else:assert s['reason']=='deadline'
        checks[name]=True
    out=root/'disk';out.mkdir()
    with patch('resource_monitor.shutil.disk_usage') as usage:
        usage.return_value.free=1024
        s=execute([sys.executable,'-c','import time;time.sleep(10)'],str(out),5,out,256*1024**2,1024**2,out/'log')
    assert s['reason']=='disk_floor' and s['group_drained'];checks['disk_floor']=True
print(json.dumps(dict(passed=True,checks=checks)),flush=True)
