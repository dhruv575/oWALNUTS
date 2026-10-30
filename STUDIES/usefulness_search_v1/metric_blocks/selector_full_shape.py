import numpy as np
from selector import select as discover

def select(coarse, fine, variances):
    v=np.asarray(variances,dtype=float)
    incumbent=np.diag(v)
    _,info=discover(coarse,fine,v)
    if not info['blocks']:return incumbent,info
    h=np.asarray(fine,dtype=float);h=(h+h.transpose(0,2,1))/2
    result=incumbent.copy();scales=[]
    try:
        for ix in info['blocks']:
            q=h[:,ix,:][:,:,ix]
            mean=(q/np.trace(q,axis1=1,axis2=2)[:,None,None]).mean(0)
            block=np.linalg.inv(mean);block=(block+block.T)/2
            scale=float(np.exp(np.median(np.log(v[ix])-np.log(np.diag(block)))))
            result[np.ix_(ix,ix)]=scale*block;scales.append(scale)
        diagonal=np.diag(result)
        normalized=result/np.sqrt(np.outer(diagonal,diagonal))
        if not np.isfinite(result).all() or min(diagonal)<=0 or np.linalg.eigvalsh(normalized).min()<=1e-10:
            raise ValueError('invalid output')
    except (ValueError,np.linalg.LinAlgError,FloatingPointError):
        return incumbent,dict(reason='full_shape_output',blocks=[])
    return result,dict(info,block_scales=scales)
