import pathlib, shutil
study=pathlib.Path(__file__).resolve().parent
repo=study.parents[2]
package=study/'funnel_error_guard_runner'
(package/'src').mkdir(parents=True,exist_ok=False)
source=(repo/'STUDIES/delta2_default_confirmation_v1/src/bin/funnel.rs').read_text()
source='//! Research-only fresh funnel guard; derived from WP63, with Gaussian control and raw draws.\n'+source[source.index('#![forbid'):]
source=source.replace('struct Funnel;','struct Funnel { noncentered: bool }')
source=source.replace('let omega = position[0];','''let omega = position[0];
        if self.noncentered {
            gradient[0] = -omega / 9.0;
            for (g,x) in gradient[1..].iter_mut().zip(&position[1..]) { *g = -x; }
            let value = -omega*omega/18.0 - 0.5*position[1..].iter().map(|x|x*x).sum::<f64>();
            return if value.is_finite() && gradient.iter().all(|x|x.is_finite()) { Ok(value) }
                else { Err(TargetError::recoverable("nonfinite Gaussian evaluation")) };
        }''')
source=source.replace('"delta2" => Ok(2.0),','"permissive" => Ok(1000.0),')
source=source.replace('fn run(\n    arm:', 'fn run(\n    target: &str,\n    arm:')
source=source.replace('let delta = arm_delta(arm)?;', 'assert!(target == "centered" || target == "noncentered");\n    let delta = arm_delta(arm)?;')
source=source.replace('let kernel = tuning.to_kernel()?;', 'let kernel = tuning.to_kernel()?;\n    assert_eq!(kernel.max_refinement_levels(), 8);')
source=source.replace('sampler.run(&Funnel, &starts)?','sampler.run(&Funnel { noncentered: target == "noncentered" }, &starts)?')
source=source.replace('"chains_data": chains_json,','"chains_data": chains_json,\n        "target": target, "columns": columns,')
source=source.replace('[arm, warmup, draws, seed, out]', '[target, arm, warmup, draws, seed, out]')
source=source.replace('=> run(arm, w, d, s, Path::new(out))','=> run(target, arm, w, d, s, Path::new(out))')
source+='''
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn gradients_and_change_of_variables() {
        for omega in [-6.0, -1.0, 3.0] {
            let z: Vec<f64> = (0..10).map(|i| if i==0 {omega} else {i as f64 / 10.0}).collect();
            let mut x=z.clone(); for v in &mut x[1..] { *v *= (omega/2.0).exp(); }
            let mut g=vec![0.;10];
            let lc=Funnel{noncentered:false}.log_density_gradient(&x,&mut g).unwrap();
            let ln=Funnel{noncentered:true}.log_density_gradient(&z,&mut g).unwrap();
            assert!((lc+4.5*omega-ln).abs()<1e-10);
            for (nc,q) in [(false,x),(true,z)] {
                let target=Funnel{noncentered:nc}; target.log_density_gradient(&q,&mut g).unwrap();
                for i in 0..10 { let mut p=q.clone(); let mut m=q.clone(); p[i]+=1e-6; m[i]-=1e-6;
                    let mut scratch=vec![0.;10];
                    let fd=(target.log_density_gradient(&p,&mut scratch).unwrap()-target.log_density_gradient(&m,&mut scratch).unwrap())/2e-6;
                    assert!((fd-g[i]).abs()<1e-5*(1.0+g[i].abs()));
                }
            }
        }
    }
}
'''
(package/'src/main.rs').write_text(source)
for name in ['Cargo.toml','Cargo.lock']:
    text=(study/'refinement_ablation_runner'/name).read_text().replace('refinement-ablation-research-runner','funnel-error-guard-runner')
    (package/name).write_text(text)
build=(study/'build_refinement_ablation.py').read_text().replace('refinement_ablation_build01','funnel_error_guard_build01').replace('refinement-ablation01','funnel-error-guard01').replace('refinement_ablation_runner','funnel_error_guard_runner').replace('refinement-ablation-research-runner','funnel-error-guard-runner')
build=build.replace("binary=cache/", "test=execute(['cargo','test','--release','--offline','--locked','-j','1'],str(study/'funnel_error_guard_runner'),180,cache,4*1024**3,1024**3,root/'test.log',output_scan_interval=2)\n(root/'TEST-SUPERVISION.json').write_text(json.dumps(test,indent=2)+'\\n');assert test['exit_code']==0 and test['group_drained']\nbinary=cache/")
(study/'build_funnel_error_guard.py').write_text(build)
