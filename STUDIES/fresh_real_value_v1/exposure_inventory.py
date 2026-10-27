"""Bounded acquisition-metadata audit; never parses price/return payloads."""
import hashlib,json,subprocess,time,zipfile
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
ROOTS=[Path('C:/dev/owalnuts'),Path('C:/dev/owalnuts-wt')]
MAX_FILE=4*1024*1024
START_KEYS=('start_ms','start_timestamp','start_ms_inclusive')
END_KEYS=('end_ms','end_timestamp','end_ms_exclusive')

def intervals(value):
    found=[]
    if isinstance(value,dict):
        for lo in START_KEYS:
            for hi in END_KEYS:
                a,b=value.get(lo),value.get(hi)
                if isinstance(a,(int,float)) and isinstance(b,(int,float)) and 1e12<a<=b<2e12:
                    found.append(dict(start_ms=a,end_ms=b,end_key=hi))
        for key,v in value.items():
            if key in ('url','request_url') and isinstance(v,str) and 'deribit' in v:
                q=parse_qs(urlsplit(v).query)
                try:found.append(dict(start_ms=int(q['start_timestamp'][0]),end_ms=int(q['end_timestamp'][0]),end_key='url_end_timestamp',endpoint=urlsplit(v).path,instrument=q.get('instrument_name')))
                except (KeyError,ValueError):pass
            if isinstance(v,(dict,list)):found.extend(intervals(v))
    elif isinstance(value,list):
        for item in value:
            if isinstance(item,(dict,list)):found.extend(intervals(item))
    return found

def eligible(name):
    n=Path(name).name.lower()
    return n.endswith('.json') and ('protocol' in n or n.startswith('request-') or n in ('acquisition-bindings.json','external-data-inventory.json'))

def main():
    started=time.monotonic();records=[];seen={};counts=dict(metadata_files=0,archive_members=0,skipped_large=0,parse_errors=0);archives=[]
    def consume(raw,label,archive=False):
        counts['archive_members' if archive else 'metadata_files']+=1
        h=hashlib.sha256(raw).hexdigest()
        if h in seen:
            if seen[h] is not None:records[seen[h]]['locations'].append(label)
            return
        try:value=json.loads(raw)
        except (ValueError,UnicodeError):counts['parse_errors']+=1;return
        found=intervals(value);seen[h]=len(records) if found else None
        if found:records.append(dict(sha256=h,locations=[label],intervals=found))
    for root in ROOTS:
        command=['rg','--files','--hidden','--no-ignore','-g','*protocol*.json','-g','request-*.json','-g','acquisition-bindings.json','-g','external-data-inventory.json','-g','*.zip',
            '-g','!**/.git/**','-g','!**/.venv/**','-g','!**/site-packages/**','-g','!**/node_modules/**','-g','!**/target/debug/**','-g','!**/target/release/**',str(root)]
        result=subprocess.run(command,capture_output=True,text=True,timeout=30)
        if result.returncode not in (0,1):raise RuntimeError(result.stderr)
        for name in result.stdout.splitlines():
            path=Path(name)
            if path.suffix.lower()=='.zip':
                if '/studies/' in path.as_posix().lower():archives.append(path)
                continue
            if not eligible(name):continue
            if path.stat().st_size>MAX_FILE:counts['skipped_large']+=1;continue
            consume(path.read_bytes(),str(path))
    for path in sorted(set(archives)):
        if time.monotonic()-started>120:raise TimeoutError('Bounded metadata audit exceeded120s')
        try:
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    if not eligible(member.filename):continue
                    if member.file_size>MAX_FILE:counts['skipped_large']+=1;continue
                    consume(archive.read(member),str(path)+'!'+member.filename,True)
        except zipfile.BadZipFile:counts['parse_errors']+=1
    out=dict(scope='Acquisition protocol/request metadata only; no return/price/response values read; bounded project inventory, not universal proof of no exposure',roots=list(map(str,ROOTS)),counts=counts,archive_files_considered=len(set(archives)),unique_metadata_hashes=len(seen),elapsed_seconds=time.monotonic()-started,records=records)
    target=Path(__file__).with_name('EXPOSURE-METADATA.json')
    with target.open('x',encoding='utf8') as f:json.dump(out,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in out.items() if k!='records'}))

if __name__=='__main__':main()
