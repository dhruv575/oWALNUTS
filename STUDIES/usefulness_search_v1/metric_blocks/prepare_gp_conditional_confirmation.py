import hashlib,json
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';source=p.parent/'gp_count/sample_conditional_v3.py'
s=source.read_text();s=s.replace('from common import Target,ROOT',"sys.path.insert(0,str(Path(__file__).resolve().parent/'local_recovery/gp_conditional_local01'))\nfrom common import Target,ROOT")
s=s.replace("(ROOT/'REFERENCE.json')","(Path(__file__).resolve().parent.parent/'gp_count/REFERENCE.json')").replace('float(serr.max())<=.2','float(serr.max())<=.1')
compile(s,'gp_conditional_confirmation_worker.py','exec');(p/'gp_conditional_confirmation_worker.py').write_text(s)
print(json.dumps(dict(original_worker_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),scope='Path adapter and prospectively tighter SD accuracy gate only; proposal and weights unchanged.')))
