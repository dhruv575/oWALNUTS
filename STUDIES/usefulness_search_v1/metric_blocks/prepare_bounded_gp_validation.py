from pathlib import Path
p=Path(__file__).resolve().parent
s=(p/'gp_transport_validation_worker.py').read_text()
start=s.index('else:\n    target_build=')
end=s.index("build=json.loads((shim.parent",start)
s=s[:start]+"""else:
    target_dir='bounded_gp_target01' if transform=='bounded' else 'gp_transport_target01'
    target_build=json.loads((LOCAL/target_dir/'SUMMARY.json').read_text());assert target_build['passed'];so=Path(target_build['library']);assert hashlib.sha256(so.read_bytes()).hexdigest()==target_build['library_sha256'];data=LOCAL/target_dir/f'fold-{fold}-{transform}.json';source=STUDY/('bounded_gp.stan' if transform=='bounded' else 'gp_transport.stan');shim=LOCAL/('bounded_gp_counter01' if transform=='bounded' else 'gp_transport_smoke01')/'counted_model.so'
"""+s[end:]
s=s.replace('2000','8000').replace('GP-TRANSPORT-VALIDATION-PROTOCOL.md','BOUNDED-GP-VALIDATION-PROTOCOL.md')
compile(s,'bounded_gp_validation_worker.py','exec')
(p/'bounded_gp_validation_worker.py').write_text(s)
s=(p/'run_gp_transport_validation.py').read_text()
s=s.replace('gp_transport_validation','bounded_gp_validation').replace('GP-TRANSPORT-VALIDATION-PROTOCOL.md','BOUNDED-GP-VALIDATION-PROTOCOL.md')
start=s.index('cal=json.loads(');end=s.index('hashes=',start)
s=s[:start]+"""cal=json.loads((l/'bounded_gp_calibration01/SUMMARY.json').read_text());assert cal['completed']
configs=[('raw','walnuts_dense',.9),('raw','low_rank',.99),('affine','walnuts_dense',.9),('affine','diag',.99),('bounded','walnuts_dense',.9),('bounded','low_rank',.99)]
for transform,mode,accept in configs[4:]:
    selected=next(x['selection'] for x in cal['selected'] if x['engine']==('walnuts' if mode.startswith('walnuts') else 'native'));assert selected['mode']==mode and selected['target_accept']==accept
"""+s[end:]
s=s.replace('948400001','948700001').replace('948500001','948800001').replace("'quadratic','walnuts_diag'","'bounded','walnuts_dense'").replace("transform=='quadratic' and mode=='walnuts_diag'","transform=='bounded' and mode=='walnuts_dense'").replace('180,d,2*1024**3,64*1024**2','300,d,2*1024**3,256*1024**2')
s=s.replace("qualified=all(x['passed'] for x in rows)","qualified=len(rows)==48 and all(x['passed'] for x in rows)")
compile(s,'run_bounded_gp_validation.py','exec')
(p/'run_bounded_gp_validation.py').write_text(s)
print('Prepared fixed 48-fit bounded validation')
