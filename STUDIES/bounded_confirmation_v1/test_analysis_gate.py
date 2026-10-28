import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'amm_accounting_v1'))
from confirmation_calendar import schedule
from analysis_gate import assess

class GateTests(unittest.TestCase):
    def fixture(self):
        calendar=schedule()['cells'];reports=[]
        for c in calendar:
            reports.append(dict(index=c['index'],cap=c['cap'],fixture={k:c[k] for k in ['month','tick','origin_ms','label_available_ms']},methods={m:dict(qualified=True) for m in ['nuts','walnuts']},comparisons=[dict(baseline=b,qualified=True,model=.1,inference=.001,total=.101) for b in ['rolling_t5','ewma_t5']]))
        return calendar,reports

    def test_missing_slot_blocks_analysis(self):
        c,r=self.fixture();result=assess(c,r[:-1]);self.assertFalse(result['primary_analysis_admitted']);self.assertEqual(result['missing'],[3049])

    def test_primary_failure_blocks_but_sensitivity_failure_disclosed(self):
        c,r=self.fixture();r[1]['methods']['nuts']['qualified']=False
        result=assess(c,r);self.assertTrue(result['primary_analysis_admitted']);self.assertEqual(len(result['diagnostic_failures']),1)
        r[0]['methods']['nuts']['qualified']=False
        self.assertFalse(assess(c,r)['primary_analysis_admitted'])

    def test_missing_baseline_and_duplicate_rejected(self):
        c,r=self.fixture();r[0]['comparisons']=[];self.assertFalse(assess(c,r)['primary_analysis_admitted'])
        with self.assertRaises(ValueError):assess(c,r+[r[0]])

if __name__=='__main__':unittest.main()
