import csv
import json
from pathlib import Path
import tempfile
import unittest
from rolling_fixtures import prepare,no_flow


class RollingTests(unittest.TestCase):
    def test_windows_refit_scaling_without_future_outcomes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'panel.csv'
            rows=[dict(origin=f'2026-01-0{i+1}T00:00:00Z',group='A',
                feature_available=f'2026-01-0{i+1}T00:00:00Z',target_end=f'2026-01-0{i+2}T00:00:00Z',x=i,y=i*i)
                for i in range(6)]
            for row in rows:row['target_available']=row['target_end']
            metadata={k:'declared' for k in ['source','rights','x_units','y_units','feature_construction','flow_classification','universe_selection']}
            def write():
                with source.open('w',newline='') as h:
                    w=csv.DictWriter(h,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
            write();a=prepare(source,metadata,root/'a',3)
            self.assertEqual(len(a['expected']),3)
            f=json.loads(Path(a['expected'][0]['fixture']).read_text())
            self.assertEqual(len(f['holdout']['y']),1)
            rows[3]['y']=100000
            write();b=prepare(source,metadata,root/'b',3)
            changed=json.loads(Path(b['expected'][0]['fixture']).read_text())
            self.assertEqual(f['data'],changed['data'])
            self.assertEqual(f['scaling'],changed['scaling'])
            self.assertNotEqual(f['holdout']['y'],changed['holdout']['y'])

    def test_ablation_keeps_outcomes_and_cannot_enter_sbc(self):
        f={'data':{'x':[[1.]],'y':[[2.]]},'holdout':{'x':[[3.]],'y':[[4.]]},'truth':[1.],'prior_predictive':True}
        a=no_flow(f)
        self.assertEqual(a['data']['y'],f['data']['y'])
        self.assertEqual(a['holdout']['x'],[[0.]])
        self.assertNotIn('truth',a)
        self.assertFalse(a['prior_predictive'])
        self.assertEqual(f['data']['x'],[[1.]])


if __name__=='__main__':unittest.main()
