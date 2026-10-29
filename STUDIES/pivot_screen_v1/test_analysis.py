import unittest
from analyze import paired,interval


class AnalysisTests(unittest.TestCase):
    def test_paired_sign_and_failures(self):
        rows=[]
        for i in range(20):
            rows.append(dict(replicate=i,methods={'nuts':dict(qualified=i!=3,strict_reference_qualified=i<10,decision=dict(regret=1.,normalized_regret=.1)),
                'laplace':dict(qualified=True,decision=dict(regret=2.,normalized_regret=.2))}))
        value=paired(rows,'nuts','laplace',1)
        self.assertEqual(value['n'],19);self.assertNotIn(3,value['replicates'])
        self.assertAlmostEqual(value['mean'],.1)
        self.assertEqual(value['raw_units']['mean'],1.)
        self.assertEqual(paired(rows,'nuts','laplace',1,strict=True)['n'],9)

    def test_empty_and_constant_intervals(self):
        self.assertIsNone(interval([],1)['mean'])
        self.assertEqual(interval([.125]*20,1)['interval_95'],[.125,.125])


if __name__=='__main__':unittest.main()
