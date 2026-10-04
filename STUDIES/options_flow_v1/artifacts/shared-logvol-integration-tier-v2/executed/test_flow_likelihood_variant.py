import json,os,subprocess,sys
from pathlib import Path
import numpy as np
import pytest
from flow_mixed_coordinates import build_model,normalized_parity,to_mixed
from pymc_flow_continuation_workflow import compile_target,validate_likelihood_variant
CANDIDATE='shared_logvol_student_t_v1'

@pytest.mark.parametrize('model,block,coordinates',[('masked-flow',32,'mixed_slopes'),('flow',0,'mixed_slopes'),('flow',32,'noncentered')])
def test_unsupported_recipes_rejected(model,block,coordinates):
 with pytest.raises(ValueError):validate_likelihood_variant(model,block,coordinates,CANDIDATE)

def test_masks_rejected_by_existing_data_contract():
 data=dict(y=[[0.]],x=[[0.]],rho=.95,nu=5.,observation_mask=[[True]])
 with pytest.raises(ValueError):build_model(data,32,CANDIDATE)

@pytest.mark.parametrize('shape',[(1,1),(7,4)])
def test_normalized_compiled_value_gradient_and_shape(shape):
 from model import simulate
 from flow_starts import canonical_starts
 data=simulate(19,periods=shape[0],groups=shape[1],holdout=1)['data'];q=to_mixed(canonical_starts(data,4),data)
 for variant in ('pymc_student_t',CANDIDATE):
  target,meta=compile_target(data,'flow',32,'mixed_slopes',variant)
  assert meta['dimension']==4+2*shape[1]+shape[0]
  assert ('likelihood_variant' in meta)==(variant==CANDIDATE)
  result=normalized_parity(data,[q[0],q[0]+.01],target);assert result['passed']

def test_t1000_archived_saved_positions():
 archive=Path(__file__).parent/'artifacts/mixed-target-optimization-v1'
 data=json.loads((archive/'inputs/fixture.json').read_text())['data']
 points=json.loads((archive/'prior-profile/profile-result.json').read_text())['points']
 target,meta=compile_target(data,'flow',32,'mixed_slopes',CANDIDATE)
 assert meta['dimension']==1012
 assert normalized_parity(data,[np.asarray(r['sampling_position']) for r in points],target)['passed']

def test_tiny_actual_worker_variant_metadata_and_canonical_serialization(tmp_path):
 from model import simulate
 fixture=simulate(29,periods=3,groups=1,holdout=1);fp=tmp_path/'fixture.json';fp.write_text(json.dumps(fixture));out=tmp_path/'worker'
 cmd=[sys.executable,str(Path(__file__).with_name('pymc_flow_continuation_workflow.py')),'--fixture',str(fp),'--out',str(out),'--seed','918','--warmup','8','--chains','4','--tiers','4','8','--coordinates','mixed_slopes','--likelihood-variant',CANDIDATE]
 process=subprocess.run(cmd,capture_output=True,text=True,env=os.environ.copy(),timeout=180)
 assert process.returncode==1,process.stderr
 report=json.loads((out/'python-pymc-flow-report.json').read_text());assert report['status']=='completed',report.get('traceback')
 assert report['likelihood_variant']==CANDIDATE
 assert report['settings']['likelihood_variant']==report['compilation']['likelihood_variant']==CANDIDATE
 assert report['arm'].endswith(CANDIDATE) and report['parity']['passed'] and report['precision_pass'] is False
 assert [a['draws'] for a in report['attempts']]==[4,8]
 for tier in (4,8):
  fit=json.loads((out/f'draws-{tier}/fit-report.json').read_text());attempt=json.loads((out/f'draws-{tier}/attempt.json').read_text())
  assert fit['likelihood_variant']==attempt['likelihood_variant']==CANDIDATE
  assert fit['arm']==attempt['arm']==report['arm']
  assert attempt['screen']['pass'] is False
 raw=json.loads((out/'draws-8/python-pymc-flow-raw.json').read_text())
 assert np.asarray(raw['canonical_draws']).shape==(4,8,9)
 assert raw['initial_positions']==report['initial_positions']
