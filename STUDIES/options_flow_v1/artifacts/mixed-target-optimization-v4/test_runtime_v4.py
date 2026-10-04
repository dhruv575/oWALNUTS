import copy,json,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from runtime_v4 import validate,environment,sha

def fixture(tmp_path):
 root=tmp_path/'package';root.mkdir();a=root/'adapter.py';e=root/'ext.pyd';a.write_text('adapter');e.write_text('extension')
 c=dict(runtime_identity=dict(package_root=str(root),adapter=dict(path=str(a),sha256=sha(a)),extension=dict(path=str(e),sha256=sha(e))),bindings={str(a):sha(a),str(e):sha(e)})
 return c,SimpleNamespace(__file__=str(a)),SimpleNamespace(__file__=str(e))
def test_correct_paths_and_hashes(tmp_path):
 c,a,e=fixture(tmp_path);assert validate(c,a,e)['adapter']['path']==a.__file__
def test_wrong_hash(tmp_path):
 c,a,e=fixture(tmp_path);Path(e.__file__).write_text('changed')
 with pytest.raises(ValueError,match='hash'):validate(c,a,e)
def test_wrong_path_identical_bytes(tmp_path):
 c,a,e=fixture(tmp_path);other=tmp_path/'other.pyd';other.write_bytes(Path(e.__file__).read_bytes());e.__file__=str(other)
 with pytest.raises(ValueError,match='path'):validate(c,a,e)
def test_env_replaces_conflicting_pythonpath(tmp_path,monkeypatch):
 c,a,e=fixture(tmp_path);monkeypatch.setenv('PYTHONPATH','wrong');env=environment(c)
 assert env['PYTHONPATH']==c['runtime_identity']['package_root'] and env['PYTHONNOUSERSITE']=='1'
def test_actual_import_only_preflight(tmp_path):
 d=Path(__file__).parent;c=json.loads((d/'benchmark-config-v4.json').read_text())
 result=subprocess.run([c['python'],str(d/'preflight_v4.py'),'--config',str(d/'benchmark-config-v4.json')],env=environment(c),capture_output=True,text=True)
 assert result.returncode==0,result.stderr
 report=json.loads(result.stdout);assert report['runtime_identity']['extension']['sha256']==c['runtime_identity']['extension']['sha256']
 with (tmp_path/'preflight-v4-result.json').open('x') as f:json.dump(dict(returncode=result.returncode,command=result.args,pythonpath=environment(c)['PYTHONPATH'],report=report),f,indent=2)
