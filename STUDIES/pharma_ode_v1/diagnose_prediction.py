import json,numpy as np
from backend import Backend,ROOT,DP
from scipy.integrate import solve_ivp
data=json.loads((ROOT/'data/theoph_1.json').read_text());prep=json.loads((ROOT/'prepared/theoph_1.json').read_text());b=Backend(data)
qs=np.random.default_rng(875100099).normal(size=(16000,data['P']))@np.array(prep['L']).T+prep['mode']
for i,q in enumerate(qs):
    try:b.predict(q)
    except ValueError:
        raw=np.empty(data['Npred']);b.lib.predict(b.ptr,q.ctypes.data_as(DP),raw.ctypes.data_as(DP))
        ka,km,vm,v,sigma=np.exp(q);times=np.array(data['pred_times'])
        # Condition a log-state continuation at the first positive prediction time.
        initial=raw[0]
        def rhs(t,y):return [np.exp(np.log(ka*data['dose']/v)-ka*t-y[0])-vm/v/(km+np.exp(y[0]))]
        sol=solve_ivp(rhs,(times[0],times[-1]),[initial],t_eval=times,rtol=1e-10,atol=1e-11,method='DOP853')
        result=dict(index=i,q=q.tolist(),legacy_log_prediction=[float(x) if np.isfinite(x) else None for x in raw],log_state_prediction=sol.y[0].tolist(),solver_success=sol.success)
        (ROOT/'PREDICTION-FAILURE-DIAGNOSIS.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));break
b.close()
