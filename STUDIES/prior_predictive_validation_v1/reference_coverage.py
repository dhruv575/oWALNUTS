"""Compare marginal coverage at all eight original independent-reference spots."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import numpy as np
from posterior_coverage import marginal, NAMES, LEVELS


def run(root):
    root = Path(root)
    seals = {}
    for line in (root/'CHECKSUMS.sha256').read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        seals[name.removeprefix('./')] = digest

    def checked(name):
        raw = (root/name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != seals.get(name):
            raise ValueError('Sealed artifact mismatch: '+name)
        return raw

    def array(prefix, entry):
        raw = checked(prefix+entry['file'])
        if hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('Array record mismatch')
        return np.load(io.BytesIO(raw), allow_pickle=False)

    rows = []
    for index in range(8):
        stream, tick = index*4, (1 if index % 2 == 0 else 32)
        prefix = f'campaign01/campaign/stream-{stream:02d}/'
        refprefix = f'campaign01/campaign/sentinel-{index:02d}/'
        ref = json.loads(checked(refprefix+'reference.json'))
        if (ref['index'], ref['stream'], ref['tick']) != (index, stream, tick):
            raise ValueError('Reference spot identity mismatch')
        data = json.loads(checked(prefix+'data.json'))
        candidate = json.loads(checked(prefix+'candidate.json'))
        record = next(r for r in candidate['rows'] if r['tick'] == tick)
        if record['candidate_status'] != 'ok' or ref['status'] != 'complete':
            rows.extend(dict(index=index, stream=stream, tick=tick, parameter=p, status='unavailable') for p in NAMES)
            continue
        h = array(prefix, data['files']['h'])
        if h.shape != (283,) or record['current_index'] != 249+tick:
            raise ValueError('Latent indexing mismatch')
        truth = [data['parameters'][p] for p in NAMES[:3]]+[h[249+tick]]
        c = marginal(array(prefix, record['compact']), truth)
        r = marginal(array(refprefix, ref['compact']), truth, retained=4000)
        for p, cm, rm in zip(NAMES, c, r):
            rows.append(dict(index=index, stream=stream, tick=tick, parameter=p,
                             status='available', reference_pass=ref['reference_diagnostics_pass'],
                             candidate=cm, reference=rm,
                             candidate_minus_reference_mean=cm['posterior_mean']-rm['posterior_mean']))
    summaries = []
    for p in NAMES:
        selected = [r for r in rows if r['parameter'] == p and r['status'] == 'available']
        for level in LEVELS:
            key = str(level)
            summaries.append(dict(parameter=p, level=level, planned=8, available=len(selected),
                                  candidate_covered=sum(r['candidate']['intervals'][key]['covered'] for r in selected),
                                  reference_covered=sum(r['reference']['intervals'][key]['covered'] for r in selected),
                                  membership_disagreements=sum(r['candidate']['intervals'][key]['covered'] != r['reference']['intervals'][key]['covered'] for r in selected)))
    return dict(scope='Exploratory eight-spot marginal interval corroboration, not an all-stream calibration test',
                numpy=np.__version__, seal_sha256=hashlib.sha256((root/'CHECKSUMS.sha256').read_bytes()).hexdigest(),
                planned=32, available=sum(r['status']=='available' for r in rows), rows=rows, summaries=summaries)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root')
    parser.add_argument('out')
    args = parser.parse_args()
    result = run(args.root)
    with Path(args.out).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(json.dumps(result['summaries']))
