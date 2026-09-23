#!/usr/bin/env python3
"""Frozen discovery/selection/single-target replay; never selects on treatment results."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import random
import re
import subprocess
import threading

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'research/results/pawn-lmr-audit'
OLD = ROOT / 'research/results/lmr-observation/corpus.json'
BOOK = ROOT / '.research-tools/books/UHO_Lichess_4852_v1.epd'
BASE = ROOT / '.research-tools/stockfish-baseline'
DIAG = ROOT / '.research-tools/pawn-lmr-audit/src/stockfish'
SEED = 20260921
DECISIVE = 32000 - 246 - 1 - 246  # VALUE_TB_WIN_IN_MAX_PLY at the pinned baseline
FIELDS = ['parent_key', 'child_key', 'move', 'alpha', 'beta', 'best_value',
          'depth', 'new_depth', 'd', 'move_count', 'stat_score', 'pawn_history',
          'ply', 'pv', 'cut', 'in_check', 'excluded_move', 'tt_pv', 'follow_pv',
          'tt_move', 'gives_check', 'eval', 'static_eval', 'correction',
          'root_depth', 'nodes', 'extension', 'capture', 'prior_capture',
          'moved_piece', 'main_history', 'cont0', 'cont1', 'tt_value', 'tt_depth',
          'tt_bound', 'tt_hit', 'parent_pawn_key', 'parent_rule50',
          'parent_repetition', 'parent_plies_from_null', 'parent_previous_key',
          'child_repetition', 'child_rule50']
SIGNED = {'alpha', 'beta', 'best_value', 'd', 'stat_score', 'pawn_history',
          'eval', 'static_eval', 'correction', 'extension', 'main_history',
          'cont0', 'cont1', 'tt_value', 'tt_depth', 'parent_repetition',
          'child_repetition'}
RESULT_FIELDS = ['ordinal', 'original_d', 'effective_d', 'scout_value',
                 'verified', 'verification_depth', 'final_value', 'stopped',
                 'scout_nodes', 'move_nodes', 'above_alpha', 'cutoff']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write_new(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def stable(text):
    return [re.sub(r' (nps|time) \d+', '', line) for line in text.splitlines()
            if line.startswith('info depth') or line.startswith('bestmove')]


def root_outcome(text):
    infos = [line for line in text.splitlines() if line.startswith('info depth')]
    best = [line for line in text.splitlines() if line.startswith('bestmove')]
    if not infos or len(best) != 1:
        raise RuntimeError('Incomplete root output')
    return {'final_info': re.sub(r' (nps|time) \d+', '', infos[-1]),
            'nodes': int(re.search(r' nodes (\d+)', infos[-1]).group(1)),
            'bestmove': best[0], 'iterations': stable(text)}


def run(engine, fen, stem, target=None):
    """A fresh UCI process, with stdout/stderr preserved even on failure."""
    environment = dict(os.environ)
    environment.pop('SF_PAWN_AUDIT_TARGET', None)
    environment.pop('SF_PAWN_AUDIT_ENTRY', None)
    if target:
        environment['SF_PAWN_AUDIT_TARGET'] = str(target['ordinal'])
        environment['SF_PAWN_AUDIT_ENTRY'] = target['identity']
    with (OUT / f'{stem}.stderr.log').open('x') as err, \
         (OUT / f'{stem}.stdout.log').open('x') as out:
        proc = subprocess.Popen([str(engine)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=err, text=True,
                                env=environment, bufsize=1)
        timer = threading.Timer(120, proc.kill)
        timer.start()
        captured = []

        def send(command):
            proc.stdin.write(command + '\n')
            proc.stdin.flush()

        def receive(marker):
            for line in proc.stdout:
                captured.append(line)
                out.write(line)
                out.flush()
                if line.startswith(marker):
                    return
            raise RuntimeError(f'{stem}: process ended before {marker}')

        try:
            send('uci')
            receive('uciok')
            send('setoption name Threads value 1')
            send('setoption name Hash value 16')
            send('ucinewgame')
            send('isready')
            receive('readyok')
            send('position fen ' + fen)
            send('go depth 13')
            receive('bestmove')
            send('quit')
            for line in proc.stdout:
                captured.append(line)
                out.write(line)
            code = proc.wait(timeout=10)
            if code:
                raise RuntimeError(f'{stem}: exit {code}')
        finally:
            timer.cancel()
            if proc.poll() is None:
                proc.kill()
                proc.wait()
    return ''.join(captured), (OUT / f'{stem}.stderr.log').read_text()


def parse_events(stderr):
    entries, results, total = {}, {}, None
    for line in stderr.splitlines():
        parts = line.split(',')
        if parts[0] == 'PAWN_AUDIT_ENTRY':
            values = list(map(int, parts[1:]))
            assert len(values) == 3 + len(FIELDS) + 2
            ordinal, prefix, digest = values[:3]
            record = dict(zip(FIELDS, values[3:-2], strict=True))
            for name in SIGNED:
                if record[name] >= 2**63:
                    record[name] -= 2**64
            entries[ordinal] = {'ordinal': ordinal, 'prefix': prefix, 'digest': digest,
                                'identity': ','.join(parts[1:-2]),
                                'entry': record, 'eligible': values[-2],
                                'target': values[-1]}
        elif parts[0] == 'PAWN_AUDIT_RESULT':
            record = dict(zip(RESULT_FIELDS, map(int, parts[1:]), strict=True))
            results[record['ordinal']] = record
        elif parts[0] == 'PAWN_AUDIT_TOTAL':
            total = dict(zip(['events', 'digest', 'target', 'hits'],
                             map(int, parts[1:]), strict=True))
        elif parts[0] == 'PAWN_AUDIT_MISMATCH':
            raise RuntimeError('Runtime anchor mismatch: ' + line)
    if total is None or entries.keys() != results.keys():
        raise RuntimeError('Missing audit totals or incomplete events')
    for ordinal, record in entries.items():
        record['result'] = results[ordinal]
    return entries, total


def candidate(event):
    entry, result = event['entry'], event['result']
    return (event['eligible'] and not result['stopped']
            and abs(result['scout_value']) < DECISIVE
            and abs(entry['alpha']) < DECISIVE and abs(entry['beta']) < DECISIVE
            and result['scout_value'] <= entry['alpha'])


def bucket(entry):
    return [0 if entry['depth'] <= 7 else 1 if entry['depth'] <= 9
            else 2 if entry['depth'] <= 11 else 3,
            0 if entry['d'] <= 2 else 1 if entry['d'] <= 4 else 2,
            0 if entry['move_count'] <= 3 else 1 if entry['move_count'] <= 7 else 2,
            entry['cut']]


def pick_hash(root_id, value):
    canonical = json.dumps([SEED, root_id, value], separators=(',', ':'), sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def discovery():
    old = json.loads(OLD.read_text())
    excluded = set(old['fens'])
    draws = random.Random(SEED).sample(range(2632036), 4096)
    wanted = set(draws)
    found = {}
    with BOOK.open() as source:
        for line_index, line in enumerate(source):
            if line_index in wanted:
                found[line_index] = line.strip()
    positions = []
    for index in draws:
        fen = found[index]
        if fen in excluded:
            continue
        excluded.add(fen)
        positions.append({'index': len(positions), 'book_line': index, 'fen': fen,
                          'root_id': hashlib.sha256(fen.encode()).hexdigest()})
        if len(positions) == 64:
            break
    assert len(positions) == 64
    assert sha(BOOK) == old['sha256']['.research-tools/books/UHO_Lichess_4852_v1.epd']
    assert sha(BASE) == old['sha256']['.research-tools/stockfish-baseline']
    bench = (OUT / 'bench.stderr.log').read_text()
    assert re.search(r'Nodes searched\s*:\s*1648567\b', bench)
    manifest = {'started_utc': stamp(), 'seed': SEED, 'depth': 13,
                'threads': 1, 'hash_mb': 16, 'book_sha256': sha(BOOK),
                'diagnostic_sha256': sha(DIAG), 'baseline_sha256': sha(BASE),
                'source_old_manifest_sha256': sha(OLD), 'fields': FIELDS,
                'protocol_sha256': sha(ROOT / 'research/agents/second-pass-pawn-causal-audit.md'),
                'runner_sha256': sha(Path(__file__)), 'positions': positions}
    write_new(OUT / 'corpus.json', manifest)
    roots = []
    for root in positions:
        prefix = f"{root['index']:02d}"
        baseline, _ = run(BASE, root['fen'], prefix + '-baseline')
        observed, stderr = run(DIAG, root['fen'], prefix + '-discovery')
        if stable(baseline) != stable(observed):
            raise RuntimeError(f'Baseline discovery mismatch: root {prefix}')
        events, totals = parse_events(stderr)
        assert totals['hits'] == 0 and totals['target'] == 0
        pool = [event for event in events.values() if candidate(event)]
        record = {'root': root, 'identical_baseline': True,
                  'outcome': root_outcome(observed), 'totals': totals,
                  'eligible_events': list(events.values()), 'pool': pool}
        write_new(OUT / f'{prefix}-discovery.json', record)
        roots.append({'index': root['index'], 'eligible': len(events), 'pool': len(pool)})
        print(f"root {prefix}: exact baseline, {len(events)} eligible, {len(pool)} fail-low", flush=True)
    write_new(OUT / 'discovery-complete.json', {'finished_utc': stamp(), 'roots': roots})


def select_targets():
    manifest = json.loads((OUT / 'corpus.json').read_text())
    assert (OUT / 'discovery-complete.json').exists()
    selected_roots = []
    for root in manifest['positions']:
        record = json.loads((OUT / f"{root['index']:02d}-discovery.json").read_text())
        pools = {}
        for event in record['pool']:
            bins = tuple(bucket(event['entry']))
            sign = 'positive' if event['entry']['pawn_history'] > 0 else 'nonpositive'
            pools.setdefault(bins, {'positive': [], 'nonpositive': []})[sign].append(event)
        common = [bins for bins, signs in pools.items() if all(signs.values())]
        item = {'root': root, 'pool_counts': [
                    {'bucket': bins, **{s: len(events) for s, events in signs.items()}}
                    for bins, signs in sorted(pools.items())], 'selected': []}
        if common:
            bins = min(common, key=lambda bins: pick_hash(root['root_id'], list(bins)))
            item['chosen_bucket'] = bins
            item['bucket_selection_hash'] = pick_hash(root['root_id'], list(bins))
            for sign in ['positive', 'nonpositive']:
                event = min(pools[bins][sign], key=lambda e: pick_hash(root['root_id'], e['identity']))
                item['selected'].append({'sign': sign, 'event': event,
                  'event_selection_hash': pick_hash(root['root_id'], event['identity'])})
        selected_roots.append(item)
    targets = sum(len(root['selected']) for root in selected_roots)
    assert targets <= 128
    write_new(OUT / 'selection.json', {'created_utc': stamp(), 'seed': SEED,
              'corpus_sha256': sha(OUT / 'corpus.json'), 'targets': targets,
              'roots': selected_roots})
    print(f'Selection frozen: {targets} targets; no treatment has run.')


def replay():
    manifest = json.loads((OUT / 'corpus.json').read_text())
    selection = json.loads((OUT / 'selection.json').read_text())
    assert sha(DIAG) == manifest['diagnostic_sha256']
    assert sha(OUT / 'corpus.json') == selection['corpus_sha256']
    write_new(OUT / 'replay-start.json', {'started_utc': stamp(),
              'selection_sha256': sha(OUT / 'selection.json'), 'targets': selection['targets']})
    treatments = []
    for selected_root in selection['roots']:
        root = selected_root['root']
        discovery_record = json.loads((OUT / f"{root['index']:02d}-discovery.json").read_text())
        for chosen in selected_root['selected']:
            event = chosen['event']
            stem = f"{root['index']:02d}-replay-{chosen['sign']}"
            record = {'root': root, 'sign': chosen['sign'],
                      'bucket': selected_root['chosen_bucket'], 'discovery_event': event}
            try:
                stdout, stderr = run(DIAG, root['fen'], stem, target=event)
                entries, totals = parse_events(stderr)
                treatment = entries[event['ordinal']]
                assert totals['target'] == event['ordinal'] and totals['hits'] == 1
                assert treatment['identity'] == event['identity']
                assert treatment['entry'] == event['entry']
                before, after = event['result'], treatment['result']
                assert after['original_d'] == before['original_d']
                assert after['effective_d'] == before['original_d'] + 1
                assert not after['stopped']
                assert abs(after['scout_value']) < 32001 and abs(after['final_value']) < 32001
                alpha = event['entry']['alpha']
                if after['scout_value'] <= alpha:
                    classification = 'still_fail_low'
                elif after['final_value'] <= alpha:
                    classification = 'exposed_illusion'
                elif not after['verified']:
                    assert after['cutoff']
                    classification = 'accepted_without_further_verification'
                else:
                    assert after['verified'] and after['cutoff']
                    classification = 'verification_supported_recovery'
                outcome = root_outcome(stdout)
                baseline_root = discovery_record['outcome']
                record.update(valid=True, classification=classification,
                  treatment_event=treatment, totals=totals, root_outcome=outcome,
                  baseline_root=baseline_root,
                  scout_nodes_delta=after['scout_nodes']-before['scout_nodes'],
                  move_nodes_delta=after['move_nodes']-before['move_nodes'],
                  root_nodes_delta=outcome['nodes']-baseline_root['nodes'],
                  root_bestmove_changed=(outcome['bestmove'].split()[1]
                                         != baseline_root['bestmove'].split()[1]))
            except Exception as error:
                record.update(valid=False, error=str(error))
                write_new(OUT / f'{stem}.json', record)
                raise
            write_new(OUT / f'{stem}.json', record)
            treatments.append(record)
            print(f"{stem}: {classification}, localnodes {record['move_nodes_delta']:+d}, "
                  f"rootnodes {record['root_nodes_delta']:+d}", flush=True)
    write_new(OUT / 'replay-complete.json', {'finished_utc': stamp(), 'treatments': treatments})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['discovery', 'select', 'replay'])
    args = parser.parse_args()
    {'discovery': discovery, 'select': select_targets, 'replay': replay}[args.phase]()
