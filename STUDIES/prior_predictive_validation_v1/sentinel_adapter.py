"""Independent nutpie adapter scaffold; source/API preflight required before fits."""
import hashlib,inspect
import numpy as np
SENTINELS=[(0,1),(4,32),(8,1),(12,32),(16,1),(20,32),(24,1),(28,32)]
def api_inventory(nutpie):
    # Inventory only: no model compilation or sampling.
    for name in ('compile_stan_model','sample'):
        if not callable(getattr(nutpie,name,None)):raise ValueError('missing nutpie API '+name)
    signature=inspect.signature(nutpie.sample)
    for name in ('draws','tune','chains','cores','seed','save_warmup','progress_bar'):
        if name not in signature.parameters:raise ValueError('unvalidated nutpie sample parameter '+name)
    return dict(version=getattr(nutpie,'__version__','unknown'),sample_signature=str(signature))
def stan_data(window):
    y=np.asarray(window,dtype=float)
    if y.shape!=(250,) or not np.isfinite(y).all():raise ValueError('exact250 reference window required')
    return dict(n=250,y=y,rho=.95,nu=5.,mu_mean=2*np.log(.005),mu_sd=1.,log_sigma_mean=np.log(.2),log_sigma_sd=.5,beta_sd=.002)
def extract(trace):
    components=[]
    for name in ('mu','log_sigma','beta','h_last'):
        a=np.asarray(trace.posterior[name].transpose('chain','draw'),dtype=float)
        if a.shape!=(4,4000) or not np.isfinite(a).all():raise ValueError('invalid reference component '+name)
        components.append(a)
    draws=np.stack(components,axis=-1)
    divergence=np.asarray(trace.sample_stats['diverging'].transpose('chain','draw'))
    if divergence.shape!=(4,4000):raise ValueError('reference divergence axes mismatch')
    if not np.isfinite(divergence).all() or not np.isin(divergence,[0,1]).all():raise ValueError('invalid divergence indicators')
    coordinates=np.asarray(trace.posterior.coords['chain'])
    if coordinates.shape!=(4,) or len(set(coordinates.tolist()))!=4:raise ValueError('invalid reference chain identities')
    return draws,dict(divergences=divergence.sum(axis=1).astype(int).tolist(),chain_coordinates=np.asarray(trace.posterior.coords['chain']).tolist())
def fit(nutpie,compiled,window,seed,validated_settings):
    # Only a future frozen runner may invoke this; no caller exists in scaffold.
    api_inventory(nutpie)
    if validated_settings.get('api_and_target_verified') is not True:raise ValueError('reference API/target preflight incomplete')
    if not 0<=seed<2**32:raise ValueError('reserved interoperable seed out of range')
    model=compiled.with_data(**stan_data(window))
    trace=nutpie.sample(model,draws=4000,tune=2000,chains=4,cores=4,seed=seed,save_warmup=True,progress_bar=False,**validated_settings['engine_options'])
    return extract(trace)
def log_density_mcse(log_integrated_density,mean_mcse):
    """Delta MCSE(log(mean density)), not MCSE(mean logdensity)."""
    a=np.asarray(log_integrated_density,dtype=float)
    if a.ndim!=2 or not np.isfinite(a).all():raise ValueError('finite chain/draw log integrated density required')
    shift=float(a.max());scaled=np.exp(a-shift);mean=float(scaled.mean())
    if not mean>0:raise ValueError('zero stabilized density mean')
    return dict(log_predictive_density=shift+np.log(mean),delta_mcse=float(mean_mcse(scaled))/mean,stabilization=shift)
