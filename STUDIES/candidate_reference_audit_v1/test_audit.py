import unittest
import numpy as np
from audit import precision
class PrecisionTests(unittest.TestCase):
    def test_constant_oracle(self):
        r=precision(np.full((4,400),-3.),np.full((4,400),.25))
        self.assertEqual(r,dict(logpdf=-3.,pit=.25,logpdf_mcse=0.,pit_mcse=0.))
    def test_reject_invalid(self):
        for logs,pits in [(np.zeros((4,399)),np.zeros((4,399))),(np.zeros((4,400)),np.full((4,400),1.1)),(np.full((4,400),np.nan),np.zeros((4,400)))]:
            with self.assertRaises(ValueError):precision(logs,pits)
if __name__=='__main__':unittest.main()
