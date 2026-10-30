from pathlib import Path
p=Path(__file__).resolve().parent;s=(p/'gp24_confirmation_worker.py').read_text()
old="so,data,source=model_files(name);shim=LOCAL/'nativemodels01'/name/'counted_model.so'"
new="so,_,source=model_files(name);data=LOCAL/f'gp_fresh_data01/scenario-{fold}/DATA.json';manifest=json.loads((LOCAL/'gp_fresh_data01/SUMMARY.json').read_text());assert hashlib.sha256(data.read_bytes()).hexdigest()==manifest['rows'][fold]['data_sha256'];shim=LOCAL/'nativemodels01'/name/'counted_model.so'"
assert old in s;s=s.replace(old,new)
start=s.index("    target_dir='bounded_gp_target01'");end=s.index("build=json.loads((shim.parent",start)
s=s[:start]+"""    target_build=json.loads((LOCAL/'bounded_gp_target01/SUMMARY.json').read_text());assert target_build['passed'];so=Path(target_build['library']);assert hashlib.sha256(so.read_bytes()).hexdigest()==target_build['library_sha256'];data=LOCAL/f'gp_fresh_pilot01/scenario-{fold}/{transform}.json';source=STUDY/'bounded_gp.stan';shim=LOCAL/'bounded_gp_counter01/counted_model.so'
"""+s[end:]
old="refpath=STUDY.parent/'gp_count/REFERENCE.json';reference=json.loads(refpath.read_text());assert reference['qualified'];ref=dict(reference['stats'],names=reference['names']);assert len(ref['names'])==24"
new="refpath=LOCAL/'gp_fresh_reference01/SUMMARY.json';reference=next(x for x in json.loads(refpath.read_text())['references'] if x['scenario']==fold);assert reference['passed'];ref=dict(reference['stats'],names=['rho','alpha']+[f'f[{j}]' for j in range(1,12)]+[f'intensity[{j}]' for j in range(1,12)])"
assert old in s;s=s.replace(old,new).replace('GP-24-CONFIRMATION-PROTOCOL.md','GP-NEWDATA-COMPARISON-PROTOCOL.md');compile(s,'gp_newdata_comparison_worker.py','exec');(p/'gp_newdata_comparison_worker.py').write_text(s)
s=(p/'run_gp24_confirmation.py').read_text().replace('gp24_confirmation','gp_newdata_comparison').replace("str(p/'gp_newdata_comparison_worker.py')","str(p/'gp_newdata_comparison_worker.py')").replace("'gp_newdata_comparison_worker.py'","'gp_newdata_comparison_worker.py'").replace('GP-24-CONFIRMATION-PROTOCOL.md','GP-NEWDATA-COMPARISON-PROTOCOL.md').replace('949000001','949800001').replace('949100001','949900001')
needle="cal=json.loads((l/'bounded_gp_calibration01/SUMMARY.json').read_text());assert cal['completed']"
s=s.replace(needle,needle+"\nassert json.loads((l/'gp_fresh_target01/SUMMARY.json').read_text())['passed'];assert json.loads((l/'gp_fresh_pilot01/SUMMARY.json').read_text())['all_qualified']")
old="pilot={x['fold']:x['pilot_gradient_calls'] for x in json.loads((l/'gp_transport_calibration01/COST-LEDGER.json').read_text())['pilots']}"
new="pilot={x['scenario']:x['result']['calls']['gradient'] for x in json.loads((l/'gp_fresh_pilot01/SUMMARY.json').read_text())['rows']}"
assert old in s;s=s.replace(old,new);compile(s,'run_gp_newdata_comparison.py','exec');(p/'run_gp_newdata_comparison.py').write_text(s)
print('Prepared48 fixed-settings fresh-data fits')
