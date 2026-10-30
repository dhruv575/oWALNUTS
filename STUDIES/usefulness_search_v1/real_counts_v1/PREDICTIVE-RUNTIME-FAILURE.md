# Initial AWS startup failure

The original real-counts-predictive-20261030 directory preserves the transferred
bundle. Startup stopped in the preflight before creating JOBS.json or dispatching
any predictive job: BridgeStan ctypes requires a NumPy ndarray, but points loaded
from TARGET-CHECK.json were Python lists. Exact error: argument4 TypeError:
argument must be an ndarray. No predictive probability or score was produced.

Reviewed repair converts each point to np.asarray(dtype=float), preserving every
point, threshold, model, quadrature rule and job budget. Dispatch uses a separate
real-counts-predictive-20261030-v2 directory. The original local predictive_bundle01
retains executed startup bytes. This is an API repair, not scientific tuning.
