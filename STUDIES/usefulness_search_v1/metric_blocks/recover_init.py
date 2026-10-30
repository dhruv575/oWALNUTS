import hashlib,json,subprocess,tarfile
from pathlib import Path
base=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030');base.mkdir(exist_ok=False);work=base/'work';work.mkdir();(base/'evidence').mkdir()
subprocess.run(['sudo','-n','mount','-t','tmpfs','-o','size=2G,uid=1000,gid=1000,mode=0700','metric-blocks-recovery',str(work)],check=True)
(base/'ACTIVE-RESEARCH.json').write_text(json.dumps(dict(purpose='Recover current metric audit after unexplained /dev/shm cleanup',work=str(work),do_not_reclaim=True,archive_pending=True),indent=2)+'\n')
print(str(work))
