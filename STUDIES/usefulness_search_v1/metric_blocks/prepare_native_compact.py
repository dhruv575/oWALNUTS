from pathlib import Path
p=Path(__file__).resolve().parent
source=(p/'native_recycling_main.rs').read_text()
source=source.replace('observe:bool)->anyhow','observe:bool,compact:bool)->anyhow')
source=source.replace('let mut positions=Vec::new();','let mut hash=Sha256::new();let mut ordinary=Acc::default();let mut conditional=Acc::default();let mut retained_divergences=0usize;let mut total_steps=0u64;let mut positions=Vec::new();')
old='positions.push(q.to_vec());progress.push(json!({"draw":p.draw,"chain":p.chain,"diverging":p.diverging,"tuning":p.tuning,"step_size":p.step_size,"num_steps":p.num_steps}));'
new='for x in q.iter(){hash.update(x.to_le_bytes());}total_steps+=p.num_steps as u64;if i>=warmup{ordinary.push(&observable(&q));retained_divergences+=p.diverging as usize;}if compact{if observe{let recorded=observer::drain();assert_eq!(recorded.len(),1);if i>=warmup{conditional.push(&recorded[0]);}}}else{'+old+'}'
assert old in source;source=source.replace(old,new)
source=source.replace('if observe{assert_eq!(recycled.len(),warmup+draws);}','if observe&&!compact{assert_eq!(recycled.len(),warmup+draws);for v in &recycled[warmup..]{conditional.push(v);}}')
source=source.replace('"all_draws":positions,','"draw_sha256":format!("{:x}",hash.finalize()),"ordinary_summary":ordinary.finish(),"conditional_summary":conditional.finish(),"retained_divergences":retained_divergences,"total_steps":total_steps,"all_draws":positions,')
source=source.replace('let observe=spec["observe"].as_bool().unwrap_or(false);','let observe=spec["observe"].as_bool().unwrap_or(false);let compact=spec["compact"].as_bool().unwrap_or(false);')
source=source.replace('warmup,draws,observe)?','warmup,draws,observe,compact)?')
source+='\n'+(p/'native_compact_support.rs').read_text()
for oldname,newname in [('native_pristine_runner','native_compact_pristine_runner'),('native_recycling_runner','native_compact_recycling_runner')]:
    dest=p/newname;dest.mkdir(exist_ok=False);(dest/'src').mkdir()
    manifest=(p/oldname/'Cargo.toml').read_text().replace(oldname.replace('_','-'),newname.replace('_','-')).replace('serde_json = "1"','serde_json = "1"\nsha2 = "=0.10.9"')
    (dest/'Cargo.toml').write_text(manifest);(dest/'src/main.rs').write_text(source)
build=(p/'build_native_recycling_retry.py').read_text().replace('native_recycling_build02','native_compact_build01').replace('native_pristine_runner','native_compact_pristine_runner').replace('native_recycling_runner','native_compact_recycling_runner')
(p/'build_native_compact.py').write_text(build)
