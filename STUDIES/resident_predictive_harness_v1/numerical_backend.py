"""Explicit research-opt-in numerical backend; no global processor mutation."""
import hashlib,importlib.util
from pathlib import Path
import numpy as np
import scipy
from scipy.special import stdtr
HERE=Path(__file__).resolve().parent
PROCESS=HERE.parent/'amm_predictive_review_v1/predictive-return-smoke/process.py'
BASE_SHA='fffc989bb6b59f4f2f055b1199f9e391fc49a5a97ea3fc436b1a348bb88875fd'
T5_SHA='94c767c783623e99f1f60d7bf5b0766f72b96975ac6ec088218da994ef7b33f3'
if hashlib.sha256(PROCESS.read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Unreviewed base numerical processor')
spec=importlib.util.spec_from_file_location('resident_numerical_base',PROCESS)
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)

class Backend:
    def __init__(self,name='scipy'):
        if name not in ('scipy','exact_t5'):raise ValueError('Unknown numerical backend')
        self.name=name
        self.metadata=dict(name=name,research_opt_in=name=='exact_t5',base_processor_sha256=BASE_SHA,
            adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scipy_version=scipy.__version__)
        if name=='exact_t5':
            path=HERE/'exact_t5_snapshot.py'
            if hashlib.sha256(path.read_bytes()).hexdigest()!=T5_SHA:raise ValueError('Unreviewed exact t5 implementation')
            import exact_t5_snapshot
            self.cdf=exact_t5_snapshot.stdtr5
            self.metadata['implementation_sha256']=T5_SHA
        else:self.cdf=stdtr

class ConfiguredReturnCDF(base.ReturnCDF):
    def __init__(self,*args,backend=None,**kwargs):
        self.backend=backend or Backend()
        super().__init__(*args,**kwargs)
        if self.backend.name=='exact_t5' and self.nu!=5:raise ValueError('exact_t5 requires nu=5')
    def __call__(self,x):
        # Same operations/order as frozen ReturnCDF.__call__; only CDF dispatch differs.
        if not np.isfinite(x):raise ValueError('nonfinite CDF argument')
        self.calls+=1;total=0.0
        for lo in range(0,len(self.m),self.chunk):
            self.budget();hi=min(lo+self.chunk,len(self.m))
            inv=self.cache.get(lo)
            if inv is None:inv=self.inverse_scales(lo,hi)
            with np.errstate(over='raise',invalid='raise'):
                standardized=(x-self.beta[lo:hi,None])*inv
            c=self.backend.cdf(self.nu,standardized)
            total+=float(np.sum(c@self.weights));self.student_t_evaluations+=c.size
        result=total/len(self.m)
        if not np.isfinite(result) or not 0<=result<=1:raise ValueError('invalid numerical CDF')
        return result
