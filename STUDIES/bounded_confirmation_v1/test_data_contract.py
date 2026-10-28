import unittest
import numpy as np
import data_contract as d

class ContractTests(unittest.TestCase):
    def bars(self):
        return [dict(open_ms=1756166400000+i*d.HALF,close_available_ms=1756166400000+(i+1)*d.HALF,close=float(np.exp(i/10000))) for i in range(3216)]

    def test_every_origin_label_is_after_window(self):
        bars=self.bars()
        for month in ['2025-09','2025-10']:
            spec=d.configure(month);y=d.panel_returns(bars,month)
            for t in range(1,spec['origins']+1):
                r=d.inputs(y,t)
                self.assertEqual(len(r['window']),250)
                self.assertEqual(r['label_index'],r['current_index']+1)
                current_bar=spec['close_start']+r['current_index']+1
                self.assertEqual(bars[current_bar]['close_available_ms'],r['origin_ms'])
                self.assertEqual(bars[current_bar+1]['close_available_ms'],r['label_available_ms'])
                altered=y.copy();altered[r['label_index']]=123
                np.testing.assert_array_equal(d.inputs(altered,t)['window'],r['window'])
            self.assertEqual(r['label_available_ms'],spec['first_origin_ms']+spec['origins']*d.HALF)

    def test_grid_and_invalid_close_rejected(self):
        bars=self.bars();bars[10]['open_ms']+=1
        with self.assertRaises(ValueError):d.panel_returns(bars,'2025-09')
        bars=self.bars();bars[50]['close']=0
        with self.assertRaises(ValueError):d.panel_returns(bars,'2025-09')

if __name__=='__main__':unittest.main()
