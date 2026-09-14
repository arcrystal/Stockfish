# Search confidence from a contradicted evaluation correction

## Recommendation

Test a small, bounded reduction adjustment for quiet late moves when a sufficiently deep transposition-table bound says that the learned correction moved the raw evaluation in the wrong direction. This is a plausible new feature at baseline `031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3`, not a demonstrated Elo improvement. It deserves an inexpensive local screen; promotion to a claimed improvement requires independent game testing and longer time controls.

The novelty is the interaction between the **direction** of a correction and an informative **bound**, rather than the already implemented magnitude of correction history. No engine source was edited or built for this investigation. No remote test was submitted.

## Current mechanism

The evaluator returns a scaled NNUE score after blending PSQT and positional outputs, optimism, material, and rule-50 damping (`src/evaluate.cpp:42–72`). Search then forms a weighted correction from pawn, minor-piece, each side's non-pawn, and two continuation correction histories (`src/search.cpp:85–106`). These histories learn the residual between search results and corrected static evaluations (`src/search.cpp:1644–1652`). They are bounded adaptive averages; they are neither independent neural-network ensembles nor statistical uncertainty estimates. [1–3]

At a TT hit, the engine retains raw evaluation in `unadjustedStaticEval`, forms corrected `ss->staticEval`, and may substitute `ttData.value` into the separate `eval` variable when the bound gives directional information (`src/search.cpp:842–853`). Lower bounds can raise `eval`; upper bounds can lower it. TT entries are partial, racy search observations, and their raw evaluation is deliberately stored without correction (`src/tt.h:35–72`, `src/tt.cpp:89–120`, `src/search.cpp:1633–1642`). [1,4]

Correction magnitude already protects search in three places: child futility margins (`search.cpp:1012`), double/triple singular-extension margins (`1274–1278`), and LMR (`1339`). LMR also receives directional information from `alpha - eval` (`1369–1370`) and the depth/value/PV properties of TT entries. Consequently, simply adding “uncertainty-aware LMR,” `abs(correctionValue)`, or an undirected TT/static difference would either duplicate existing work or overlap strongly with existing features. [1]

## Why the proposed feature may add information

Let raw evaluation be `E`, corrected evaluation `E + C`, and an informative TT lower bound be `L`. If `L > E` while `C < 0`, the correction moves away from every result compatible with that lower bound. The symmetric case is an upper bound `U < E` while `C > 0`. This is a stronger conflict than merely observing that corrected evaluation differs from a bound. For example, `E=+80`, `C=-40`, and `L=+140` imply that the correction moved from +80 to +40 despite search evidence pointing above +140. These numbers are Stockfish internal units, not UCI centipawns.

The engine already replaces `eval` in these cases. However, history updates, shallow quiet futility, and several improving predicates continue to use corrected `ss->staticEval`, while the correction-derived LMR protection does not distinguish corroborated and contradicted corrections. A small additional investment in alternative quiet moves could prevent a stale or aliased correction from reinforcing an overly selective search. This is a causal hypothesis, not an empirical finding.

The initial patch deliberately leaves evaluation, history learning, pruning gates, and TT storage unchanged, making its effect easy to isolate. It changes only the depth allocated to surviving quiet late moves. This also means it cannot rescue a move already discarded by the earlier quiet-pruning stage; that is a limitation of this first experiment.

## Exact proposed patch

Insert the following immediately after Step 5 static evaluation, before the improving flags. This location avoids crossing a new initialization through the later `goto moves_loop` and snapshots the current node before recursive searches change shared histories.

```cpp
    // Protect quiet alternatives when a searched bound contradicts the correction.
    const int correctionConflict =
      !rootNode && !ss->inCheck && !excludedMove && is_valid(ttData.value)
          && !is_decisive(ttData.value) && ttData.depth >= depth - 3
          && ((correctionValue < 0 && ttData.value > unadjustedStaticEval
               && (ttData.bound & BOUND_LOWER))
              || (correctionValue > 0 && ttData.value < unadjustedStaticEval
                  && (ttData.bound & BOUND_UPPER)))
        ? std::min(std::abs(correctionValue) / 131072, 128)
        : 0;
```

Then insert after the existing `r -= std::abs(correctionValue) / 26310;` in Step 18:

```cpp
        if (!capture && moveCount > 1)
            r -= 2 * correctionConflict;
```

This adds at most 256 reduction units before subsequent scaling, or one quarter of a nominal ply. Stockfish ultimately rounds reductions to whole depths, so a quarter-ply adjustment changes the depth on a subset of moves. The existing ALL-node scaling can amplify the adjustment somewhat; this is not an absolute cap on the final scaled change. The factor 2, cap 128, and three-ply depth allowance are initial experimental choices, not fitted optima or historically proven values.

The flags exclude root nodes, in-check sentinel evaluations, and excluded-move searches whose reused static evaluation is not genuinely raw. `is_valid` must precede `is_decisive`, which asserts validity. A decisive TT score is excluded. `BOUND_EXACT` satisfies both masks, but only the appropriate strict value comparison can activate. No new TT probes, history loads, memory allocation, or NNUE evaluations are required. The mathematical argument is conditional on the TT bound being useful; selective search, collisions, races, and graph-history interaction prevent treating it as ground truth.

## Prior work and negative evidence

| Prior experiment | Relevance | Recorded outcome |
|---|---|---|
| [PR #5727, Adjust LMR with correction history](https://github.com/official-stockfish/Stockfish/pull/5727), merged December 2024 | Introduced the existing absolute-correction LMR protection, with a compensating base-reduction increase | Historical STC and LTC passes; the [LTC run](https://tests.stockfishchess.org/tests/view/6761e10f86d5ee47d95431fa) is linked in the commit. It does not test the proposed interaction. |
| [PR #5748, Corrplexity for futility pruning](https://github.com/official-stockfish/Stockfish/pull/5748), January 2025 | Added correction magnitude to child futility margins | Historical STC and LTC passes. |
| [PR #5776, Remove eval/static-eval equality check](https://github.com/official-stockfish/Stockfish/pull/5776), January 2025 | Removed a condition restricting the correction margin to cases without TT substitution | Historical simplification STC and LTC passes. A blanket separation of TT and correction confidence has already failed to justify its complexity. |
| [PR #5767, Correction history quad extensions](https://github.com/official-stockfish/Stockfish/pull/5767), January 2025 | Shows correction-based search changes can have strongly different scaling | Commit records an approximately −4.4 Elo STC estimate but two VVLTC passes. The architecture and exact implementation later changed. |
| [PR #5251, Revert TT/improving reduction](https://github.com/official-stockfish/Stockfish/pull/5251), May 2024 | A TT-based LMR condition passed STC/LTC but regressed at longer controls | Revert passed VLTC and VVLTC. |
| [PR #5283, Revert TT-value depth reduction](https://github.com/official-stockfish/Stockfish/pull/5283), May 2024 | Further evidence that a superficially successful TT confidence heuristic can scale badly | Revert passed two VVLTC tests. |

The first four entries were verified through local commit messages and source diffs; #5727, #5748, and #5767 were also opened on GitHub. The two reverts were inspected in full through local git history. Direct Fishtest pages returned an access/internal error to the web tool, so the historical test outcomes above are attributed to the repository's commit records rather than falsely represented as independently downloaded test data.

Searches of local history for correction, complexity, confidence, uncertainty, disagreement, cancellation, and TT/static-evaluation interactions did not find this exact directional conjunction. Web search likewise did not locate a matching upstream proposal. This does **not** establish global novelty: unmerged personal branches and unindexed Fishtest experiments remain unsearched.

Two tempting alternatives were rejected for this first patch. Using `sum(abs(weighted corrections)) - abs(sum(weighted corrections))` as ensemble disagreement mistakes additive, correlated history components for independent predictors. Exposing NNUE PSQT/positional disagreement to search would require a broader evaluator/cache design and has historical predecessors; the engine already uses this quantity in evaluation scaling. [2,5]

## Costs, failure modes, and falsification

The direct cost is a few integer comparisons, masks, and a capped absolute value per non-qsearch node, plus a cheap conditional per surviving move. Actual cost is dominated by additional search nodes, not these instructions. The signal can be rare because sufficiently deep TT entries often cut off before reaching LMR. If it is almost never reached, apparent strength results will be noisy and implementation overhead may dominate.

A contradicted correction may be correct for future searched positions while the TT bound is stale or tactically shallow. The confidence signal also overlaps with existing `alpha - eval` and absolute correction features. More quiet search could displace useful tactical depth or worsen long-control search explosions. A hard gate on TT depth might create abrupt behavior at iterative-deepening boundaries.

An instrumentation-only diagnostic, kept out of the candidate binary, should count eligible main-search nodes, conflict nodes, and quiet LMR moves whose rounded depth changes. Split positive versus negative correction, upper versus lower bound, depth, and PV status. If feasible, sample whether a deeper follow-up search agrees with the conflict bound. Reject the explanatory story if conflict does not enrich for evaluation error or useful quiet re-searches. Such a diagnostic still cannot establish Elo.

## Test strategy

1. Preserve the exact baseline and network; build baseline and candidate with identical architecture, compiler, flags, and process/thread settings. Produce a new deterministic bench signature and run existing legal-move, mate, reproducibility, and search-safety checks appropriate to the repository. Examine fixed-work speed independently from search node changes.
2. Perform a small, paired-opening local match as a crash and gross-regression screen. A few hundred or thousand games cannot support a small Elo claim. Retain all results, including failures, and do not repeatedly restart until a favorable estimate appears.
3. If operationally sound, submit one documented Fishtest STC SPRT against the exact baseline using the project's current accepted bounds and settings. The previous experiment's thresholds are historical examples, not automatically today's submission policy. Separate variants instead of bundling them.
4. A successful STC candidate needs an independent LTC confirmation. Because this is reduction logic and related changes have reversed at long controls, follow with VLTC/VVLTC at 180+1.8 or longer as indicated by current `search.cpp:75–83`. Include a multi-thread check, where TT/history races change the signal distribution.
5. Claim an Elo improvement only for the tested conditions after completed statistical evidence. Selective screening among many agent ideas creates winner-selection bias; the confirmation must not reuse the screening games. Report run URLs, exact SHAs, net, time control, SPRT state, sample size, and uncertainty rather than bench nodes as strength evidence.

## Sources and reading coverage

1. Stockfish baseline [`src/search.cpp`](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/search.cpp), direct local read of lines **1–170 and 735–1907**. This covers correction helpers, main search, bound handling, pruning, singular extensions, reductions, history/TT updates, and qsearch. The earlier orchestration/time-management range and later utility range were not fully read in this assignment.
2. Stockfish baseline [`src/evaluate.cpp`](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/evaluate.cpp), **all 105 lines**.
3. Stockfish baseline [`src/history.h`](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/history.h), **all 261 lines**.
4. Stockfish baseline [`src/tt.h`](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/tt.h), **all 125 lines**, and [`src/tt.cpp`](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/tt.cpp), **all 298 lines**.
5. Historical original complexity-search implementations: [`7678d63c`, January 2022](https://github.com/official-stockfish/Stockfish/commit/7678d63cf2323e51c01e60cdff4ac3d685313790), and [`442c40b4`, June 2022](https://github.com/official-stockfish/Stockfish/commit/442c40b43de8ede1e424efa674c8d45322e3b43c), full local messages and search diffs read.
6. Stockfish baseline [`src/types.h`](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/types.h), **lines 145–200** and targeted symbol matches for validity/decisive constants.
7. Additional historical messages/diffs read: `e7e78aa0`, `1611b9c9`, `e2612f9a`, `5868b4cb`, `38c5fc33`, `9b90cd88`, `72a34587`, `e3c9ed77`, and `254b6d5e`. History searches were broader than the commits read in full.

Research confidence: **high** in the baseline mechanism and prior-art overlap; **moderate** in the direction-conflict rationale; **low** in a positive Elo outcome before experiments.
