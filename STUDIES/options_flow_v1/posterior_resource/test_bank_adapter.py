import copy
from pathlib import Path
import pytest
from . import bank_adapter as a

def manifest():
 pilot=Path(__file__).resolve().parent.parent/'artifacts/posterior-resource-pilot-v1/plan.json'
 return dict(excluded_pilot_manifest=str(pilot),excluded_pilot_manifest_sha256=a.sha(pilot),qualified=False,phase='prospective_reference_bank',posterior_sha256='target',excluded_resource_pilot_ids=['fit-0-public','fit-1-reference','fit-2-reference','fit-3-public'],endpoints=copy.deepcopy(a.ENDPOINTS),fits=[dict(id=f'{b}{i}',backend=b,sampler_seed=j*100+i,initialization_seed=1000+j*100+i) for j,b in enumerate(['public','reference']) for i in range(16)])

def test_pilot_and_duplicate_streams_cannot_enter():
 m=manifest();a.manifest_check(m)
 m['fits'][0]['id']='fit-0-public'
 with pytest.raises(ValueError):a.manifest_check(m)
 m=manifest();m['fits'][1]['initialization_seed']=m['fits'][0]['sampler_seed']
 with pytest.raises(ValueError):a.manifest_check(m)

def test_two_fit_resource_pilot_is_not_bank():
 m=manifest();m['fits']=m['fits'][:2]+m['fits'][16:18]
 with pytest.raises(ValueError):a.manifest_check(m)

def test_missing_fit_denominator_retained(monkeypatch):
 m=manifest()
 def fail(spec,target):raise FileNotFoundError(spec['id'])
 monkeypatch.setattr(a,'admit_fit',fail)
 r=a.collect(m);assert r['expected']==32 and len(r['outcomes'])==32 and not r['admitted'] and not r['reference_bank_resolved']

def test_predictive_scope_cannot_silently_drop():
 m=manifest();m['endpoints'].pop('observed_group0_h1_0.95')
 with pytest.raises(ValueError):a.manifest_check(m)


def test_renaming_pilot_fit_does_not_evade_exclusion():
 m=manifest();m['fits'][0]['sampler_seed']=198110002
 with pytest.raises(ValueError,match='pilot stream'):a.manifest_check(m)


def valid_checkpoint():
 d=dict(rhat=1.,bulk_ess=500.,tail_ess=500.,interval_90=[-1.,1.],endpoint_mcse=[.01,.01])
 return dict(status='completed',draws=4000,retained_divergences=0,evaluation=dict(chain_count=4,
  canonical_parameter_diagnostics={f'q_{i}':copy.deepcopy(d) for i in range(1012)},
  functionals={k:copy.deepcopy(d) for k in a.FUNCTIONALS},
  forecast=dict(rows=[dict(horizon=1,group=g,lower=-1.,upper=1.,endpoint_mcse=[.01,.01]) for g in range(4)])))


@pytest.mark.parametrize('case',['coordinate','functional','forecast','precision','rhat','divergence'])
def test_full_gate_recomputed_not_trusted(case):
 c=valid_checkpoint();a.checkpoint_check(c,4000)
 if case=='coordinate':c['evaluation']['canonical_parameter_diagnostics'].pop('q_1000')
 elif case=='functional':c['evaluation']['functionals'].pop('beta_3')
 elif case=='forecast':c['evaluation']['forecast']['rows'][3]['group']=0
 elif case=='precision':c['evaluation']['forecast']['rows'][0]['endpoint_mcse']=[.041,.01]
 elif case=='rhat':c['evaluation']['canonical_parameter_diagnostics']['q_999']['rhat']=0
 else:c['retained_divergences']=1
 with pytest.raises(ValueError):a.checkpoint_check(c,4000)
