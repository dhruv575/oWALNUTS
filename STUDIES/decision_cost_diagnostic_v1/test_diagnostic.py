import unittest
from diagnostic import loss, integrated, analyze, COSTS

class DecisionTests(unittest.TestCase):
    def test_tie_and_outcomes(self):
        self.assertEqual(loss(.1,.3,.1),.3)
        self.assertEqual(loss(.1001,.3,.1),.1)

    def test_integral_independent_piecewise(self):
        for m in (0,.0005,.2,1):
            for y in (0,.01,.7,1):
                self.assertAlmostEqual(integrated(m,y),m*m/2+y*(1-m))
                # Oracle clairvoyant action threshold y: regret integrates to half squared error.
                self.assertAlmostEqual(integrated(m,y)-integrated(y,y),(m-y)**2/2)

    def test_complete_grid_and_direction(self):
        rows=[dict(y=.01,means=dict(candidate=.01,ewma_t5=0,rolling_t5=0))]
        r=analyze(rows)
        self.assertEqual(len(r['cost_grid']),len(COSTS))
        self.assertGreater(r['cost_grid'][0]['advantages']['ewma_t5'],0)
        self.assertEqual(r['cost_grid'][-1]['advantages']['ewma_t5'],0)
        self.assertEqual(r['cost_grid'][0]['arms']['ewma_t5']['disagreement_with_candidate'],1)

if __name__=='__main__': unittest.main()
