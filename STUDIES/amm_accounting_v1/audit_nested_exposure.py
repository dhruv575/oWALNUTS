"""Bounded nested-archive acquisition metadata scan, without filesystem extraction."""
import io,json,hashlib,tarfile,zipfile,time,sys
from pathlib import Path
from exposure_inventory import eligible,intervals

def run(inventory,outer_audit,output):
    inv=json.loads(Path(inventory).read_text());prior=json.loads(Path(outer_audit).read_text())
    start=time.monotonic();records=[];scanned=[];errors=[];limits=[];seen=set()
    def scan(handle,label,depth):
        if depth>4:limits.append(label);return
        if time.monotonic()-start>240:raise TimeoutError('Nested audit deadline')
        iszip=label.endswith('.zip')
        with (zipfile.ZipFile(handle) if iszip else tarfile.open(fileobj=handle,mode='r:*')) as archive:
            for m in (archive.infolist() if iszip else archive):
                name=m.filename if iszip else m.name;size=m.file_size if iszip else m.size
                if (m.is_dir() if iszip else not m.isfile()):continue
                nested=name.endswith(('.zip','.tgz','.tar.gz','.tar'))
                if not nested and not eligible(name):continue
                full=label+'!'+name
                if size>(134217728 if nested else 4194304):limits.append(full);continue
                raw=archive.read(m) if iszip else archive.extractfile(m).read()
                sha=hashlib.sha256(raw).hexdigest()
                if nested:
                    if sha in seen:continue
                    seen.add(sha);scan(io.BytesIO(raw),full,depth+1)
                else:
                    found=intervals(json.loads(raw))
                    if found:records.append(dict(location=full,sha256=sha,intervals=found))
        scanned.append(label)
    # Reopen only parents with nested members; scan also their metadata.
    parents=sorted({name.split('!')[0] for name in prior['nested_archives']})
    for parent in parents:
        try:
            with Path(parent).open('rb') as handle:scan(handle,parent,0)
        except Exception as e:errors.append(dict(path=parent,error=type(e).__name__))
    overlaps=[dict(location=r['location'],interval=x) for r in records for x in r['intervals'] if x['start_ms']<=inv['candidate_end_ms'] and x['end_ms']>=inv['candidate_start_ms']]
    result=dict(scanned=scanned,records=records,overlaps=overlaps,errors=errors,limits=limits,elapsed_seconds=time.monotonic()-start,scope='Nested archive metadata, hash-deduplicated; no price/return payload parsing; 128MiB nested member and depth4 bounds')
    out=Path(output);assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(scanned=len(scanned),overlaps=len(overlaps),errors=len(errors),limits=len(limits))))

if __name__=='__main__':run(*sys.argv[1:])
