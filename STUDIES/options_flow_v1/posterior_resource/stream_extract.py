"""Single-pass bounded-row JSON extraction; no numerical imports at module load."""
import hashlib,json,math,re,time
from pathlib import Path

class Stream:
    def __init__(self,path,chunk=65536):
        self.file=open(path,'rb');self.buffer='';self.pos=0;self.chunk=chunk;self.hash=hashlib.sha256();self.bytes=0
    def refill(self):
        raw=self.file.read(self.chunk)
        if not raw:return False
        self.hash.update(raw);self.bytes+=len(raw);self.buffer=self.buffer[self.pos:]+raw.decode('ascii');self.pos=0;return True
    def char(self):
        if self.pos==len(self.buffer) and not self.refill():raise ValueError('Truncated raw array')
        c=self.buffer[self.pos];self.pos+=1;return c
    def nonspace(self):
        c=self.char()
        while c.isspace():c=self.char()
        return c
    def expect(self,wanted):
        if self.nonspace()!=wanted:raise ValueError('Unexpected raw array delimiter')
    def finish(self):
        pending=self.buffer[self.pos:];self.pos=len(self.buffer);divergent=[]
        while True:
            while True:
                match=re.search(r'"divergent"\s*:\s*\[',pending)
                if not match:
                    pending=pending[-32:];break
                end=pending.find(']',match.end())
                if end<0:
                    pending=pending[match.start():]
                    if len(pending)>2000000:raise ValueError('Excessive diagnostic array')
                    break
                values=json.loads(pending[match.end()-1:end+1])
                if any(type(v) is not bool for v in values):raise ValueError('Invalid divergence flags')
                divergent.append(values);pending=pending[end+1:]
            if not self.refill():break
            pending+=self.buffer[self.pos:];self.pos=len(self.buffer)
        self.file.close();return dict(raw_sha256=self.hash.hexdigest(),raw_bytes=self.bytes,divergence_arrays=divergent)


def extract(raw,out,*,chains,draws,dimension,groups=4,rho=.95,x_next=0.):
    """One1012-vector at a time; retained arrays live in an .npy memmap.

    Includes compact all14physical functionals and group0 observed-CDF inputs;
    no prediction noise or pooled-fit independence claim is introduced.
    """
    import numpy as np
    out=Path(out);out.mkdir(parents=True,exist_ok=False);tick=time.perf_counter()
    stream=Stream(raw);q=None;header=''
    try:
        while True:
            header+=stream.char()
            if len(header)>1000000:raise ValueError('Canonical array key not in bounded header')
            if re.search(r'"canonical_draws"\s*:\s*$',header):break
        q=np.lib.format.open_memmap(out/'canonical.npy',mode='w+',dtype='float64',shape=(chains,draws,dimension))
        stream.expect('[')
        for chain in range(chains):
            if chain:stream.expect(',')
            stream.expect('[')
            for draw in range(draws):
                if draw:stream.expect(',')
                stream.expect('[');parts=['['];size=1
                while True:
                    end=stream.buffer.find(']',stream.pos)
                    if end>=0:
                        part=stream.buffer[stream.pos:end+1];parts.append(part);size+=len(part);stream.pos=end+1;break
                    part=stream.buffer[stream.pos:];parts.append(part);size+=len(part);stream.pos=len(stream.buffer)
                    if size>dimension*80:raise ValueError('Excessive/non-numeric draw vector')
                    if not stream.refill():raise ValueError('Truncated raw vector')
                if size>dimension*80:raise ValueError('Excessive/non-numeric draw vector')
                row=json.loads(''.join(parts))
                if len(row)!=dimension or any(type(v) not in (int,float) or not math.isfinite(v) for v in row):raise ValueError('Wrong dimension/nonfinite raw draw')
                q[chain,draw]=row
            stream.expect(']')
        stream.expect(']');metadata=stream.finish();q.flush()
        k=4+2*groups
        if dimension<=k:raise ValueError('Missing latent path')
        vals={'beta_bar':np.asarray(q[...,0]),'tau':np.exp(q[...,1]),'mu_h':np.asarray(q[...,2]),'sigma_h':np.exp(q[...,3]),'h_terminal':np.asarray(q[...,-1]),'h_mean':q[...,k:].mean(axis=-1)}
        for g in range(groups):vals[f'alpha_{g}']=.3*q[...,4+g];vals[f'beta_{g}']=q[...,0]+vals['tau']*q[...,4+groups+g]
        vals['cdf_location']=vals['alpha_0']+vals['beta_0']*x_next
        vals['cdf_future_mean']=vals['mu_h']+rho*(vals['h_terminal']-vals['mu_h'])
        vals['cdf_future_sd']=vals['sigma_h']
        if any(not np.isfinite(v).all() for v in vals.values()):raise ValueError('Derived compact values nonfinite')
        np.savez(out/'compact.npz',**vals)
        metadata.update(chains=chains,draws=draws,dimension=dimension,shape=[chains,draws,dimension],seconds=time.perf_counter()-tick,
            canonical_bytes=(out/'canonical.npy').stat().st_size,compact_bytes=(out/'compact.npz').stat().st_size,
            compact_names=list(vals),chain_order_preserved=True,draw_order_preserved=True,predictive_contract=dict(group=0,horizon=1,x_next=x_next,rho=rho,innovation_multiplier=1.,observation='StudentT with exp(h_next/2) scale'),
            memory_policy='One JSON draw vector plus disk-backed canonical array; compact arrays remain chain-by-draw. No full raw JSON object decoding.')
        return metadata
    finally:
        stream.file.close()
        if q is not None:del q
