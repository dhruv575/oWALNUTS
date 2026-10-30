import hashlib,json
from pathlib import Path
study=Path(__file__).resolve().parent;parent=study/'work_profile_runner';dest=study/'refinement_ablation_runner';dest.mkdir(exist_ok=False);(dest/'src').mkdir()
source=(parent/'src/main.rs').read_text();old='Tuning::default().step_size(step)';assert source.count(old)==1
source=source.replace(old,'Tuning::default().step_size(step).max_refinement_levels(input["levels"].as_u64().unwrap_or(2) as usize).max_error(input["max_error"].as_f64().unwrap_or(1.0))')
old='"revision":result.algorithm_revision()';assert source.count(old)==1
source=source.replace(old,old+',"levels":chain.metadata().tuning().max_refinement_levels(),"max_error":chain.metadata().tuning().max_error()')
(dest/'src/main.rs').write_text(source)
for name in ['Cargo.toml','Cargo.lock']:(dest/name).write_text((parent/name).read_text().replace('work-profile-research-runner','refinement-ablation-research-runner'))
build=(study/'build_work_profile.py').read_text().replace('work_profile_build01','refinement_ablation_build01').replace('work-profile01','refinement-ablation01').replace('work_profile_runner','refinement_ablation_runner').replace('work-profile-research-runner','refinement-ablation-research-runner')
(study/'build_refinement_ablation.py').write_text(build)
paths=[parent/'src/main.rs',dest/'src/main.rs',dest/'Cargo.toml',dest/'Cargo.lock',study/'build_refinement_ablation.py']
(study/'local_recovery/REFINEMENT-ABLATION-PROVENANCE.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n')
