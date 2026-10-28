"""Deterministic prior sensitivity, with no empirical bound selection."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from scipy.integrate import quad
from scipy.special import ndtr
from scipy.stats import norm


def run(out):
    out=Path(out);out.mkdir(exist_ok=False);m=np.log(.2);sd=.5;rho=.95;rows=[]
    for cap in (.5,1.,2.):
        upper=(np.log(cap)-m)/sd;mass=ndtr(upper)
        def weighted(z,k):return np.exp(k*(m+sd*z))*norm.pdf(z)/mass
        moments={}
        for k in (0,1,2):
            numerical,error=quad(lambda z:weighted(z,k),-14,upper,epsabs=1e-12,epsrel=1e-12)
            exact=np.exp(k*m+.5*k*k*sd*sd)*ndtr(upper-k*sd)/mass
            assert abs(numerical-exact)<1e-10 and error<1e-10
            moments[str(k)]=dict(value=float(exact),quadrature=float(numerical),absolute_error=float(abs(numerical-exact)))
        excursions={}
        for factor in (2.,10.,100.):
            # Volatility scale exp(h/2) relative to exp(mu/2), conditional
            # stationary AR deviation, marginalizing only sigma's prior.
            def event(z):
                sigma=np.exp(m+sd*z)
                threshold=2*np.log(factor)*np.sqrt(1-rho*rho)/sigma
                return 2*norm.sf(threshold)*norm.pdf(z)/mass
            value,error=quad(event,-14,upper,epsabs=1e-12,epsrel=1e-12)
            assert error<1e-10
            excursions[str(factor)]=dict(probability=float(value),quadrature_error=float(error))
        rows.append(dict(sigma_cap=cap,excluded_original_prior_mass=float(norm.sf(upper)),truncated_sigma_moments=moments,stationary_volatility_excursion_probabilities=excursions,stationary_95pct_volatility_factor_at_cap=float(np.exp(norm.ppf(.975)*cap/(2*np.sqrt(1-rho*rho))))))
    result=dict(rows=rows,log_sigma_prior_mean=float(m),log_sigma_prior_sd=sd,rho=rho,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='Prior-only sensitivity. Excursions mean volatility is above factor or below its reciprocal relative to exp(mu/2). No bound selected, no fit, no market justification.')
    (out/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':run(sys.argv[1])
