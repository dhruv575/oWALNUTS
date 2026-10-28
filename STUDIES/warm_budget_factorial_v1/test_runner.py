import tempfile,unittest
from pathlib import Path
import numpy as np
from linear_runner import run_lane
from worker import settings
class RunnerTests(unittest.TestCase):
    def test_two_budget_shape_and_seed_schedule(self):
        class Engine:
            def __init__(self,y,seeds):self.i=0;self.seeds=seeds
            def advance(self,y,k):
                i=self.i;self.i+=1
                return np.zeros((4,k,4)),dict(call_index=i,seed=self.seeds['warm']+4*i,diagnostics=[dict(divergent=np.zeros(k,dtype=bool)) for _ in range(4)])
            def close(self):pass
        for k in (400,1600):
            with tempfile.TemporaryDirectory() as d:
                result=run_lane(np.zeros(253),updates=2,seeds=dict(initial=1,warm=100),score_ticks=[2],retain_ticks=[2],engine_factory=Engine,score_hook=lambda *args:dict(status='ok'),output=Path(d)/'run',k=k)
                self.assertEqual(result['status'],'complete');self.assertEqual(result['native_completed'],2)
                self.assertEqual(np.load(Path(d)/'run/draws/000002.npy').shape,(4,k,4))
    def test_factorial_pairing(self):
        for j in range(0,12,2):
            a,b=settings(j),settings(j+1)
            self.assertEqual(a[:2],b[:2]);self.assertEqual(a[3],b[3]);self.assertEqual((a[2],b[2]),(400,1600))
if __name__=='__main__':unittest.main()
