from scoring_worker import *
def audit():
    verify_freeze();out=BASE/'audit';out.mkdir(exist_ok=False);start=time.perf_counter()
    result=json.loads((BASE/'scoring/SUMMARY.json').read_text());cells=json.loads((BASE/'scoring/CELLS.json').read_text());y=np.array(cells['heldout']);d=data();model=GridGP(d)
    for name,rows in cells['predictors'].items():
        summary=summarize(y,rows);assert all(abs(summary[k]-result['summaries'][name][k])<1e-12 for k in summary)
    cheap=json.loads((BASE/'inputs/CHEAP.json').read_text());checks={}
    for name in ['homogeneous','fixed_cell','empirical_bayes']:
        c=cheap[name];b=c['rate'];shape=np.broadcast_to(c['shape'],(200,));expected=gammaln(shape+y)-gammaln(shape)-gammaln(y+1)+shape*np.log(b/(b+.8))+y*np.log(.8/(b+.8))
        error=max(abs(expected-np.array([r['log_score'] for r in cells['predictors'][name]])));assert error<1e-10;checks[name]=float(error)
    blocks=np.array([(i//5)*2+j//5 for i in range(20) for j in range(10)]);resamples=np.random.default_rng(955000030).integers(0,8,size=(10000,8));gp=np.array([r['log_score'] for r in cells['predictors']['gp']])
    for row in result['comparisons']:
        other=np.array([r['log_score'] for r in cells['predictors'][row['competitor']]]);delta=gp-other;block=np.array([delta[blocks==i].mean() for i in range(8)]);boot=block[resamples].mean(1)
        assert abs(delta.mean()-row['gain'])<1e-12 and abs(np.quantile(boot,.05/6)-row['lower'])<1e-12
    rates=[]
    for root in GP_PATHS:
        values=physical(np.load(root/'DRAWS.npz')['q'],model);rates.append(values[:,:,205:].copy());del values
    rates=np.concatenate(rates);lp=poisson.logpmf(y[None,None,:],.8*rates);shift=lp.max((0,1));p=np.exp(lp-shift);influence=(p/p.mean((0,1))).mean(2)
    aggregate_mcse=float(np.asarray(az.mcse(az.convert_to_dataset({'p':influence}),method='mean').p))
    numerical_failures=[]
    for group,row in enumerate(result['precision']):
        errors=np.array(row['log_score_mcse'])
        for index in np.flatnonzero(errors>.02):numerical_failures.append(dict(group=group,cell=int(index),grid_x=int(index//10),grid_y=int(index%10),mcse=float(errors[index])))
    rates=rates.reshape(-1,200);replicates=[]
    for seed in [955000101,955000102,955000103,955000104]:
        rows=mixture(y,lambda i:rates[:,i],np.ones(len(rates)),seed);replicates.append(dict(seed=seed,**summarize(y,rows)))
    write(out/'SUMMARY.json',dict(passed=True,analytic_score_errors=checks,aggregate_log_score_mcse=aggregate_mcse,per_cell_failures=numerical_failures,predictive_draw_replicates=replicates,seconds=time.perf_counter()-start,primary_result_unchanged=result['positive_predictive_value_pilot'],scope='Audit and auxiliary numerical variability only; original failed gates unchanged'))
    verify_freeze();print(json.dumps(dict(passed=True,aggregate_mcse=aggregate_mcse,failures=len(numerical_failures),replicates=replicates)),flush=True)
if __name__=='__main__':audit()
