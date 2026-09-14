# Use child bound direction when verifying a TT cutoff

## Candidate and status

At baseline `031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3`, change the existing child-TT verification so that only a directionally informative child bound vetoes an otherwise eligible parent cutoff. The proposed change adds two logical lines and no table storage, probes, tunable constants, or neural evaluations. It is a credible, easily falsifiable experiment, not a proven Elo improvement.

This is preferable as a first TT experiment to changing replacement depth/age constants or widening entries. Its predicted benefit is avoiding extra search caused by treating a loose bound as an exact contradiction. Its principal risk is that the current deliberately heuristic numeric disagreement is useful even when not logically conclusive.

## Mechanism in this baseline

`TTEntry` is 10 bytes. Three entries plus two padding bytes form a 32-byte cluster. The entry stores a 16-bit key, depth, packed generation/PV/bound flags, move, score, and raw evaluation. `probe()` returns a local copy but the field reads can race with other writers. The table is intentionally economical rather than collision-free or transactionally consistent. The main search validates the score before using it. [1]

The move is updated independently of whether the accompanying new score/depth wins admission. Score admission favors exact bounds, a different key, a sufficiently deep/PV new result, or an older generation. Restricted secondary aging remains for decisive inexact scores; separate search-side aging penalizes inexact bounds that cannot cut off in the current window. Replacing all of these with a “correctness first” scheme would be a large and dubious Elo experiment. [1,3,4]

The main-search cutoff at `src/search.cpp:882–919` requires adequate TT depth, the useful parent bound direction, a valid value, and node-type compatibility. It suppresses cutoffs at very high rule-50 counts. At depth at least seven, with a legal TT move and a nondecisive parent TT score, it temporarily makes that move and probes the child. A missing child score permits the parent cutoff. A child numeric score on the expected side also permits it. Numeric disagreement vetoes it, **without examining `ttDataNext.bound`**. [2]

The parent test is bound-aware. The child test is not. Since no child data already means “no reason to veto,” an inconclusive one-sided bound is a natural additional case of no useful veto evidence.

## Bound algebra

Let the parent cutoff window be `(beta-1, beta)` and let the child stored numeric bound be `x` from the child's perspective. The check concerns consistency along the **stored TT move**, whose value is `V(ttMove) = -V(child)`. A low value for this move does not disprove a full-node fail-high if a different move wins; this remains a stored-line reliability heuristic.

| Parent result | Child score relation considered a disagreement | Child bound that actually establishes the disagreement | Inconclusive opposite bound |
|---|---|---|---|
| Parent TT line expected fail-high: `V(ttMove) >= beta` | `x > -beta` | Child lower bound `child >= x`, implying `V(ttMove) < beta` | Child upper bound `child <= x`; the child may still be much lower |
| Parent result fail-low: `V < beta` | `x <= -beta` | Child upper bound `child <= x`, implying `V(ttMove) >= beta` | Child lower bound `child >= x`; the child may still be much higher |

For example, take `beta=100`, a parent lower bound 130, and a child upper bound −80. The child might actually score −150, fully consistent with the stored TT line supporting the parent cutoff. Baseline nevertheless vetoes because `-(-80) < 100`. Conversely, a child **lower** bound −80 contradicts that line's expected fail-high and should retain the existing veto. Another parent move might still fail high. These are internal score units, not UCI centipawns.

Exact bounds carry both bits, so their handling remains unchanged. The fail-low equality case is deliberate: child upper bound `x == -beta` implies `V(ttMove) >= beta`, contradicting fail-low. This truth table was checked by enumerating both parent sides, all four bound flags, and child values below/equal/above `-beta`. Only inconclusive opposite-bound cases, plus the racy valid-score/BOUND_NONE case, gain cutoffs.

The interval reasoning explains the proposed feature; it does not make selective-search TT bounds mathematically reliable. Entries can be stale, aliased, shallower than the current search, or produced under different selective decisions.

## Exact proposed diff

In `src/search.cpp`, replace the comment and conditional around lines 911–916:

```diff
-                // Check that the ttValue after the tt move would also trigger a cutoff
+                // Veto the cutoff only when the child bound contradicts it.
                 if (!is_valid(ttDataNext.value))
                     return ttData.value;

-                if ((ttData.value >= beta) == (-ttDataNext.value >= beta))
+                if ((ttData.value >= beta) == (-ttDataNext.value >= beta)
+                    || !(ttDataNext.bound
+                         & (ttData.value >= beta ? BOUND_LOWER : BOUND_UPPER)))
                     return ttData.value;
```

No change to `tt.cpp` or `tt.h` is required. Keep the preexisting pseudo-legality/legal checks, parent decisive-score guard, depth gate, rule-50 gate, and child missing-score fallback. Do not bundle a child-depth threshold, score normalization change, or replacement policy into this candidate.

The bound mask is intentionally reversed relative to the parent's useful-bound mask: the child has the opposite side to move, and the question is whether it **contradicts** the parent. A same-direction mask would be a semantic error.

## Prior work

The relevant primary history supports testing a refinement while cautioning against treating it as a free correctness win:

* [PR #6069, Check evaluation after ttMove before doing a tt cut](https://github.com/official-stockfish/Stockfish/pull/6069), merged May 2025, introduced this child probe and numeric test. It recorded STC and LTC passes, with 239,136 and 448,770 games respectively. The exact [LTC run](https://tests.stockfishchess.org/tests/view/681902de3629b02d74b16f6d) is linked from the PR and local commit. This is evidence that the existing veto has value, not that the proposed refinement does. [5]
* [PR #6094, Small tt verify simplification](https://github.com/official-stockfish/Stockfish/pull/6094), commit `dfa176fc`, simplified the comparisons and removed child mate-score normalization, recording no functional change and a non-regression STC pass. Neither its before nor after code checks child bound direction. Avoid reintroducing the removed normalization as purported novel work. [6]
* [PR #6819, Penalize TTEs whose inexact value mismatches the current window](https://github.com/official-stockfish/Stockfish/pull/6819), May 2026, already implements search-side bound/window reliability through selective aging. Its STC/LTC passes and unsuccessful VVLTC reversion support the principle that bound-aware TT handling can matter, but it changes replacement behavior rather than this child veto. [3]
* [PR #6818, Reintroduce Secondary TT Aging](https://github.com/official-stockfish/Stockfish/pull/6818), May 2026, restricts aging to decisive inexact entries to repair elementary mate finding. The source explicitly warns about VVLTC scaling when aging singular-extension entries. This argues against casually broadening aging as a first experiment. [4]

Local source-history searches, including the full evolution of the child conditional, found no upstream `ttDataNext.bound` check. A targeted web search did not locate the exact candidate. This is a bounded prior-art check; failed unmerged branches and unindexed Fishtest runs remain a novelty limitation.

## Other avenues examined

**Rule-50 semantics:** `Position::key()` is already adjusted in eight-halfmove buckets starting at 14, and `value_from_tt()` downgrades potentially false mate/tablebase scores near the 50-move limit. The main cutoff additionally stops at count 96. Therefore, “include rule-50 in the TT” is already implemented approximately. Exact rule-50 tagging would fragment useful transpositions and requires its own evidence. A 2025 zeroing-move cutoff guard existed historically; mechanically reintroducing it without tracing subsequent changes is not a novel proposal. [7]

**Qsearch and main-search reuse:** main depths and qsearch depth zero are deliberately ordered separately. Qsearch can accept sufficiently deep main-search bounds and exports upper/lower bounds. A tempting candidate is preventing shallow qsearch moves from replacing a deeper entry's move when its score is rejected. This targets a real possible move/score mismatch, but the independent move-refresh rule is longstanding, and a fresh tactical move can be useful despite a retained deeper bound. It is a broader admission-policy experiment than the chosen mask. [1,2]

**ProbCut admission:** commit `d89730d5` in 2020 protected deeper TT data from ProbCut writes, but `6edc29d7` removed that protection in 2022 after simplification tests. “Preserve deeper data” is not a sufficient novelty or strength argument. [8]

**Dual bounds:** a historical implementation storing both upper and lower bounds was reverted in 2012 (`a2f46446`), with insufficient evidence to justify its added code. Hardware and engine architecture have changed since then, so this does not rule it out permanently; it does make a single bound-mask experiment much cheaper to interpret. [9]

## Cost, risks, and validation

The incremental computation is one bound-mask read and a few logical operations inside a branch that already performs a move, legality checks, and a child TT probe. It introduces no cache-footprint increase. The main effect should be more parent cutoffs and fewer expanded nodes when the child numeric score is inconclusive. Any fixed-node speed change and any playing-strength change must be measured separately.

The strongest reason it may fail is that an inconclusive child bound still correlates with a stale or tactically wrong parent score. The numeric heuristic may intentionally exploit that correlation. Extra cutoffs can then hide necessary re-searches, especially in long-control searches with persistent TT entries. Multithreaded races may change the ratio of inconsistent flags to useful bounds. Graph-history effects and near-rule-50 positions remain only partially modeled.

For a local diagnostic, count the additional cutoffs by parent direction and child bound, and record the later deeper-search result for a small sampled subset. Keep instrumentation out of the final test binary. If no significant fraction of previous vetoes becomes eligible, the hypothesized savings are too small to justify overhead. If newly accepted parent cutoffs often reverse under deeper search, reject the causal story.

For validation, use identical baseline/candidate compiler, architecture, NNUE, hash, and threads. Confirm deterministic bench output, UCI operation, legal-move/reproducibility checks, and existing mate-search regressions. Run a local paired-opening screen for crashes or a gross loss; do not infer small Elo from a short match. A promising candidate needs Fishtest STC and independent LTC at current project-approved settings, followed by long-control verification because this changes TT selectivity. Include a multi-thread configuration and at least one larger hash condition. Publish all exact SHAs and results, including failed variants. No test has yet been run for this candidate.

## Source inventory and files actually read

1. Baseline [`src/tt.cpp`](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/tt.cpp), all **298 lines**, and [`src/tt.h`](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/tt.h), all **125 lines**; fully inspected in wave 1 and refreshed in this wave.
2. Baseline [`src/search.cpp`](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/search.cpp): retained wave-1 reading **1–170, 735–1907**; newly read **1900–2015**, including complete `value_to_tt`/`value_from_tt`. Targeted references rechecked at **882–927**, **1072–1110**, **1633–1652**, and **1716–1897**.
3. `319d61effdad40ac633425d6504a98f6d2ad0cd2`, complete local commit message and diffs; GitHub PR #6819 opened.
4. `94beadffb3e9d93ebfe05d5366878ffb68ab67c9`, complete local commit message and diff; GitHub PR #6818 opened.
5. `6e9b5af0f002ff1175998631e07a1c92735cae62`, complete local message and search diff; PR #6069 opened and examined for bound-related discussion. No such discussion was found in retrieved content.
6. `dfa176fc7ee795b69fa72ea1322486a8d8b0647a`, complete local message and search diff; `git log -L` of the child-cutoff conditional inspected.
7. Baseline [`src/position.h`](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/position.h): **310–345**; `src/position.cpp` rule-50/key symbols were located but the full file was not read. Historical `75f07da9` message/diff inspected.
8. `d89730d5c8dcf10eb9e1d91a81f903d9fc3c949a` and `6edc29d720b43383a04bd2208e9666a6f3173a64`, complete local messages and search diffs.
9. `a2f46446cf1c91bc293a6acea9ce268e81534042`, message and diff statistics only; full old implementation not read.
10. Baseline [`src/types.h`](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/types.h), **132–146 and 228–244**, plus prior **145–200**. `6596f0ea` was inspected and rejected as unrelated move-picker history, not TT-write policy.

Direct Fishtest retrieval failed in the preceding wave. Historical results here are attributed to official PRs and local commits, not independently fetched result payloads. No engine edits, build, branch changes, remote writes, UI actions, or test submissions were performed.
