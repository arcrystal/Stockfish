#!/usr/bin/env python3
"""Summarize the full observational funnel; these are not causal/Elo estimates."""
from pathlib import Path
import json,re,collections
OUT=Path(__file__).resolve().parent/'results/singular-witness-observation'
FIELDS='depth alpha beta tt sb sv witness capture check eligible tt_result generated rank score seen searched witness_alpha value quiet_before capture_before quiet_nodes_before capture_nodes_before witness_nodes final_move'.split()
rows=[]; nodes=0
for p in sorted(OUT.glob('[0-9][0-9]-observed.stderr.log')):
    text=p.read_text()
    nodes+=int(re.search(r'Nodes searched\s*:\s*(\d+)',text)[1])
    for line in text.splitlines():
        if line.startswith('WIT '):
            vals=list(map(int,line.split()[1:]));assert len(vals)==len(FIELDS)
            row=dict(zip(FIELDS,vals));row['position']=int(p.name[:2]);rows.append(row)
E=[r for r in rows if r['eligible']]
G=[r for r in E if r['generated']]
A=[r for r in G if r['rank']>1]
S=[r for r in A if r['searched']]
summary={'nodes':nodes,'singular_attempts':len(rows),'concrete_witness':sum(r['witness']!=0 for r in rows),'multi_cut_result':sum(r['sv']>=r['sb'] and r['sv']>=r['beta'] and abs(r['sv'])<31507 for r in rows),'eligible':len(E),'eligible_tt_cuts':sum(r['tt_result']>=r['beta'] for r in E),'quiet_generated':len(G),'generated_bad_quiet':sum(r['rank']==0 for r in G),'generated_rank1':sum(r['rank']==1 for r in G),'generated_rank_gt1':len(A),'rank_gt1_positions':len({r['position'] for r in A}),'rank_gt1_seen':sum(r['seen'] for r in A),'rank_gt1_searched':len(S),'rank_gt1_pruned':sum(r['seen'] and not r['searched'] for r in A),'rank_gt1_unreached':sum(not r['seen'] for r in A),'rank_gt1_alpha_improvements':sum(r['value']>r['witness_alpha'] for r in S),'rank_gt1_beta_cutoffs':sum(r['value']>=r['beta'] for r in S),'rank_gt1_final_best':sum(r['final_move']==r['witness'] for r in A),'rank_gt1_prior_quiet_nodes':sum(r['quiet_nodes_before'] for r in A),'rank_gt1_prior_capture_nodes':sum(r['capture_nodes_before'] for r in A),'rank_gt1_witness_nodes':sum(r['witness_nodes'] for r in A),'rank_histogram':dict(sorted(collections.Counter(r['rank'] for r in G).items()))}
funnel=collections.Counter()
for r in rows:
    if r['sv'] < r['sb']: reason='singular_fail_low'
    elif r['sv'] >= r['beta'] and abs(r['sv']) < 31507: reason='multi_cut'
    elif r['check']: reason='in_check'
    elif not r['witness']: reason='no_concrete_witness'
    elif r['capture']: reason='capture_witness'
    elif r['eligible']: reason='eligible'
    else: reason='other'
    funnel[reason]+=1
summary['funnel']=dict(funnel)
summary['outcome_costs']={}
for label,rs in [('cutoff',[r for r in A if r['searched'] and r['value']>=r['beta']]),('failed',[r for r in A if r['searched'] and r['value']<r['beta']]),('unreached',[r for r in A if not r['searched']])]:
    summary['outcome_costs'][label]={'count':len(rs),'prior_quiet_nodes':sum(r['quiet_nodes_before'] for r in rs),'witness_nodes':sum(r['witness_nodes'] for r in rs),'other_final_best':sum(r['final_move'] not in (0,r['witness']) for r in rs)}
summary['split']={}
for label,sub in [('first32',[r for r in A if r['position']<32]),('last32',[r for r in A if r['position']>=32])]:
 summary['split'][label]={'interventions':len(sub),'searched':sum(r['searched'] for r in sub),'alpha_improvement':sum(r['searched'] and r['value']>r['witness_alpha'] for r in sub),'beta_cutoff':sum(r['searched'] and r['value']>=r['beta'] for r in sub)}
summary['applicable_records']=A
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='applicable_records'},indent=2))
