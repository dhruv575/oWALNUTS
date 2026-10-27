import copy,unittest
import numpy as np
from report import summarize,N,ARMS

class ReportFixtures(unittest.TestCase):
    def ledger(self):
        return [dict(tick=i,arms={arm:dict(status='ok',logpdf=3-j,pit=.5,forecast_seconds=.1+j) for j,arm in enumerate(ARMS)}) for i in range(1,N+1)]
    def starts(self,length,count):return np.zeros((count,int(np.ceil(N/length))),dtype=int)
    def test_fixed_pairing_and_all_block_outputs_without_rng(self):
        r=summarize(self.ledger(),replicates=2,seed=17,starts_provider=self.starts)
        self.assertEqual(r['planned_forecasts'],4464)
        for name,value in [('candidate_minus_rolling_t5',1.),('candidate_minus_ewma_t5',2.)]:
            s=r['paired'][name];self.assertEqual(s['full_mean'],value)
            self.assertEqual(s['daily_means'],[value]*31)
            self.assertEqual(s['block_intervals'],{str(k):[value,value] for k in [24,48,96]})
    def test_missing_retains_denominators_and_independent_arms(self):
        rows=self.ledger();rows[70]['arms']['candidate']=dict(status='unavailable',forecast_seconds=.2)
        r=summarize(rows,replicates=2,seed=17,starts_provider=self.starts)
        s=r['paired']['candidate_minus_rolling_t5'];self.assertIsNone(s['full_mean']);self.assertEqual(s['available_origins'],1487)
        self.assertEqual(s['block_intervals'],{str(k):None for k in [24,48,96]})
        self.assertEqual(r['arms']['rolling_t5']['logscore']['available_origins'],1488)
        self.assertEqual(r['arms']['candidate']['costs']['forecast_seconds']['measured_origins'],1488)
    def test_duplicate_and_invalid_scores_rejected(self):
        rows=self.ledger();rows[1]=copy.deepcopy(rows[0])
        with self.assertRaises(ValueError):summarize(rows,replicates=2,starts_provider=self.starts)
        rows=self.ledger();rows[0]['arms']['candidate']['pit']=1.1
        with self.assertRaises(ValueError):summarize(rows,replicates=2,starts_provider=self.starts)

    def test_wrapped_partial_block_uses_same_nonconstant_tick_vector(self):
        rows=self.ledger()
        for i,row in enumerate(rows):
            row['arms']['candidate']['logpdf']=float(i)
            row['arms']['rolling_t5']['logpdf']=float(i)/2
        def end_starts(length,count):return np.full((count,int(np.ceil(N/length))),N-1,dtype=int)
        result=summarize(rows,replicates=2,seed=17,starts_provider=end_starts)
        # L96:15 full [1487,0..94] blocks plus48 entries [1487,0..46].
        expected=(15*(1487+sum(range(95)))+1487+sum(range(47)))/1488
        self.assertEqual(result['arms']['candidate']['logscore']['block_intervals']['96'],[expected,expected])
        self.assertEqual(result['paired']['candidate_minus_rolling_t5']['block_intervals']['96'],[expected/2,expected/2])

if __name__=='__main__':unittest.main()
