from pathlib import Path
p=Path(__file__).resolve().parent
for name in ['gp_wal_pristine_runner','gp_wal_tuned_runner']:
    folder=p/name;folder.mkdir(exist_ok=False);(folder/'src').mkdir();manifest=(p/'fixed_metric_runner/Cargo.toml').read_text().replace('fixed-metric-research-runner',name.replace('_','-'));(folder/'Cargo.toml').write_text(manifest);source=(p/'model_online.rs').read_text()
    if name=='gp_wal_tuned_runner':
        source=source.replace('let mut sampler = Sampler::new()', 'let target_accept = input["target_accept"].as_f64().unwrap_or(0.8);\n    let mut sampler = Sampler::new()').replace('.threads(4).limits(','.adaptation(Adaptation::DualAveraging { target_accept }).threads(4).limits(').replace('WarmupConfig::new(0.8)?','WarmupConfig::new(target_accept)?')
    (folder/'src/main.rs').write_text(source)
build=(p/'build_momentum_pool.py').read_text().replace('momentum_pool_build01','gp_wal_build01').replace("[('momentum_pool_runner',[]),('momentum_pool_probe_runner',[])]","[('gp_wal_pristine_runner',[]),('gp_wal_tuned_runner',[])]")
(p/'build_gp_wal.py').write_text(build)
