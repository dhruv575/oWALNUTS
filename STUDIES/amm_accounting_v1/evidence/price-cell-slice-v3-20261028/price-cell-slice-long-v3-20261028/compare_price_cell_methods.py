"""All-coordinate comparison of fixed synthetic fits; retains failed slots."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
import arviz as az
from price_cell_fixtures import fixture


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(root,reference,out):
    root=Path(root);reference=Path(reference);out=Path(out);out.mkdir(exist_ok=False)
    receipt=json.loads((root/'SUPERVISION.json').read_bytes())
    if not receipt.get('group_drained'):raise ValueError('Campaign not drained')
    jobs=json.loads((root/'FINAL.json').read_bytes());rows=[];bindings={}
    for j,(n,width) in enumerate([(12,.001),(12,.00001),(250,.001),(250,.00001)]):
        relevant=[x for x in jobs if x['index']//4==j]
        row=dict(fixture=j,n=n,width=width,chains_completed=sum(x.get('exit_code')==0 and x.get('group_drained',False) for x in relevant))
        if row['chains_completed']!=4:row['status']='incomplete';rows.append(row);continue
        arrays=[]
        for c in range(4):
            p=root/f'job-{4*j+c}/fit/draws.npz';bindings[str(p)]=sha(p)
            with np.load(p) as f:
                assert f['warmup'].shape==(1000,3+2*n) and f['draws'].shape==(4000,3+2*n)
                arrays.append(f['draws'])
        a=np.stack(arrays);assert np.isfinite(a).all()
        independent=az.from_dict(posterior=dict(mu=a[:,:,0],log_sigma=a[:,:,1],beta=a[:,:,2],z=a[:,:,3:3+n],u=a[:,:,3+n:]))
        p=reference/f'job-{j}/fit/trace.nc';bindings[str(p)]=sha(p);nuts=az.from_netcdf(p)
        data,_=fixture(n,width)
        with np.load(reference/f'job-{j}/fit/fixture.npz') as f:
            assert np.array_equal(f['lower'],data['lower_cell']) and np.array_equal(f['upper'],data['upper_cell'])
        left=az.summary(independent,var_names=['mu','log_sigma','beta','z','u'],round_to='none')
        right=az.summary(nuts,var_names=['mu','log_sigma','beta','z','u'],round_to='none')
        assert list(left.index)==list(right.index) and len(left)==3+2*n
        table=left.add_prefix('slice_').join(right.add_prefix('nuts_'))
        table['combined_z']=(left['mean']-right['mean'])/np.hypot(left['mcse_mean'],right['mcse_mean'])
        for name,summary in [('slice',left),('nuts',right)]:
            table[name+'_pass']=(summary.r_hat<=1.01)&(summary.ess_bulk>=400)&(summary.ess_tail>=400)
        table.to_csv(out/f'fixture-{j}-coordinates.csv')
        row.update(status='compared',slice_failed_coordinates=table.index[~table.slice_pass].tolist(),nuts_failed_coordinates=table.index[~table.nuts_pass].tolist(),mean_flags=table.index[abs(table.combined_z)>4].tolist(),max_abs_combined_z=float(abs(table.combined_z).max()),scope='Finite synthetic diagnostics and mean comparison, not general fidelity proof')
        rows.append(row);nuts.close();independent.close()
    result=dict(rows=rows,bindings=bindings,source_sha256=sha(__file__))
    (out/'REPORT.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result))


if __name__=='__main__':run(*sys.argv[1:])
