"""Bounded deterministic density admission at remapped states; no sampling."""
import hashlib,json,sys,time
from pathlib import Path
import numpy as np
from price_cell_remap import shift
from price_cell_native import compile_target
from price_cell_sv import target


def run(out):
    out=Path(out);out.mkdir(exist_ok=False);start=time.monotonic();rows=[]
    for n in (2,12,250):
        lo=.002*np.sin(np.arange(n+1)*.17)-.0005;hi=lo+.001
        q=np.tile(np.r_[2*np.log(.005),np.log(.2),.0001,np.sin(np.arange(n)*.31),np.cos(np.arange(n)*.23)],(4,1))
        q[:,3:]+=np.arange(4)[:,None]*.07
        remapped,metric,steps=shift(q,np.ones_like(q),np.ones(4)*.1,lo[:-1],hi[:-1],lo[1:],hi[1:])
        lower=lo[1:].copy();upper=hi[1:].copy();owner=compile_target(lower,upper,initial=0.)
        for c in range(4):
            actual,g=owner.value_gradient(remapped[c]);expected,eg=target(remapped[c],lower,upper,0.)
            np.testing.assert_allclose(actual,expected,atol=1e-9,rtol=1e-12)
            np.testing.assert_allclose(g,eg,atol=1e-8,rtol=1e-10)
            rows.append(dict(n=n,chain=c,value_error=abs(actual-expected),max_gradient_error=float(abs(g-eg).max())))
        before=owner.value_gradient(remapped[0]);lower[:]+=10;upper[:]+=10
        after=owner.value_gradient(remapped[0]);assert before[0]==after[0];np.testing.assert_array_equal(before[1],after[1])
    root=Path(__file__).resolve().parent
    names=['check_price_cell_remap_native.py','price_cell_remap.py','price_cell_native.py','price_cell_sv.py','price_cells.py']
    result=dict(rows=rows,caller_mutation_isolated=True,elapsed_seconds=time.monotonic()-start,sources={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names},scope='Deterministic remap and callback density admission only; live WarmSession retarget and sampling untested')
    (out/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':run(sys.argv[1])
