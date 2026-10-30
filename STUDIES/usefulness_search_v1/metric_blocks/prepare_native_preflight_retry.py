from pathlib import Path
import hashlib,json
p=Path(__file__).resolve().parent
old=p/'test_native_recycling.py'
text=old.read_text().replace("native_recycling_test01","native_recycling_test02").replace("[float(2*i-3)]+[0.]*(d-1)","[float(2*i-3)]+[0.1*j for j in range(1,d)]")
assert text!=old.read_text()
(p/'test_native_recycling_retry.py').write_text(text)
(p/'NATIVE-RECYCLING-START-REPAIR.json').write_text(json.dumps(dict(original_sha256=hashlib.sha256(old.read_bytes()).hexdigest(),reason='Native transformed_hamiltonian.rs check_all rejects zero transformed gradient entries. Test01 preserved; test02 changes only output folder and common starts, with identical seeds, thresholds and kernels.',starts='first coordinate -3,-1,1,3; remaining coordinates 0.1*j for j=1,...,d-1'),indent=2)+'\n')
