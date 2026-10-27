"""Fixed causal query construction; no future label argument."""
import numpy as np
OFFSETS=np.array([-2.,-1.,0.,1.,2.])
def query_grid(window):
    window=np.asarray(window,dtype=np.float64)
    if window.shape!=(250,) or not np.isfinite(window).all():raise ValueError('finite250-window required')
    center=float(np.mean(window));scale=float(np.std(window,ddof=0))
    if not np.isfinite([center,scale]).all() or scale<=0:raise ValueError('nonpositive/nonfinite causal grid scale')
    queries=center+scale*OFFSETS
    if not np.isfinite(queries).all():raise ValueError('nonfinite causal grid queries')
    return dict(center=center,scale=scale,offsets=OFFSETS.tolist(),queries=queries.tolist(),std_ddof=0)
