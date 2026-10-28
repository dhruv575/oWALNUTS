import unittest
from unittest.mock import patch
import numpy as np
import prepare

class BaselineFailureTests(unittest.TestCase):
    def test_one_baseline_exception_preserves_all_three_slots(self):
        fit=dict(location=0.,scale=1.,df=5.)
        with patch.object(prepare.baselines,'fit_t5',side_effect=RuntimeError('fixture failure')),patch.object(prepare.baselines,'ewma_t5',return_value=dict(status='ok',**fit)),patch.object(prepare.baselines,'nig_ar1',return_value=fit):
            rows=prepare.baseline_task((0,'2025-09',1,np.zeros(250),np.zeros(251),dict(status='ok',**fit),0.))
        self.assertEqual([r['method'] for r in rows],['rolling_t5','ewma_t5','nig_ar1'])
        self.assertIsNone(rows[0]['score']);self.assertEqual(rows[0]['fit']['status'],'failed')
        self.assertTrue(all(r['score'] is not None for r in rows[1:]))

if __name__=='__main__':unittest.main()
