import csv
import tempfile
import unittest
from pathlib import Path
from ingest import ingest


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'panel.csv'
        self.meta={k:'documented' for k in ['source','rights','x_units','y_units',
            'feature_construction','flow_classification','universe_selection']}
        self.rows=[dict(origin=f'2026-01-0{i+1}T00:00:00Z',group=g,
            feature_available=f'2026-01-0{i+1}T00:00:00Z',
            target_end=f'2026-01-0{i+2}T00:00:00Z',x=i+1,y=2*i+int(g))
            for i in range(4) for g in ['0','1']]
        for row in self.rows:row['target_available']=row['target_end']

    def run_ingest(self):
        with self.path.open('w',newline='') as h:
            writer=csv.DictWriter(h,fieldnames=self.rows[0]); writer.writeheader(); writer.writerows(self.rows)
        return ingest(self.path,self.meta,3)

    def test_scaling_never_uses_holdout(self):
        first=self.run_ingest()
        self.rows[-1]['x']=10000; self.rows[-1]['y']=-10000
        second=self.run_ingest()
        self.assertEqual(first['scaling'],second['scaling'])
        self.assertEqual(first['data'],second['data'])
        self.assertNotEqual(first['provenance']['sha256'],second['provenance']['sha256'])

    def test_leakage_rejected(self):
        self.rows[0]['feature_available']='2026-01-02T00:00:00Z'
        with self.assertRaisesRegex(ValueError,'leakage'): self.run_ingest()

    def test_missing_group_rejected(self):
        self.rows.pop()
        with self.assertRaisesRegex(ValueError,'unbalanced'): self.run_ingest()

    def test_duplicate_rejected(self):
        self.rows.append(self.rows[0])
        with self.assertRaisesRegex(ValueError,'duplicate'): self.run_ingest()

    def test_delayed_training_outcome_is_not_available_at_cutoff(self):
        self.rows[4]['target_available']='2026-01-04T00:15:00Z'
        with self.assertRaisesRegex(ValueError,'training outcomes unavailable'):self.run_ingest()


if __name__=='__main__': unittest.main()
