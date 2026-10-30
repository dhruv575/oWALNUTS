from pathlib import Path
study=Path(__file__).resolve().parent;package=study/'compact_original_runner';(package/'src').mkdir(parents=True,exist_ok=False)
s=(study/'compact_recycling_runner/src/main.rs').read_text().replace('owalnuts::recycling','measurement::recycling')
s=s.replace('let observe=input["observe"].as_bool().unwrap_or(false);','let observe=input["observe"].as_bool().unwrap_or(false);\n        if observe {return Err("original-kernel control cannot observe trajectories".into());}')
(package/'src/main.rs').write_text(s)
c=(study/'compact_recycling_runner/Cargo.toml').read_text().replace('name = "compact-recycling-runner"','name = "compact-original-runner"').replace('owalnuts = { package =','owalnuts = { path = "../../../.." }\nmeasurement = { package =')
(package/'Cargo.toml').write_text(c)
b=(study/'build_compact_recycling.py').read_text().replace('compact_recycling_build01','compact_original_build01').replace('compact_recycling_runner','compact_original_runner').replace('compact-recycling-runner','compact-original-runner')
(study/'build_compact_original.py').write_text(b)
