from pathlib import Path
p=Path(__file__).resolve().parent;s=(p/'gp_wal_calibration_worker.py').read_text()
old="so,data,source=model_files(name);shim=LOCAL/'nativemodels01'/name/'counted_model.so';"
new="fold=int(sys.argv[5]);transform=sys.argv[6];target_build=json.loads((LOCAL/'gp_transport_target01/SUMMARY.json').read_text());assert target_build['passed'];so=Path(target_build['library']);assert hashlib.sha256(so.read_bytes()).hexdigest()==target_build['library_sha256'];data=LOCAL/f'gp_transport_target01/fold-{fold}-{transform}.json';source=STUDY/'gp_transport.stan';shim=LOCAL/'gp_transport_smoke01/counted_model.so';"
assert old in s;s=s.replace(old,new).replace('out=dict(model=name,','out=dict(fold=fold,transform=transform,model=name,').replace('GP-WAL-CALIBRATION-PROTOCOL.md','GP-TRANSPORT-CALIBRATION-PROTOCOL.md').replace('dict(model=name,settings=kwargs)','dict(model=str(so),data=str(data),settings=kwargs)')
(p/'gp_transport_calibration_worker.py').write_text(s)
