import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];study=ROOT.parent/'STUDIES/options_flow_v1';prototype=ROOT/'correlated-reference-draft';out=Path(__file__).parent
sys.path[:0]=[str(prototype),str(study)]
import correlated_reference_study as controller
import reference_bank_vectorized as vector
original=vector.batch_cached_parameter;calls=[]
def spy(*a,**k):calls.append((a[2],a[3]));return original(*a,**k)
vector.batch_cached_parameter=spy
p=dict(study=str(study),memory_bytes=2*1024**3,implementation='vectorized',prefixes=[16,32,64],bootstrap_replicates=300,minimum_tail_count=1,alpha=.05,relative_half_width=.1,backend_equivalence_relative_width=.02,length_equivalence_relative_width=.1,source={'reference_bank.py':controller.sha(study/'reference_bank.py')})
c=dict(id='tiny-production-route-smoke',fits_per_backend=2,lengths=[32,64],rho=.9,backend_b_shift=0.,fit_seeds=[501,502,503,504],init_seeds=[601,602,603,604],bootstrap_seed=701)
controller.guarded_worker(p,c,out)
assert len(calls)==8
controller.validate_outputs(out,c,p)
result=controller.load(out/'result.json');bank=controller.load(out/'bank.json');resource=controller.load(out/'resources.json');diagnostic=controller.load(out/'prefix-diagnostic.json')
assert result['status']=='completed' and result['bounds']==[bank['endpoints'][k] for k in ['lo','hi']]
assert resource['peak_committed_bytes']<=p['memory_bytes'] and set(diagnostic['estimates'])=={'16','32','64'}
assert all(result['shared_reference_covariance'][i][i]>0 for i in [0,1])
controller.save(out/'smoke-evidence.json',dict(scope='Tiny exploratory helperconfig; NOT frozen28cellcampaign. Reuses prior testseeds501..701.',calls=calls,checks_passed=True,resources=resource,source={str(f):controller.sha(f) for f in [Path(__file__),prototype/'correlated_reference_study.py',prototype/'gaussian_ar_indicator.py',study/'reference_bank.py',study/'reference_bank_vectorized.py',study/'reference_bank_allocation.py',study/'hardware_control.py']}))
