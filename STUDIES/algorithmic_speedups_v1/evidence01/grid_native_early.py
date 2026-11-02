import json
from followup_campaign import run,BASE,PY
if __name__=='__main__':
    assert json.loads((BASE/'GRID-NATIVE-PREFLIGHT.json').read_text())['passed']
    row=run('grid_native_worker.py','nuts_grid',954100003,'grid_native_early01',PY)
    (BASE/'GRID-NATIVE-EARLY-STATUS.json').write_text(json.dumps(row,indent=2))
