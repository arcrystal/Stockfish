#!/usr/bin/env python3
"""Observe existing singular witnesses without changing ordering or search."""
import datetime, hashlib, json, re, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'research/results/singular-witness-observation'
CORPUS=ROOT/'research/results/lmr-observation'
ENGINE=ROOT/'.research-tools/singular-witness-diagnostic/src/stockfish'
manifest=json.loads((CORPUS/'corpus.json').read_text())
manifest.pop('comparisons',None)
manifest['started_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
manifest['sha256'][str(ENGINE.relative_to(ROOT))]=hashlib.sha256(ENGINE.read_bytes()).hexdigest()
manifest['comparisons']=[]
with (OUT/'corpus.json').open('x') as f: json.dump(manifest,f,indent=2)
def stable(text):
    return [re.sub(r' (nps|time) \d+', '',line) for line in text.splitlines() if line.startswith(('bestmove','info depth'))]
for i,fen in enumerate(manifest['fens']):
    result=subprocess.run([str(ENGINE),'bench','16','1','13',str(CORPUS/f'position-{i:02d}.fen'),'depth'],capture_output=True,text=True,timeout=90,check=True)
    (OUT/f'{i:02d}-observed.stdout.log').write_text(result.stdout)
    (OUT/f'{i:02d}-observed.stderr.log').write_text(result.stderr)
    if stable(result.stdout)!=stable((CORPUS/f'{i:02d}-baseline.stdout.log').read_text()): raise RuntimeError(f'Behavior mismatch {i}')
    manifest['comparisons'].append({'position':i,'identical_search':True})
    print(f'position {i+1}/64 verified',flush=True)
manifest['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
(OUT/'corpus.json').write_text(json.dumps(manifest,indent=2)+'\n')
