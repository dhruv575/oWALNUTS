from pathlib import Path
p=Path(__file__).resolve().parent;s=(p/'gp_wal_calibration_worker.py').read_text();needle="so,data,source=model_files(name);shim=LOCAL/'nativemodels01'/name/'counted_model.so';";assert needle in s
replacement="""fold=int(sys.argv[5]);transform=sys.argv[6]
if transform=='raw':
    so,data,source=model_files(name);shim=LOCAL/'nativemodels01'/name/'counted_model.so'
else:
    target_build=json.loads((LOCAL/'gp_transport_target01/SUMMARY.json').read_text());assert target_build['passed'];so=Path(target_build['library']);assert hashlib.sha256(so.read_bytes()).hexdigest()==target_build['library_sha256'];data=LOCAL/f'gp_transport_target01/fold-{fold}-{transform}.json';source=STUDY/'gp_transport.stan';shim=LOCAL/'gp_transport_smoke01/counted_model.so'
"""
s=s.replace(needle,replacement).replace('out=dict(model=name,','out=dict(fold=fold,transform=transform,model=name,').replace('GP-WAL-CALIBRATION-PROTOCOL.md','GP-TRANSPORT-VALIDATION-PROTOCOL.md').replace('dict(model=name,settings=kwargs)','dict(model=str(so),data=str(data),settings=kwargs)');(p/'gp_transport_validation_worker.py').write_text(s)
