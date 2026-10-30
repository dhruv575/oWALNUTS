from pathlib import Path
p=Path(__file__).resolve().parent;folder=p/'gp_tail_replay_runner';folder.mkdir(exist_ok=False);(folder/'src').mkdir();(folder/'Cargo.toml').write_text((p/'gp_wal_tuned_runner/Cargo.toml').read_text().replace('gp-wal-tuned-runner','gp-tail-replay-runner'));s=(p/'gp_wal_tuned_runner/src/main.rs').read_text();needle='"revision": result.algorithm_revision()';assert needle in s
extra='''"revision": result.algorithm_revision(), "chain_details":result.chains().iter().map(|c|json!({
      "discarded":c.metadata().discarded(),"step_size":c.metadata().tuning().step_size(),
      "mass_updates":c.telemetry().metric_updates().iter().map(|m|json!({"dense":m.mass_dense()})).collect::<Vec<_>>(),
      "retained_calls":c.telemetry().retained().target_calls_total(),
      "diagnostics":c.diagnostics().iter().skip(c.metadata().discarded()).map(|d|json!({
        "depth":d.depth(),"calls":d.target_evaluations(),"leaves":d.leaves_built(),
        "refinement_level":d.selected_refinement_level(),"reverse_rejections":d.reverse_coarser_rejections(),
        "stop":format!("{:?}",d.stop()),"changed":d.position_changed(),"macro_length":d.trajectory_macro_length()
      })).collect::<Vec<_>>()
    })).collect::<Vec<_>>()''';s=s.replace(needle,extra);(folder/'src/main.rs').write_text(s)
s=(p/'build_gp_wal.py').read_text().replace('gp_wal_build02','gp_tail_build01').replace("[('gp_wal_pristine_runner',[]),('gp_wal_tuned_runner',[])]","[('gp_tail_replay_runner',[])]");(p/'build_gp_tail.py').write_text(s)
