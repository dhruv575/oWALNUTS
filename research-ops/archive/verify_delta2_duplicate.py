import hashlib,json,subprocess
from pathlib import Path
p=Path(__file__).resolve().parent
m=json.loads((p/'delta2-duplicate-audit-20261030.json').read_bytes())
repo=p.parents[1]
commits={r['commit'] for r in m['files']}
for commit in commits:subprocess.run(['git','-C',str(repo),'merge-base','--is-ancestor',commit,'origin/main'],check=True)
for r in m['files']:
    b=subprocess.check_output(['git','-C',str(repo),'cat-file','blob',r['blob']])
    assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256']
result=dict(passed=True,files=len(m['files']),bytes=m['total_bytes'],manifest_sha256=hashlib.sha256((p/'delta2-duplicate-audit-20261030.json').read_bytes()).hexdigest(),scope='Every remote file matched an independently read local Git blob; source commit ancestor of origin/main. Git objects retained.')
(p/'delta2-duplicate-local-verification-20261030.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
