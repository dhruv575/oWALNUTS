"""Fetch tagged dependency metadata and checksum-verified backend for inspection."""
import hashlib,io,json,tarfile,tomllib,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parent/'local_recovery/native_source01';root.mkdir(exist_ok=False)
records=[]
def fetch(url,name,limit):
    with urllib.request.urlopen(url,timeout=30) as response:raw=response.read(limit+1)
    assert len(raw)<=limit
    (root/name).write_bytes(raw);records.append(dict(url=url,file=name,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
    return raw
lock=fetch('https://raw.githubusercontent.com/pymc-devs/nutpie/v0.16.11/Cargo.lock','Cargo.lock',1024**2)
fetch('https://raw.githubusercontent.com/pymc-devs/nutpie/v0.16.11/Cargo.toml','Cargo.toml',1024**2)
dep=next(p for p in tomllib.loads(lock.decode())['package'] if p['name']=='nuts-rs')
raw=fetch('https://static.crates.io/crates/nuts-rs/nuts-rs-'+dep['version']+'.crate','nuts-rs.crate',16*1024**2)
assert hashlib.sha256(raw).hexdigest()==dep['checksum']
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
    assert sum(m.size for m in archive.getmembers())<64*1024**2
    archive.extractall(root,filter='data')
(root/'SOURCES.json').write_text(json.dumps(dict(records=records,dependency=dep,checksum_verified=True,scope='Tagged source provenance; not proof of installed wheel build identity.'),indent=2)+'\n')
print(json.dumps(dict(version=dep['version'],checksum_verified=True)))
