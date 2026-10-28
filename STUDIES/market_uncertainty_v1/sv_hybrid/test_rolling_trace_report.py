import tempfile
import unittest
from pathlib import Path
import numpy as np
import arviz as az
from rolling_trace_report import report_trace
from rolling_record_audit import sha


class RetainedTrace(unittest.TestCase):
    def test_full_coordinate_report_and_compact_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rng=np.random.default_rng(301)
            full=rng.normal(size=(4,400,253));full[:,:,0]-=10;full[:,:,1]-=2
            mu,ls=full[:,:,0],full[:,:,1]
            h=mu+np.exp(ls)*full[:,:,3]/np.sqrt(1-.95**2)
            for i in range(4,253):h=mu+.95*(h-mu)+np.exp(ls)*full[:,:,i]
            compact=np.concatenate([full[:,:,:3],h[:,:,None]],axis=-1)
            posterior={name:compact[:,:,i] for i,name in enumerate(('mu','log_sigma','beta','h_last'))}
            posterior['z']=full[:,:,3:]
            warmup={name:np.zeros((4,1000)) for name in ('mu','log_sigma','beta','h_last')}
            warmup['z']=np.zeros((4,1000,250))
            trace=az.from_dict(posterior=posterior,warmup_posterior=warmup,save_warmup=True,
                               sample_stats=dict(diverging=np.zeros((4,400),dtype=bool)))
            trace.to_netcdf(root/'trace.nc')
            for group in trace.groups():getattr(trace,group).close()
            trace.close()
            np.savez_compressed(root/'draws.npz',full=full,compact=compact)
            np.save(root/'lane.npy',compact)
            expected=dict(trace_sha256=sha(root/'trace.nc'),draws_sha256=sha(root/'draws.npz'))
            result=report_trace(root,expected,root/'lane.npy')
            self.assertEqual(len(result['coordinates']),254)
            self.assertEqual(result['metadata']['divergences'],[0,0,0,0])
            compact[0,0,0]+=1;np.save(root/'lane.npy',compact)
            with self.assertRaisesRegex(ValueError,'lane compact'):
                report_trace(root,expected,root/'lane.npy')

if __name__=='__main__':unittest.main()
