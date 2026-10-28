import unittest
from build_tables import records,render
class TableTests(unittest.TestCase):
    def test_complete_denominators_and_signs(self):
        rows=records()
        self.assertEqual(len(rows),44)
        self.assertEqual({k:sum(r['kind']==k for r in rows) for k in ('density','tail','decision')},dict(density=8,tail=24,decision=12))
        for r in rows:self.assertLessEqual(r['interval'][0],r['interval'][1])
        june=next(r for r in rows if r['kind']=='density' and r['month']=='2026-06' and r['control']=='ewma_t5')
        self.assertLess(june['interval'][0],0)
        feb=next(r for r in rows if r['kind']=='tail' and r['month']=='2026-02' and r['control']=='ewma_t5' and r['endpoint']=='short')
        self.assertLess(feb['mean'],0)
        april=next(r for r in rows if r['kind']=='decision' and r['month']=='2026-04' and r['control']=='ewma_t5')
        self.assertLess(april['mean'],0)
        self.assertEqual(render(rows).count('| 2026-'),40)
        self.assertEqual(render(rows).count('| 2025-12'),4)
if __name__=='__main__':unittest.main()
