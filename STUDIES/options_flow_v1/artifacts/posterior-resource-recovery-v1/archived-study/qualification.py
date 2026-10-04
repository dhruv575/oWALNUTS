"""Fail-closed component gates over JSON reports and an explicit frozen manifest.

No jobs are launched and no pilot is promoted. Manifest contract:
  status='FROZEN', protocol_sha256=<hash>, alpha=.05, tolerance=.05,
  nominal=.9, family_size=<all simultaneous primary claims>, min_replicates=1200,
  models={name:{primary:[{name,kind:'functional',key} or
     {name,kind:'forecast',horizon:1,group:0}], ...exactly six}},
  cells=[{id,model,arm,seed,fixture_sha256,source_sha256,settings,dimension,
          prior_predictive:True}].
Reports are supplied as {cell_id: report}; absent IDs count as failures. Each
report must additionally record phase='qualification' and protocol_sha256.
Source hashes are checked against the frozen per-arm expectation, not assumed
equal between different implementations. Build verification belongs to runner.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from scipy.stats import beta
from calibration_design import coverage_interval


PRIMARY_NAMES = {
    'flow': {'beta_bar', 'tau', 'mu_h', 'sigma_h', 'h_terminal', 'next_observed_y'},
    'local_level': {'h_initial', 'h_terminal', 'h_mean', 'sigma_obs', 'sigma_rw',
                    'next_observed_log_price'},
}


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_manifest(manifest):
    if manifest.get('status') != 'FROZEN' or not manifest.get('protocol_sha256'):
        raise ValueError('A frozen protocol identity is required; pilot manifests are ineligible')
    cells = manifest.get('cells', [])
    ids = [c['id'] for c in cells]
    if not cells or len(ids) != len(set(ids)):
        raise ValueError('Expected cells must be nonempty and have unique IDs')
    for name, model in manifest['models'].items():
        primaries = model.get('primary', [])
        names = [p['name'] for p in primaries]
        if len(names) != 6 or len(set(names)) != 6:
            raise ValueError('Exactly six distinct named primary functionals per model required')
        kind = model.get('kind', name)
        if kind not in PRIMARY_NAMES or set(names) != PRIMARY_NAMES[kind]:
            raise ValueError('Primary names must match the declared flow/local-level scope')
        if sum(p.get('kind') == 'forecast' for p in primaries) != 1:
            raise ValueError('Primary family must include exactly one observed predictive interval')
        forecast_name = 'next_observed_y' if kind == 'flow' else 'next_observed_log_price'
        for primary in primaries:
            if primary['name'] == forecast_name:
                if primary.get('kind') != 'forecast' or primary.get('horizon') != 1 or primary.get('group') != (0 if kind == 'flow' else None):
                    raise ValueError('Predictive primary must be next observation, group zero for flow')
            elif primary.get('kind') != 'functional' or primary.get('key') != primary['name']:
                raise ValueError('Primary names must select their matching physical functional')
    for cell in cells:
        if cell['model'] not in manifest['models'] or cell.get('dimension', 0) < 1:
            raise ValueError('Invalid cell model/dimension')
        if any(key not in cell for key in ('arm', 'seed', 'fixture_sha256', 'source_sha256', 'settings')):
            raise ValueError('Expected cell identity, settings and source hashes are mandatory')
        if not cell['source_sha256'] or not cell['fixture_sha256']:
            raise ValueError('Nonempty frozen source and fixture hashes required')


def interval_gate(interval, mcse, fraction=.02):
    """Both endpoints must be finite and precise relative to positive width."""
    if not isinstance(interval, (list, tuple)) or len(interval) != 2:
        return False
    if not isinstance(mcse, (list, tuple)) or len(mcse) != 2:
        return False
    if not all(finite(v) for v in list(interval)+list(mcse)):
        return False
    width = interval[1]-interval[0]
    return width > 0 and all(0 <= v <= fraction*width for v in mcse)


def _primary(report, selector):
    evaluation = report['evaluation']
    if selector['kind'] == 'functional':
        row = evaluation['functionals'][selector['key']]
        return row['interval_90'], row['endpoint_mcse'], row.get('truth')
    if selector['kind'] == 'forecast':
        rows = [r for r in evaluation['forecast']['rows']
                if r.get('horizon') == selector['horizon']
                and r.get('group') == selector.get('group')]
        if len(rows) != 1:
            raise ValueError('Exactly one matching predictive row required')
        row = rows[0]
        return [row['lower'], row['upper']], row['endpoint_mcse'], row.get('observed')
    raise ValueError('Unknown primary selector kind')


def cell_gate(report, expected, model, protocol_sha256, require_truth=False, require_qualification=True):
    """Recompute health and precision rather than trust a cached healthy flag."""
    reasons = []
    if report is None:
        return {'pass': False, 'reasons': ['missing expected report'], 'coverage': {}}
    if report.get('status') != 'completed': reasons.append('worker not completed')
    if require_qualification and (report.get('phase') != 'qualification' or report.get('protocol_sha256') != protocol_sha256):
        reasons.append('not a report from the frozen qualification protocol')
    for key in ('arm', 'seed', 'fixture_sha256', 'source_sha256', 'settings'):
        if report.get(key) != expected.get(key): reasons.append(f'mismatched {key}')
    evaluation = report.get('evaluation', {})
    if expected['settings'].get('chains', 0) < 4 or evaluation.get('chain_count') != expected['settings'].get('chains'):
        reasons.append('chain count mismatch or fewer than four chains')
    if report.get('retained_divergences') != 0: reasons.append('missing or nonzero retained divergences')
    checks = evaluation.get('canonical_parameter_diagnostics', {})
    if set(checks) != {f'q_{j}' for j in range(expected['dimension'])}:
        reasons.append('canonical coordinate diagnostics incomplete')
    all_checks = list(checks.values())+list(evaluation.get('functionals', {}).values())
    for row in all_checks:
        if not all(finite(row.get(k)) for k in ('rhat', 'bulk_ess', 'tail_ess')) or not (
                0 < row['rhat'] <= 1.01 and row['bulk_ess'] >= 400 and row['tail_ess'] >= 400):
            reasons.append('convergence gate failed'); break
    coverage = {}
    for selector in model['primary']:
        try:
            interval, mcse, truth = _primary(report, selector)
            if not interval_gate(interval, mcse):
                reasons.append('endpoint precision failed: '+selector['name'])
            if require_truth and not finite(truth):
                reasons.append('missing finite generated truth: '+selector['name'])
            coverage[selector['name']] = bool(finite(truth) and all(finite(v) for v in interval)
                                              and interval[0] <= truth <= interval[1])
        except (KeyError, TypeError, ValueError, IndexError):
            reasons.append('missing/invalid primary: '+selector['name'])
            coverage[selector['name']] = False
    return {'pass': not reasons, 'reasons': reasons, 'coverage': coverage}


def calibration_gate(manifest, reports):
    validate_manifest(manifest)
    alpha = manifest.get('alpha', .05)
    nominal = manifest.get('nominal', .9)
    tolerance = manifest.get('tolerance', .05)
    if nominal != .9 or tolerance != .05 or not 0 < alpha <= .05:
        raise ValueError('This gate implements frozen 90% coverage within five points, alpha<=.05')
    groups = {}
    for cell in manifest['cells']:
        groups.setdefault((cell['model'], cell['arm']), []).append(cell)
    family = manifest.get('family_size', 6*len(groups))
    if family < 6*len(groups):
        raise ValueError('Family size understates simultaneous model/arm claims')
    summaries = {}
    for (name, arm), cells in groups.items():
        model = manifest['models'][name]
        checks = {}
        hits = {p['name']: 0 for p in model['primary']}
        healthy = 0
        for cell in cells:
            gate = cell_gate(reports.get(cell['id']), cell, model, manifest['protocol_sha256'], True)
            if cell.get('prior_predictive') is not True:
                gate['pass'] = False; gate['reasons'].append('fixture is not prior-generative')
            checks[cell['id']] = gate
            if gate['pass']:
                healthy += 1
                for key in hits: hits[key] += int(gate['coverage'][key])
        count = len(cells)
        usable_lower = 0. if healthy == 0 else float(beta.ppf(alpha, healthy, count-healthy+1))
        stats = {}
        for key, covered in hits.items():
            ci = coverage_interval(covered, count, family, alpha)
            stats[key] = {'usable_and_covering': covered, 'attempted': count,
                          'coverage': covered/count, 'simultaneous_ci': list(ci),
                          'pass': ci[0] >= nominal-tolerance and ci[1] <= nominal+tolerance}
        enough = count >= max(1200, manifest.get('min_replicates', 1200))
        # Every expected failed cell fails this component; aggregate rates remain
        # visible so no missing/failed run can be silently dropped or replaced.
        passed = enough and healthy == count and usable_lower >= .99 and all(s['pass'] for s in stats.values())
        summaries[f'{name}/{arm}'] = {'pass': passed, 'attempted': count, 'usable': healthy,
                 'enough_replicates': enough, 'usable_probability_lower_95': usable_lower,
                 'functionals': stats, 'cells': checks}
    return {'calibration_component_pass': all(s['pass'] for s in summaries.values()),
            'family_size': family, 'groups': summaries, 'qualified': False,
            'scope': 'Coverage equivalence only; no rank-SBC, long-path, market or usability claim.'}


def paired_performance_gate(pairs, reports, model, protocol_sha256):
    """Basic all-pairs health/matching/speed screen, not a speed CI analysis.

    pairs=[{'candidate':expected_cell,'reference':expected_cell}]. Comparison
    requires same fixture, seed, dimension and settings; each side's source hash
    is matched to its own frozen expected implementation. Different retained
    counts for a time-to-precision study need a separate registered tier adapter.
    """
    results = []
    for pair in pairs:
        a, b = pair['candidate'], pair['reference']
        ra, rb = reports.get(a['id']), reports.get(b['id'])
        ga = cell_gate(ra,a,model,protocol_sha256)
        gb = cell_gate(rb,b,model,protocol_sha256)
        matched = all(a.get(k) == b.get(k) for k in ('fixture_sha256','seed','dimension','settings'))
        ta = ra.get('end_to_end_seconds') if ra else None
        tb = rb.get('end_to_end_seconds') if rb else None
        valid = ga['pass'] and gb['pass'] and matched and finite(ta) and finite(tb) and ta > 0 and tb > 0
        results.append({'candidate':a['id'],'reference':b['id'],'pass':bool(valid),
                        'candidate_gate':ga,'reference_gate':gb,'matched':matched,
                        'speedup':tb/ta if valid else None})
    all_valid = bool(results) and all(r['pass'] for r in results)
    ratio = math.exp(sum(math.log(r['speedup']) for r in results)/len(results)) if all_valid else None
    return {'all_pairs_pass':all_valid,'geomean_speedup':ratio,
            'material_speed_screen':bool(all_valid and ratio >= 1.25 and min(r['speedup'] for r in results) >= .90),
            'pairs':results,'qualified':False,
            'scope':'Requires preregistered paired uncertainty, workload aggregation and full goal evidence.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path)
    parser.add_argument('reports',type=Path,help='JSON mapping expected cell IDs to reports')
    args = parser.parse_args()
    print(json.dumps(calibration_gate(json.loads(args.manifest.read_text()),
                                     json.loads(args.reports.read_text())),indent=2,allow_nan=False))
