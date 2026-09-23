# Second-pass research: optimize decision value per unit of search

Pinned engine: `031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3`, unchanged `nn-134a887f4c8f.nnue`. This report supersedes the first orchestration document's stale candidate ranking; the experiment ledger remains authoritative for actual results.

**Current decision:** this pass has no supported production upgrade. Four prior STC candidates failed; the new SEE optimization preserved outputs but failed its speed gate; the completed identical-prefix pawn-history audit found zero threshold recoveries in either matched group. No new Fishtest trial is justified from this evidence. This does not exhaust every possible idea: cost-aware ordering remains an unexecuted diagnostic design, and rare or deeper effects remain unmeasured.

## What the four failures teach

Four independent STC gainer hypotheses were rejected, with negative point estimates. Their mechanisms were not four independent routes to better allocation: each attempted to make a local signal more logically faithful (excluded-search correction, TT-bound consistency, threat geometry, repetition return). Only correction's reported 95% Elo interval excludes zero, but none qualifies as an improvement. The appropriate response is to change the selection method, not relabel a failed hypothesis as a correctness improvement or combine the failures.

Stockfish's scores, history entries, TT bounds and reduction flags are coupled control signals. Some represent chess values imperfectly yet predict whether a subtree is worth searching. For example, an excluded-search fail-low can mean "only one move keeps the evaluation afloat". Removing that signal because it is not a formal unrestricted-position bound can remove useful pessimism. A child TT numeric disagreement may indicate unstable search even when its logical bound is inconclusive. A broad escape bonus may encode tactical urgency without representing exact post-move safety. These explanations are plausible interpretations, not causal diagnoses proven by the four game tests.

A future proposal must identify a repeated search decision, a measurable prediction error in the existing policy, and a cheaper or better-targeted response. "More correct", "more depth", "fewer nodes", and "more accurate score" are insufficient objectives independently.

## Why this engine is stronger than simple minimax

Minimax is the decision rule, not a feasible budget policy. Uniform full-width depth grows exponentially with branching factor. Stockfish spends its available computation unevenly while retaining the minimax/negamax structure at searched nodes.

- **Alpha-beta and principal-variation search avoid proving irrelevant precision.** A move that cannot improve the incumbent only needs a bound. With good ordering, a narrow-window test usually answers this cheaply; only promising moves get expensive full-window work. This is exact for an exhaustive tree with exact leaves; Stockfish's reductions and pruning intentionally introduce additional approximation.
- **Iterative deepening purchases predictions.** Earlier iterations seed the PV, TT moves, aspiration center and histories. Its shallow work pays for cheaper ordering and tighter bounds deeper down. Going directly to a large depth would throw away those predictors and reduce the ability to return a completed result when time runs out.
- **LMR allocates depth according to likely relevance.** Late, low-history moves often fail low, so a shallow test cheaply dismisses them. A reduced fail-high triggers verification. The asymmetric risk is important: unnecessary verification costs time, while a false reduced fail-low can hide the best move and never be verified.
- **Pruning turns learned regularities into savings.** Null-move search asks whether the position is strong even after yielding a turn; futility compares estimated improvement with the search window; SEE cheaply filters implausible exchanges. None of these should be evaluated solely for formal minimax soundness. They are useful when saved work buys more decision quality than the missed exceptions cost.
- **Singular extensions spend depth where alternatives look poor.** The engine tests the other moves at a lower threshold. A convincingly unique move merits deeper investigation; several adequate moves make deep forced-line work less valuable. The excluded search is also an information source, not just overhead.
- **Quiescence and NNUE divide tactical and positional work.** A static leaf in the middle of a capture sequence is unstable. Quiescence resolves a selected tactical frontier, and the trained network estimates the remaining long-term position. Sparse feature updates and SIMD make that inference affordable at many leaves. Better leaf prediction also improves pruning and ordering, not merely terminal score accuracy.
- **Memory amortizes decisions across transpositions and nearby contexts.** TT entries reuse position-specific work. Main, continuation, pawn and correction histories generalize less specific evidence. Their value depends on predictive utility, cache cost and calibration under the current selective search.
- **Time management and SMP choose where the whole budget goes.** Root instability and falling evaluations alter time expenditure, while workers explore related searches and share useful information. A stronger subtree policy can still lose if it consumes time needed for later moves or scales badly with depth/threads.

The baseline already uses many superficially attractive proposed signals: unsigned correction magnitude adjusts multiple search decisions; child static-evaluation hindsight changes reduced depth; root effort affects score smoothing and time; follow-PV state protects expected lines; null-move failures accumulate; fail-high recovery adjusts subsequent iterative depths. A creative proposal must specify the information those existing features do not already capture.

## New selection criteria

1. Prefer a frequent, consequential allocation decision over a rare geometric or formal inconsistency.
2. Reuse information the baseline already paid to obtain before adding evaluation, probes or broad searches.
3. Separate the prediction target from the table name. A move can be worth searching early because it is expensive to refute, even if it rarely produces a final cutoff. A history update that rewards such a move is not necessarily mislabeled.
4. Measure both avoided work and missed opportunities. Existing reduced-search verification data contain only selected fail-highs. They cannot measure reduced fail-low false negatives without separate audits.
5. Compare within existing depth, reduction, node-type and history buckets. A new feature correlated with an existing one is not incremental evidence.
6. Predeclare one intervention and a held-out diagnostic. Treat local root agreement/score regret as proxies; independent STC then LTC evidence remains necessary for Elo.

## Rejected shortcut: gate the post-LMR continuation bonus on verification success

The root independently noticed the baseline awards `1334` after a reduced fail-high even if its deeper verification fails low. It would be tempting to reward only the final success. Historical evidence argues against presenting that as a new insight: accepted commits `2ce47573` (October 2024) and `0dabf4f3` (March 2025, PR 5933), identified by the LMR researcher, removed a negative verification-failure malus and then removed the outcome gate. Their official commit messages report STC/LTC simplification passes. The bonus can help order moves that create costly verification work; ordering and reduction reliability are distinct targets. The second pass therefore does not restore the old conditional bonus.

## Source anchors and prior-art limits

Implementation claims above refer to the pinned [search.cpp](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/search.cpp), [movepick.cpp](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/movepick.cpp), and the existing architecture report's NNUE/TT source inventory. This second-pass orchestrator re-read main search, quiescence setup, root iteration/time allocation and move-picker scoring/stages.

Additional bounded historical review inspected `0f602f90349885d6379c08984fdfcd5f3da429d0` (fail-high depth recovery, September 2026), `93ed4b53c4f602c4cc41dbdb67961a2a4712c60b` (effort-weighted root averages, July 2026), `5c93616a3f7517c69eef55cdea67d6f04da63ce9` (aspiration narrowing, October 2025), and `fc54d8730174cdb5cfc4f7074b90128e706e4040` (reverted aspiration adjustment due to mate failures, September 2025). These show how recently tuned and coupled root allocation already is; they do not rule out further improvement. Historical test figures are from official local commit messages, not newly downloaded test payloads.

## Historical proposal, subsequently rejected: retain the singularity refuter

The strongest information-reuse proposal before measurement was a position-specific quiet move witness produced by an already-paid singularity test. The later diagnostic rejected its expected payoff, as recorded below. If the excluded search finds an alternative above `singularBeta` but below the actual parent `beta`, and the TT move subsequently fails to cut, the parent may search other quiet moves before that known alternative. The proposed intervention would retain the witness locally and move it to the front of the **already-good quiet** stage, after good captures, without exempting it from normal pruning or giving it a separate reduction bonus.

This is a ranking proposal, not a correctness repair. The excluded search updates histories before parent quiet scoring, so the parent already benefits indirectly. The explicit witness could add exact-position specificity beyond those generalized history updates. It could also be useless because the histories already place it first, or harmful because it only cleared the lower singular threshold. Candidates with `value >= beta` already cause multi-cut and cannot benefit; nodes where the TT move cuts also cannot benefit. The diagnostic must measure this entire narrowing funnel, not advertise all singular-search nodes as opportunities.

The information-reuse researcher subsequently completed a logging-only baseline instrument preserving baseline bench and recording the witness's natural parent rank after history learning, whether it remains an already-good quiet, whether it is reached or pruned, its result against the actual parent window, and the work on intervening siblings. None of those observed outcomes proves that promotion improves play: reordering changes LMR, TT and history trajectories. If a meaningful opportunity survives, one isolated prototype then needs held-out fixed-budget analysis and normal strength testing.

There is strong contrary prior art to simple special-move promotion. Explicit killer ordering was removed by `985b9fd7b05d1d81be7a1ac90862a5790ee56176` (July 2024, PR 5511), remaining killers by `2343f71f3ff524e937f81b2922705081f8907980` (PR 5517), and the countermove heuristic by `a45c2bc34ae03dd35402e6cf26d515bae1425517` (PR 5441), with official commit messages recording nonregression STC/LTC passes. The proposed witness differs by coming from the exact same board position rather than a sibling at the same ply or analogous preceding move. That distinction needs measured incremental value; it does not evade the historical warning automatically.

## Historical alternative, not promoted: a separate LMR reliability signal

A separate table could predict whether a reduced fail-high survives deeper verification without changing the existing continuation-history bonus. That is conceptually cleaner than forcing one history score to predict both ordering utility and reduction reliability. However, no production rule follows directly: a verification fail-low can mean the extra ply was valuable because it exposed a tactical illusion. Suppressing deeper work in historically unreliable contexts could preserve the illusion, exactly the opposite of the intended benefit. Suppressing deeper work in reliable contexts might instead abandon genuinely promising lines. A survival predictor needs a paired-depth audit of decision regret before it can justify gating the optional `+1` re-search extension. The root collected baseline LMR outcomes and costs; the resulting evidence did not justify a production patch.

## Initial LMR measurement: do not add a new predictor yet

The root's logging-only diagnostic completed 64 seed-20260920 UHO positions at depth 13, with unchanged baseline benchmark **1648567** and identical iteration depth/score/nodes/PV/bestmove to the uninstrumented binary. Across 26,746 actual deeper verifications, 23,496 were quiet; 18,862 quiet verifications remained above alpha (**80.28%**). The current optional-extra-ply group had 8,793/10,205 above alpha (**86.16%**), versus 10,069/13,291 (**75.76%**) without that trigger. Positive `statScore` had 9,876/11,673 (**84.61%**), versus 8,986/11,823 (**76.00%**) for nonpositive scores. The raw aggregate key `negative_history` includes zero and should be described as nonpositive.

These are descriptive conditional rates, not independent trials or causal treatment effects. Nevertheless, they show the existing selectors already enrich for successful verification. A separate reliability table has not demonstrated additional information beyond those selectors, let alone a useful change of action. Do not promote it merely because failures exist. The LMR researcher independently recomputed the counts from all 64 raw logs; full evidence is in `../results/lmr-observation/` and the detailed report. Nested verifier node totals overlap and are not a disjoint fraction of total work. There is currently a **no-go** for implementing or strength-testing the reliability gate.

## Witness measurement: its main payoff did not survive

The information researcher completed all 64 depth-13 roots, preserving every compared iteration depth/score/nodes/PV/bestmove and baseline bench 1648567. The corpus searched 1,704,360 nodes. I independently recomputed the funnel and costs from the 64 raw observation logs:

| Funnel | Count |
|---|---:|
| Singular verification attempts | 38,227 |
| Concrete move witnesses | 19,824 |
| Eligible non-check quiet witnesses below actual beta | 6,081 |
| Parent reaches quiet generation | 724 |
| Witness already first good quiet | 615 |
| Witness belongs to bad quiets | 2 |
| Witness has a later good-quiet rank | 107 |
| Later witness actually searched | 93 |
| Later witness cuts at actual parent beta | 23 |
| Later witness fails current alpha | 70 |
| Earlier move cuts before later witness is reached | 14 |

All 107 later-rank cases were distributed across 41 roots. Three had no earlier legal searched quiet despite the pseudo-legal rank gap, so rank alone slightly overstates the opportunity. No later witness was observed emitted and then pruned. The first 32 roots contained 56 rank interventions and 15 witness cutoffs; the last 32 contained 51 and 8. These are correlated descriptive events, not samples with independent binomial significance.

The decisive observation is **cost**: the 23 witness cutoffs had only **231 preceding quiet-search nodes** between them, approximately 0.014% of corpus nodes even before accounting for nested overlap and changed state under promotion. The 70 naturally reached failed witnesses used 5,148 nodes themselves. Fourteen other quiet moves cut before the witness was reached; those competing searches used 6,469 nodes. That last figure is not a cost the proposal can save—the alternative witness was not established to cut at all.

Histories already put about 85% of generated eligible witnesses first. Thus direct exact-position information existed, but the current machinery was already exploiting almost all of it, and the residual cases offered little observed avoidable work. The strong version of the candidate's rationale did not survive measurement. **Do not implement or submit this fixed promotion rule on the current evidence.** A predeclared deeper diagnostic of the same rule could investigate scaling, but is not an excuse to move thresholds or promote bad quiets until a more favorable slice appears. No new strength claim follows from the observational counts.

## Historical selected experiment, subsequently set aside: less repeated SEE work

The root selected the minimal qsearch SEE-reuse proposal for one bounded runtime falsification. Qsearch sometimes asks the same unchanged position and move whether its exchange value clears two thresholds. A passed threshold at least as high as the later `-74` already answers that later question. The proposed boolean skips only this proved-true second call; all first-call failure score updates and every other path remain intact. The [independent proof audit and exact patch proposal](second-pass-see-proof.md) cover pin/king handling, non-normal moves, and the limits of that source argument.

The logging-only diagnostic retained both calls and found **zero implication violations**, unchanged bench **1648567**, and identical complete iteration traces across all 64 depth-13 roots. It recorded **15,219 eligible calls among 213,141 final qsearch SEE calls** (7.14%). However, **72.47%** of those eligible calls returned before generating attacks. Only **4,190 of 1,714,568** total engine SEE attack-generation entries (0.244%) and **5,578 of 2,542,087** loop iterations (0.219%) would be avoided. Counts include main-search and move-picker SEE in the denominator, and are workload-specific.

The SEE researcher recommended low priority because the saved expensive work is small. The root nevertheless chose a single cheap, fixed whole-engine speed experiment to resolve whether saved simple calls and generated code outweigh the additional branch/state. That is a reasonable falsification, not evidence that the candidate is already strong. The completed test used one isolated baseline-rooted production branch, exact output and functional checks, then 20 alternating paired depth-15 benchmark timings with other task builds and game workloads stopped. No parameter variants or broader move-picker reuse are bundled into it. Runtime benefit was not established, so this did not advance to Fishtest.

The broader search-policy alternatives remain research leads. Pawn history showed only weak exploratory residual verification association after coarse current-feature conditioning, with no reduced-fail-low labels. A new coefficient is unjustified. Cost-aware ordering has a coherent conditional probability/cost objective, but costs and success probabilities change with move order and later moves are censored; the [dedicated report](second-pass-cost-ordering.md) specifies a frozen prospective diagnostic rather than a production penalty.


## SEE runtime result: set aside without a rating test

The isolated candidate `5e16e3f3` passed baseline bench 1648567, all 75 functional tests, all 20 reproducibility cases, and a legal-move threshold-property harness covering 70 positions, 2,172 legal moves, 17,795,196 threshold queries and 143,554 specific implications, including all four move types. The first harness link attempt failed because embedded-network object references were resolved from the wrong directory; the corrected working-directory run passed, and both logs are retained.

The predeclared 20 paired PGO timings then completed, with all 42 runs including warmups searching exactly 3,749,986 nodes. Search-time geometric speedup was **+0.100%**, approximate 95% interval **[−0.176%, +0.376%]**. External wall speedup was **−0.019%**, interval **[−0.270%, +0.232%]**. This does not establish useful whole-engine speed improvement. The branch is preserved, but the candidate is **set aside, with no Fishtest submission and no timing reroll**.

The next substantive investigation was [the pawn-context causal audit](second-pass-pawn-causal-audit.md), now completed below. It targeted missing labels—reduced fail-lows that deeper verification would recover—rather than adding a heuristic from selected fail-high data. Its protocol fixed an unseen 64-root corpus, matched pawn-sign groups and at most 128 single-event depth interventions replayed from the original root prefix. No coefficient or production rule was chosen.


## Final causal allocation result: no supported protection rule

The fixed seed-20260921 corpus excluded the previous 64 exact FENs. All 64 discovery traces matched unmodified baseline. Every root supplied one positive-pawn-history and one nonpositive-pawn-history baseline fail-low in the same frozen depth/scout-depth/move-count/cut-node bucket. The selection manifest was frozen before treatment (SHA-256 `5932cf589f772e3562b5bbe7a2c898e7b143becccf04e41c4ce3dd091392195a`). All **128** single-event `d→d+1` replays completed with matching pre-intervention prefix/entry identities and exactly one intervention. I independently recomputed outcomes from the completed records.

| Outcome | Positive pawn history | Nonpositive pawn history |
|---|---:|---:|
| Selected valid interventions | 64 | 64 |
| Still fail-low after deeper scout | 64 | 64 |
| Verification-supported recoveries | 0 | 0 |
| Exposed illusions / accepted without further verification | 0 / 0 | 0 / 0 |
| Unchanged local scout/move node count | 52 | 55 |
| Unchanged complete-root node count | 47 | 54 |
| Changed actual root best move | 6 | 2 |
| Sum of local additional nodes | +135 | +23 |
| Sum of complete-root node differences | +35,007 | −55,782 |

No deeper scout crossed alpha, so none triggered the retained ordinary verification. The paired recovery discordants are **0 versus 0**: there is no information about positive-sign enrichment in this sample. Do not attach a zero-width uncertainty interval to the two zero rates. Under a simple independent-root binomial model, each 0/64 rate has an exact two-sided 95% interval from 0 to approximately **5.60%**. This describes the selected sample's limited sensitivity, not a bound on every Stockfish position or on Elo.

Most nominal depth increments did not change the local node count. Existing TT and hindsight mechanisms can erase or transform a nominal extra ply; this audit did not attribute each unchanged case to a particular mechanism. Changed full-root costs and best moves are not strength evidence: even the 25 cases with changed local scout scores all remained below alpha, and state/history effects can propagate to subsequent searches. Whole-root node changes ranged from −8,798 to +34,296 in the positive group and −35,928 to +13,312 in controls; opposite signs are not evidence that one pawn group improved play.

The decision is **do not add a pawn-history reduction coefficient or submit a protection patch on this evidence**. We did not observe the hypothesized recovered threshold improvements, let alone a targeting advantage or playing-strength gain. The sample remains limited to a fixed depth, selected nonpositive-statScore contexts, coarse within-root matching and one nominal ply; it does not prove that deeper or rare blind spots are absent. No extra samples, relaxed gates or favorable-subgroup variants were run.

This second pass changed the standard of selection: attractive code interpretations were required to survive measured marginal-information, cost or causal-allocation checks. Several did not. The honest deliverable is the verified explanation, tested negative results and reproducible audit, rather than labeling another unsupported patch a stronger engine.
