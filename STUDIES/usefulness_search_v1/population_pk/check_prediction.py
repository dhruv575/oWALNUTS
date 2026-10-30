import json
import numpy as np
from native import Native,ROOT
from predictive import prediction,data
b=Native();p=json.loads((ROOT/'PREPARED.json').read_text());m=json.loads((ROOT/'MODES.json').read_text());points=[np.array(p['mode']),np.array(m['secondary_mode'])]+[x for x in np.array(m['starts'])]
errors=[]
for q in points:
 errors.append(float(np.max(abs(prediction(q)-b.model.predict(q)[:,-2:].ravel()))))
weights,doses,c0,times,observed=data();q=np.array(p['mode']);q[6:-1]=0.;q[0]=1000.;q[1]=np.log(.1);q[2]=np.log(.5);limit_error=float(np.max(abs(prediction(q)-(np.log(c0[:,None]+doses[:,None]/(.5*weights[:,None]))-.1*times).ravel())));assert limit_error<1e-10;q[1]=1000.;assert np.isneginf(prediction(q)).all()
r=dict(instant_absorption_limit_error=limit_error,points=len(points),max_log_prediction_error=max(errors),passed=max(errors)<1e-6);(ROOT/'PREDICTION-CHECK.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));b.close();assert r['passed']
