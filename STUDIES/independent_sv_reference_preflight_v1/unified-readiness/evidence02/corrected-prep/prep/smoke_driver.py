"""Bind the prepared runtime and execute only the three frozen literal stages."""
import argparse,hashlib,json,os,sys,time
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--bundle',required=True);p.add_argument('--preparation',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 bundle=Path(a.bundle).absolute();prep=Path(a.preparation).absolute();out=Path(a.output).absolute();out.mkdir(exist_ok=False)
 source_manifest=json.loads((bundle/'BUNDLE-MANIFEST.json').read_text());sources={str(bundle/name):digest for name,digest in source_manifest.items()}
 if not all(sha(name)==digest for name,digest in sources.items()):raise RuntimeError('smoke bundle drift')
 identity=json.loads((prep/'runtime-identity.json').read_text())
 if sys.prefix!=identity['prefix']:raise RuntimeError('smoke runtime prefix differs')
 if sha(prep/'runtime-identity.json')!=json.loads((prep/'preparation.json').read_text())['runtime_identity_sha256']:raise RuntimeError('runtime inventory altered')
 study=bundle/'STUDIES/prior_predictive_validation_v1';sys.path.insert(0,str(study))
 from resource_monitor import execute
 spec=json.loads((study/'PROTOCOL-DRAFT.json').read_text());spec['status']='development_authorized';spec['sources']=sources
 runtime=dict(prefix=identity['prefix'],packages=identity['distributions'],binaries=dict(identity['native_modules']))
 runtime['binaries'][identity['executable_realpath']]=identity['executable_sha256']
 for path,digest in identity['entry_sources'].items():runtime['binaries'][path]=digest
 sdk_sources=json.loads((prep/'sdk-source-inventory.json').read_text())
 if sha(prep/'sdk-source-inventory.json')!=json.loads((prep/'preparation.json').read_text())['sdk_source_inventory_sha256']:raise RuntimeError('SDK inventory altered')
 sources.update({str(Path('/home/ubuntu/.bridgestan/bridgestan-2.9.0')/name):digest for name,digest in sdk_sources.items()})
 spec['runtimes']={kind:runtime for kind in ('candidate','sides','reference')}
 spec['python_by_kind']={kind:sys.executable for kind in ('candidate','sides','reference')}
 spec['target_path']=str(bundle/'STUDIES/resident_predictive_harness_v1/sv_target.py')
 evaluator=bundle/'STUDIES/predictive_value_diagnostic_v1/predictive_density.py';spec['evaluator'].update(path=str(evaluator),sha256=sha(evaluator))
 stan=bundle/'STUDIES/independent_sv_reference_preflight_v1/model.stan'
 spec['reference'].update(api_and_target_verified=True,stan_path=str(stan),stan_sha256=sha(stan),bridgestan_sdk='/home/ubuntu/.bridgestan/bridgestan-2.9.0',sdk_makefile_sha256='21f9f85c5d2390ba61cfb23015514b4f7dcb678b9f89927ece6bc43ec4eafeee',capture_path=str(bundle/'STUDIES/independent_sv_reference_preflight_v1/compiler_capture.py'),engine_options=dict(target_accept=.8,maxdepth=10,store_mass_matrix=True,low_rank_modified_mass_matrix=False,transform_adapt=False))
 manifest=out/'development-manifest.json';manifest.write_text(json.dumps(spec,indent=2))
 state=dict(status='running',planned_stages=['candidate','sides','reference'],stages=[],scope='literal engineering fixture; no calibration evidence');statepath=out/'stages.json'
 statepath.write_text(json.dumps(state,indent=2))
 started=time.monotonic()
 for kind,limit in [('candidate',180),('sides',90),('reference',300)]:
  left=580-(time.monotonic()-started)
  if left<=5 or any(row['status']!='complete' for row in state['stages']):
   state['stages'].append(dict(stage=kind,status='not_started',reason='prior failure or shared budget'));continue
  command=['taskset','-c','0-3',os.path.abspath(sys.executable),str(study/'readiness.py'),kind,'--manifest',str(manifest),'--out',str(out/'work')]
  record=execute(command,study,min(limit,left),out,4*1024**3,1024**3,out/(kind+'.log'))
  ok=False
  try:
   evidence=json.loads((out/'work'/('readiness-'+kind+'.json')).read_text())
   ok=record['status']=='exited' and record['exit_code']==0 and record['group_drained'] and not record.get('orphaned_children_after_leader_exit',False) and evidence['status']=='complete'
  except Exception as exc:record['evidence_error']=repr(exc)
  state['stages'].append(dict(stage=kind,status='complete' if ok else 'failed',monitor=record));statepath.write_text(json.dumps(state,indent=2))
 state['status']='complete' if len(state['stages'])==3 and all(row['status']=='complete' for row in state['stages']) else 'failed'
 state['elapsed_seconds']=time.monotonic()-started;state['postrun_sources_match']=all(sha(name)==digest for name,digest in sources.items())
 if not state['postrun_sources_match']:state['status']='integrity_failed'
 statepath.write_text(json.dumps(state,indent=2));return 0 if state['status']=='complete' else 1
if __name__=='__main__':raise SystemExit(main())
