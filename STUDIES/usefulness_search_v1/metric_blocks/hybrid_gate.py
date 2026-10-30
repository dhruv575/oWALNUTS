import numpy as np

def evaluate(x,y):
    """Leave-one-chain-out score prediction; no target names or outcomes."""
    x=np.asarray(x,dtype=float);y=np.asarray(y,dtype=float);folds=[]
    try:
        if x.ndim!=3 or x.shape!=y.shape or x.shape[0]!=4 or not np.isfinite(x).all() or not np.isfinite(y).all():
            raise ValueError('invalid pilot arrays')
        for held in range(4):
            train=[i for i in range(4) if i!=held];tx=x[train].reshape(-1,x.shape[-1]);ty=y[train].reshape(tx.shape)
            mean=tx.mean(0);scale=tx.std(0,ddof=1)
            if min(scale)<=0:raise ValueError('constant pilot coordinate')
            design=np.column_stack([np.ones(len(tx)),(tx-mean)/scale]);coef,_,rank,_=np.linalg.lstsq(design,ty,rcond=None)
            if rank!=design.shape[1]:raise ValueError('rank deficient design')
            pred=np.column_stack([np.ones(len(x[held])),(x[held]-mean)/scale])@coef;e=y[held]-pred
            centered=y[held]-y[held].mean(0);_,r=np.linalg.qr(centered,mode='reduced')
            if np.linalg.matrix_rank(r)!=x.shape[-1]:raise ValueError('rank deficient held-out scores')
            relative=np.linalg.solve(r.T,e.T).T;r2=1-float(np.linalg.norm(relative,ord=2)**2)
            if not np.isfinite(r2):raise ValueError('nonfinite R2')
            folds.append(dict(held_chain=held,worst_direction_r2=r2))
        return dict(use_fisher=all(f['worst_direction_r2']>0 for f in folds),folds=folds)
    except (ValueError,np.linalg.LinAlgError,FloatingPointError) as exc:
        return dict(use_fisher=False,folds=folds,reason=str(exc))
