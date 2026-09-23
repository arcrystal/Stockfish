# Second pass: learn whether a reduced-search surprise deserves an extra ply

Research date: 20 September 2026. Baseline: `031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3`. No engine files were changed. This is a falsifiable research candidate, not an Elo improvement or a recommendation to submit another speculative Fishtest immediately.

## The lesson from the failed batch

The four rejected STC hypotheses are evidence against our original choice of interventions. Three intervals include zero, but none supports the requested gain. “A search quantity is not a mathematically valid bound” and “this geometry classification is inaccurate” were insufficient reasons to expect a stronger engine. Stockfish spends a scarce node budget under deliberately biased, learned heuristics. Removing a bias changes the allocation of that budget and its training signals, often unfavorably. The authoritative outcomes are in [the ledger](../EXPERIMENTS.md).

The next experiment should identify a recurring, expensive *prediction error* with information not already represented in the allocator. It should then change one allocation decision while preserving the existing predictor's other useful effects. Adding a second correction-history confidence term without such evidence does not clear this bar.

## What the LMR loop really does

Alpha-beta replaces exhaustive minimax work with bound proofs: a child worse than an already available alternative need not be solved exactly. Move ordering makes these proofs arrive sooner. Iterative deepening supplies a likely principal variation and transposition moves; history tables supply context-dependent cutoff expectations. A narrow PVS window asks only whether a move beats alpha. Late-move reduction (LMR) makes a stronger, fallible assumption: a late, historically weak move can answer that question at less depth. A reduced fail-high is a reason to pay for verification, not an exact evaluation.

The baseline's actual feedback path is more elaborate than “reduce bad moves.” In `search.cpp:1330–1374`, reduction depends on former PV status, cut-node expectation, a capture TT move, descendant cutoff counts, correction magnitude, history and the alpha/eval gap. `statScore` blends global quiet move history with the previous one- and two-ply continuation contexts. In `1383–1405`, the engine searches reduced depth `d`, verifies a result above alpha if the adjusted target is deeper, and may add an extra ply when the reduced value exceeds the previous best by 53 internal units. The child can itself adjust depth using the parent's reduction and static-evaluation change (`874–878`). These interacting mechanisms explain why “one less reduction” is not a predictable amount of extra work.

After a reduced fail-high, the baseline awards continuation bonus 1334 even if subsequent verification refutes the move. This is **not an obvious training bug**. A move that repeatedly challenges a shallow search may be worth ordering early or reducing less even when it is ultimately refuted: spending a little more immediately can avoid paying for a misleading scout and then a second search. Later best-move and failed-move updates supply different information. Continuation entries are bounded online heuristics, not calibrated probabilities. [Pinned source](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/search.cpp).

## Important prior art rules out the obvious patch

The precise proposal “reward the move only if full verification succeeds” already existed and was removed. [Commit `0dabf4f3`, PR 5933](https://github.com/official-stockfish/Stockfish/pull/5933) replaced `(value >= beta) * 1800` with a constant 1600. Its official record reports STC and LTC simplification passes with bounds [-1.75,0.25]. Earlier [commit `2ce47573`](https://github.com/official-stockfish/Stockfish/commit/2ce47573b4d3664dca4cbc4354c8c600540d16ad) removed the negative verification-failure history malus, also with simplification passes. These do not prove the present constant is optimal; they make restoring outcome-dependent continuation rewards a poor next choice without new evidence.

Separate historical support for adapting allocation exists, but does not establish this candidate. [Commit `56444ce1`](https://github.com/official-stockfish/Stockfish/commit/56444ce1f7e2204d69c35f5826f74130adc77b2c) gave extra reward to late successful verifications and passed gainer STC/LTC. That logic was later simplified away. [CMHC, PR 6653](https://github.com/official-stockfish/Stockfish/pull/6653) conditions continuation updates on agreement among histories; its recorded gainer passes show context interactions can carry information, but also mean a generic “history agreement” idea is not new.

The current extra-ply threshold has survived simplification: commits [4d4c6ebd](https://github.com/official-stockfish/Stockfish/commit/4d4c6ebd0255f29a45fb5e071fc7471ab0adf316) and [1047f844](https://github.com/official-stockfish/Stockfish/commit/1047f844d13ba890463c0eaf337b4fef613c2725) removed depth terms in December 2025, with STC/LTC simplification passes. Adding arbitrary depth thresholds would reverse demonstrated simplifications. Likewise, generic intermediate verification was introduced in 2013 (`8e9d4081`) and removed in 2015 (`7b8ffe0f`); simply adding a third scout is not the new proposal.

Historical results above are attributed to local official commit records; PRs 5933 and 6653 were additionally opened on the web. Their games have not been independently downloaded or reanalysed here. The history search is bounded, not a novelty proof.

## One exact candidate: separate verification reliability from move ordering

Keep every existing history update and ordinary full-depth verification. Learn a separate, tiny per-worker predictor of whether an actually verified reduced fail-high survives. Use that predictor **only to gate the speculative additional ply**, not to suppress verification, alter ordinary LMR depth, alter move order, or change alpha/beta semantics.

An exact initial design, fixed before seeing its game results:

1. Add a zero-initialized per-worker `Stats<i16, 1024, PIECE_NB, SQUARE_NB, 2>` table. Its key is `[movedPiece][destination][cutNode]`; size is 4 KiB for 16 pieces, 64 squares and two node classes. Zero means no evidence against the existing behavior. Clear with the worker's other histories. This deliberately avoids additional shared atomics and pawn-hash lookups.
2. Only use/train it at non-root, non-PV, non-check, non-excluded nodes on quiet moves with valid non-decisive alpha and search returns. Require a genuinely reduced scout (`d < newDepth` before the existing adjustment) followed by an actual deeper verification. Promotions, captures, and aborted searches are ineligible. Preserve the original pre-recursion table value for the decision; nested searches may update the table.
3. Keep the current `doDeeperSearch` condition, adding `&& !(eligible && reliabilityBefore < -512)`. Keep `doShallowerSearch` unchanged. Thus an unsupported move still receives the baseline full-depth verifier; only its additional speculative ply is absent. The current `d < newDepth` precondition ensures that when the gate changes a decision, ordinary full-depth verification remains deeper than the reduced scout.
4. After completed verification, update that table entry by `+64` if `value > alpha`, otherwise `-64`, using the existing saturating `StatsEntry` update. Do not update from a reduced result without verification. Do not feed this new statistic to continuation history.

The constants define a conservative, falsifiable first design, not tuned values: from zero, several consecutive failures are required to cross -512; in the stationary signed-outcome approximation the threshold selects roughly less than 25% survival. Integer rounding and changing search conditions mean this is not a calibrated probability. The table's context is intentionally coarse and may fail to generalize.

The causal hypothesis is that recurring moves can be strong *shallow challengers* but poor *deep survivors*. Existing continuation reward correctly learns the first role; a separate statistic may learn the second. The current large reduced-score surprise triggers extra depth even when that type of surprise repeatedly evaporates. Avoiding unnecessary extra-ply work there could free nodes for other unresolved lines. This is distinct from the failed correction-bound candidate and from report 01's TT/correction disagreement.

The additional cost is one small-table read on an eligible reduced search and an update after verification, plus state/control overhead. Most ineligible searches should not load it. Whether the table reduces search work enough to repay the cost is entirely unmeasured.

## The adversarial case is central, not an afterthought

Repeated failures may mean that the *extra ply is exactly what discovers the refutation*. Gating it could turn well-refuted tactical mirages into false cutoffs. A quiet queen move can look winning at the scout horizon; the ordinary verifier may still miss the defender's forcing reply, and only the extra ply finds it. Learning “this queen move usually fails” and searching it less is then causally backward.

Conversely, a low-survival bucket may contain a rare but decisive sound sacrifice. Piece/destination aliasing can transfer pessimism between unrelated positions. Deeper verifier scores remain selective, not truth; the policy also changes its own labels once enabled. TT hits, history adaptation and iterative deepening create correlated observations. Longer controls may change both calibration and the value of the extra ply. These risks are why observational refutation counts alone cannot justify submission.

Reversing the gate to suppress extra depth for *high*-survival moves does not solve this identification problem. Those may be precisely the promising lines Stockfish intends to extend, even when both depths exceed alpha. The observed quantity `P(verifier survives | context)` is not the desired treatment effect of using an extra ply on decision quality per node. Until paired depth evidence identifies that effect, neither gate direction has earned a production recommendation. The table design is a concrete hypothesis to falsify, not a way to convert correlation into a justified search policy.

## Cheap discriminator before changing the engine policy

The lead's generic logging-only LMR diagnostic can answer the first question without duplicating instrumentation. Preserve baseline search decisions, every original return and TT write, and benchmark signature 1648567. The extra shadow table must not influence search. Its pre-event value is the prediction; its post-verification update is the outcome. Logging only predictions after an outcome would leak the answer.

Record the parent position/move identity, root sample and iteration, depth, pre-adjustment `newDepth`, reduced `d`, node type, check/excluded/capture flags, alpha/beta/bestValue, pre-search global history and both continuation components, `statScore`, reduced result, original `doDeeperSearch`, whether verification actually occurred, target depth, verifier result, stop state and both search node deltas. Snapshot history values before recursion. Decisive/invalid/sentinel scores need separate categories rather than arithmetic bucket overflow.

Useful fixed bins:

| Dimension | Bins |
|---|---|
| Actual reduction `newDepth - d` | <=0, 1, 2, 3, >=4 |
| Parent depth | 2–3, 4–5, 6–8, 9–12, >=13 |
| `statScore` | <-8192, [-8192,-2048), [-2048,2048), [2048,8192), >=8192 |
| Reduced excess above alpha | 1–16, 17–64, 65–256, >=257 |
| Outcome | no verifier; verifier <=alpha; between alpha/beta; >=beta; aborted |
| Shadow reliability | <-512; [-512,0); [0,512); >=512 |

Also record reduced excess over **bestValue**, because that is the extra-ply trigger; excess over alpha is not interchangeable. Separate PV/CUT/ALL, quiet/capture and TT/non-TT move categories. A count of “LMR fail-highs” that combines actual reductions with extensions or no-verification cases would misstate the mechanism.

First use the standard bench only to check instrumentation. Then use a fixed, published, disjoint collection of ordinary book and middlegame/endgame positions at fixed work/depth, with root-level train/holdout splitting and a frozen predictor. Reject the candidate if the low-reliability bucket has negligible incidence, fails to predict verification failure on held-out roots after stratifying by current `statScore` and reduction, or costs little enough that the entire target budget is immaterial. Bootstrap by root position rather than treating recursive nodes as independent observations. Never add nested verifier node counts and call their sum a fraction of the whole tree: these subtrees overlap.

Even a successful prediction diagnostic is insufficient. Before a production policy, perform bounded **counterfactual paired replays** for sampled eligible events: baseline verifier at `newDepth+1` versus ordinary verifier at `newDepth`, from equivalent position, stack, TT and history state. Replay both from independently restored identical snapshots; running them sequentially against a warmed TT would bias cost and outcome. If exact state restoration is impractical, admit that limitation and use isolated whole-root A/B replay; do not label a fresh-FEN search an equivalent node replay.

The desired observation is not merely “deep verification often fails.” It is “ordinary verification reaches the same alpha decision more cheaply for the predicted low-survival group, while the withheld extra ply rarely changes that decision.” Count newly introduced fail-highs explicitly. If saved cost disappears or false cutoffs concentrate in that group, reject this design rather than tune thresholds until a favorable test appears. Equal-node whole-root checks against a substantially deeper reference can further detect tactical deterioration, although the reference is not an oracle.

Only after these two discriminators support the mechanism should this isolated design get source review, functional/reproducibility checks, fixed local screening and a standard independent STC/LTC sequence. Because this changes depth allocation, long-control scaling needs explicit scrutiny even after an LTC pass. A positive Elo claim still requires completed match evidence.

## Recommendation and confidence

The lead completed an observational corpus during this investigation: 64 fixed-seed UHO positions, depth 13, one thread and 16 MiB hash. Its instrumentation retained identical iteration scores, PVs, best moves and node counts against the baseline for every corpus position. I read the instrumentation patch, corpus runner and [summary](../results/lmr-observation/summary.json), then independently recomputed these rates from all 64 raw `LMR` logs:

| Actual quiet verification group | Verifications | Above alpha after verification | Survival rate |
|---|---:|---:|---:|
| All quiet | 23,496 | 18,862 | 80.28% |
| Existing optional extra ply | 10,205 | 8,793 | 86.16% |
| No optional extra ply | 13,291 | 10,069 | 75.76% |
| Positive `statScore` | 11,673 | 9,876 | 84.61% |
| Nonpositive `statScore` | 11,823 | 8,986 | 76.00% |

“Extra ply” here means the recorded verification target exceeds the pre-adjustment `newDepth`; it does not mean every effective recursive path searched one extra ply. The summary's `negative_history` label actually groups nonpositive `statScore`, including zero. Rates condition on scouts that triggered actual verification, not on all moves; they are correlated event counts, not independent trials or Elo results. The aggregate includes both PV and non-PV nodes and has broader eligibility than the proposed table. It is a first discriminator, not a direct simulation of the new policy.

This evidence strengthens the **no-go for another production tweak now**: existing score-surprise and history rules already separate likely survivors. The report supplies no residual predictive information beyond those rules and no causal evidence that either group can safely lose a ply. A new shadow table must first beat that existing conditioning on held-out positions; paired depth audits must then justify an allocation direction. Copying the aggregate false-positive rate into a proposed penalty would ignore the engine's successful selection.

**Do not submit a continuation-bonus outcome gate.** Its direct prior art is adverse. The distinct verification-reliability table above is the best new bounded LMR intervention from this investigation, but it is a *diagnostic candidate*, not yet the best production upgrade. Confidence is high in the baseline/prior-art analysis, moderate that repeated verification outcomes contain measurable information, and low that suppressing speculative extension converts that information into Elo. If the root agent's allocator diagnostic finds a stronger, cheaper signal, this idea should lose the comparison rather than consume a test slot by inertia.

Reading performed: current unchanged baseline search ranges 770–1080, 1120–1655 and 1960–2085; history type/update definitions; complete experiment ledger and report 01; orchestration synthesis; targeted historical diffs/messages listed above. This report does not repeat the previous team-wide entire-repository reading claim as a new individual audit.
