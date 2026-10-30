import ast,hashlib,json
from pathlib import Path
import numpy as np,bridgestan as bs
from quadratic_transport import encode,decode
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_transport_divergence_replay01';replay=json.loads((r/'REPLAY.json').read_text());assert replay['passed'];src=(p/'audit_gp_transport_tails.py').read_bytes();audit=json.loads((l/'gp_transport_tail_audit01/SUMMARY.json').read_text());assert hashlib.sha256(src).hexdigest()==audit['inputs'][str(p/'audit_gp_transport_tails.py')]
for node in ast.parse(src).body:
    if isinstance(node,ast.FunctionDef) and node.name=='jacobian':exec(compile(ast.Module(body=[node],type_ignores=[]),'<verified-jacobian>','exec'))
m=json.loads((l/'gp_transport_qualified02/fold-2/MAP.json').read_text());target_summary=json.loads((l/'gp_transport_target01/SUMMARY.json').read_text());so=Path(target_summary['library']);assert hashlib.sha256(so.read_bytes()).hexdigest()==target_summary['library_sha256'];target=bs.StanModel(str(so),data=(l/'gp_transport_target01/fold-2-quadratic.json').read_text(),seed=1);a=np.load(r/'DRAWS-STATS.npz');mask=a['sample_stats__diverging'].astype(bool);indices=np.argwhere(mask);rows=[]
for chain,draw in indices:
    row=dict(chain=int(chain),draw=int(draw),points={})
    for label in ['start','end']:
        z=a['sample_stats__divergence_'+label][chain,draw];point=dict(finite_coordinates=bool(np.isfinite(z).all()),zmax=float(np.max(abs(z))) if np.isfinite(z).all() else None)
        try:
            with np.errstate(all='ignore'):q,J=jacobian(z[None],m);sv=np.linalg.svd(J[0],compute_uv=False)
            lp,g=target.log_density_gradient(z);assert np.isfinite(lp) and np.isfinite(g).all() and np.isfinite(sv).all();point.update(evaluated=True,log_density=float(lp),gradient_norm=float(np.linalg.norm(g)),jacobian_condition=float(sv[0]/sv[-1]),jacobian_largest=float(sv[0]),rho=float(np.exp(q[0,0])),alpha=float(np.exp(q[0,1])))
            if label=='start':point['stored_gradient_error']=float(np.max(abs(g-a['sample_stats__divergence_start_gradient'][chain,draw])/(1+abs(g))))
        except Exception as e:point.update(evaluated=False,error=str(e))
        row['points'][label]=point
    rows.append(row)
summary={}
for label in ['start','end']:
    points=[x['points'][label] for x in rows];good=[x for x in points if x['evaluated']];summary[label]=dict(total=len(points),evaluated=len(good),quantiles={key:np.quantile([x[key] for x in good],[0,.5,.95,1]).tolist() for key in ['zmax','log_density','gradient_norm','jacobian_condition','jacobian_largest','rho','alpha']},stored_gradient_error_max=max(x.get('stored_gradient_error',0.) for x in good))
out=dict(completed=True,summary=summary,rows=rows,scope='Exact replayed divergent proposal records; exploratory diagnosis, not posterior evidence or unique causal attribution',gradient_probe_calls=2*len(rows));(r/'PROPOSAL-AUDIT.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');print(json.dumps(summary))
