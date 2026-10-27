"""Bind a reviewed production bundle after complete literal readiness; no execution."""
import argparse,hashlib,json,sys
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())

def bind(bundle,preparation,smoke,output,authorize=False):
 bundle=Path(bundle).absolute();prep=Path(preparation).absolute();smoke=Path(smoke).absolute();output=Path(output).absolute()
 if output.exists():raise FileExistsError('Immutable manifest must be new')
 readiness=read(smoke/'supervisor.json')
 if readiness.get('readiness_complete')is not True or readiness.get('group_drained')is not True:raise ValueError('Complete drained literal readiness required')
 stages=read(smoke/'stages/stages.json')
 if stages.get('status')!='complete' or [r.get('stage') for r in stages.get('stages',[])]!=['candidate','sides','reference'] or any(r.get('status')!='complete' for r in stages['stages']):raise ValueError('All three literal stages required')
 prepared=read(prep/'preparation.json');identity_path=prep/'runtime-identity.json'
 if prepared.get('status')!='complete' or sha(identity_path)!=prepared['runtime_identity_sha256']:raise ValueError('Verified isolated runtime required')
 identity=read(identity_path);inventory=read(bundle/'BUNDLE-MANIFEST.json');sources={str(bundle/name):digest for name,digest in inventory.items()}
 for path,want in sources.items():
  if sha(path)!=want:raise ValueError('Production source drift '+path)
 # Every Python module shared with the successful smoke must have identical bytes.
 development=read(smoke/'stages/development-manifest.json');compared=[]
 for path,want in development['sources'].items():
  relative=path.replace('\\','/').partition('/STUDIES/')[2]
  if relative and relative.endswith('.py'):
   target=bundle/'STUDIES'/relative
   if not target.exists() or sha(target)!=want:raise ValueError('Python source differs from successful readiness '+relative)
   compared.append(relative)
 if not compared:raise ValueError('Missing readiness source provenance')
 study=bundle/'STUDIES/prior_predictive_validation_v1';spec=read(study/'PROTOCOL-DRAFT.json')
 if spec['planned_streams']!=32 or spec['planned_updates_per_stream']!=32 or spec['reference_sentinels']!=[[0,1],[4,32],[8,1],[12,32],[16,1],[20,32],[24,1],[28,32]]:raise ValueError('Fixed scientific denominators changed')
 spec['status']='frozen_authorized' if authorize else 'frozen_pending_authorization';spec['sources']=sources;spec.pop('unresolved',None)
 sdk=Path('/home/ubuntu/.bridgestan/bridgestan-2.9.0');sdk_inventory_path=prep/'sdk-source-inventory.json'
 if sha(sdk_inventory_path)!=prepared['sdk_source_inventory_sha256']:raise ValueError('SDK inventory drift')
 sources.update({str(sdk/name):digest for name,digest in read(sdk_inventory_path).items()})
 runtime=dict(prefix=identity['prefix'],packages=identity['distributions'],binaries=dict(identity['native_modules']))
 runtime['binaries'][identity['executable_realpath']]=identity['executable_sha256'];runtime['binaries'].update(identity['entry_sources'])
 
 for kind in ('candidate','sides','reference'):
  if development['runtimes'][kind]!=runtime or development['python_by_kind'][kind]!=identity['executable']:raise ValueError('Runtime differs from successful literal readiness '+kind)
 spec['runtimes']={kind:runtime for kind in ('candidate','sides','reference','report')};spec['python_by_kind']={kind:identity['executable'] for kind in spec['runtimes']}
 spec['target_path']=str(bundle/'STUDIES/resident_predictive_harness_v1/sv_target.py')
 evaluator=bundle/'STUDIES/predictive_value_diagnostic_v1/predictive_density.py';spec['evaluator'].update(path=str(evaluator),sha256=sha(evaluator))
 stan=bundle/'STUDIES/independent_sv_reference_preflight_v1/model.stan'
 if sha(stan)!=development['reference']['stan_sha256']:raise ValueError('Stan target differs from successful readiness')
 spec['reference'].update(api_and_target_verified=True,stan_path=str(stan),stan_sha256=sha(stan),bridgestan_sdk=str(sdk),sdk_makefile_sha256=development['reference']['sdk_makefile_sha256'],capture_path=str(bundle/'STUDIES/independent_sv_reference_preflight_v1/compiler_capture.py'),engine_options=development['reference']['engine_options'])
 spec['provenance']=dict(readiness_supervisor_sha256=sha(smoke/'supervisor.json'),readiness_stage_sha256=sha(smoke/'stages/stages.json'),runtime_identity_sha256=sha(identity_path),bundle_manifest_sha256=sha(bundle/'BUNDLE-MANIFEST.json'),shared_python_modules_compared=len(compared),binder_sha256=sha(__file__))
 output.parent.mkdir(parents=True,exist_ok=True)
 with output.open('x') as handle:json.dump(spec,handle,indent=2);handle.write('\n')
 return spec
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--bundle',required=True);p.add_argument('--preparation',required=True);p.add_argument('--smoke',required=True);p.add_argument('--output',required=True);p.add_argument('--authorize-execution',action='store_true');a=p.parse_args();bind(a.bundle,a.preparation,a.smoke,a.output,a.authorize_execution)
