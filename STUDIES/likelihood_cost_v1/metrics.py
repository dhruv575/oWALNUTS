import numpy as np


def assess(target,draws,divergences=0,depth_hits=0):
    import owalnuts
    if draws.ndim!=3 or draws.shape[0]!=4 or draws.shape[2]!=target.dim or not np.isfinite(draws).all():raise ValueError('Invalid sample shape')
    raw=owalnuts.summary(np.ascontiguousarray(draws),[f'q{i}' for i in range(target.dim)])
    features=target.features(draws.reshape(-1,target.dim)).reshape(4,draws.shape[1],-1)
    fs=owalnuts.summary(np.ascontiguousarray(features),[f'f{i}' for i in range(features.shape[-1])])
    mean=features.mean(axis=(0,1));error=np.abs(mean-target.truth());tol=target.tolerance()
    mcse=np.array([r['mcse_mean'] for r in fs]);allrows=raw+fs
    rhat=np.array([r['rhat'] for r in allrows]);ess=np.array([[r['ess_bulk'],r['ess_tail']] for r in allrows])
    diagnostic=bool(np.isfinite(rhat).all() and np.isfinite(ess).all() and rhat.max()<=1.01 and ess.min()>=400 and divergences==0 and depth_hits==0)
    accuracy=bool(np.isfinite(error).all() and np.all(error<=tol) and np.isfinite(mcse).all() and np.all(mcse<=tol/2))
    def finite(x):return float(x) if np.isfinite(x) else None
    return dict(passed=diagnostic and accuracy,diagnostic_pass=diagnostic,accuracy_pass=accuracy,
        max_error_ratio=finite(np.max(error/tol)),max_mcse_ratio=finite(np.max(mcse/(tol/2))),rhat_max=finite(rhat.max()),ess_min=finite(ess.min()),
        estimate=mean.tolist(),truth=target.truth().tolist(),absolute_error=error.tolist(),tolerance=tol.tolist(),
        functional_mcse=[finite(x) for x in mcse],divergences=divergences,depth_hits=depth_hits)
