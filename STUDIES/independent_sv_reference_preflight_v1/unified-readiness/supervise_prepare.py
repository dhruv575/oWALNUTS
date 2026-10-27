"""External preparation monitor; imports reviewed scoped process ownership monitor."""
import argparse,hashlib,importlib.util,json,os,sys
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--monitor',required=True);p.add_argument('--monitor-sha256',required=True);p.add_argument('--requirements',required=True);p.add_argument('--requirements-sha256',required=True);a=p.parse_args()
 monitor=Path(a.monitor)
 if hashlib.sha256(monitor.read_bytes()).hexdigest()!=a.monitor_sha256:raise RuntimeError('monitor source mismatch')
 spec=importlib.util.spec_from_file_location('frozen_preparation_monitor',monitor);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 root=Path(a.root).absolute();root.mkdir(exist_ok=False)
 result=module.execute([os.path.abspath(sys.executable),str(Path(__file__).with_name('prepare.py')),'--root',str(root/'work'),'--requirements',a.requirements,'--requirements-sha256',a.requirements_sha256],Path(__file__).parent,600,root,4*1024**3,3*1024**3,root/'preparation.log',ownership_env='OWALNUTS_PREPARATION_TOKEN')
 result['preparation_complete']=False
 try:
  evidence=json.loads((root/'work/preparation.json').read_text())
  result['preparation_complete']=result['status']=='exited' and result['exit_code']==0 and result['group_drained'] and not result.get('orphaned_children_after_leader_exit',False) and evidence['status']=='complete'
 except Exception as exc:result['evidence_error']=repr(exc)
 (root/'supervisor.json').write_text(json.dumps(result,indent=2))
 return 0 if result['preparation_complete'] else 1
if __name__=='__main__':raise SystemExit(main())
