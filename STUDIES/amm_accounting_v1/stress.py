"""Fixed deterministic engineering grid; never a trading-performance study."""
import concurrent.futures,hashlib,itertools,json,math,os,platform,time
from pathlib import Path
from scipy.optimize import minimize_scalar
from pool import Pool

def check(args):
    logx,logratio,shock,fee=args;x=math.exp(logx);y=x*math.exp(logratio);p=math.exp(logratio+shock)
    before=Pool(x,y);after,t=before.arbitrage(p,fee);scale=before.value(p)
    conservation=abs(t['pool_trade_pnl']+t['counterparty_profit'])/scale
    invariant=max(0,1-after.base*after.quote/(x*y))
    # Independent normalized 1:1 pool optimizer, then use reserve homogeneity.
    external=math.exp(shock);g=1-fee;candidates=[0.]
    for side in ('base','quote'):
        def objective(a):
            output=g*a/(1+g*a)
            return a-external*output if side=='quote' else external*a-output
        opt=minimize_scalar(objective,bounds=(0,1000),method='bounded',options={'xatol':1e-12})
        if not opt.success:raise ValueError('Oracle optimizer failed')
        candidates.append(-opt.fun)
    oracle=max(candidates)*y
    discrepancy=abs(oracle-t['counterparty_profit'])/scale
    ratio=after.quote/after.base
    band=max(0,(g*ratio-p)/p,(p-ratio/g)/p)
    if max(conservation,invariant,discrepancy,band)>1e-10 or t['counterparty_profit'] < -1e-10*scale:
        raise ValueError(dict(case=args,conservation=conservation,invariant=invariant,oracle=discrepancy,band=band))
    return dict(conservation=conservation,invariant=invariant,oracle=discrepancy,band=band)

if __name__=='__main__':
    start=time.monotonic()
    grid=list(itertools.product((-6,-3,0,3,6),(-6,-3,0,3,6),(-5,-1,-.1,-.01,-.001,0,.001,.01,.1,1,5),(0,.0001,.003,.03,.2)))
    workers=min(12,os.cpu_count() or 1)
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as ex:results=list(ex.map(check,grid,chunksize=25))
    result=dict(status='passed',cases=len(grid),workers=workers,elapsed_seconds=time.monotonic()-start,
                maxima={k:max(r[k] for r in results) for k in results[0]},python=platform.python_version(),
                source_hashes={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ('pool.py','stress.py','test_pool.py','PLAN.md')},
                scope='Deterministic accounting/optimizer checks only; no forecast or profit evidence')
    with Path('stress-results.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))
