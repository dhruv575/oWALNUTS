"""Bounded full predictive-return diagnostic; see PLAN.md. No sampling."""
import argparse
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy
from numpy.polynomial.hermite import hermgauss
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.special import stdtr

HERE = Path(__file__).resolve().parent
PS = (.05,.5,.95)
CACHE_LIMIT = 128*1024*1024


def identity(path):
    b = path.read_bytes()
    return dict(path=str(path.resolve()),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())


class ReturnCDF:
    def __init__(self,m,sigma,beta,nu,nodes,deadline,cache_budget,chunk=512):
        self.m,self.sigma,self.beta = [np.asarray(x,dtype=float).ravel() for x in (m,sigma,beta)]
        if not len(self.m) or self.m.shape!=self.sigma.shape or self.m.shape!=self.beta.shape:
            raise ValueError('parameter shape mismatch')
        if not all(np.isfinite(x).all() for x in (self.m,self.sigma,self.beta)) or np.any(self.sigma<=0):
            raise ValueError('nonfinite parameter or nonpositive innovation scale')
        if not np.isfinite(nu) or nu<=0:
            raise ValueError('invalid Student-t degrees of freedom')
        self.nu,self.nodes,self.deadline,self.chunk = nu,nodes,deadline,chunk
        z,w = hermgauss(nodes)
        self.z,self.weights = np.sqrt(2)*z,w/np.sqrt(np.pi)
        if np.any(self.weights<=0) or abs(self.weights.sum()-1)>1e-12:
            raise ValueError('invalid quadrature weights')
        self.calls,self.student_t_evaluations,self.cached_bytes = 0,0,0
        self.cache = {}
        for lo in range(0,len(self.m),chunk):
            hi = min(lo+chunk,len(self.m))
            needed = (hi-lo)*nodes*8
            if needed<=cache_budget-self.cached_bytes:
                self.cache[lo] = self.inverse_scales(lo,hi)
                self.cached_bytes += needed

    def budget(self):
        if time.perf_counter()>=self.deadline:
            raise TimeoutError('five-minute local processing ceiling')

    def inverse_scales(self,lo,hi):
        self.budget()
        with np.errstate(over='raise',invalid='raise',under='ignore'):
            h = self.m[lo:hi,None]+self.sigma[lo:hi,None]*self.z
            inv = np.exp(-h/2)
        if not np.isfinite(inv).all() or np.any(inv<=0):
            raise ValueError('inverse scale outside supported floating-point range')
        return inv

    def __call__(self,x):
        if not np.isfinite(x):
            raise ValueError('nonfinite CDF argument')
        self.calls += 1
        total = 0.0
        for lo in range(0,len(self.m),self.chunk):
            self.budget()
            hi = min(lo+self.chunk,len(self.m))
            inv = self.cache.get(lo)
            if inv is None:
                inv = self.inverse_scales(lo,hi)
            with np.errstate(over='raise',invalid='raise'):
                standardized = (x-self.beta[lo:hi,None])*inv
            c = stdtr(self.nu,standardized)
            total += float(np.sum(c@self.weights))
            self.student_t_evaluations += c.size
        result = total/len(self.m)
        if not np.isfinite(result) or not 0<=result<=1:
            raise ValueError('invalid numerical CDF')
        return result

    def quantiles(self):
        center = float(np.median(self.beta))
        width = max(float(np.exp(np.median(self.m)/2)),float(np.std(self.beta)),1e-10)
        for expansion in range(61):
            lo,hi = center-width,center+width
            if not np.isfinite([lo,hi]).all():
                raise ValueError('quantile bracket overflow')
            flo,fhi = self(lo),self(hi)
            if flo<min(PS) and fhi>max(PS):
                break
            width *= 2
        else:
            raise ValueError('failed to bracket predictive quantiles')
        q = [brentq(lambda x:self(x)-p,lo,hi,xtol=1e-12,rtol=1e-12) for p in PS]
        residuals = [abs(self(x)-p) for x,p in zip(q,PS)]
        if max(residuals)>1e-8 or not q[0]<q[1]<q[2]:
            raise ValueError('quantile root or monotonicity failure')
        return dict(probabilities=list(PS),quantiles=q,residuals=residuals,
                    bracket=[lo,hi],bracket_expansions=expansion,cdf_evaluations=self.calls,
                    student_t_evaluations=self.student_t_evaluations,cached_bytes=self.cached_bytes)


def independent_cdf(x,m,sigma,beta,nu):
    pieces,errors = [],[]
    for mm,ss,bb in zip(m,sigma,beta):
        value,error = quad(lambda z:stdtr(nu,(x-bb)*np.exp(-(mm+ss*z)/2))
            *np.exp(-z*z/2)/np.sqrt(2*np.pi),-12,12,epsabs=1e-12,epsrel=1e-12)
        if error>1e-10:
            raise ValueError('independent quadrature error too large')
        pieces.append(value)
        errors.append(error)
    return float(np.mean(pieces)),float(max(errors))


def validate(deadline):
    fixtures = [([-10.6],[.2],[.001]),([-9.6],[.4],[-.002]),
                ([-11,-8.8],[.2,1.4],[-.001,.002])]
    results = []
    for i,args in enumerate(fixtures):
        matrices = [np.array(a,dtype=float) for a in args]
        cdfs = [ReturnCDF(*matrices,5,n,deadline,CACHE_LIMIT) for n in (64,128)]
        qs = [cdf.quantiles() for cdf in cdfs]
        checks = []
        for p,q in zip(PS,qs[1]['quantiles']):
            independent,error = independent_cdf(q,*matrices,5)
            discrepancy = abs(independent-p)
            if discrepancy>1e-7:
                raise ValueError('independent predictive CDF fixture failed')
            checks.append(dict(p=p,quad_error=error,cdf_discrepancy=discrepancy))
        if len(args[0])==1 and abs(qs[1]['quantiles'][1]-args[2][0])>1e-10:
            raise ValueError('symmetric median fixture failed')
        results.append(dict(fixture=i,rules=qs,independent_checks=checks))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate-only',action='store_true')
    parser.add_argument('--study',type=Path,help='WP97 source directory with protocol.json')
    parser.add_argument('--cells',type=Path,help='Read-only WP97 cell artifacts directory')
    parser.add_argument('--out',type=Path,default=HERE)
    args = parser.parse_args()
    filename = 'fixture-results.json' if args.validate_only else 'smoke-results.json'
    target = args.out/filename
    if target.exists():
        raise SystemExit(f'Preserving existing {target}; use a new output directory')
    if not args.validate_only and (args.study is None or args.cells is None):
        parser.error('--study and --cells are required for the fixed one-origin smoke')
    start = time.perf_counter()
    deadline = start+300
    result = dict(kind='diagnostic only; no calibration, inference qualification or trading claim',
        created_utc=datetime.now(timezone.utc).isoformat(),status='pending',mode='fixtures' if args.validate_only else 'one-origin',
        source=identity(Path(__file__)),plan=identity(HERE/'PLAN.md'),
        environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform()),
        cache_limit_bytes=CACHE_LIMIT,local_timing_only=True)
    sources,cdfs = [],[]
    try:
        result['fixtures'] = validate(deadline)
        if not args.validate_only:
            proto_path = args.study/'protocol.json'
            cell = args.cells/'ref-real-lo'
            log = cell/'ticks.jsonl'
            sources = [identity(proto_path),identity(log)]
            proto = json.loads(proto_path.read_text())
            records = [json.loads(line) for line in log.read_text().splitlines()]
            selected = [r for r in records if r.get('tick')==2]
            if len(selected)!=1 or selected[0].get('status')!='ok':
                raise ValueError('fixed ref-real-lo tick2 unavailable, duplicated or original gate failed')
            rec = selected[0]
            raw_path = cell/rec['file']
            if raw_path.resolve().parent!=cell.resolve():
                raise ValueError('raw filename escapes cell directory')
            sources.append(identity(raw_path))
            raw = np.frombuffer(raw_path.read_bytes(),dtype='<f4')
            if raw.size!=rec['chains']*rec['draws']*4:
                raise ValueError('WP97 compact four-field shape mismatch')
            a = raw.reshape(rec['chains'],rec['draws'],4)[rec['kept']].astype(float)
            mu,log_sigma,beta,h_last = [a[...,i].ravel() for i in range(4)]
            m = mu+proto['model']['rho']*(h_last-mu)
            sigma = np.exp(log_sigma)
            result['original_record'] = rec
            result['selected_components'] = len(m)
            rules = {}
            for nodes in (64,128):
                begin = time.perf_counter()
                remaining = CACHE_LIMIT-sum(c.cached_bytes for c in cdfs)
                cdf = ReturnCDF(m,sigma,beta,proto['model']['nu'],nodes,deadline,remaining)
                cdfs.append(cdf)
                rules[str(nodes)] = cdf.quantiles()
                rules[str(nodes)]['local_processing_seconds'] = time.perf_counter()-begin
                result['rules'] = rules
            q64,q128 = np.array(rules['64']['quantiles']),np.array(rules['128']['quantiles'])
            differences = [abs(cdfs[1](q)-p) for q,p in zip(q64,PS)]
            result['node_comparison'] = dict(cdf_discrepancy_at_64_roots=differences,
                endpoint_difference_over_128_interval_width=((q64-q128)/(q128[2]-q128[0])).tolist(),
                within_diagnostic_cdf_tolerance=max(differences)<=1e-6,
                caveat='64/128 agreement is a numerical diagnostic, not an error bound or posterior MCSE')
            result['status'] = 'completed' if max(differences)<=1e-6 else 'quadrature_disagreement'
        else:
            result['status'] = 'fixtures_passed'
    except Exception as exc:
        result.update(status='budget_exhausted' if isinstance(exc,TimeoutError) else 'failed',error=str(exc))
    result['input_identities'] = sources
    result['input_integrity_after'] = all(identity(Path(p['path']))['sha256']==p['sha256'] for p in sources)
    if not result['input_integrity_after']:
        result['status'] = 'input_changed'
    result['processing_stats'] = [dict(nodes=c.nodes,cdf_evaluations=c.calls,
        student_t_evaluations=c.student_t_evaluations,cached_bytes=c.cached_bytes) for c in cdfs]
    result['total_local_processing_seconds'] = time.perf_counter()-start
    args.out.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(result,handle,indent=2,allow_nan=False)
        handle.write('\n')
    print(json.dumps(dict(status=result['status'],seconds=result['total_local_processing_seconds'],output=str(target))))
    if result['status'] not in ('completed','fixtures_passed'):
        raise SystemExit(1)


if __name__=='__main__':
    main()
