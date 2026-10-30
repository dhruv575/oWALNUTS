import itertools
import numpy as np


def select(coarse, fine, variances):
    v = np.asarray(variances, dtype=float)
    base = np.diag(v)
    def fallback(reason):
        return base.copy(), {'reason': reason, 'blocks': []}
    a, b = np.asarray(coarse), np.asarray(fine)
    d = len(v)
    if d < 2 or d > 16:
        return fallback('dimension')
    if (a.shape != b.shape or a.ndim != 3 or a.shape[1:] != (d, d)
            or len(a) < 2 or not np.isfinite(a).all()
            or not np.isfinite(b).all() or not np.isfinite(v).all() or min(v) <= 0):
        return fallback('invalid')
    for x, y in zip(a, b):
        scale = max(np.linalg.norm(y), 1e-300)
        if max(np.linalg.norm(x-y), np.linalg.norm(y-y.T)) / scale > 1e-4:
            return fallback('derivative')
    h = (b + b.transpose(0, 2, 1)) / 2
    diag = np.diagonal(h, axis1=1, axis2=2)
    eligible = np.flatnonzero(np.all(diag > 0, axis=0)).tolist()
    compatible = set()
    for i, j in itertools.combinations(eligible, 2):
        ratio = np.log(diag[:, i]) - np.log(diag[:, j])
        off = h[:, i, j] / np.sqrt(diag[:, i] * diag[:, j])
        if np.ptp(ratio) <= np.log(1.25) and np.ptp(off) <= .05:
            compatible.add((i, j))
    qualified = []
    count = 0
    for k in range(2, len(eligible)+1):
        for block in itertools.combinations(eligible, k):
            count += 1
            if count > 65536:
                return fallback('budget')
            if not all(pair in compatible for pair in itertools.combinations(block, 2)):
                continue
            q = h[:, block, :][:, :, block]
            z = np.diagonal(q, axis1=1, axis2=2)
            corr = q / np.sqrt(z[:, :, None]*z[:, None, :])
            e = np.linalg.eigvalsh(corr)
            if np.min(e) <= 1e-10:
                continue
            condition = e[:, -1] / e[:, 0]
            if np.min(condition) >= 5 and np.max(condition) <= 1e8:
                qualified.append(frozenset(block))
    maximal = [s for s in qualified if not any(s < t for t in qualified)]
    if not maximal:
        return fallback('no_block')
    if any(s & t for s, t in itertools.combinations(maximal, 2)):
        return fallback('overlap')
    result = base.copy()
    for s in maximal:
        ix = sorted(s)
        q = h[:, ix, :][:, :, ix]
        mean = (q / np.trace(q, axis1=1, axis2=2)[:, None, None]).mean(axis=0)
        cov = np.linalg.inv(mean)
        corr = cov / np.sqrt(np.outer(np.diag(cov), np.diag(cov)))
        result[np.ix_(ix, ix)] = corr * np.sqrt(np.outer(v[ix], v[ix]))
    normalized = result / np.sqrt(np.outer(v, v))
    if not np.isfinite(result).all() or np.linalg.eigvalsh(normalized).min() <= 1e-10:
        return fallback('output')
    return result, {'reason': 'selected', 'blocks': [sorted(s) for s in maximal],
                    'subsets': count}
