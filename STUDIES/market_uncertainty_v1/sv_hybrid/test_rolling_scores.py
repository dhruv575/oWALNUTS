import unittest
import numpy as np
from rolling_scores import precision


class ScoreReconstruction(unittest.TestCase):
    def test_extreme_constant_and_density_averaging(self):
        result=precision(np.full((4,400),-10000.),np.full((4,400),.25))
        self.assertEqual(result,dict(logpdf=-10000.,pit=.25,logpdf_mcse=0.,pit_mcse=0.))
        logs=np.tile(np.log([1.,3.]),(4,200))
        result=precision(logs,np.full((4,400),.5))
        self.assertAlmostEqual(result['logpdf'],np.log(2.))
        self.assertNotAlmostEqual(result['logpdf'],logs.mean())

    def test_bad_axes_and_probabilities_rejected(self):
        with self.assertRaisesRegex(ValueError,'Four chains'):
            precision(np.zeros((400,4)),np.zeros((400,4)))
        with self.assertRaisesRegex(ValueError,'Invalid'):
            precision(np.zeros((4,400)),np.full((4,400),1.01))

if __name__=='__main__':unittest.main()
