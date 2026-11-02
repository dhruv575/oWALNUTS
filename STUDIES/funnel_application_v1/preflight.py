from backend import *
from scipy.special import expit
def independent(p,data):
    mu,tau=p[:2];theta=p[2:];z=(theta-mu)/tau
    return -mu*mu/8+np.log(tau)-tau*tau/2+np.sum(np.array(data['y'])*theta-np.array(data['n'])*np.logaddexp(0,theta)-.5*z*z-np.log(tau))
rows=[]
for case in ['weak','mixed']:
    data=json.loads((BASE/(case+'.json')).read_text());backends=[Backend(data,s,956001001) for s in ['centered','noncentered','hybrid']]
    physical=to_physical(backends[0].starts,data,'centered')
    for b in backends:assert np.allclose(to_physical(b.starts,data,b.space),physical,atol=1e-12)
    for p in physical:
        for b in backends:
            q=from_physical(p,data,b.space);lp,g=b.value(q);expected=independent(p,data)+(~flags(data,b.space)).sum()*np.log(p[1]);value_error=abs(lp-expected);fd=[]
            for i in range(14):
                delta=np.eye(14)[i]*1e-6;v=(b.value(q+delta)[0]-b.value(q-delta)[0])/2e-6;fd.append(abs(v-g[i])/max(1,abs(g[i])))
            assert value_error<1e-8 and max(fd)<1e-5
            rows.append(dict(case=case,space=b.space,tau=float(p[1]),value_error=float(value_error),gradient_error=float(max(fd))))
    for b in backends:b.close()
(BASE/'PREFLIGHT.json').write_text(json.dumps(dict(passed=True,rows=rows),indent=2));print('preflight passed')
