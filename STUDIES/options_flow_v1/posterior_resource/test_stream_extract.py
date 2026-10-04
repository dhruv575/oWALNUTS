import hashlib,json
from pathlib import Path
import numpy as np
import pytest
from .stream_extract import extract


def test_stream_exact_rows_hash_compact_prediction_and_divergences(tmp_path):
    q=np.zeros((4,8,15));q[...,0]=.2;q[...,1]=-.7;q[...,2]=-.5;q[...,3]=-1.2
    q[...,4:8]=.1;q[...,8:12]=.4;q[...,12:]=np.arange(3)*.1
    flags=[[False]*8 for _ in range(4)];flags[1][3]=True
    raw=tmp_path/'raw.json';raw.write_text(json.dumps(dict(canonical_draws=q.tolist(),retained_chunk_diagnostics=[[dict(divergent=v) for v in flags]],padding='x'*140000,initial_positions=q[:,0,:].tolist())))
    result=extract(raw,tmp_path/'out',chains=4,draws=8,dimension=15,rho=.8,x_next=.6)
    restored=np.load(tmp_path/'out/canonical.npy',mmap_mode='r');np.testing.assert_array_equal(restored,q)
    compact=np.load(tmp_path/'out/compact.npz')
    np.testing.assert_allclose(compact['cdf_location'],.03+(.2+np.exp(-.7)*.4)*.6)
    np.testing.assert_allclose(compact['cdf_future_mean'],-.5+.8*(.2+.5))
    assert result['raw_sha256']==hashlib.sha256(raw.read_bytes()).hexdigest() and result['raw_bytes']==raw.stat().st_size
    assert result['divergence_arrays']==flags and compact['beta_bar'].shape==(4,8)
    with pytest.raises(FileExistsError):extract(raw,tmp_path/'out',chains=4,draws=8,dimension=15)


@pytest.mark.parametrize('value',[True,None,float('nan')])
def test_invalid_numeric_rows_rejected(tmp_path,value):
    row=[0.]*15;row[2]=value;raw=tmp_path/'bad.json';raw.write_text(json.dumps(dict(canonical_draws=[[row]])))
    with pytest.raises(ValueError):extract(raw,tmp_path/'out',chains=1,draws=1,dimension=15)


@pytest.mark.parametrize('chains,draws,dimension',[(2,1,15),(1,2,15),(1,1,14)])
def test_exact_shape_not_silent_truncation(tmp_path,chains,draws,dimension):
    raw=tmp_path/'bad.json';raw.write_text(json.dumps(dict(canonical_draws=[[[0.]*15]])))
    with pytest.raises(ValueError):extract(raw,tmp_path/'out',chains=chains,draws=draws,dimension=dimension)


def test_posterior_hash_ignores_only_starts_truth_labels():
    from .controller import posterior,validate_streams
    f=dict(data=dict(y=[[1]],x=[[2]],initial_positions=[[3]]),holdout=dict(x=[[4]],y=[[5]]),truth=[6])
    import copy
    g=copy.deepcopy(f);g['data']['initial_positions']=[[7]];g['truth']=[8];g['holdout']['y']=[[9]]
    assert posterior(f)==posterior(g)
    g['data']['y']=[[2]];assert posterior(f)!=posterior(g)
    with pytest.raises(ValueError):validate_streams([])


@pytest.mark.parametrize('chunk',[1,7,31,256])
def test_rows_across_buffer_boundaries(tmp_path,monkeypatch,chunk):
    from . import stream_extract as module
    original=module.Stream
    monkeypatch.setattr(module,'Stream',lambda path:original(path,chunk=chunk))
    q=np.arange(2*3*15,dtype=float).reshape(2,3,15)/100
    raw=tmp_path/'raw.json';raw.write_text(json.dumps(dict(canonical_draws=q.tolist())))
    meta=module.extract(raw,tmp_path/'out',chains=2,draws=3,dimension=15)
    np.testing.assert_array_equal(np.load(tmp_path/'out/canonical.npy'),q)
    assert meta['raw_sha256']==hashlib.sha256(raw.read_bytes()).hexdigest()


def test_truncated_header_closes_handle(tmp_path,monkeypatch):
    from . import stream_extract as module
    original=module.Stream;opened=[]
    def tracked(path):
        stream=original(path);opened.append(stream);return stream
    monkeypatch.setattr(module,'Stream',tracked)
    raw=tmp_path/'bad.json';raw.write_text('{"wrong":')
    with pytest.raises(ValueError):module.extract(raw,tmp_path/'out',chains=1,draws=1,dimension=15)
    assert opened[0].file.closed
