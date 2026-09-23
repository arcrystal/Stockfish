#!/usr/bin/env python3
"""Fixed-seed, fixed-depth observational corpus; not a strength or speed test."""
import datetime, hashlib, json, random, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'research/results/lmr-observation'
BOOK = ROOT / '.research-tools/books/UHO_Lichess_4852_v1.epd'
BASE = ROOT / '.research-tools/stockfish-baseline'
DIAG = ROOT / '.research-tools/lmr-observation/src/stockfish'
indices = sorted(random.Random(20260920).sample(range(2632036), 64))
fens = []
with BOOK.open() as stream:
    wanted = set(indices)
    for i, line in enumerate(stream):
        if i in wanted:
            fens.append(line.strip())
manifest = {'seed':20260920, 'depth':13, 'hash_mb':16, 'threads':1,
            'line_indices_zero_based':indices, 'fens':fens,
            'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [BASE, DIAG, BOOK]}}
with (OUT/'corpus.json').open('x') as f: json.dump(manifest,f,indent=2)
comparisons=[]
for i,fen in enumerate(fens):
    fenfile=OUT/f'position-{i:02d}.fen';fenfile.write_text(fen+'\n')
    signatures=[]
    for name,engine in [('baseline',BASE),('observed',DIAG)]:
        result=subprocess.run([str(engine),'bench','16','1','13',str(fenfile),'depth'],capture_output=True,text=True,timeout=90,check=True)
        (OUT/f'{i:02d}-{name}.stdout.log').write_text(result.stdout)
        (OUT/f'{i:02d}-{name}.stderr.log').write_text(result.stderr)
        # Ignore timing/NPS but require all iteration depth, score, nodes and PV/bestmove outputs.
        stable=[]
        for line in result.stdout.splitlines():
            if line.startswith('bestmove'): stable.append(line)
            elif line.startswith('info depth'):
                stable.append(re.sub(r' (nps|time) \d+', '',line))
        signatures.append(stable)
    if signatures[0]!=signatures[1]: raise RuntimeError(f'Behavior mismatch at {i}')
    comparisons.append({'position':i,'identical_search':True})
    print(f'position {i+1}/64 verified',flush=True)
manifest['comparisons']=comparisons
manifest['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
(OUT/'corpus.json').write_text(json.dumps(manifest,indent=2)+'\n')
