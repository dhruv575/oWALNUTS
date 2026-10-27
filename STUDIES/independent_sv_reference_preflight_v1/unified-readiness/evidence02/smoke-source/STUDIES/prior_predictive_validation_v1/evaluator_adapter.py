"""Explicit adapter to reviewed observed-return evaluator, never generates data."""
import hashlib,importlib.util,time
from pathlib import Path
import numpy as np
class Evaluator:
    def __init__(self,path,expected_sha256,seconds_per_call=30.):
        path=Path(path)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected_sha256:raise ValueError('evaluator source mismatch')
        if not np.isfinite(seconds_per_call) or seconds_per_call<=0:raise ValueError('positive evaluator cap required')
        spec=importlib.util.spec_from_file_location('frozen_observed_return_evaluator',path)
        self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
        if not callable(getattr(self.module,'evaluate_observation',None)):raise ValueError('missing observed-return API')
        self.seconds=seconds_per_call;self.identity=dict(path=str(path),sha256=expected_sha256)
    def __call__(self,draws,label):
        r=self.module.evaluate_observation(draws,label,rho=.95,nu=5,orders=(64,128),chunk=512,deadline=time.monotonic()+self.seconds)
        return dict(r,cdf=r['pit'],evaluator_identity=self.identity)
    def oracle(self,parameters,current_latent,label):
        # True CURRENT h only. evaluate_observation itself integrates the next innovation.
        component=np.array([[[parameters['mu'],parameters['log_sigma'],parameters['beta'],current_latent]]],dtype=float)
        return self(component,label)
