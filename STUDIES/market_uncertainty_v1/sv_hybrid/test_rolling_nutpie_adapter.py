import unittest
from unittest.mock import Mock
import numpy as np
from rolling_nutpie_adapter import DrawResident

class AdapterTests(unittest.TestCase):
    def resident(self):
        r=DrawResident.__new__(DrawResident);r.closed=False;r.y=np.arange(250,dtype=float);r.tick=0
        r.seeds={'warm':704040000};r.last=np.zeros((4,253));r.last[:,1]=np.log(.2);r.retained={2}
        r._fit=Mock(return_value=(np.zeros((4,400,4)),{}));return r
    def test_causal_window_seed_schedule_and_retention(self):
        r=self.resident();r.advance(250.,400)
        args=r._fit.call_args.args
        np.testing.assert_array_equal(args[0],np.arange(1,251,dtype=float));self.assertEqual(args[2:],(704040000,400,1,False))
        r.advance(251.,400);self.assertEqual(r._fit.call_args.args[2:],(704040004,400,2,True))
        self.assertEqual(r.tick,2);np.testing.assert_array_equal(r.y,np.arange(2,252,dtype=float))
    def test_failure_poisoning_preserves_last_completed_window(self):
        r=self.resident();before=r.y.copy();r._fit.side_effect=RuntimeError('failure')
        with self.assertRaises(RuntimeError):r.advance(250.,400)
        self.assertTrue(r.closed);self.assertEqual(r.tick,0);np.testing.assert_array_equal(r.y,before)
