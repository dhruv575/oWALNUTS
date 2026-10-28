import unittest
import numpy as np
from posterior_coverage import marginal


class CoverageTests(unittest.TestCase):
    def test_known_grid_and_outside_truth(self):
        grid = np.arange(1600, dtype=float).reshape(4, 400)
        draws = np.stack([grid]*4, axis=-1)
        result = marginal(draws, [799.5, -1, 1600, 799.5])
        self.assertEqual(result[0]['fraction_below_truth'], .5)
        self.assertTrue(all(v['covered'] for v in result[0]['intervals'].values()))
        self.assertFalse(any(v['covered'] for v in result[1]['intervals'].values()))
        self.assertFalse(any(v['covered'] for v in result[2]['intervals'].values()))

    def test_ties_and_invalid_shape(self):
        rows = marginal(np.zeros((4, 400, 4)), [0]*4)
        self.assertTrue(all(r['ties'] == 1600 for r in rows))
        with self.assertRaises(ValueError):
            marginal(np.zeros((1600, 4)), [0]*4)


if __name__ == '__main__':
    unittest.main()
