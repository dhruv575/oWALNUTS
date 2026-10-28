import unittest
import numpy as np
from market_worker import decode,sample


class WorkerTests(unittest.TestCase):
    def test_mapping_preserves_all_slots(self):
        self.assertEqual(len({decode(i) for i in range(192)}),192)
        self.assertEqual(decode(191),(23,1,3))
        with self.assertRaises(ValueError):decode(192)

    def test_failure_preserves_retained_draws_without_retry(self):
        calls=[]
        def fake(model,q,rng,budget):
            calls.append(1)
            if len(calls)==4:raise RuntimeError('intentional')
            return q.copy(),{}
        r,f,c=sample(np.zeros(250),0,81,warmup=1,retained=5,function=fake)
        self.assertEqual(r['status'],'incomplete');self.assertEqual(len(calls),4)
        self.assertEqual(f.shape,(2,253));self.assertEqual(c.shape,(2,4))

    def test_literal_actual_sweeps_both_methods(self):
        for method in (0,1):
            r,f,c=sample(np.resize([.001,-.002,.0005,0.,.003],250),method,82+method,warmup=1,retained=2)
            self.assertEqual(r['status'],'complete');self.assertEqual(f.shape,(2,253))
            np.testing.assert_array_equal(f[:,:3],c[:,:3])


if __name__=='__main__':unittest.main()
