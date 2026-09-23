#!/usr/bin/env python3
"""Exploratory matched-bin descriptions, not causal estimates or held-out inference."""
from pathlib import Path
from collections import defaultdict
import json
OUT=Path(__file__).resolve().parent/'results/lmr-pawn-observation'
summary={}
for split,ids in [('first32',range(32)),('last32',range(32,64))]:
    groups=defaultdict(lambda:[0,0]);cells=defaultdict(lambda:[[0,0],[0,0]])
    for i in ids:
        for line in (OUT/f'{i:02d}.stderr.log').read_text().splitlines():
            if not line.startswith('LMR,'):continue
            r=list(map(int,line.split(',')[1:]))
            depth,d,nd,vd,rank,h,pv,cut,capture,check,ttpv,alpha,beta,best,ev,red,val,rn,vn,pawn,incheck,excluded=r
            if capture or pv or incheck or excluded or nd<=d:continue
            survived=int(val>alpha);sign=int(pawn>0)
            key=('positive' if h>0 else 'nonpositive')+'_stat/'+('positive' if sign else 'nonpositive')+'_pawn'
            groups[key][0]+=1;groups[key][1]+=survived
            stratum=(min(depth//2,8),min(nd-d,4),min(rank//4,4),h//4096,cut)
            cells[stratum][sign][0]+=1;cells[stratum][sign][1]+=survived
    matched=[v for v in cells.values() if min(v[0][0],v[1][0])>=10]
    weights=[min(v[0][0],v[1][0]) for v in matched]
    delta=sum(w*(v[1][1]/v[1][0]-v[0][1]/v[0][0]) for w,v in zip(weights,matched))/sum(weights) if weights else None
    summary[split]={'groups':dict(groups),'matched_strata':len(matched),'matched_min_count':sum(weights),'weighted_survival_difference_positive_pawn':delta}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
