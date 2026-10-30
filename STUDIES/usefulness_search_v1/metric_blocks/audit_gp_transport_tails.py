import hashlib,json
from pathlib import Path
import numpy as np
from quadratic_transport import encode,decode
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_transport_tail_audit01';r.mkdir(exist_ok=False);validation=json.loads((l/'gp_transport_validation01/SUMMARY.json').read_text());assert validation['completed'];rows=[];hashes={str(p/n):hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ['quadratic_transport.py','audit_gp_transport_tails.py','GP-TRANSPORT-TAIL-AUDIT-PROTOCOL.md']}
def jacobian(z,m):
    q=decode(z,m);e=encode(q,m,True);n,d=z.shape;J=np.zeros((n,d,d))
    for j,v in enumerate(m['parts']):
        w=np.asarray(v['w']);der=np.broadcast_to(w[:j],(n,j)).copy();index=j
        for i in range(j):
            for k in range(i,j):der[:,i]+=w[index]*e[:,k];der[:,k]+=w[index]*e[:,i];index+=1
        if j:J[:,j,:]=np.einsum('ni,nik->nk',der,J[:,:j,:])
        J[:,j,j]+=v['s']
    return q,np.einsum('ij,njk->nik',np.asarray(m['L']),J)
def quantiles(x):return np.quantile(x,[0,.5,.95,1]).tolist() if len(x) else None
for fold in range(4):
    mf=l/f'gp_transport_qualified02/fold-{fold}/MAP.json';m=json.loads(mf.read_text());hashes[str(mf)]=hashlib.sha256(mf.read_bytes()).hexdigest()
    for rep in range(2):
        d=l/f'gp_transport_validation01/{fold}-{rep}-quadratic-diag';f=d/'DRAWS-STATS.npz';sf=d/'SUMMARY.json';hashes[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest();hashes[str(sf)]=hashlib.sha256(sf.read_bytes()).hexdigest();s=json.loads(sf.read_text());a=np.load(f);z=a['sample_stats__unconstrained_draw'];div=a['sample_stats__diverging'].astype(bool);assert int(div.sum())==s['divergences'];q,J=jacobian(z.reshape(-1,13),m);sv=np.linalg.svd(J,compute_uv=False);assert np.isfinite(sv).all() and (sv[:,-1]>0).all();condition=(sv[:,0]/sv[:,-1]).reshape(4,2000);largest=sv[:,0].reshape(4,2000);q=q.reshape(4,2000,13);checks=[]
        for index in [0,4000,7999]:
            point=z.reshape(-1,13)[index:index+1];fd=[]
            for j in range(13):
                delta=np.zeros_like(point);delta[0,j]=1e-5;fd.append((decode(point+delta,m)[0]-decode(point-delta,m)[0])/2e-5)
            error=float(np.max(abs(J[index]-np.asarray(fd).T)/(1+abs(J[index]))));assert error<=1e-6;checks.append(error)
        rho=np.exp(q[:,:,0]);alpha=np.exp(q[:,:,1]);zmax=np.max(abs(z),axis=2);np.savez_compressed(r/f'{fold}-{rep}.npz',q=q,rho=rho,alpha=alpha,jacobian_condition=condition,jacobian_largest=largest,zmax=zmax,diverging=div);chains=[]
        for chain in range(4):
            groups={}
            for label,mask in [('all',np.ones(2000,bool)),('divergent',div[chain]),('nondivergent',~div[chain])]:
                groups[label]=dict(count=int(mask.sum()),rho=quantiles(rho[chain,mask]),alpha=quantiles(alpha[chain,mask]),jacobian_condition=quantiles(condition[chain,mask]),jacobian_largest=quantiles(largest[chain,mask]),zmax=quantiles(zmax[chain,mask]),acceptance=quantiles(a['sample_stats__mean_tree_accept'][chain,mask]),steps=quantiles(a['sample_stats__n_steps'][chain,mask]))
            steps=a['sample_stats__step_size'][chain];chains.append(dict(chain=chain,step_size_min=float(steps.min()),step_size_max=float(steps.max()),groups=groups))
        row=dict(fold=fold,replicate=rep,seed=s['seed'],qualified=s['passed'],divergences=s['divergences'],jacobian_checks=checks,chains=chains);rows.append(row);print(json.dumps(dict(fold=fold,replicate=rep,divergences=s['divergences'],condition_max=float(condition.max()),zmax=float(zmax.max()))),flush=True)
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in hashes.items());(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,rows=rows,inputs=hashes,quantile_order=['min','median','p95','max'],scope='Selected-endpoint association only, not divergent-proposal geometry or causation'),indent=2,allow_nan=False)+'\n')
