"""Historical-output adapter compatibility test only; never calibration evidence."""
import sys,json,zipfile,os,hashlib,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];STUDY=ROOT/'STUDIES/options_flow_v1'
sys.path.insert(0,str(STUDY))
import production_calibration_adapter as a
def write(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False)
def main(out):
 out=Path(out).resolve();out.mkdir(exist_ok=False)
 base=STUDY/'artifacts/fresh-paired-comparison-v1';plan=a.load(base/'run-v1/plan.json');old=next(c for c in plan['cells'] if c['id']=='pair00-reference')
 original=a.load(old['report']);report=copy.deepcopy(original);provenance=a.load(base/'independent-terminal-review/provenance.json')
 newbindings={};sources={};remapping={}
 with zipfile.ZipFile(base/'independent-terminal-review/executed-sources.zip') as z:
  for path,h in original['bindings'].items():
   if path==old['fixture']:continue
   if Path(path).suffix=='.py':
    meta=provenance['source_entries'][path];target=out/'archived-sources'/meta['entry'];target.parent.mkdir(exist_ok=True);target.write_bytes(z.read(meta['entry']))
    assert a.digest(target)==h
    newbindings[str(target)]=h;sources[str(target)]=h;remapping[path]=str(target)
   else:
    assert a.digest(path)==h
    newbindings[path]=h
 fixture=out/'fixture.json';fixture.write_bytes(Path(old['fixture']).read_bytes());newbindings[str(fixture)]=a.digest(fixture)
 report['bindings']=newbindings;worker=out/'worker';worker.mkdir()
 write(worker/'report.json',report)
 for path in Path(old['worker_directory']).glob('draws-*.json'):
  # Hardlinks are read-only inputs to this test; never modify linked raw arrays.
  if path.name.endswith('-raw.json'):os.link(path,worker/path.name)
  else:(worker/path.name).write_bytes(path.read_bytes())
 (worker/'invocation-timing.json').write_bytes((Path(old['worker_directory'])/'invocation-timing.json').read_bytes())
 hardware=a.load(old['hardware']);write(out/'hardware.json',hardware)
 procedure=dict(worker_kind='reference',worker_arm='numpyro-mixed-slopes-continuation',coordinates='mixed_slopes',implementation='associative',warmup=1000,chains=4,tiers=[1000,2000,4000,8000],relative_mcse=.02,timeout_seconds=1800,cpus=[0],bound_files={k:v for k,v in newbindings.items() if k!=str(fixture)},runtime_bindings={plan['python']:a.digest(plan['python'])},study_directory=str(STUDY),batch_size=1000,target_accept=.9)
 ph=a.object_digest(procedure);f=a.load(fixture);contract=a.fixture_contract(f,'flow')
 selectors=[dict(name=n,kind='functional',key=n) for n in contract['names']]+[dict(name=f'forecast_{g}',kind='forecast',horizon=1,group=g) for g in range(4)]
 manifest=dict(model='flow',arm='reference',procedure=procedure,procedure_sha256=ph,protocol_sha256='HISTORICAL_ADAPTER_COMPATIBILITY_TEST_ONLY',selectors=selectors)
 cell=dict(id='historical-schema-test',model='flow',arm='reference',procedure_sha256=ph,dataset_seed=f['seed'],chain_seed=old['sampler_seed'],source_sha256=sources,fixture_sha256=a.digest(fixture),truth=a.select_truth(contract,selectors),fixture_path=str(fixture),output_directory=str(worker),status_path=str(out/'status.json'),hardware_path=str(out/'hardware.json'),started_path=str(out/'started.json'),worker_command=hardware['command'])
 oldstatus=a.load(old['controller_status']);write(out/'status.json',dict(elapsed_seconds=oldstatus['elapsed_seconds'],returncode=oldstatus['returncode'],hardware_sha256=a.digest(out/'hardware.json'),report_sha256=a.digest(worker/'report.json')))
 write(out/'started.json',dict(protocol_sha256=manifest['protocol_sha256'],procedure_sha256=ph,fixture_sha256=cell['fixture_sha256'],dataset_seed=cell['dataset_seed']))
 result=a.normalize_cell(manifest,cell)
 evidence=dict(test_passed=result['usable'] and result['provenance_valid'],qualified=False,calibration_evidence=False,scope='Historical actual saved report/raw compatibility only. No sampling. Prospective envelope manufactured solely for test; source paths remapped to exact archived bytes. Final report statistics/evaluations untouched; only bindings remapped. Never feed this test record to a calibration summary.',original_report_sha256=a.digest(old['report']),adapter_sha256=a.digest(a.__file__),source_remapping=remapping,result=result)
 write(out/'test-result.json',evidence);write(out/'test-envelope.json',dict(manifest=manifest,cell=cell))
 print(json.dumps(dict(test_passed=evidence['test_passed'],errors=result['normalization']['errors'])))
if __name__=='__main__':main(sys.argv[1])
