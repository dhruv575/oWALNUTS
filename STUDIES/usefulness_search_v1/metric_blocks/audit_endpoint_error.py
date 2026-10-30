import hashlib,json,math
from pathlib import Path
p=Path(__file__).resolve().parent;r=p/'local_recovery/endpoint_error_audit01';r.mkdir(exist_ok=False)
def step(q,v,h):
    g=-q;Q=q+h*v+h*h*g/2;G=-Q;P=v+h*(g+G)/2
    Q3=q+h*v+h*h*(g/3+G/6);P3=v+h*(g/6+2*((g+G)/2)/3+G/6)
    return Q,P,Q3,P3,h*h*abs(G-g)/6
rows=[]
for q,v in [(1.,0.),(0.,1.)]:
    samples=[]
    for h in [.2,.1,.05,.025,.0125]:
        Q,P,Q3,P3,e=step(q,v,h);b=step(Q,-P,h)
        assert abs(P-P3)<1e-15 and abs(abs(Q-Q3)-e)<1e-15
        assert abs(b[0]-q)<1e-15 and abs(b[1]+v)<1e-15 and abs(b[4]-e)<1e-15
        qe=abs(Q-(q*math.cos(h)+v*math.sin(h)));pe=abs(P-(-q*math.sin(h)+v*math.cos(h)))
        samples.append(dict(h=h,indicator=e,position_error=qe,momentum_error=pe,indicator_to_phase_error=e/max(qe,pe)))
    orders={key:[math.log(a[key]/b[key],2) for a,b in zip(samples,samples[1:])] for key in ['indicator','position_error','momentum_error']}
    assert all(abs(x-(4 if q else 3))<.01 for x in orders['indicator'])
    assert all(abs(x-(3 if q else 4))<.01 for x in orders['momentum_error'])
    if q:assert samples[-1]['indicator_to_phase_error']<.013
    rows.append(dict(initial=[q,v],samples=samples,orders=orders))
out=dict(passed=True,conclusion='Midpoint-average substitution loses leading momentum-error information at oscillator turning points; not a general endpoint-estimator impossibility result.',rows=rows,source_hashes={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ['audit_endpoint_error.py','ENDPOINT-ERROR-AUDIT.md']})
(r/'SUMMARY.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
