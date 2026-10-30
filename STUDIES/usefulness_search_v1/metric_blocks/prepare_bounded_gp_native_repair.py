from pathlib import Path
p=Path(__file__).resolve().parent
s=(p/'bounded_gp_validation_worker.py').read_text().replace('BOUNDED-GP-VALIDATION-PROTOCOL.md','BOUNDED-GP-NATIVE-REPAIR-PROTOCOL.md')
compile(s,'bounded_gp_native_repair_worker.py','exec')
(p/'bounded_gp_native_repair_worker.py').write_text(s)
s=(p/'run_bounded_gp_calibration.py').read_text()
s=s.replace('bounded_gp_calibration','bounded_gp_native_repair').replace('BOUNDED-GP-CALIBRATION-PROTOCOL.md','BOUNDED-GP-NATIVE-REPAIR-PROTOCOL.md')
start=s.index('assert json.loads(');end=s.index('hashes=',start)
s=s[:start]+"configs=[(m,a) for a in [.999,.9999] for m in ['diag','low_rank']];jobs=[(fold,t,m,a) for fold in range(4) for t in ['raw','bounded'] for m,a in (configs if fold%2==0 else list(reversed(configs)))];"+s[end:]
s=s.replace('948600001','948900001').replace('180,d,2*1024**3,64*1024**2','300,d,2*1024**3,256*1024**2').replace("for transform in ['bounded']:","for transform in ['raw','bounded']:").replace("for engine in ['walnuts','native']:","for engine in ['native']:")
s=s.replace('eligible=[];selected=[]','assert len(rows)==32\neligible=[];selected=[]')
compile(s,'run_bounded_gp_native_repair.py','exec')
(p/'run_bounded_gp_native_repair.py').write_text(s)
print('Prepared32 native calibration fits')
