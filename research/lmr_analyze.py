#!/usr/bin/env python3
"""Summarize existing verification events; does not infer causal effects or Elo."""
from pathlib import Path
import json
OUT = Path(__file__).resolve().parent / 'results/lmr-observation'
rows=[]
for p in sorted(OUT.glob('*-observed.stderr.log')):
    for line in p.read_text().splitlines():
        if line.startswith('LMR,'):
            rows.append(list(map(int,line.split(',')[1:])))
groups=[('all',lambda r:True),('quiet',lambda r:not r[8]),
        ('capture',lambda r:r[8]),
        ('quiet+extension',lambda r:not r[8] and r[3]>r[2]),
        ('quiet+no_extension',lambda r:not r[8] and r[3]<=r[2]),
        ('quiet+positive_history',lambda r:not r[8] and r[5]>0),
        ('quiet+negative_history',lambda r:not r[8] and r[5]<=0)]
summary={}
for name,condition in groups:
    values=[r for r in rows if condition(r)]
    summary[name]={'count':len(values),
        'verified_above_alpha':sum(r[16]>r[11] for r in values),
        'verification_nodes_inclusive':sum(r[18] for r in values),
        'reduced_nodes_inclusive':sum(r[17] for r in values)}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
