import json,zipfile
from pathlib import Path
root=Path('/home/ubuntu/infra/posteriordb/posterior_database')
for p in root.rglob('*gp_pois_regr*'):
 if not p.is_file():continue
 print(str(p))
 if p.suffix=='.json':
  print(p.read_text()[:10000])
 elif p.suffix=='.zip':
  with zipfile.ZipFile(p) as z:
   print('members',z.namelist()[:5])
   if '/data/' in str(p):print(z.read(z.namelist()[0]).decode()[:10000])
