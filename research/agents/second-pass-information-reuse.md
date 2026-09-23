# Second pass: reuse the move that refuted singularity

Baseline: `031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3`. Investigation date: 20 September 2026. This is a research proposal, not an implemented change or an Elo claim. The initial proposal involved no engine edits. A later explicitly authorized observational-only diagnostic is documented below; it changes no search decisions. The [ledger](../EXPERIMENTS.md) records four rejected search candidates and one NNUE implementation that did not establish a speed benefit.

## What actually makes this engine strong

A fixed-depth minimax search spends most of its budget proving facts irrelevant to the root decision. Alpha-beta avoids some of that work without changing the answer of a complete fixed-depth search. With favorable ordering, its effective tree can be vastly smaller. Stockfish then deliberately departs from complete fixed-depth search: it predicts where another unit of computation could change the answer and spends unevenly.

Its main sources of information are complementary:

- Iterative deepening buys a move ordering and score estimate for the next iteration. Aspiration windows and PVS ask narrow questions for most moves: can this alternative beat the incumbent? A promising answer is verified with a larger search.
- TT entries preserve local search evidence: a move, score bound, depth, static evaluation, and PV status. A sufficiently useful entry can save an entire search, supply the first move, or improve the evaluation estimate used in pruning.
- Histories generalize successful moves across positions. Butterfly history remembers a move, continuation history remembers its move context, and pawn history distinguishes structures. The combination influences ordering, pruning, and reductions. It is an online allocation policy, not a catalogue of objectively good chess moves.
- Singular search spends a shallow excluded-move search to discover whether the TT move is unusually necessary. A singular result extends that line; multiple successful moves can justify a multi-cut; ambiguous nonsingularity can reduce the TT move.
- NNUE supplies a strong leaf estimate that sees patterns a short tactical tree does not resolve. Incremental accumulators reuse changed features, lazily evaluate positions actually needed, and reuse cached king-relative feature state. Its main advantage is strong evaluation at an affordable cost, not exhaustive strategic understanding.
- Quiescence and SEE reduce the instability of material exchanges at leaves. Their limited search complements the neural estimate. Neither is intended to exactly solve every tactical or positional question.

These techniques are coupled. The previous queen patch altered ordering, which also altered move-count pruning and LMR. A more accurate geometric term need not allocate computation better. The previous correction and TT patches may have removed heuristically useful warning signals even where the new interpretation was formally cleaner. Their negative point estimates support changing the research objective: find new useful information, then show that the current allocation policy is failing to exploit it. Semantic elegance is insufficient.

These observations follow the pinned [search implementation](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/search.cpp), [move picker](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/movepick.cpp), [evaluation](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/evaluate.cpp), and [accumulator](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/nnue/nnue_accumulator.cpp) code. They are mechanism descriptions, not an additive Elo decomposition.

## One precise candidate

**Retain the concrete quiet move that refutes singularity, and move it to the front of the parent's existing good-quiet group.** Reuse a search already paid for; add no new search, pruning exemption, extension, network, or history table.

This proposal is deliberately narrower than a second TT move or a new killer heuristic. The evidence belongs to this exact position during this invocation. It expires when the node returns.

### Exact chronology in the baseline

1. The parent constructs `MovePicker` before its move loop.
2. `MAIN_TT` returns the TT move before generating/scoring either captures or quiets.
3. While considering this TT move, singular verification calls `search<NonPV>` on the same position and stack entry with the TT move excluded, at about half depth and window `[singularBeta-1, singularBeta]`.
4. An alternative can raise alpha and become that excluded search's local `bestMove`. The search updates normal histories but deliberately does not write an excluded result into the TT. Its return value communicates the score; the particular alternative move is discarded.
5. If the excluded value reaches the parent's beta, the existing multi-cut returns immediately. There is no opportunity for the proposed ordering change.
6. Otherwise the parent searches its TT move. Only if that also does not cut does it continue to captures and quiets. `QUIET_INIT` then reads the histories that the excluded search already updated.

Therefore the claim is **not** that the parent's move list has stale history scores. It has fresh scores. The potential missing information is exact-position identity, beyond the broad statistical updates those scores contain.

### Bounded implementation specification

A first prototype, if diagnostics justify it, would do only this:

- Clear an output move immediately before the excluded call. Populate it only when that excluded search actually finds a `bestMove` in its move loop; early pruning, TT-derived results, no-move exits, and interrupted searches produce no witness. A dedicated stack scratch member can avoid changing every search function's calling convention; verify struct size and ownership before choosing it.
- Retain the witness in the parent only for a non-check node, a legal quiet alternative different from the TT move, and `singularBeta <= value < beta`. The upper inequality matters: the existing multi-cut already handles higher results.
- Pass/store that move in the parent's `MovePicker`. At `QUIET_INIT`, perform the unchanged scoring and partial sort. If the witness belongs to the existing good-quiet group (`score > -14000`), rotate it to the front of that group. Keep its numeric score unchanged. Otherwise do nothing.
- Preserve good-capture precedence, bad-capture precedence over bad quiets, quiet skipping, all search pruning, all LMR formulas, all history updates, and all singular-extension decisions. Do not promote the witness out of the bad-quiet group. Do not exempt it from SEE or futility.

This can be implemented without an arbitrary new weighting coefficient. Rotation adds a bounded scan/move only in the rare nominated case; score computation is already required. It still changes move-count-dependent allocation. A first quiet reaches the move-count/LMR rules sooner and receives the ordinary treatment for that rank. That is the intervention being tested; a separate reduction-protection bonus would confound it.

## Why the idea could help, and why it could easily fail

A quiet with recent direct search evidence in the exact position might be more likely to improve alpha than one with better aggregate history. Searching it earlier could find a cutoff before several speculative siblings and avoid reducing it excessively. In a tactical position a historically uncommon defensive or preparatory move can be the concrete nonsingular alternative.

However, the informative cases are severely filtered. The excluded result must be below the actual beta, the TT move must fail to cut, good captures must fail to cut, and the updated histories must still place the witness behind another good quiet. The strongest results already trigger multi-cut. The useful denominator is not the number of singular searches.

The strongest counterexample is an alternative that merely clears a low `singularBeta`, yet loses to a better quiet at the parent's higher alpha. Promoting that move spends depth on a mediocrity and pushes the true improvement later, where it can be reduced or pruned. Moreover, the excluded search itself can choose the first adequate move, not the best alternative; its move is a threshold witness. It is not a principal variation or a reliable exact score. The existing negative extension of the TT move already redistributes effort to all alternatives, and the existing history bonus may already promote this witness sufficiently.

For these reasons I recommend a cheap diagnostic only, not another immediate Fishtest submission. A belief that “direct evidence is always better” would repeat the first pass's mistake.

## Diagnostic that can reject this before consuming match games

Use a logging-only baseline build, preserving its bench signature and root outputs. Run a fixed diverse position sample at fixed node budgets. Split discovery and held-out positions in advance; avoid analyzing only illustrative successes. No additional searches are needed for the first stage.

For each singular verification record the node identity, parent depth/window, TT value, singular threshold/depth, whether a concrete alternative was found, its move/capture status, returned bound/result, and whether existing multi-cut ended the node. For eligible quiet witnesses, record:

1. Whether the parent's TT move cuts; whether a good capture cuts; whether quiet generation is reached.
2. The witness's natural **post-history-update** quiet score/rank, whether it qualifies as good quiet, and the exact count of affected nodes per million search nodes.
3. Whether it is actually searched, pruned, or never reached; its pre-search reduction/depth; its returned value relative to the parent's actual alpha and beta at that time; and the eventual node best move.
4. Nodes spent on quiet siblings before reaching it, and whether those earlier siblings improve alpha or cut off first. Keep those competing successes as costs, not just the apparent savings when the witness eventually cuts.
5. The gap `parentBeta - singularBeta` and `ttValue - parentBeta`. These distinguish a nearly relevant threshold witness from a weak low-window certificate. Report all predeclared buckets rather than selecting whichever looks best afterward.

Do not treat a pruned witness as a known missed winner. Do not treat nodes spent on earlier siblings as guaranteed savings: those searches change histories, TT state, alpha, and subsequent depths. Natural-rank versus eventual cutoff comparisons have survivorship bias because many witnesses are never searched. They are screening evidence, not causal or Elo evidence.

Reject the proposal if useful interventions are negligible, histories already rank almost all witnesses first, or reached witnesses overwhelmingly fail the actual alpha while earlier good quiets often succeed. Conversely, a frequent rank gap with retained high-window usefulness would justify one isolated prototype and a predetermined fixed-node comparison on held-out positions. Measure root decision changes, completed work, actual wall time, and failures. Do not select variants by small game Elo or node-count alone. Functional tests and a fixed local gross-regression screen precede a standard independent STC trial; LTC remains required after any STC pass.

## Prior work and novelty limits

Stockfish has previously reused the *score* from singular verification to change move-count pruning: [b34a690c](https://github.com/official-stockfish/Stockfish/commit/b34a690cd4aa6d828ae0f47b427167f4e6392db7). That mechanism was later [removed with non-regression testing](https://github.com/official-stockfish/Stockfish/commit/b1f522930d58118a6035870fe7d02b3d82681ec8). Both facts matter; a once-successful conceptual family is no guarantee that extra reuse pays in the present engine.

[Killers were removed in 2024](https://github.com/official-stockfish/Stockfish/commit/2343f71f3ff524e937f81b2922705081f8907980), with compensating history initialization and non-regression support. This warns against assuming that another remembered quiet automatically adds useful information beyond histories. This proposal retains an exact same-position witness, not a move inferred from a sibling at the same ply, but it still must establish marginal value.

Local history searches for singular/alternative-move/killer changes and a bounded web search did not establish a previous matching accepted implementation. That is not proof of novelty. The source and mechanism are the justification; novelty is not.

## Scope and conclusion

Read during this investigation: complete `movepick.cpp`, `movepick.h`, and `evaluate.cpp`; `search.cpp` initialization, evaluation/TT, early pruning, move loop, singular search, LMR/re-search, completion, and history-update sections; `search.h` stack interface; first 230 lines of `nnue_accumulator.cpp`; NNUE network/architecture call sites; previous reports 03/04/06 and orchestration; current ledger. Historical commits inspected: `b34a690c`, `b1f52293`, `2343f71f`.

The candidate offers a plausible new information channel at limited cost, but its opportunity is narrower than an initial description suggests. It should compete with other second-pass ideas on measured marginal information and incidence. There is currently no evidence sufficient to call it a strong improving upgrade.


## Measured diagnostic outcome: do not promote this rule to a strength test

The lead subsequently authorized a logging-only implementation in the ignored baseline worktree `.research-tools/singular-witness-diagnostic`. Its default bench remained **1,648,567 nodes**. At depth 13, one thread, Hash=16, all **64** fixed-seed UHO positions matched the baseline's every iteration depth, score, node count, PV, and bestmove after ignoring time/NPS. The corpus totaled **1,704,360 nodes**. This is an observational position sample, not a speed measurement or game match. The previously generated corpus is reused without selecting positions for this hypothesis.

The complete mutually exclusive funnel for **38,227 singular attempts** was:

| Branch outcome, in search-code order | Count |
|---|---:|
| Excluded result below singularBeta | 15,615 |
| Existing multi-cut handles nonsingular result | 15,524 |
| Remaining node in check | 100 |
| Remaining node without concrete witness | 215 |
| Remaining witness is capture | 692 |
| Eligible quiet lower-window witness | 6,081 |

Of the 6,081 eligible witnesses, **5,356** were preempted by the TT move's cutoff. **724** reached quiet generation. One further case did not reach that stage. Among generated quiets, **615 (84.9%) were already first**, two were bad quiets outside the proposed rule, and **107** had a good-quiet rank above one. The intervention would occur about **63 times per million searched nodes**, across 41 positions. Natural ranks were 82 at rank 2, 19 at rank 3, three at rank 4, two at rank 5, and one at rank 7. These are move-picker ranks of pseudo-legal good quiets excluding the TT duplicate; parent legality still applies.

Of the 107 potential interventions, 93 witnesses were naturally searched: **23 cut off at the actual parent beta, 70 did not improve actual alpha**. No emitted witness was pruned. The remaining 14 were never reached because a different quiet became the final best move and cut off first. The first 32 positions contained 56 potential interventions and 15 witness cutoffs; the last 32 contained 51 and eight. This split is descriptive, not a new selection procedure.

The important cost result is unfavorable to the proposed rationale. In the **23** naturally successful witness cases, preceding searched quiet siblings used only **231 nodes** altogether, about **0.014%** of total corpus nodes. The 70 failing witnesses themselves cost 5,148 nodes. In the 14 unreached cases, the already successful earlier quiets cost 6,469 nodes; promoting an unsearched witness ahead of them would add unknown cost and may alter their depth. Those 6,469 nodes must not be booked as avoidable work. Aggregate node accounting can overlap between nested observations; neither sum is a causal savings estimate.

This does not prove the rule loses Elo. It rejects the present justification for spending on a production prototype or Fishtest: the existing history update usually carries the useful information already, the occasions that differ are scarce, naturally successful witnesses have little preceding work to save, and no missed-pruning mechanism appeared. Changing rank still changes LMR and could affect a longer horizon, but there is no measured reason to claim that secondary effect improves allocation. Do not reroll the rank/threshold rule from these outcomes.

Implementation observations: adding the scratch `Move` left `sizeof(Search::Stack)` at **64 bytes** on the local clang/macOS host, measured for baseline and diagnostic. Scratch is cleared immediately before the excluded call and populated only from that call's concrete final bestMove. It is read immediately afterward; recursive singular verification is disabled. Parent ordering/ranks are observed without mutation. Fixed-depth runs completed normally; interrupted-search observations would require separate handling. A finalMove of zero generally cannot distinguish all early-return causes by itself.

All raw records, build/default-bench logs, instrumentation diff, manifest, per-position traces, and full summary are retained in [singular-witness-observation](../results/singular-witness-observation/). The runner is [witness_observe.py](../witness_observe.py), and analysis is [witness_summarize.py](../witness_summarize.py). The analyzer applies the baseline's ordered singular-fail-low before multi-cut branch and decisive threshold `31507`; simple `value >= beta` alone overcounts multi-cuts.

Additional prior-art review by the orchestrator: explicit killer ordering was removed in commit `985b9fd7` (PR 5511), killers entirely in `2343f71f` (PR 5517), and countermoves in `a45c2bc3` (PR 5441), with STC/LTC non-regression support. Exact same-position evidence distinguishes the proposed witness from those sibling-ply/previous-move analogues. The diagnostic nevertheless shows that this distinction alone supplies little additional opportunity on the measured sample.
