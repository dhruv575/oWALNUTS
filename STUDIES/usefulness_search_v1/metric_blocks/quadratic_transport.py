import numpy as np
def features(e,j):
    return np.column_stack([e[:,i] for i in range(j)]+[e[:,i]*e[:,k] for i in range(j) for k in range(i,j)]) if j else np.empty((len(e),0))
def fit(q):
    mu=q.mean(0);cov=np.cov(q,rowvar=False);cov+=np.eye(q.shape[1])*np.trace(cov)/q.shape[1]*1e-6;L=np.linalg.cholesky(cov);e=np.linalg.solve(L,(q-mu).T).T;parts=[]
    for j in range(q.shape[1]):
        F=features(e,j);fm=F.mean(0);fs=F.std(0);fs=np.where(fs>1e-12,fs,1.);X=(F-fm)/fs;ym=e[:,j].mean();w=np.linalg.solve(X.T@X+10*np.eye(X.shape[1]),X.T@(e[:,j]-ym))/fs;intercept=ym-fm@w;res=e[:,j]-intercept-F@w;s=float(np.sqrt(np.mean(res*res)));assert .1<=s<=10;parts.append(dict(w=w.tolist(),intercept=float(intercept),s=s))
    return dict(mu=mu.tolist(),L=L.tolist(),parts=parts)
def encode(q,m,affine=False):
    e=np.linalg.solve(np.asarray(m['L']),(q-np.asarray(m['mu'])).T).T
    if affine:return e
    return np.column_stack([(e[:,j]-v['intercept']-features(e,j)@v['w'])/v['s'] for j,v in enumerate(m['parts'])])
def decode(z,m):
    e=np.zeros_like(z)
    for j,v in enumerate(m['parts']):e[:,j]=v['s']*z[:,j]+v['intercept']+features(e,j)@v['w']
    return e@np.asarray(m['L']).T+np.asarray(m['mu'])
def logdet(m,affine=False):return float(np.linalg.slogdet(np.asarray(m['L']))[1]+(0 if affine else sum(np.log(v['s']) for v in m['parts'])))
def score(q,g,m,affine=False):
    ge=g@np.asarray(m['L'])
    if affine:return ge
    e=encode(q,m,True);gz=np.empty_like(ge)
    for j in reversed(range(q.shape[1])):
        v=m['parts'][j];w=np.asarray(v['w']);gz[:,j]=ge[:,j]*v['s'];der=np.broadcast_to(w[:j],(len(q),j)).copy();index=j
        for i in range(j):
            for k in range(i,j):
                der[:,i]+=w[index]*e[:,k];der[:,k]+=w[index]*e[:,i];index+=1
        ge[:,:j]+=ge[:,j,None]*der
    return gz
