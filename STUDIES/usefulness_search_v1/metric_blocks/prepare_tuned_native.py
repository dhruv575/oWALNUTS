from pathlib import Path
p=Path(__file__).resolve().parent
for old,new in [('banana_native_pristine_runner','tuned_native_pristine_runner'),('banana_native_recycling_runner','tuned_native_recycling_runner')]:
    out=p/new;out.mkdir(exist_ok=False);(out/'src').mkdir();(out/'Cargo.toml').write_text((p/old/'Cargo.toml').read_text().replace(old.replace('_','-'),new.replace('_','-')))
    text=(p/old/'src/main.rs').read_text();needle='s.adapt_options.step_size_settings.jitter=None;';assert text.count(needle)==2;text=text.replace(needle,needle+'s.adapt_options.step_size_settings.target_accept=spec["target_accept"].as_f64().unwrap_or(0.8);');(out/'src/main.rs').write_text(text)
build=(p/'build_native_compact.py').read_text().replace('native_compact_build01','tuned_native_build01').replace('native_compact_pristine_runner','tuned_native_pristine_runner').replace('native_compact_recycling_runner','tuned_native_recycling_runner');(p/'build_tuned_native.py').write_text(build)
