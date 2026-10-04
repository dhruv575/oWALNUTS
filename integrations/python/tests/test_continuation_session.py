"""Additive CFunc sessions: replay, lifetime and request validation."""
import gc
import weakref
import numpy as np
import pytest
import owalnuts


def gaussian():
    numba=pytest.importorskip('numba')
    @numba.cfunc(owalnuts.numba_raw_signature(),nopython=True)
    def callback(dim,q,g,user):
        value=0.
        for i in range(dim):
            scale=1.+i
            g[i]=-q[i]/scale
            value-=.5*q[i]*q[i]/scale
        return value
    return owalnuts.from_cfunc(callback,2)


@pytest.mark.parametrize('cache',[False,True])
def test_chunked_sampling_is_bitwise_equal_to_ordinary_sample(cache):
    target=gaussian();starts=np.array([[.1,-.2],[-.3,.4]])
    tuning=owalnuts.Tuning(max_depth=5)
    settings=dict(init=starts,chains=2,warmup=60,seed=8172,threads=1,tuning=tuning,cache_initial_evaluation=cache)
    full=owalnuts.sample(target,draws=13,**settings)
    with owalnuts.start_session(target,max_draws=13,**settings) as session:
        assert session.progress()['target_calls']==0
        with pytest.raises(Exception):session.draw(1)
        warmup=session.adapt()
        assert warmup.is_warmup and warmup.samples.shape==(2,0,2)
        with pytest.raises(Exception):session.adapt()
        with pytest.raises(Exception):session.draw(14)
        chunks=[session.draw(1),session.draw(5),session.draw(7)]
        np.testing.assert_array_equal(np.concatenate([c.samples for c in chunks],axis=1),full.samples)
        assert [(c.retained_start,c.retained_end) for c in chunks]==[(0,1),(1,6),(6,13)]
        for i in range(2):
            transition_fields=['depth','stop','target_evaluations','divergent','max_abs_energy_error',
                'leaves_built','selected_refinement_level','zero_density_evaluations','trajectory_macro_length']
            assert set(chunks[-1].diagnostics[i])==set(transition_fields)
            for name in transition_fields:
                observed=np.concatenate([c.diagnostics[i][name] for c in [warmup,*chunks]])
                np.testing.assert_array_equal(observed,full.chains[i][name])
            np.testing.assert_array_equal(chunks[-1].metadata[i]['mass_diagonal'],full.chains[i]['metadata']['mass_diagonal'])
            assert chunks[-1].metadata[i]['final_step_size']==full.chains[i]['metadata']['final_step_size']
        assert sum(c.target_calls for c in [warmup,*chunks])==chunks[-1].cumulative_target_calls
        assert chunks[-1].cumulative_target_calls==full.target_calls
        with pytest.raises(Exception):session.draw(1)
    assert session.progress()['closed']
    session.close()


def test_native_worker_owns_compiled_target_until_closed():
    target=gaussian();reference=weakref.ref(target)
    session=owalnuts.start_session(target,init=np.array([[.1,.2]]),chains=1,warmup=2,max_draws=2)
    del target;gc.collect()
    assert reference() is not None
    session.adapt();session.draw(2);session.close();gc.collect()
    assert reference() is None


def test_invalid_inputs_and_cancel_before_adapt():
    target=gaussian();settings=dict(init=np.zeros((1,2)),chains=1,max_draws=2,warmup=2)
    for changes in [dict(threads=2),dict(max_draws=0),dict(init=np.zeros(2)),dict(mass=np.eye(2)),dict(init=np.array([[np.nan,0.]]))]:
        with pytest.raises((ValueError,RuntimeError)):owalnuts.start_session(target,**dict(settings,**changes))
    with pytest.raises(TypeError):owalnuts.start_session(lambda x:x,**settings)
    session=owalnuts.start_session(target,**settings)
    session.cancel();session.close()
    assert session.progress()['target_calls']==0
    with pytest.raises(Exception):session.adapt()
