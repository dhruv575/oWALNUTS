import hashlib,subprocess,sys
from pathlib import Path
root=Path('/home/ubuntu/lanes/gp-qualified-cost-20261030')
assert (root/'results/SUMMARY.json').exists(),'Batch must be terminal before archiving'
process=subprocess.Popen(['tar','-czf','-','-C',str(root.parent),root.name],stdout=subprocess.PIPE)
h=hashlib.sha256()
while True:
 b=process.stdout.read(1024*1024)
 if not b:break
 h.update(b);sys.stdout.buffer.write(b)
code=process.wait();sys.stdout.buffer.flush();print('ARCHIVE_SHA256='+h.hexdigest(),file=sys.stderr,flush=True);sys.exit(code)
