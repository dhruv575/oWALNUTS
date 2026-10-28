import unittest
from confirmation_calendar import schedule

class CalendarTests(unittest.TestCase):
    def test_complete_causal_grid(self):
        p=schedule();rows=p['cells']
        self.assertEqual(len(rows),3050)
        for month,n in [('2025-09',1440),('2025-10',1488)]:
            primary=[r for r in rows if r['month']==month and r['primary']]
            self.assertEqual([r['tick'] for r in primary],list(range(1,n+1)))
            self.assertTrue(all(b['origin_ms']-a['origin_ms']==1800000 for a,b in zip(primary,primary[1:])))
        for r in rows:
            self.assertEqual(r['window_stop']-r['window_start'],250)
            self.assertEqual(r['label_index'],r['window_stop'])
            self.assertEqual(r['label_available_ms']-r['origin_ms'],1800000)
        for cap in [.5,2.]:
            subset=[r for r in rows if r['cap']==cap]
            self.assertEqual(len(subset),61)
            self.assertTrue(all((r['tick']-1)%48==0 for r in subset))

    def test_seed_slots_disjoint(self):
        p=schedule();seeds=[r[k] for r in p['cells'] for k in ['nuts_seed','stan_data_seed','walnuts_seed']]
        self.assertEqual(len(seeds),len(set(seeds)))
        self.assertLess(max(seeds),p['bootstrap_seed_reservation'][0])

if __name__=='__main__':unittest.main()
