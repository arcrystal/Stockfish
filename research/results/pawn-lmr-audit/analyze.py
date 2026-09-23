#!/usr/bin/env python3
"""Descriptive matched-root analysis; no engine execution or parameter fitting."""
import collections
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
raw = json.loads((HERE / 'replay-complete.json').read_text())
treatments = raw['treatments']
assert len(treatments) == 128 and all(t['valid'] for t in treatments)
CLASSES = ['still_fail_low', 'exposed_illusion', 'verification_supported_recovery',
           'accepted_without_further_verification']


def cdf(k, n, probability):
    return sum(math.comb(n, i) * probability**i * (1-probability)**(n-i)
               for i in range(k+1))


def probability_at_cdf(k, n, target):
    low, high = 0., 1.
    for _ in range(80):
        middle = (low+high)/2
        if cdf(k, n, middle) > target:
            low = middle
        else:
            high = middle
    return (low+high)/2


def clopper_pearson(successes, count):
    return [0. if successes == 0 else probability_at_cdf(successes-1, count, .975),
            1. if successes == count else probability_at_cdf(successes, count, .025)]


def cost_description(values):
    return {'sum': sum(values), 'mean': statistics.mean(values),
            'median': statistics.median(values), 'min': min(values), 'max': max(values)}


summary = {'valid_treatments': len(treatments), 'matched_roots': 64,
           'selection_sha256': hashlib.sha256((HERE/'selection.json').read_bytes()).hexdigest(),
           'groups': {}, 'pairs': []}
for sign in ['positive', 'nonpositive']:
    group = [t for t in treatments if t['sign'] == sign]
    assert len(group) == 64
    counts = collections.Counter(t['classification'] for t in group)
    successes = counts['verification_supported_recovery']
    summary['groups'][sign] = {
      'count': len(group), 'classifications': {key: counts[key] for key in CLASSES},
      'recovery_rate': successes/len(group),
      'descriptive_binomial_95_interval': clopper_pearson(successes, len(group)),
      'cost_deltas': {key: cost_description([t[key] for t in group])
                     for key in ['scout_nodes_delta', 'move_nodes_delta', 'root_nodes_delta']},
      'unchanged_cost_counts': {key: sum(t[key] == 0 for t in group)
                               for key in ['scout_nodes_delta', 'move_nodes_delta', 'root_nodes_delta']},
      'all_three_costs_unchanged': sum(all(t[key] == 0 for key in
                  ['scout_nodes_delta', 'move_nodes_delta', 'root_nodes_delta']) for t in group),
      'root_bestmoves_changed': sum(t['root_bestmove_changed'] for t in group),
      'entire_root_trace_unchanged': sum(t['root_outcome']['iterations']
                                      == t['baseline_root']['iterations'] for t in group),
      'scout_score_changed': sum(t['treatment_event']['result']['scout_value']
                               != t['discovery_event']['result']['scout_value'] for t in group),
      'baseline_root_nodes': sum(t['baseline_root']['nodes'] for t in group)}

for index in range(64):
    pair = {t['sign']: t for t in treatments if t['root']['index'] == index}
    assert pair.keys() == {'positive', 'nonpositive'}
    p, n = pair['positive'], pair['nonpositive']
    summary['pairs'].append({
      'root_index': index, 'bucket': p['bucket'],
      'positive_recovery': int(p['classification'] == 'verification_supported_recovery'),
      'nonpositive_recovery': int(n['classification'] == 'verification_supported_recovery'),
      'positive_move_nodes_delta': p['move_nodes_delta'],
      'nonpositive_move_nodes_delta': n['move_nodes_delta'],
      'positive_root_nodes_delta': p['root_nodes_delta'],
      'nonpositive_root_nodes_delta': n['root_nodes_delta']})
b = sum(p['positive_recovery'] and not p['nonpositive_recovery'] for p in summary['pairs'])
c = sum(p['nonpositive_recovery'] and not p['positive_recovery'] for p in summary['pairs'])
summary['paired_recovery'] = {'positive_only': b, 'nonpositive_only': c,
    'both': sum(p['positive_recovery'] and p['nonpositive_recovery'] for p in summary['pairs']),
    'neither': sum(not p['positive_recovery'] and not p['nonpositive_recovery'] for p in summary['pairs']),
    'observed_difference': (b-c)/64,
    'exact_mcnemar_two_sided_p': min(1., 2*sum(math.comb(b+c, i) for i in range(min(b,c)+1))/2**(b+c))
                               if b+c else None,
    'note': 'No discordants gives no conditional comparison information; no zero-width interval.'}
with (HERE/'summary.json').open('x') as stream:
    json.dump(summary, stream, indent=2)
    stream.write('\n')
print(json.dumps({k:v for k,v in summary.items() if k != 'pairs'}, indent=2))
