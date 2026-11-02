import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
import json,time,sys
from pathlib import Path
import numpy as np
from grid import GridGP,JITTER

def main(data_path,out):
    data=json.loads(Path(data_path).read_text());a=GridGP(data);b=GridGP(data,dense=True)
    rng=np.random.default_rng(954000001);rows=[];points=[]
    for rho in [.3,.7,1.,2.]:
        q=rng.normal(0,.2,data['N']+5);q[:2]=[np.log(rho),np.log(1.2)];points.append(q)
        av,ag=a.evaluate(q);bv,bg=b.evaluate(q)
        factor=a.factor(q[:2]);s=np.column_stack([a.apply(factor,e) for e in np.eye(a.n)])
        k=1.2**2*np.exp(-.5*a.dist/rho**2)+np.eye(a.n)*JITTER
        errors=[]
        for j in [0,1,2,5,len(q)-1]:
            p=q.copy();m=q.copy();p[j]+=1e-4;m[j]-=1e-4
            fd=(a.evaluate(p)[0]-a.evaluate(m)[0])/2e-4
            errors.append(float(abs(fd-ag[j])/max(1.,abs(ag[j]))))
        rows.append(dict(rho=rho,density_error=float(abs(av-bv)),gradient_error=float(np.max(abs(ag-bg)/np.maximum(1,abs(bg)))),finite_difference_error=max(errors),covariance_error=float(np.max(abs(s@s.T-k)))))
    timings=[]
    for repeat in range(5):
        row={}
        for name,model in [('dense',b),('grid',a)] if repeat%2==0 else [('grid',a),('dense',b)]:
            t=time.perf_counter()
            for _ in range(10):
                for q in points:model.evaluate(q)
            row[name]=(time.perf_counter()-t)/40
        timings.append(row)
    passed=all(r['density_error']<=1e-5 and r['gradient_error']<=1e-3 and r['finite_difference_error']<=1e-3 and r['covariance_error']<=1e-10 for r in rows)
    result=dict(passed=passed,rows=rows,seconds_per_evaluation=timings,grid=[a.nx,a.ny],scope='Dense versus grid symmetric whitening; no posterior or Stan-speed claim')
    Path(out).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
    return 0 if passed else 1
if __name__=='__main__':sys.exit(main(*sys.argv[1:]))
