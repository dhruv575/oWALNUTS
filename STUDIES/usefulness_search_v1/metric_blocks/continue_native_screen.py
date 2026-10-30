"""Finish the frozen four-chunk screen, verifying each archive before advancing."""
import json,subprocess,sys
from pathlib import Path
study=Path(__file__).resolve().parent
for chunk in [2,3,4]:
    root=study/'local_recovery'/f'nativescreen{chunk:02d}'
    assert not root.exists(), 'Never overwrite or duplicate an existing chunk'
    subprocess.run([sys.executable,str(study/'run_native_screen_chunk.py'),str(chunk)],check=True)
    subprocess.run([sys.executable,str(study/'archive_native_batch.py'),root.name],check=True)
    assert json.loads((root.parent/(root.name+'_archive')/'VERIFICATION.json').read_text())['passed']
