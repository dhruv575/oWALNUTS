import unittest
from reference_predictive import LABELS,contrasts


class PredictiveTests(unittest.TestCase):
    def fixture(self):
        values=dict(status='available',logpdf=2.,pit=.4,logpdf_mcse=.02,pit_mcse=.01)
        return [dict(method=m,label=y,**values) for m in range(2) for y in LABELS],[dict(label=y,**values) for y in LABELS]

    def test_fixed_slots_keep_missing_and_separate_mcse(self):
        a,b=self.fixture();b[1]['status']='unavailable';a[0]['logpdf']=1.
        result=contrasts(a,b)
        self.assertEqual(len(result),6)
        self.assertEqual(sum(r['status']=='unavailable' for r in result),2)
        self.assertEqual(result[0]['logpdf_difference'],-1.)
        self.assertEqual(result[0]['reference_logpdf_mcse'],.02)

    def test_duplicate_slots_rejected(self):
        a,b=self.fixture()
        with self.assertRaisesRegex(ValueError,'slots'):contrasts(a+[a[0]],b)


if __name__=='__main__':unittest.main()
