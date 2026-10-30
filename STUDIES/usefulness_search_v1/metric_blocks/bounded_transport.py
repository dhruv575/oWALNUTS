import numpy as np
K=4.
def features(e,j):
    phi=K*np.tanh(e/K)
    return np.column_stack([e[:,i] for i in range(j)]+[phi[:,i]*phi[:,k] for i in range(j) for k in range(i,j)]) if j else np.empty((len(e),0))
def fit(q):
    mu=q.mean(0);cov=np.cov(q,rowvar=False);cov+=np.eye(q.shape[1])*np.trace(cov)/q.shape[1]*1e-6;L=np.linalg.cholesky(cov);e=np.linalg.solve(L,(q-mu).T).T;parts=[]
    for j in range(q.shape[1]):
        F=features(e,j);fm=F.mean(0);fs=F.std(0);fs=np.where(fs>1e-12,fs,1.);X=(F-fm)/fs;ym=e[:,j].mean();w=np.linalg.solve(X.T@X+10*np.eye(X.shape[1]),X.T@(e[:,j]-ym))/fs;intercept=ym-fm@w;res=e[:,j]-intercept-F@w;s=float(np.sqrt(np.mean(res*res)));assert .1<=s<=10;parts.append(dict(w=w.tolist(),intercept=float(intercept),s=s))
    return dict(mu=mu.tolist(),L=L.tolist(),parts=parts,K=K)
def encode(q,m,affine=False):
    assert m['K']==K;e=np.linalg.solve(np.asarray(m['L']),(q-np.asarray(m['mu'])).T).T
    if affine:return e
    return np.column_stack([(e[:,j]-v['intercept']-features(e,j)@v['w'])/v['s'] for j,v in enumerate(m['parts'])])
def decode(z,m):
    assert m['K']==K;e=np.zeros_like(z)
    for j,v in enumerate(m['parts']):e[:,j]=v['s']*z[:,j]+v['intercept']+features(e,j)@v['w']
    return e@np.asarray(m['L']).T+np.asarray(m['mu'])
def logdet(m,affine=False):return float(np.linalg.slogdet(np.asarray(m['L']))[1]+(0 if affine else sum(np.log(v['s']) for v in m['parts'])))
def derivative(e,j,v):
    phi=K*np.tanh(e/K);dp=1-(phi/K)**2;w=np.asarray(v['w']);der=np.broadcast_to(w[:j],(len(e),j)).copy();index=j
    for i in range(j):
        for k in range(i,j):der[:,i]+=w[index]*dp[:,i]*phi[:,k];der[:,k]+=w[index]*dp[:,k]*phi[:,i];index+=1
    return der
def score(q,g,m):
    ge=g@np.asarray(m['L']);e=encode(q,m,True);gz=np.empty_like(ge)
    for j in reversed(range(q.shape[1])):
        v=m['parts'][j];gz[:,j]=ge[:,j]*v['s'];ge[:,:j]+=ge[:,j,None]*derivative(e,j,v)
    return gz
def jacobian(q,m):
    e=encode(q,m,True);n,d=q.shape;J=np.zeros((n,d,d))
    for j,v in enumerate(m['parts']):
        if j:J[:,j,:]=np.einsum('ni,nik->nk',derivative(e,j,v),J[:,:j,:])
        J[:,j,j]+=v['s']
    return np.einsum('ij,njk->nik',np.asarray(m['L']),J)
def derivative_bound(m):
    d=len(m['parts']);B=np.zeros((d,d));S=np.diag([v['s'] for v in m['parts']])
    for j,v in enumerate(m['parts']):
        w=abs(np.asarray(v['w']));B[j,:j]=w[:j];index=j
        for i in range(j):
            for k in range(i,j):B[j,i]+=K*w[index];B[j,k]+=K*w[index];index+=1
    return abs(np.asarray(m['L']))@np.linalg.solve(np.eye(d)-B,S)
