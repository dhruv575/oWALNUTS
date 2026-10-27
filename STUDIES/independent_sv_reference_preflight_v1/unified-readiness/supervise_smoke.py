"""Whole literal-smoke 600s envelope, including runtime admission and child stages."""
import argparse,hashlib,importlib.util,json,os,sys
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--bundle',required=True);p.add_argument('--preparation',required=True);p.add_argument('--root',required=True);a=p.parse_args()
 bundle=Path(a.bundle).absolute();manifest=json.loads((bundle/'BUNDLE-MANIFEST.json').read_text())
 if not all(hashlib.sha256((bundle/k).read_bytes()).hexdigest()==v for k,v in manifest.items()):raise RuntimeError('bundle mismatch')
 monitor=bundle/'STUDIES/prior_predictive_validation_v1/resource_monitor.py';spec=importlib.util.spec_from_file_location('smoke_monitor',monitor);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 root=Path(a.root).absolute();root.mkdir(exist_ok=False);prep=Path(a.preparation).absolute();python=prep/'env/bin/python'
 command=[os.path.abspath(python),str(Path(__file__).with_name('smoke_driver.py')),'--bundle',str(bundle),'--preparation',str(prep),'--output',str(root/'stages')]
 result=m.execute(command,bundle,600,root,4*1024**3,1024**3,root/'smoke.log',ownership_env='OWALNUTS_READINESS_TOKEN')
 result['readiness_complete']=False
 try:
  evidence=json.loads((root/'stages/stages.json').read_text())
  result['readiness_complete']=result['status']=='exited' and result['exit_code']==0 and result['group_drained'] and not result.get('orphaned_children_after_leader_exit',False) and evidence['status']=='complete' and [r['stage'] for r in evidence['stages']]==['candidate','sides','reference'] and all(r['status']=='complete' for r in evidence['stages'])
 except Exception as exc:result['evidence_error']=repr(exc)
 result['qualification']=None;(root/'supervisor.json').write_text(json.dumps(result,indent=2))
 return 0 if result['readiness_complete'] else 1
if __name__=='__main__':raise SystemExit(main())
