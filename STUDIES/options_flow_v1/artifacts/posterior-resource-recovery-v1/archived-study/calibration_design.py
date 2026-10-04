"""Exact independent-replicate coverage-equivalence planning, not an SBC rank test.

Use one Bernoulli per independent generated dataset for a specified parameter
interval. Multiple correlated parameters may use Bonferroni simultaneous bounds;
do not treat horizon/group rows within a dataset as independent replicates.
"""
import argparse
import json
import numpy as np
from scipy.stats import beta, binom


def coverage_interval(successes, trials, family_size=1, alpha=.05):
    if trials < 1 or not 0 <= successes <= trials or family_size < 1 or not 0 < alpha < 1:
        raise ValueError('invalid counts, family size, or alpha')
    a=alpha/family_size/2
    return (0. if successes==0 else float(beta.ppf(a,successes,trials-successes+1)),
            1. if successes==trials else float(beta.ppf(1-a,successes+1,trials-successes)))


def operating_characteristics(trials, nominal=.9, tolerance=.05, family_size=1, actual=None):
    actual=nominal if actual is None else actual
    if not 0 < nominal-tolerance < nominal+tolerance < 1 or not 0 <= actual <= 1:
        raise ValueError('invalid probability or equivalence range')
    counts=np.arange(trials+1)
    accepted=[k for k in counts if (lambda ci:ci[0]>=nominal-tolerance and ci[1]<=nominal+tolerance)(
        coverage_interval(int(k),trials,family_size))]
    return {'replicates':trials,'nominal':nominal,'tolerance':tolerance,'family_size':family_size,
            'actual_coverage':actual,'accepted_counts': [int(min(accepted)),int(max(accepted))] if accepted else None,
            'per_functional_probability_of_equivalence':float(binom.pmf(accepted,trials,actual).sum()),
            'note':'Power is per functional; simultaneous all-functional power depends on dependence. Interval bounds control familywise error by Bonferroni.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trials',type=int,nargs='+',default=[100,200,400,800])
    p.add_argument('--family-size',type=int,default=6)
    p.add_argument('--tolerance',type=float,default=.05)
    a=p.parse_args()
    print(json.dumps([operating_characteristics(n,tolerance=a.tolerance,family_size=a.family_size) for n in a.trials],indent=2))
