import json
from types import SimpleNamespace
import numpy as np
import pytest
from pymc_continuation_workflow import run_session, bindings, verify_bindings


class Session:
    def __init__(self, starts, fail=False):
        self.starts=starts; self.end=0; self.calls=0; self.adaptations=0; self.closed=False; self.fail=fail
    def chunk(self,n,warmup=False):
        start=self.end
        if not warmup:self.end+=n
        self.calls+=n+1
        samples=np.broadcast_to(self.starts[:,None,:],(len(self.starts),n,self.starts.shape[1])).copy()
        if n:samples+=np.arange(start,self.end)[None,:,None]*.001
        return SimpleNamespace(samples=samples,retained_start=start,retained_end=self.end,
            target_calls=n+1,cumulative_target_calls=self.calls,initialization_target_calls=int(warmup),
            metadata=[dict(mass_diagonal=[1.]*self.starts.shape[1],final_step_size=.1)],
            diagnostics=[dict(divergent=[False]*n) for _ in self.starts],cumulative_work=[])
    def adapt(self):self.adaptations+=1;return self.chunk(0,True)
    def draw(self,n):
        if self.fail and self.end:raise RuntimeError('controlled failure')
        return self.chunk(n)
    def close(self):self.closed=True
    def progress(self):return dict(closed=self.closed,target_calls=self.calls)


def setup_run(tmp_path,fail=False,verify=lambda:None):
    starts=np.zeros((4,3)); sessions=[]; admissions=[]; evaluations=[]
    def factory(target,**kw):
        admissions.append(kw);s=Session(kw['init'],fail);sessions.append(s);return s
    def evaluate(q,fixture,seed):
        evaluations.append((q.copy(),seed));return dict(computational_screen_pass=True)
    report=run_session(None,dict(data=dict(y=[0.])),starts,tmp_path,19,1000,[4,8],'centered',{},
        session_factory=factory,evaluator=evaluate,screen=lambda *a:dict(pass_=False,**{'pass':False}),verify=verify)
    return report,sessions,admissions,evaluations


def test_one_admission_adaptation_and_exact_prefix(tmp_path):
    report,sessions,admissions,evaluations=setup_run(tmp_path)
    assert report['status']=='completed' and not report['precision_pass']
    assert len(admissions)==1 and admissions[0]['max_draws']==8 and admissions[0]['warmup']==1000
    assert sessions[0].adaptations==1 and sessions[0].closed
    np.testing.assert_array_equal(evaluations[0][0],evaluations[1][0][:,:4])
    assert [v[1] for v in evaluations]==[130019,130019]
    assert report['total_target_calls']==1+5+5
    assert [a['added_draws'] for a in report['attempts']]==[4,4]


def test_failure_keeps_previous_tier_and_charges_attempt(tmp_path):
    report,sessions,_,_=setup_run(tmp_path,fail=True)
    assert report['status']=='failed' and report['attempts'][-1]['status']=='failed'
    assert report['attempts'][-1]['seconds_including_evaluation_and_serialization']>=0
    assert (tmp_path/'draws-4'/'python-pymc-raw.json').exists()
    assert json.loads((tmp_path/'draws-8'/'attempt.json').read_text())['status']=='failed'
    assert sessions[0].closed


def test_binding_mutation_stops_before_admission(tmp_path):
    source=tmp_path/'source.py';source.write_text('original');snapshot=bindings([source]);source.write_text('changed')
    report,sessions,admissions,_=setup_run(tmp_path,verify=lambda:verify_bindings(snapshot))
    assert report['status']=='failed' and not sessions and not admissions
    assert 'changed' in report['error']


def test_invalid_tiers_do_not_admit(tmp_path):
    with pytest.raises(ValueError):
        run_session(None,{},np.zeros((4,3)),tmp_path,1,1000,[8,4],'centered',{},session_factory=lambda **kw:pytest.fail())


def test_failed_adapt_charged_and_cleanup_does_not_mask_error(tmp_path):
    class FailedSession(Session):
        def adapt(self):raise RuntimeError('original adaptation failure')
        def progress(self):raise RuntimeError('progress failure')
        def close(self):self.closed=True;raise RuntimeError('close failure')
    s=FailedSession(np.zeros((4,3)));checkpoints=[]
    report=run_session(None,dict(data=dict(y=[0.])),s.starts,tmp_path,1,1000,[4],'centered',{},
        session_factory=lambda *a,**kw:s,checkpoint=lambda r:checkpoints.append(dict(r)))
    assert report['status']=='failed' and report['error']=='original adaptation failure'
    assert report['adapt_seconds']>=0 and report['total_sampling_seconds']==report['adapt_seconds']
    assert len(report['cleanup_errors'])==3 and s.closed and checkpoints


def test_warmup_and_every_tier_checkpointed(tmp_path):
    snapshots=[];s=Session(np.zeros((4,3)))
    run_session(None,dict(data=dict(y=[0.])),s.starts,tmp_path,1,1000,[4,8],'centered',{},
        session_factory=lambda *a,**kw:s,evaluator=lambda *a:dict(computational_screen_pass=True),
        screen=lambda *a:{'pass':False},checkpoint=lambda r:snapshots.append(len(r['attempts'])))
    assert snapshots==[0,1,1,2,2,2]


def test_public_native_session_matches_uninterrupted_canonical_prefix(tmp_path):
    import owalnuts
    import numba
    from pymc_workflow import coordinate_transport
    @numba.cfunc(owalnuts.numba_raw_signature(),nopython=True)
    def density(dim,q,g,user):
        result=0.
        for i in range(dim):g[i]=-q[i];result-=.5*q[i]*q[i]
        return result
    target=owalnuts.from_cfunc(density,3)
    fixture=dict(data=dict(y=[.3],anchor=0.,anchor_mode='exogenous',nu=5.))
    starts=np.array([[.1,-1.,-1.],[.2,-.9,-1.1],[.3,-1.1,-.9],[.4,-1.2,-.8]])
    forward,inverse=coordinate_transport(fixture['data'],'observation_residual')
    full=owalnuts.sample(target,init=forward(starts),chains=4,warmup=20,draws=8,seed=172,threads=1)
    report=run_session(target,fixture,starts,tmp_path,172,20,[4,8],'observation_residual',{},
        evaluator=lambda *a:dict(computational_screen_pass=True),screen=lambda *a:{'pass':False})
    assert report['status']=='completed',report.get('error')
    first=json.loads((tmp_path/'draws-4'/'python-pymc-raw.json').read_text())
    last=json.loads((tmp_path/'draws-8'/'python-pymc-raw.json').read_text())
    np.testing.assert_array_equal(last['canonical_draws'],inverse(full.samples))
    np.testing.assert_array_equal(first['canonical_draws'],np.asarray(last['canonical_draws'])[:,:4])
    np.testing.assert_array_equal(last['initial_positions'],starts)
    assert report['total_target_calls']==full.target_calls
    assert len(last['retained_chunk_diagnostics'][0][0])==9
