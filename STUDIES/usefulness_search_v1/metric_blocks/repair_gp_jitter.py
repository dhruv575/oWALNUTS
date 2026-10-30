import hashlib,json,shutil,difflib
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';old=l/'gp_jitter_source01';out=l/'gp_jitter_source02';shutil.copytree(old,out)
b=json.loads((l/'gp_jitter_build01/SUMMARY.json').read_text())
for x in b['rows']:
    src=Path(x['binary']);assert hashlib.sha256(src.read_bytes()).hexdigest()==x['binary_sha256'];shutil.copy2(src,l/'gp_jitter_build01'/src.name)
f=out/'src/walnutpie.rs';s=f.read_text();s=s.replace('    capture_acceptance: bool,','    capture_acceptance: bool,\n    research_jitter_disabled: bool,',1).replace('            capture_acceptance: false,','            capture_acceptance: false,\n            research_jitter_disabled: false,',1)
s=s.replace('            if transition_index >= *discarded {\n                let amplitude:', '            if transition_index >= *discarded && !config.research_jitter_disabled {\n                let amplitude:',1)
needle='            transition_config.capture_acceptance = true;';assert s.count(needle)==1;s=s.replace(needle,needle+'\n            transition_config.research_jitter_disabled = true;')
# This prototype is exercised only on diagonal and dense GP paths. Also exclude
# structured-refresh one-transition warmup calls explicitly, without claiming
# its retained schedule semantics have been tested.
needle='        one.capture_acceptance = true;';assert s.count(needle)==1;s=s.replace(needle,needle+'\n        one.research_jitter_disabled = transition < config.discarded;')
f.write_text(s);baseline=(p.parents[2]/'src/walnutpie.rs').read_text();(p/'GP-JITTER-KERNEL-02.patch').write_text(''.join(difflib.unified_diff(baseline.splitlines(True),s.splitlines(True),fromfile='src/walnutpie.rs',tofile='gp_jitter_source02/src/walnutpie.rs',n=0)))
(out/'SOURCE-HASHES.json').write_text(json.dumps({str(f.relative_to(out)):hashlib.sha256(f.read_bytes()).hexdigest() for f in out.rglob('*') if f.is_file() and f.name!='SOURCE-HASHES.json'},indent=2)+'\n')
name='gp_jitter_candidate02_runner';d=p/name;shutil.copytree(p/'gp_jitter_candidate_runner',d);f=d/'Cargo.toml';f.write_text(f.read_text().replace('gp-jitter-candidate-runner','gp-jitter-candidate02-runner').replace('gp_jitter_source01','gp_jitter_source02'))
s=(p/'build_gp_jitter.py').read_text().replace('gp_jitter_build01','gp_jitter_build02').replace("[('gp_jitter_original_runner',[]),('gp_jitter_candidate_runner',[])]","[('gp_jitter_candidate02_runner',[])]");(p/'build_gp_jitter02.py').write_text(s)
s=(p/'test_gp_jitter.py').read_text().replace("r=l/'gp_jitter_test01'","r=l/'gp_jitter_test02'").replace("bins=b['rows']","bins=[b['rows'][0],json.loads((l/'gp_jitter_build02/SUMMARY.json').read_text())['rows'][0]]").replace("registry('gp_jitter_candidate_runner')","registry('gp_jitter_candidate02_runner')").replace("'test_gp_jitter.py','prepare_gp_jitter.py','GP-JITTER-KERNEL.patch'","'test_gp_jitter02.py','repair_gp_jitter.py','GP-JITTER-KERNEL-02.patch'")
s=s.replace('build=b,source_hashes=', 'build=bins,source_hashes=');(p/'test_gp_jitter02.py').write_text(s)
