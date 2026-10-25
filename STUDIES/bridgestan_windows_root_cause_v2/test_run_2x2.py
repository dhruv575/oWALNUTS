import unittest

import run_2x2 as R


class Tests(unittest.TestCase):
    def test_matrix(self):
        cells = R.cells()
        self.assertEqual(len(cells), 240)
        counts = {}
        for c in cells:
            counts[c["cell"]] = counts.get(c["cell"], 0) + 1
        self.assertEqual(set(counts.values()), {60})
        self.assertEqual(len({c["case_id"] for c in cells}), 240)
        self.assertFalse({c["seed"] for c in cells} & {90101, 90102, 90103})

    def test_latin_square_positions(self):
        cells = R.cells()
        position = {}
        for i in range(0, 240, 4):
            for j, c in enumerate(cells[i:i + 4]):
                position.setdefault(c["cell"], [0, 0, 0, 0])[j] += 1
        for counts in position.values():
            self.assertEqual(counts, [15, 15, 15, 15])

    def test_rc_forms(self):
        self.assertEqual(R.rc_forms(3221226356)["hex_32"], "0xC0000374")

    def test_fisher(self):
        self.assertAlmostEqual(R.fisher_one_sided(5, 120, 0, 120), 0.0300, places=3)
        self.assertEqual(R.fisher_one_sided(0, 120, 0, 120), 1.0)


if __name__ == "__main__":
    unittest.main()
