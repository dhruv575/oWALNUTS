import unittest

import run_phase_c as C


class Tests(unittest.TestCase):
    def test_matrix(self):
        cells = C.cells()
        self.assertEqual(len(cells), 12)
        self.assertEqual(len({c["case_id"] for c in cells}), 12)
        self.assertFalse({c["seed"] for c in cells} & {90101, 90102, 90103})
        firsts = [cells[i]["arm"] for i in range(0, 12, 2)]
        self.assertEqual(firsts, ["serialised", "unserialised", "serialised"] * 2)
        for i in range(0, 12, 2):
            self.assertEqual(cells[i]["seed"], cells[i + 1]["seed"])
            self.assertNotEqual(cells[i]["arm"], cells[i + 1]["arm"])


if __name__ == "__main__":
    unittest.main()
