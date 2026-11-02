"""Compile old/new native backends in a temporary directory; preserve study evidence."""
import ctypes as c
import json
from pathlib import Path
import subprocess
import tempfile
import time
import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[2]
SOURCE = 'STUDIES/physics_pendulum_v1/pendulum.cpp'
DP = c.POINTER(c.c_double)
def ptr(x): return x.ctypes.data_as(DP)

def load(path):
    lib = c.CDLL(str(path))
    lib.create.argtypes = [c.c_double,c.c_double,c.c_double,c.c_int,c.c_int,DP,DP,DP,DP]
    lib.create.restype = c.c_void_p
    lib.destroy.argtypes = [c.c_void_p]
    lib.predict.argtypes = [c.c_void_p,DP,c.c_int,DP,DP]
    lib.predict.restype = c.c_int
    lib.evaluate.argtypes = [c.c_uint64,DP,DP,DP,c.c_void_p]
    return lib

with tempfile.TemporaryDirectory() as directory:
    directory = Path(directory)
    old = subprocess.check_output(['git','show','acea9c8a:'+SOURCE],cwd=ROOT)
    (directory/'old.cpp').write_bytes(old)
    for name, source in [('old',directory/'old.cpp'),('new',ROOT/SOURCE)]:
        subprocess.run(['g++','-std=c++17','-O3','-fPIC','-shared',str(source),'-o',str(directory/(name+'.so'))],check=True)
    before, after = load(directory/'old.so'), load(directory/'new.so')
    after.predict_batch.argtypes = [c.c_void_p,c.c_int,DP,c.c_int,DP,DP]
    times = np.array([0.,.2,1.,2.,4.])
    observed = np.zeros_like(times)
    center, matrix = np.zeros(2), np.eye(2)
    q = np.random.default_rng(71).uniform([-3.,-.5],[0.,1.5],size=(128,2))
    result = {'cases': [], 'maximum_independent_error': 0.}
    for linear in [0,1]:
        contexts = [lib.create(2.4,.05,.01,linear,len(times),ptr(times),ptr(observed),ptr(center),ptr(matrix)) for lib in [before,after]]
        try:
            baseline = np.empty((len(q),len(times)))
            candidate = np.empty_like(baseline)
            for i,row in enumerate(q):
                assert before.predict(contexts[0],ptr(row),len(times),ptr(times),ptr(baseline[i])) == 0
            assert after.predict_batch(contexts[1],len(q),ptr(q),len(times),ptr(times),ptr(candidate)) == 0
            assert np.array_equal(baseline,candidate), np.max(abs(baseline-candidate))
            for row in q[:8]:
                values=[]
                for lib,context in zip([before,after],contexts):
                    grad,lp=np.empty(2),np.empty(1)
                    status=lib.evaluate(2,ptr(row),ptr(grad),ptr(lp),context)
                    values.append((status,lp.copy(),grad.copy()))
                assert values[0][0]==values[1][0] and np.array_equal(values[0][1],values[1][1]) and np.array_equal(values[0][2],values[1][2])
            for i,row in enumerate(q[:4]):
                damping, stiffness = np.exp(row)
                def rhs(t,y): return [y[1],-damping*y[1]-stiffness*(y[0] if linear else np.sin(y[0]))]
                solution=solve_ivp(rhs,(0.,4.),[2.4,0.],t_eval=times,method='DOP853',rtol=1e-12,atol=1e-12)
                error=float(np.max(abs(solution.y[0]-candidate[i])))
                assert solution.success and error < 1e-6
                result['maximum_independent_error']=max(result['maximum_independent_error'],error)
            timings=[]
            for _ in range(5):
                start=time.perf_counter()
                for i,row in enumerate(q): before.predict(contexts[0],ptr(row),len(times),ptr(times),ptr(baseline[i]))
                old_time=time.perf_counter()-start
                start=time.perf_counter()
                after.predict_batch(contexts[1],len(q),ptr(q),len(times),ptr(times),ptr(candidate))
                timings.append([old_time,time.perf_counter()-start])
            result['cases'].append({'linear':bool(linear),'prediction_bitwise_equal':True,'gradient_bitwise_equal':True,'timings_seconds':timings})
        finally:
            for lib,context in zip([before,after],contexts): lib.destroy(context)
    print(json.dumps(result,indent=2))
