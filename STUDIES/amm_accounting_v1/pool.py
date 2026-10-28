"""Generic retained-input-fee pool; pathwise ledger, not expected-profit model."""
from dataclasses import dataclass
import math

def positive(v):
    if not math.isfinite(v) or v <= 0: raise ValueError('Positive finite value required')

@dataclass(frozen=True)
class Pool:
    base: float
    quote: float

    def __post_init__(self):
        positive(self.base);positive(self.quote)

    def value(self, price):
        positive(price)
        v=self.base*price+self.quote
        positive(v)
        return v

    def swap(self, side, amount, fee, price):
        if side not in ('base','quote'): raise ValueError('Invalid input token')
        if not math.isfinite(amount) or amount < 0: raise ValueError('Invalid amount')
        if not math.isfinite(fee) or not 0 <= fee < 1: raise ValueError('Invalid fee')
        positive(price)
        g=1-fee
        if side=='quote':
            out=self.base*(g*amount/(self.quote+g*amount))
            after=Pool(self.base-out,self.quote+amount)
            profit=price*out-amount
        else:
            out=self.quote*(g*amount/(self.base+g*amount))
            after=Pool(self.base+amount,self.quote-out)
            profit=out-price*amount
        if not all(map(math.isfinite,(out,profit,amount*fee))): raise ValueError('Nonfinite swap')
        return after,dict(side=side,input=amount,output=out,fee_token=side,retained_fee=amount*fee,
                         counterparty_profit=profit,pool_trade_pnl=after.value(price)-self.value(price))

    def arbitrage(self, price, fee):
        positive(price)
        if not math.isfinite(fee) or not 0 <= fee < 1: raise ValueError('Invalid fee')
        g=1-fee
        if price > self.quote/(g*self.base):
            amount=(math.sqrt(price*self.base*g*self.quote)-self.quote)/g
            return self.swap('quote',max(amount,0),fee,price)
        if price < g*self.quote/self.base:
            amount=(math.sqrt(self.quote*g*self.base/price)-self.base)/g
            return self.swap('base',max(amount,0),fee,price)
        return self,dict(side='none',input=0.,output=0.,fee_token=None,retained_fee=0.,
                         counterparty_profit=0.,pool_trade_pnl=0.)

def replay(initial, prices, fees):
    """One price move then one arb opportunity per event; no artificial endowment."""
    prices=list(prices);fees=list(fees)
    if len(prices)!=len(fees)+1 or not prices: raise ValueError('Event lengths')
    pool=initial;rows=[]
    for before_price,price,fee in zip(prices,prices[1:],fees):
        old=pool
        inventory_pnl=old.base*(price-before_price)
        pool,trade=old.arbitrage(price,fee)
        rows.append(dict(price=price,fee=fee,inventory_pnl=inventory_pnl,trade=trade,
                         base=pool.base,quote=pool.quote,value=pool.value(price)))
    return dict(initial_value=initial.value(prices[0]),final_value=pool.value(prices[-1]),
                inventory_pnl=math.fsum(r['inventory_pnl'] for r in rows),
                trade_pnl=math.fsum(r['trade']['pool_trade_pnl'] for r in rows),rows=rows)
