import math,unittest
from scipy.optimize import minimize_scalar
from pool import Pool,replay

class Accounting(unittest.TestCase):
    def test_zero_fee_closed_form(self):
        for price in (.01,.5,1,2,100):
            p=Pool(1,1);q,t=p.arbitrage(price,0)
            self.assertAlmostEqual(q.base,1/math.sqrt(price))
            self.assertAlmostEqual(q.quote,math.sqrt(price))
            self.assertAlmostEqual(t['counterparty_profit'],(math.sqrt(price)-1)**2)

    def test_no_trade_band(self):
        p=Pool(2,6);fee=.01
        for price in (2.97,3.,3/.99):
            q,t=p.arbitrage(price,fee)
            self.assertEqual(q,p);self.assertEqual(t['input'],0)

    def test_token_and_value_conservation(self):
        p=Pool(2,6)
        for side in ('base','quote'):
            q,t=p.swap(side,.2,.003,3)
            if side=='base':
                self.assertAlmostEqual(q.base-p.base,.2);self.assertAlmostEqual(p.quote-q.quote,t['output'])
            else:
                self.assertAlmostEqual(q.quote-p.quote,.2);self.assertAlmostEqual(p.base-q.base,t['output'])
            self.assertGreater(q.base*q.quote,p.base*p.quote)
            self.assertAlmostEqual(t['pool_trade_pnl'],-t['counterparty_profit'])

    def test_independent_profit_optimizer(self):
        p=Pool(1.7,3.2)
        for price in (.1,.8,1.8,2.,3.,20):
            for fee in (0,.0005,.003,.03):
                q,t=p.arbitrage(price,fee)
                candidates=[0.]
                for side in ('base','quote'):
                    def objective(a):
                        g=1-fee
                        if side=='quote':return a-price*p.base*g*a/(p.quote+g*a)
                        return price*a-p.quote*g*a/(p.base+g*a)
                    opt=minimize_scalar(objective,bounds=(0,1000),method='bounded',options={'xatol':1e-12})
                    candidates.append(-opt.fun)
                self.assertAlmostEqual(t['counterparty_profit'],max(candidates),places=9)

    def test_self_financing_path(self):
        r=replay(Pool(1,1),[1,2,.5,3,1],[.003]*4)
        self.assertAlmostEqual(r['final_value']-r['initial_value'],r['inventory_pnl']+r['trade_pnl'])
        self.assertLess(r['trade_pnl'],0)
        self.assertTrue(all(x['trade']['retained_fee']>0 for x in r['rows']))

    def test_invalid(self):
        for fee in (-.1,1,float('nan')):
            with self.assertRaises(ValueError):Pool(1,1).arbitrage(1,fee)
        with self.assertRaises(ValueError):Pool(0,1)

if __name__=='__main__':unittest.main()
