#!/usr/bin/env python3
"""Add pre-scout pawn-history labels to the unchanged, fixed observational corpus."""
import datetime, hashlib, json, re, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/'research/results/lmr-observation'
OUT=ROOT/'research/results/lmr-pawn-observation'; OUT.mkdir(exist_ok=True)
ENGINE=ROOT/'.research-tools/lmr-observation/src/stockfish'
manifest={'source_corpus':'../lmr-observation/corpus.json','binary_sha256':hashlib.sha256(ENGINE.read_bytes()).hexdigest(),'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'comparisons':[]}
with (OUT/'manifest.json').open('x') as f:json.dump(manifest,f)
def stable(text):
 return [re.sub(r' (nps|time) \d+', '',line) for line in text.splitlines() if line.startswith(('info depth','bestmove'))]
for i in range(64):
 result=subprocess.run([str(ENGINE),'bench','16','1','13',str(SOURCE/f'position-{i:02d}.fen'),'depth'],capture_output=True,text=True,timeout=90,check=True)
 (OUT/f'{i:02d}.stdout.log').write_text(result.stdout);(OUT/f'{i:02d}.stderr.log').write_text(result.stderr)
 assert stable(result.stdout)==stable((SOURCE/f'{i:02d}-baseline.stdout.log').read_text()), i
 manifest['comparisons'].append({'position':i,'identical_search':True})
manifest['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('All 64 baseline-equivalence comparisons passed')
