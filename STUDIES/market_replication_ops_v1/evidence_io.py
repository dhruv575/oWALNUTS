"""Minimal immutable operational metadata; no scientific arrays or RNG."""
import json,os
from pathlib import Path
def exclusive(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
