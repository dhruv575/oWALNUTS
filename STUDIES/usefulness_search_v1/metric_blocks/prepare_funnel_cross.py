from pathlib import Path
study=Path(__file__).resolve().parent;package=study/'funnel_cross_runner';(package/'src').mkdir(parents=True,exist_ok=False)
source=(study/'refinement_ablation_runner/src/main.rs').read_text()
funnel=(study/'funnel_error_guard_runner/src/main.rs').read_text()
target=funnel[funnel.index('struct Funnel'):funnel.index('fn arm_delta')]
source=source.replace('struct Gaussian;','const DIMENSION:usize=10;\n'+target+'\nstruct Gaussian;')
source=source.replace('Metric::fixed_dense(mass.clone())','if input["metric"].as_str()==Some("diagonal") { Metric::fixed_diagonal(mass.clone()) } else { Metric::fixed_dense(mass.clone()) }')
source=source.replace('unwrap_or(2) as usize','unwrap_or(8) as usize')
needle='else {\n        let data=fs::read_to_string'
assert source.count(needle)==1
source=source.replace(needle,'else if input["target"].as_str()==Some("funnel") { run(Funnel {noncentered:false},&input)? }\n    else if input["target"].as_str()==Some("noncentered") {run(Funnel {noncentered:true},&input)?}\n    '+needle)
source+=funnel[funnel.index('#[cfg(test)]'):]
(package/'src/main.rs').write_text(source)
for name in ['Cargo.toml','Cargo.lock']:(package/name).write_text((study/'refinement_ablation_runner'/name).read_text().replace('refinement-ablation-research-runner','funnel-cross-runner'))
build=(study/'build_funnel_error_guard.py').read_text().replace('funnel_error_guard_build02','funnel_cross_build01').replace('funnel-error-guard02','funnel-cross01').replace('funnel_error_guard_runner','funnel_cross_runner').replace('funnel-error-guard-runner','funnel-cross-runner')
(study/'build_funnel_cross.py').write_text(build)
