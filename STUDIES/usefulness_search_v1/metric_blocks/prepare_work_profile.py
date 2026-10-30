import hashlib,json
from pathlib import Path
study=Path(__file__).resolve().parent;parent=study/'fixed_metric_runner';dest=study/'work_profile_runner';dest.mkdir(exist_ok=False);(dest/'src').mkdir()
source=(parent/'src/main.rs').read_text();needle='"revision":result.algorithm_revision()';assert source.count(needle)==1
fields=['target_calls_initial','target_calls_forward','target_calls_reverse','target_calls_total','accepted_forward_micro_steps','forward_refinement_attempts','reverse_coarsening_attempts','leaves_attempted','leaves_built','refinement_exhaustion_stops','reverse_coarser_stops','maximum_depth_stops','zero_density_evaluations','nonfinite_position_rejections','recoverable_target_failures']
work=','.join('"'+k+'":chain.telemetry().retained().'+k+'()' for k in fields)
source=source.replace(needle,needle+',"work":json!({'+work+',"refinement_level_built":chain.telemetry().retained().refinement_level_built(),"all_phase_calls":chain.telemetry().total().target_calls_total()})')
(dest/'src/main.rs').write_text(source)
for name in ['Cargo.toml','Cargo.lock']:(dest/name).write_text((parent/name).read_text().replace('fixed-metric-research-runner','work-profile-research-runner'))
paths=[parent/'src/main.rs',dest/'src/main.rs',dest/'Cargo.toml',dest/'Cargo.lock']
(study/'local_recovery/WORK-PROFILE-PROVENANCE.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n')
