import unittest
from calibration_design import coverage_interval, operating_characteristics


class CalibrationDesignTests(unittest.TestCase):
    def test_exact_extreme_bounds(self):
        self.assertEqual(coverage_interval(0,20)[0],0.)
        self.assertEqual(coverage_interval(20,20)[1],1.)
        self.assertAlmostEqual(coverage_interval(0,20)[1],1-.025**(1/20))

    def test_multiplicity_widens_bounds(self):
        single=coverage_interval(90,100,1)
        multiple=coverage_interval(90,100,6)
        self.assertLess(multiple[0],single[0])
        self.assertGreater(multiple[1],single[1])

    def test_small_smoke_cannot_qualify(self):
        result=operating_characteristics(100,family_size=6)
        self.assertIsNone(result['accepted_counts'])
        self.assertEqual(result['per_functional_probability_of_equivalence'],0.)

    def test_design_distinguishes_miscalibration(self):
        good=operating_characteristics(800,family_size=6)
        bad=operating_characteristics(800,family_size=6,actual=.8)
        self.assertGreater(good['per_functional_probability_of_equivalence'],.9)
        self.assertLess(bad['per_functional_probability_of_equivalence'],.001)


if __name__=='__main__':unittest.main()
