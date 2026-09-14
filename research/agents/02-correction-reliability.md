# Correction-history reliability in excluded-move searches

## Recommendation

Test a one-condition change that prevents negative correction-history training from the root of an excluded-move search. Keep positive updates, ordinary search updates, and the existing multi-cut update unchanged.

The causal case is strong: a failed search of the alternatives to the transposition-table move does not establish an upper bound on the original position. Current Stockfish nevertheless allows that result to lower the correction histories of the original position. The Elo effect remains unmeasured; this is a candidate for testing, not an established improvement.

Baseline: `031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3`. All locations below refer to that commit. No engine source, branches, builds, commits, remote content, or Fishtest runs were changed for this investigation.

## Exact proposed patch

```diff
diff --git a/src/search.cpp b/src/search.cpp
--- a/src/search.cpp
+++ b/src/search.cpp
@@
     // Adjust correction history if the best move is not a capture and
     // the error direction matches whether we are above/below bounds.
     if (!ss->inCheck && !(bestMove && pos.capture(bestMove))
+        && (!excludedMove || bestMove)
         && (bestValue > ss->staticEval) == bool(bestMove))
```

Suggested eventual explanatory comment: “An excluded-move fail-low does not bound the value of the full position.” Keep the first experiment to this guard; changing weights, update magnitude, score clipping, or other search heuristics would obscure the result.

## Current learning mechanism

`src/search.cpp:85–131` applies a weighted combination of pawn, minor-piece, white non-pawn, black non-pawn, and two continuation correction values to the raw evaluation. These are small integer statistics maintained online during search. The four structural histories are shared by threads on a NUMA node; continuation correction history is worker-local. `src/history.h:60–84` updates a bounded statistic with a bonus and gravity term. `src/history.h:148–194` defines correction storage, and `src/history.h:227–247` maps structural keys into it. [1, 2]

The final search update at `src/search.cpp:1644–1652` skips positions in check and quiet-result cases whose score direction is inconsistent with `bestMove`. For a node without `bestMove`, the comparison accepts `bestValue <= ss->staticEval`; for a node with `bestMove`, it accepts only `bestValue > ss->staticEval`. Equality produces a zero bonus. The signed bonus is proportional to the score difference and current depth, then is bounded before training every correction component. [1]

That sign restriction already handles an important ordinary-bound issue. A normal fail-low gives an upper bound and may justify lowering the evaluation; a normal fail-high gives a lower bound and may justify raising it. Simply requiring exact scores would remove much of the intended learning and is not the proposed fix.

## Where the evidence changes meaning

The singular extension block at `src/search.cpp:1261–1270` temporarily assigns `ss->excludedMove` to the TT move, then calls `search<NonPV>` on the same position and stack frame at approximately half depth. Its deliberately shifted narrow window asks whether some other move is competitive. The move loop at `src/search.cpp:1139` skips the excluded move. [1]

Let `M` be all legal moves, `e` the excluded move, and `V(m)` a move value in an idealized minimax model. The full position has value `max(V(m): m in M)`. An excluded search instead considers `max(V(m): m in M without e)`.

An upper bound on the second maximum places no upper bound on the first. For example, a strong excluded move can coexist with many poor alternatives. When the alternatives fail low, `bestMove` is absent and the existing final update can train a negative correction even though the real position is much better than the static evaluation. The four structural keys and the continuation keys do not encode the excluded move, so the learned penalty transfers to ordinary searches of the real position. This is a mathematical distinction between the two search targets, not a claim that Stockfish's selective-search bounds are formal proofs.

The no-alternative case makes the mismatch especially clear. At `src/search.cpp:1581`, an excluded search with zero legal non-excluded moves sets `bestValue = alpha`. Here `alpha` is the artificial singular-search window boundary. If it is below static evaluation, the current code can train from it even though no remaining move was evaluated. The proposed guard covers this case automatically. [1]

Positive evidence has the opposite direction: finding a sufficiently good allowed move remains evidence that at least one move in the full position is good. Therefore the guard retains excluded searches with `bestMove`. Combined with the existing direction test, those are precisely the positive-update cases. These are still heuristic lower bounds because of reductions and pruning; the patch preserves the current policy toward that uncertainty.

## Shared stack-frame details

The excluded search reuses the same `Stack* ss`, so the static-evaluation behavior matters. At `src/search.cpp:839–840`, the excluded branch assigns `unadjustedStaticEval` and local `eval` from the already corrected `ss->staticEval`; it does not assign `ss->staticEval` or apply correction again. Ordinary recursive moves search `ss + 1`, not the same frame. The proposed check uses the local `excludedMove` captured at node entry, so the outer caller resetting `ss->excludedMove` after return does not affect its decision. [1]

There are same-frame early returns into quiescence search, such as razoring, that can refresh `ss->staticEval`. Such an invocation returns directly and never reaches this final correction update. The patch does not attempt to change all same-frame mutation behavior or make correction histories synchronous. It addresses only the final update's unsupported negative evidence.

The update added for successful multi-cut pruning at `src/search.cpp:1296–1301` remains intact. It runs in the surrounding normal search after the exclusion has been cleared and trains positively when the alternatives themselves exceed static evaluation. Blanket suppression of all excluded-search learning would be a broader experiment with a weaker causal justification.

## Why this can matter beyond one node

One accepted final update changes four shared structural tables and, when the previous move is valid, two continuation entries. The present read weights are positive, so a negative update tends to lower all six contributions together. Structural features deliberately generalize over positions. Pawn keys ignore most piece motion; minor-piece keys ignore pawns, major pieces, and kings; per-color non-pawn keys ignore pawns and the other color. `Position::set_state()` at `src/position.cpp:488–519` establishes these definitions. [2, 3]

This sharing is useful for true evaluation residuals, but it also spreads a penalty generated by the artificial move restriction. The full position's correction can then influence pruning, move reductions, and extension margins in other parts of the tree: see the uses of `correctionValue` at `src/search.cpp:1012`, `1274`, and `1339`. The strongest hypothesis is better retention of forcing positions with one good quiet move and weak alternatives.

The update is not merely a hash collision. Even a collision-free structural table would conflate the full position and the same position with one move excluded, because neither key contains the move restriction. Increasing table size would therefore not resolve this mechanism.

## Prior work and evidence against overconfidence

The original correction-history implementation, accepted on December 31, 2023, already lacked an excluded-move guard. It was introduced from Caissa and passed both short and long time-control tests. Therefore this is a longstanding behavior, not a newly identified regression. Its historical success is a reason to demand Elo evidence before claiming that the logically cleaner policy is better. [4]

The November 2025 correction-condition simplification passed non-regression tests: 95,136 STC games and 256,440 LTC games. That change deliberately favored a simpler directional condition even though it changed some learning behavior. Current search contains many coupled heuristics whose compensations can make a less literal residual useful. [5]

The August 1, 2026 multi-cut correction update passed STC after 151,072 games and LTC after 109,866 games; the recorded LTC LLR was 2.96 for normalized bounds `<0.50,2.50>`. Its commit credits PlentyChess and an LLM-assisted port. This is close precedent for learning from successful searches of alternatives, and supports preserving positive multi-cut evidence. It does not establish that suppressing excluded fail-lows wins. [6]

A cautionary example is the correction bonus after successful null-move pruning: it passed gain tests in May 2024, then its removal passed non-regression tests in June 2024. Plausible new update sources can be fragile or redundant. [7, 8]

Repository history searches for excluded/correction and singular/correction combinations, plus GitHub issue/PR searches, found no prior accepted patch matching this exact guard. Search coverage was limited to available history and indexed issue/PR material; failed or private Fishtest experiments may exist. No claim of worldwide novelty is made.

## Other reliability hypotheses considered

| Mechanism | Evidence in this baseline | Decision |
|---|---|---|
| Excluded-search negative residual | Directly reachable final update, incorrect target-set upper-bound interpretation | Recommend first |
| Require exact search scores | Most useful online observations are directional fail bounds; current code already checks direction | Reject as too broad |
| Avoid mate/tablebase-score training | Final update has no explicit decisive-score guard; a large residual is bounded but can train strongly | Plausible separate test, less clearly beneficial because tactical errors can be useful to learn |
| Suppress draw-result updates | Immediate draw returns skip training, but ancestors can train on a drawing line; structural keys omit repetition history | Plausible contamination, but broad filtering would lose fortress/draw knowledge and requires source tracking |
| Reduce correlated-table updates | Every residual trains multiple overlapping feature tables | Current weights are tuned; confidence counters or residual decomposition add state, costs, and tuning needs |
| Increase table size or add collision tags | Structural hash aliasing exists | Does not fix restricted-search semantic aliasing; more memory and cache traffic |
| Ignore continuation updates around null moves | Neutral sentinel contexts are reused | Requires a separate study of intentionally shared sentinel learning and lower-ply behavior |

Draw evidence was checked against `Position::is_draw()`/`is_repetition()` at `src/position.cpp:1496–1506`, the early returns in main/quiescence search, and the existing rule-50 damping in `src/evaluate.cpp:72–73`. None provides as narrowly isolated a first experiment as the excluded-search guard. [1, 3, 9]

## Costs, risks, and validation

The implementation adds one cheap Boolean condition and no storage, key changes, UCI options, or NNUE changes. It should reduce some history writes; a speed gain is possible but should not be presumed. A new branch layout could offset those savings. The standard bench signature should change if any affected update influences later search.

The main Elo risk is removal of useful pessimism. Excluded fail-lows may deliberately or accidentally teach that a position is fragile and has only one viable continuation. The present engine may use that penalty as a useful search-allocation signal, even though it is not a literal static-evaluation error. Search conditions and correction weights may have adapted around it. The guard changes this behavior precisely where singular extensions are active, so the effect can scale with depth and thread count.

Recommended sequence:

1. Build the unmodified baseline and this one-condition candidate with the same compiler, architecture, and network. Record commit hashes, networks, signatures, and build commands.
2. Run existing reproducibility/engine correctness checks and obtain deterministic single-thread bench signatures. No new permanent tests are needed for a heuristic change this small.
3. In an optional diagnostic build, count final correction updates partitioned by `excludedMove`, `bestMove`, sign, and `moveCount == 0`; verify only excluded/no-best-move updates disappear. Keep diagnostics out of the submitted patch.
4. Screen with paired openings and equal hardware. A small local result only detects large regressions; do not present it as an Elo gain.
5. Submit an isolated Fishtest STC SPRT against the frozen baseline, then the appropriate LTC validation if STC supports continuing. Use current Fishtest conventions at submission time and record exact run URLs. Because singular behavior is depth-sensitive, a favorable STC result alone is insufficient.
6. Inspect longer-time-control and multithread behavior before calling the patch a robust gain. If the candidate fails, record the failure and reject this guard rather than repeatedly trying minor variants until noise yields a positive result.

Confidence: high that the code permits the described training; high that the guard removes only excluded/no-best-move final updates; moderate that the removed evidence is an undesirable residual for generalization; unknown Elo sign until games are played.

## Sources

1. Stockfish developers. [Baseline search implementation](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/search.cpp). Local source inspected at the frozen commit.
2. Stockfish developers. [Baseline history implementation](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/history.h). Local source inspected.
3. Stockfish developers. [Baseline position implementation](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/position.cpp). Local source inspected.
4. Michael Chaly / Stockfish. [Introduce static evaluation correction history](https://github.com/official-stockfish/Stockfish/commit/b4d995d0d910044cf4ea2ad3ee30fd1d21070cd8), December 31, 2023. Commit and recorded test results read locally.
5. Daniel Monroe / Stockfish. [Simplify correction update condition, PR 6375](https://github.com/official-stockfish/Stockfish/pull/6375), October–November 2025. PR read on the web; accepted commit `c9a2aff48529d5b624cb60c9e70354dacad39a57` inspected locally. [STC record](https://tests.stockfishchess.org/tests/view/68e5034ea017f472e763dc5a), [LTC record](https://tests.stockfishchess.org/tests/view/68e71ae4a017f472e763e291); result figures verified from the primary PR/commit text.
6. mstembera, Yoshie2000 / Stockfish. [Multi cut pruning correction history](https://github.com/official-stockfish/Stockfish/commit/218c74ec4d97807afaab3a4dbda94f43e6e02647), August 1, 2026. [STC record](https://tests.stockfishchess.org/tests/view/6a596dca5529b8472df81060), [LTC record](https://tests.stockfishchess.org/tests/view/6a6508b6c054e285ae028b5f). Commit inspected locally; direct web opening of the LTC record failed, so figures are attributed to the accepted commit rather than an independently fetched live run.
7. Michael Chaly / Stockfish. [Update correction history in case of successful null move pruning](https://github.com/official-stockfish/Stockfish/commit/0c797367a3a9783ff87422d543eb2106fea3e948), May 21, 2024. Local commit inspected.
8. evqsx / Stockfish. [Remove the correction history bonus in null move search](https://github.com/official-stockfish/Stockfish/commit/4151c06b744a3145617200ca8f76285aae193dc2), June 8, 2024. Local commit inspected.
9. Stockfish developers. [Baseline evaluation implementation](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/evaluate.cpp). Local source inspected.
10. anematode / Stockfish. [Share correction history between threads](https://github.com/official-stockfish/Stockfish/commit/1a67ccc72ef2e3c06e9c905a793a14416d53643f), December 23, 2025. Commit/diff and multiple time-control/thread-count test records in its message inspected locally.

## Files and history explicitly read

Full files: `src/history.h`, `src/evaluate.cpp`.

Relevant sections: `src/search.cpp` correction read/write helpers, stack initialization, move/null-move setup, history clearing, main search from node entry through final update, quiescence entry/evaluation/final update; `src/search.h` stack and worker correction members; `src/position.h` state fields and key/draw accessors; `src/position.cpp` key construction, key update references, draw/repetition detection; `src/types.h` bounds and score definitions; `src/tt.h` TT data/probe/write semantics; `src/misc.h` relaxed atomic wrapper.

Historical diffs/messages: `b4d995d0`, `d29c8bd5`, `c9a2aff4`, `7ac8e622`, `7a7c033a`, `1a67ccc7`, `6592b13d`, `218c74ec`, `0c797367`, `4151c06b`; repository log queries for correction/corrhist/history/excluded/singular terms. This inventory is deliberately scoped; it is not a claim that this agent read every repository file.
