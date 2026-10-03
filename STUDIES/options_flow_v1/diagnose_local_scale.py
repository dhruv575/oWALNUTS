"""Read saved local-level draws only; descriptive geometry diagnostics, no fitting.

Usage: python diagnose_local_scale.py MAIN_STUDY_DIR NEW_OUTPUT_JSON
The generating truth is neither read nor used by the diagnostic calculations.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def describe(x):
    x=np.asarray(x,float)
    return dict(mean=float(x.mean()),sd=float(x.std()),
                quantiles=dict(zip(['.05','.25','.5','.75','.95'],np.quantile(x,[.05,.25,.5,.75,.95]).tolist())))


def acf(x,lags=(1,10,50,100,500,1000)):
    x=np.asarray(x,float);x=x-x.mean();n=len(x)
    transformed=np.fft.rfft(x,n=1 << (2*n-1).bit_length())
    cov=np.fft.irfft(transformed*np.conjugate(transformed))[:n]
    values=cov/cov[0]
    return {str(lag):float(values[lag]) for lag in lags if lag<n}


def correlations(values):
    names=list(values)
    matrix=np.corrcoef(np.stack([values[name] for name in names]))
    return {a:{b:float(matrix[i,j]) for j,b in enumerate(names)} for i,a in enumerate(names)}


def analyze(study):
    base=study/'artifacts'/'breadth-v1'/'cells'
    result=dict(kind='exploratory_completed_draw_diagnostic',qualified=False,
                script_sha256=digest(__file__),uses_truth=False,
                limitations=['Both fits failed health gates; neither is posterior truth.',
                             'Correlations are descriptive and do not prove a reparameterization will help.',
                             'ACF is a biased finite-sample FFT estimate, not a new ESS estimator.'],arms={})
    for arm in ['autodiff','numpyro']:
        directory=base/f'local_level-00-{arm}'/'draws-8000'
        raw_path=directory/f'{arm}-raw.json';report_path=directory/f'{arm}-report.json';data_path=directory/'data.json'
        raw=json.loads(raw_path.read_text());report=json.loads(report_path.read_text());data=json.loads(data_path.read_text())
        q=np.asarray([chain['draws'] for chain in raw['chains']],float)
        y=np.asarray(data['y']);dt=np.asarray(data['dt']);nu=float(data['nu'])
        if q.shape!=(4,8000,len(y)+2) or not np.isfinite(q).all():raise ValueError('Unexpected completed-draw shape')
        h=q[...,:-2];lo=q[...,-2];lr=q[...,-1];obs=np.exp(lo);rw=np.exp(lr)
        residual=h-y;increment=np.diff(h,axis=-1)/np.sqrt(dt)
        residual_rms=np.sqrt(np.mean(residual**2,axis=-1));increment_rms=np.sqrt(np.mean(increment**2,axis=-1))
        standardized_residual_rms=residual_rms/obs
        standardized_increment_rms=increment_rms/rw
        residual_fraction=np.mean(residual**2/(nu*obs[...,None]**2+residual**2),axis=-1)
        values=dict(log_sigma_obs=lo,log_sigma_rw=lr,
                    log_residual_rms=np.log(residual_rms),log_increment_rms=np.log(increment_rms),
                    log_standardized_residual_rms=np.log(standardized_residual_rms),
                    log_standardized_increment_rms=np.log(standardized_increment_rms),
                    student_t_residual_fraction=residual_fraction)
        per_chain=[]
        for c in range(4):
            chain=dict(chain=c,sigma_obs=describe(obs[c]),sigma_rw=describe(rw[c]),
                       terminal_latent=describe(h[c,:,-1]),
                       residual_rms=describe(residual_rms[c]),increment_rms=describe(increment_rms[c]),
                       standardized_residual_rms=describe(standardized_residual_rms[c]),
                       standardized_increment_rms=describe(standardized_increment_rms[c]),
                       log_sigma_obs_acf=acf(lo[c]),log_sigma_rw_acf=acf(lr[c]),
                       residual_rms_acf=acf(np.log(residual_rms[c])),
                       correlations=correlations({name:value[c] for name,value in values.items()}),
                       sigma_obs_mean_by_1000_draw_block=[float(v.mean()) for v in np.split(obs[c],8)],
                       sigma_obs_below_prior_median_quarter=float(np.mean(obs[c]<.02)),
                       sigma_obs_below_prior_median_half=float(np.mean(obs[c]<.04)))
            per_chain.append(chain)
        result['arms'][arm]=dict(source_sha256={path.name:digest(path) for path in [raw_path,report_path,data_path]},
                                source_report=str(report_path),source_status=report['status'],
                                healthy=report['healthy'],retained_divergences=report['retained_divergences'],
                                functionals=report['evaluation']['functionals'],
                                pooled_correlations=correlations({name:value.ravel() for name,value in values.items()}),
                                chains=per_chain)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError('Diagnostic outputs are immutable')
    result=analyze(args.study.resolve())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False)
    for name,arm in result['arms'].items():
        print(name,'pooled logscale correlations',arm['pooled_correlations']['log_sigma_obs'])
        for chain in arm['chains']:
            print(chain['chain'],'sigma_obs mean',chain['sigma_obs']['mean'],
                  'acf',chain['log_sigma_obs_acf'],'blockmeans',chain['sigma_obs_mean_by_1000_draw_block'])
