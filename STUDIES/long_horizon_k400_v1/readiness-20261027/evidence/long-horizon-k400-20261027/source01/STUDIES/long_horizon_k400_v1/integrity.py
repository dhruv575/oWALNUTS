"""Single-pass artifact integrity audit before descriptive reporting."""
import hashlib,json
from pathlib import Path
import numpy as np

def audit(root):
    root=Path(root).resolve();errors=[];verified=set();inventory={}
    def check(path,want):
        path=Path(path).resolve()
        if not path.is_relative_to(root):errors.append('outside campaign: '+str(path));return
        try:
            got=hashlib.sha256(path.read_bytes()).hexdigest();inventory[str(path.relative_to(root))]=got
            if got!=want:errors.append('hash mismatch: '+str(path.relative_to(root)))
            else:verified.add(str(path.relative_to(root)))
        except OSError:errors.append('missing artifact: '+str(path.relative_to(root)))
    def walk(value,base):
        if isinstance(value,dict):
            if 'file' in value and 'sha256' in value:check(base/value['file'],value['sha256'])
            if 'copy_path' in value and 'sha256' in value:check(value['copy_path'],value['sha256'])
            for v in value.values():walk(v,base)
        elif isinstance(value,list):
            for v in value:walk(v,base)
    for path in sorted(root.rglob('*.json')):
        if 'compiler-workspace' in path.parts:continue
        try:
            raw=path.read_bytes();value=json.loads(raw);inventory[str(path.relative_to(root))]=hashlib.sha256(raw).hexdigest()
            if 'lanes' in path.parts:
                base=root/'lanes'/path.relative_to(root/'lanes').parts[0]
            else:base=path.parent
            walk(value,base)
            if isinstance(value,dict) and value.get('native_record_sha256'):check(base/'native'/f"{value['tick']:06d}.json",value['native_record_sha256'])
            if isinstance(value,dict) and value.get('compact') and value.get('compact_value_sha256'):
                array=np.load(base/value['compact']['file'],allow_pickle=False)
                if hashlib.sha256(array.tobytes(order='C')).hexdigest()!=value['compact_value_sha256']:errors.append('compact value mismatch: '+str(path))
        except Exception as exc:errors.append('invalid evidence '+str(path)+': '+repr(exc))
    for path in root.glob('lanes/*/progress.jsonl'):
        raw=path.read_bytes();lines=raw.splitlines()
        for i,line in enumerate(lines):
            try:
                event=json.loads(line)
                if event.get('event')=='tick_completed':check(path.parent/'records'/f"{event['tick']:06d}.json",event['record_sha256'])
            except Exception as exc:
                # A final partial append after process death is preserved and explicitly flagged.
                errors.append('invalid progress line '+str(path)+':'+str(i+1)+': '+repr(exc))
        inventory[str(path.relative_to(root))]=hashlib.sha256(raw).hexdigest()
    return dict(integrity_ok=not errors,verified_referenced_files=len(verified),errors=errors,inventory=inventory)
