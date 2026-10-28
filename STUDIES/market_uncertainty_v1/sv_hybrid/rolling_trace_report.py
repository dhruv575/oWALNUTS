"""Cross-check retained NUTS traces before all-coordinate diagnostics."""
from pathlib import Path
import numpy as np
import arviz as az
from literal_reference import extract_full, extract_compact
from reference_report import summarize
from rolling_record_audit import sha


def report_trace(directory, expected, lane_compact=None, draws=400):
    directory=Path(directory)
    if draws not in (200,400):raise ValueError('Fixed initialization or update draws')
    for name in ('trace','draws'):
        path=directory/('trace.nc' if name=='trace' else 'draws.npz')
        if sha(path)!=expected[name+'_sha256']:raise ValueError('Retained artifact hash mismatch')
    trace=az.from_netcdf(directory/'trace.nc')
    try:
        full=extract_full(trace,draws);compact,metadata=extract_compact(trace,draws)
        if trace.warmup_posterior.sizes.get('draw')!=1000 or trace.warmup_posterior.sizes.get('chain')!=4:
            raise ValueError('Warmup axes mismatch')
        with np.load(directory/'draws.npz',allow_pickle=False) as saved:
            if not np.array_equal(full,saved['full']) or not np.array_equal(compact,saved['compact']):
                raise ValueError('Trace and saved draws disagree')
        if lane_compact is not None and not np.array_equal(compact,np.load(lane_compact,allow_pickle=False)):
            raise ValueError('Trace and lane compact disagree')
        result=summarize(full,compact)
        result.update(metadata=metadata,diagnostic_passed=not result['flagged_coordinates'] and sum(metadata['divergences'])==0,
                      trace_sha256=expected['trace_sha256'],draws_sha256=expected['draws_sha256'],
                      scope='Retained-window diagnostics only; no whole-path posterior qualification')
        return result
    finally:
        for group in trace.groups():getattr(trace,group).close()
        trace.close()
