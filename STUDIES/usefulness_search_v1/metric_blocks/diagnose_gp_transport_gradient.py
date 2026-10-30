import json
from pathlib import Path
import numpy as np,bridgestan as bs
from quadratic_transport import encode,decode,score,logdet
from native_common import model_files
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_transport_qualified01';f=r/'fold-0';m=json.loads((f/'MAP.json').read_text());a=np.load(f/'INPUTS.npz');q=a['q'];g=a['gradient'];z=encode(q,m);gz=score(q,g,m);so,data,_=model_files('gp_pois_regr-gp_pois_regr');target=bs.StanModel(str(so),data=data.read_text(),seed=1);rows=[]
for index in [0,len(q)//2,len(q)-1]:
    for h in [1e-2,1e-3,1e-4,1e-5,1e-6]:
        point=z[index:index+1];fd=[];jac=[]
        for j in range(13):
            d=np.zeros_like(point);d[0,j]=h;qa=decode(point+d,m);qb=decode(point-d,m);fd.append((target.log_density(qa[0])-target.log_density(qb[0]))/(2*h));jac.append((qa[0]-qb[0])/(2*h))
        error=float(np.max(abs(gz[index]-fd)/(1+abs(gz[index])+abs(np.asarray(fd)))));det_error=float(abs(np.linalg.det(np.asarray(jac).T)/np.exp(logdet(m))-1));rows.append(dict(index=index,h=h,gradient_error=error,determinant_error=det_error))
(r/'GRADIENT-DIAGNOSIS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows))
