import argparse,json
from pathlib import Path
from runtime_v4 import validate
p=argparse.ArgumentParser();p.add_argument('--config',required=True);a=p.parse_args();c=json.loads(Path(a.config).read_text())
import owalnuts,owalnuts._owalnuts as extension
print(json.dumps(dict(status='passed',runtime_identity=validate(c,owalnuts,extension))))
