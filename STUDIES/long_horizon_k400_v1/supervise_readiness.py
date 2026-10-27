"""One 600-second literal-only readiness envelope, no production admission."""
import argparse,json,sys
from pathlib import Path
from runtime import admit,sha
from linear_runner import exclusive
from resource_monitor import execute
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('output');a=p.parse_args();admit(a.manifest,readiness=True);identity=sha(a.manifest);out=Path(a.output).absolute();out.mkdir(exist_ok=False);here=Path(__file__).resolve().parent
    result=execute([sys.executable,str(here/'readiness.py'),str(Path(a.manifest).absolute()),str(out/'work')],here,600,out,4*1024**3,1024**3,out/'readiness.log',ownership_env='OWALNUTS_READINESS_TOKEN',output_scan_interval=2)
    evidence=json.loads((out/'work'/'READINESS.json').read_text()) if (out/'work'/'READINESS.json').exists() else {}
    result['manifest_unchanged']=sha(a.manifest)==identity;result['readiness_complete']=evidence.get('status')=='complete' and result.get('exit_code')==0 and result.get('status')=='exited' and result.get('group_drained') and not result.get('orphaned_children_after_leader_exit') and result['manifest_unchanged'];exclusive(out/'SUPERVISION.json',result)
    raise SystemExit(0 if result['readiness_complete'] else 1)
