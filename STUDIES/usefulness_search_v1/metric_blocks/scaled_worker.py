import hashlib,json,subprocess,sys,time
from pathlib import Path
import numpy as np
from scaled_policy import prepare
start=time.monotonic();inp=json.loads(Path(sys.argv[1]).read_text());out=Path(sys.argv[2]);folder=out.parent
pilotpath=Path(inp['pilot']);raw=pilotpath.read_bytes();pilot=json.loads(raw);x=np.asarray(pilot['draws'])
args=inp['sampler'];assert args['starts']==x[:,-1,:].tolist()
target=None
if inp['policy'] not in ['auto','dense']:
    import bridgestan as bs
    target=bs.StanModel(args['model'],data=Path(args['data']).read_text(),seed=1)
detail=prepare(x,target,inp['policy']);args=dict(args,arm=detail['mode'])
args.pop('mass',None)
if detail['mass'] is not None:args['mass']=np.asarray(detail['mass']).ravel().tolist()
(folder/'POLICY.json').write_text(json.dumps(dict(detail,pilot_sha256=hashlib.sha256(raw).hexdigest()),indent=2,allow_nan=False)+'\n')
sampler_input=folder/'SAMPLER-INPUT.json';sampler_input.write_text(json.dumps(args,indent=2)+'\n')
subprocess.run([inp['binary'],str(sampler_input),str(out)],check=True)
# Full timing comes from the outer supervisor, including imports and this output.
# Do not duplicate raw draws or overwrite the sampler's own clock.
