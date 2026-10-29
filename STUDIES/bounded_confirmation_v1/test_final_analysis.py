import unittest
import numpy as np
from final_analysis import describe
from confirmation_bootstrap import summarize


class FinalAnalysisTests(unittest.TestCase):
    def test_complete_calendar_matches_frozen_bootstrap(self):
        x=np.random.default_rng(17).normal(size=(400,3))
        result=describe(x,398300000)
        for offset,block in enumerate([96,48,336]):
            expected=summarize(x,400,block,398300000+offset)
            np.testing.assert_allclose(result['blocks'][offset]['interval_95'],expected['interval_95'],rtol=0,atol=1e-14)
            np.testing.assert_allclose(result['blocks'][offset]['lower_9875'],expected['lower_9875'],rtol=0,atol=1e-14)

    def test_gaps_preserve_constant_mean_and_denominator(self):
        x=np.full((400,2),.125);x[[20,310]]=np.nan
        result=describe(x,398300000)
        self.assertEqual(result['planned'],400)
        self.assertEqual(result['qualified'],398)
        for block in result['blocks']:
            self.assertEqual(block['interval_95'],[[.125,.125],[.125,.125]])


if __name__=='__main__':unittest.main()
