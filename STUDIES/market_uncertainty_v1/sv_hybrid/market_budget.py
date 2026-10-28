"""Only explicitly reviewed campaign budgets; no adaptive extension."""
def budget(spec):
    pair=(spec['warmup'],spec['retained'])
    if pair==(1000,2000):factor=1
    elif pair==(4000,8000) and spec.get('methods')==[2]:factor=4
    else:raise ValueError('Unreviewed sampling budget')
    return dict(warmup=pair[0],retained=pair[1],cap=300*factor-5,
                evaluations=2000000*factor,chain_seconds=300*factor,
                chain_bytes=64*1024**2*factor,outer_seconds=4800*factor,
                queue_seconds=4450*factor,outer_bytes=8*1024**3*factor)
