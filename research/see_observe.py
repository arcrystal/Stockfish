#!/usr/bin/env python3
"""Observe redundant SEE decisions without changing the baseline search policy."""
import datetime
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'research/results/see-observation'
SOURCE = ROOT / 'research/results/lmr-observation'
DIAG = ROOT / '.research-tools/see-observation/src/stockfish'
BASE = ROOT / '.research-tools/stockfish-baseline'
KEYS = ['qnodes', 'first_calls', 'first_passes', 'final_calls', 'eligible',
        'violations', 'other_attack_entries', 'noneligible_final_attack_entries',
        'eligible_final_attack_entries', 'other_loop_iterations',
        'noneligible_final_loop_iterations', 'eligible_final_loop_iterations']


def stable(text):
    return [re.sub(r' (nps|time) \d+', '', line) if line.startswith('info depth') else line
            for line in text.splitlines()
            if line.startswith('info depth') or line.startswith('bestmove')]


corpus = json.loads((SOURCE / 'corpus.json').read_text())
base_hash = hashlib.sha256(BASE.read_bytes()).hexdigest()
assert base_hash == corpus['sha256']['.research-tools/stockfish-baseline']
manifest = {'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'source_corpus': str((SOURCE / 'corpus.json').relative_to(ROOT)),
            'source_corpus_sha256': hashlib.sha256((SOURCE / 'corpus.json').read_bytes()).hexdigest(),
            'baseline_sha256': base_hash,
            'diagnostic_sha256': hashlib.sha256(DIAG.read_bytes()).hexdigest(),
            'depth': 13, 'hash_mb': 16, 'threads': 1, 'positions': []}
with (OUT / 'manifest.json').open('x') as stream:
    json.dump(manifest, stream, indent=2)
totals = dict.fromkeys(KEYS, 0)
for i, fen in enumerate(corpus['fens']):
    fenfile = SOURCE / f'position-{i:02d}.fen'
    assert fenfile.read_text().strip() == fen
    command = [str(DIAG), 'bench', '16', '1', '13', str(fenfile), 'depth']
    result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=90)
    for suffix, content in [('stdout', result.stdout), ('stderr', result.stderr)]:
        with (OUT / f'{i:02d}-observed.{suffix}.log').open('x') as stream:
            stream.write(content)
    baseline = (SOURCE / f'{i:02d}-baseline.stdout.log').read_text()
    if stable(result.stdout) != stable(baseline):
        raise RuntimeError(f'Search behavior changed at position {i}')
    rows = [line for line in result.stderr.splitlines() if line.startswith('SEEREUSE,')]
    assert len(rows) == 1
    counts = dict(zip(KEYS, map(int, rows[0].split(',')[1:]), strict=True))
    assert counts['violations'] == 0
    for key, count in counts.items():
        totals[key] += count
    manifest['positions'].append({'index': i, 'identical_search': True, 'counts': counts})
    print(f'position {i+1}/64 verified', flush=True)
manifest['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
(OUT / 'summary.json').write_text(json.dumps(totals, indent=2) + '\n')
print(json.dumps(totals, indent=2))
