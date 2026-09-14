# Unscored workers should abstain from SMP voting

## Recommendation

Test one small consistency change to `ThreadPool::get_best_thread()`: workers whose best root score is still the initialization sentinel `-VALUE_INFINITE` should neither set the score-normalization baseline nor cast a vote. An eligible scored worker should also replace an unscored initial `bestThread`, including when both recommend the same move with equal PV lengths.

The mechanism is directly supported by source and synthetic voter cases. A worker with no observation can currently change the winner among other workers by setting an extreme normalization baseline. This is not a claim that standard SMP games frequently encounter that state. Expected relevance is concentrated in extremely short searches, delayed worker scheduling, high thread counts, mixed-speed cores, and stop/go-mate interruption scenarios. Standard STC/LTC Elo improvement is unproven and may be too small to detect.

Baseline: `031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3`. No engine code, build, branch, commit, remote content, UI state, or Fishtest submission was changed by this investigation.

## Exact patch

All three changes belong to the same policy: no-score workers provide no voting evidence. Preserve the existing decisive-score and inexact-loss eligibility rules.

```diff
diff --git a/src/thread.cpp b/src/thread.cpp
--- a/src/thread.cpp
+++ b/src/thread.cpp
@@
     for (auto&& th : threads)
-        minScore = std::min(minScore, th->worker->rootMoves[0].score);
+        if (th->worker->rootMoves[0].score != -VALUE_INFINITE)
+            minScore = std::min(minScore, th->worker->rootMoves[0].score);

     // Vote according to score, and select the best thread
     for (auto&& th : threads)
-        votes[th->worker->rootMoves[0].pv[0]] += th->worker->rootMoves[0].score - minScore + 14;
+        if (th->worker->rootMoves[0].score != -VALUE_INFINITE)
+            votes[th->worker->rootMoves[0].pv[0]] += th->worker->rootMoves[0].score - minScore + 14;
@@
         else if (newThreadDecisive
                  || (!is_loss(newThreadMove.score)
-                     && (newThreadMoveVote > bestThreadMoveVote
+                     && (bestThreadMove.score == -VALUE_INFINITE
+                         || newThreadMoveVote > bestThreadMoveVote
                          || (newThreadMoveVote == bestThreadMoveVote
                              && newThreadMove.pv.size() > bestThreadMove.pv.size()))))
```

Use the exact sentinel check, not `is_valid()`: Stockfish's `is_valid()` only excludes `VALUE_NONE`, and would accept `-VALUE_INFINITE`. No new weights, counters, fields, locks, or worker scheduling policies are introduced. [1, 2]

## Current cooperation and voting

Stockfish uses independent worker searches with shared TT information and selected shared histories. Workers maintain their own root move lists and ordinary local search state. The main thread starts helpers, runs its own search, sets `stop`, and waits for helpers to finish before selecting the final worker. The selection therefore operates on stopped search state; this proposal does not create additional live shared-state reads. [1, 3, 4]

The vote for a worker is currently:

```text
worker_score - minimum_score_among_all_workers + 14
```

Votes are grouped by recommended root move. The selection loop prefers proven decisive outcomes according to the existing policy; otherwise it uses the total move vote and breaks ties with PV length. Since July 2026 the ordinary vote no longer multiplies by search depth. [1, 5]

Every new root move starts with `score = -VALUE_INFINITE`, a one-move PV containing a legal root move, and zero effort. `ThreadPool::start_thinking()` copies this initialized root list to all workers and resets their node/depth counters. A worker that sees `threads.stop` before entering its first iterative-deepening iteration leaves that score untouched. A worker stopped before the first root move is recorded can likewise retain the sentinel. [1, 3, 4]

The delayed-worker path is possible because waking a helper queues a job and signals its condition variable; the main thread does not wait for every helper to finish a root iteration before making progress. Root setup itself is synchronized before searching starts, so the legal root move is available even if no score is produced. Source reachability does not establish how often OS scheduling actually triggers the state in representative matches.

## How an empty observation changes other votes

Consider three scored workers:

| Worker | Recommended move | Score |
|---|---|---:|
| 0 | A | 100 |
| 1 | B | 0 |
| 2 | B | 0 |

With no other workers, `minScore = 0`. Move A receives 114 votes and B receives 28, so A wins under the current formula.

Now add a delayed worker whose default root move is C and whose score remains `-32001`. Current `minScore` becomes `-32001`. A receives 32,115 votes, B receives 64,030, and C receives 14. B now wins even though the new worker supplied no evaluated evidence about A, B, or C.

The normalization is intended to shift *observed* scores to positive weights. The sentinel instead adds approximately 32,000 votes per scored worker, overwhelming ordinary score differences and making worker headcount dominate. Merely suppressing the empty worker's own 14 votes would not solve this: it must also be omitted from the minimum calculation.

Conversely, omitting it only from the minimum would let its score produce a large negative contribution to its default move. Both guards are required. The candidate keeps A at 114 and B at 28 after adding the empty worker, as if the empty observation had abstained.

These calculations were verified with an independent Python implementation of the current vote formula and selection cases. They are synthetic states, not captured engine runs, and the numbers are internal search scores rather than centipawns.

## Why the third selection guard is needed

The initial `bestThread` is the main thread. Suppose it is unscored and recommends default move C with PV length one. A helper has genuinely scored C and also has a one-move PV, which is possible at shallow depth. Both candidates have the same aggregate move vote because they refer to the same map key, and their PV lengths tie. The current selection can therefore keep the unscored main thread even after the vote fix.

The third guard promotes an eligible scored worker over that unscored initial candidate without changing vote comparisons between scored workers. This preserves the chosen chess move in that special case, but it repairs the score/PV provenance selected for output and for `bestPreviousScore`/`bestPreviousAverageScore`, which are retained for time management on the next move. [3]

The guard is deliberately inside the existing `!is_loss(newThreadMove.score)` branch. It does not introduce a preference for an inexact decisive-loss recommendation over the fallback legal root move. Exact decisive outcomes remain handled by the existing override.

## Aborted-search and bound audit

The engine already contains substantial protection that a general “prefer complete workers” proposal would overlook:

- Root move records track aspiration upper/lower bound flags. The flags are set when a result falls outside the searched window. They do not mean every retained finite score is a completed whole-root search snapshot. [3, 4]
- At the end of an interrupted first-PV iteration, an exact mate/TB-loss score is rolled back to the previously retained best PV when available. Without an earlier PV, the depth-one loss is marked inexact. [3]
- MultiPV restoration protects earlier proven losses when a secondary PV search is interrupted. It may restore a valid previous score/PV or mark the resulting information inexact. [3]
- Forgotten mate scores can be restored from a prior iteration. Final voting only treats non-sentinel, decisive, non-inexact scores as decisive evidence. [1, 3]

None of these paths synthesizes an ordinary evaluated score for a worker that never produced one. An entirely unstarted iteration is skipped by the `while` condition. Within an aborted iteration, the sentinel is excluded from `is_exact_loss()`, so no loss restoration fabricates a value from it. This distinction is the basis of the candidate.

Discarding every inexact worker would be much broader. A finite lower-bound observation can be useful evidence for a strong move, and bound labels arise from aspiration search rather than an independent calibrated confidence model. Replacing raw scores with `uciScore` is also not automatically safer: it would move fail-high and fail-low observations in different directions and sacrifice fail-soft information. Those alternatives are not included.

## Edge cases checked

The following selector outcomes were checked in the synthetic Python model, using the baseline's decisive threshold and the proposed three guards:

| State | Baseline | Candidate |
|---|---|---|
| Three scored workers as above plus an empty worker | B wins after sentinel changes normalization | A wins as with scored workers alone |
| Every worker has sentinel score | Main thread's initialized legal root move | Same fallback |
| Unscored main; scored helper has same move and one-ply PV | Main retains sentinel metadata | Helper's finite metadata selected |
| Unscored main; helper has ordinary finite score for a different move | Helper | Helper |
| Unscored main; helper has exact decisive loss | Helper through decisive override | Same |
| Unscored main; only helper has inexact decisive loss | Main fallback | Same |
| Scored main; other worker unscored | Scored main remains eligible winner | Same |

When all workers are unscored, `minScore` remains `VALUE_INFINITE`, but the accumulation loop performs no arithmetic with it. Map lookups in the final loop yield zero. Sentinel candidates are not decisive and fail the ordinary `!is_loss` eligibility check, so the initialized main-thread fallback remains. There is no need to invent a score or add an all-empty special case.

## Prior work and novelty limits

The July 2026 thread-selection simplification passed non-regression SMP STC after 437,904 games and SMP LTC after 484,778 games. Its author also documented unsuccessful attempts to improve depth-relative weighting. These results argue against casually reintroducing depth weights or adding a novel confidence formula without strong evidence. [5]

Before May 2026 the vote multiplied by completed depth; the May simplification switched that factor to root depth, and July removed it. A worker that had not completed depth one could previously contribute zero of its own votes, depending on the exact historical state. However, its sentinel could still influence `minScore` and therefore every other worker's vote. The proposed abstention is not equivalent to restoring the old depth multiplier. [5, 6]

February/March 2026 changes explicitly repaired aborted mate-loss handling and allowed helper threads to stop go-mate searches. This is why the candidate preserves the current decisive and inexact-loss policy instead of redesigning it. A separate March 2026 fix ensured positive time budgets at very low controls; it improves startup behavior but is not a scheduler guarantee that every helper has produced a score. [7, 8, 9]

Thread-diversity reduction tweaks are also already explored: a thread-index-based reduction term passed in August 2025 and was removed by a non-regression simplification in September. Shared correction histories were independently tested across several thread counts, so extra voter diversity cannot be assumed to offset the known value of cooperation. [10, 11]

Available history and issue/PR searches for voting, no-score, unsearched, `minScore`, and `VALUE_INFINITE` found no accepted patch matching the proposed three guards. That search is not proof of novelty. Failed/private branches or unindexed discussions may contain the same abstention rule.

## Alternative SMP directions rejected for this first experiment

| Alternative | Assessment |
|---|---|
| Discount workers sharing a history shard | Their observations are correlated, but all workers also share TT evidence. NUMA grouping alone is not a calibrated independence model and could underweight a productive shard. |
| Allocate one full vote per distinct root move | Discards the tested benefit of agreement and confuses diversity with evidence quality. |
| Reintroduce depth-weighted votes | Recently removed after large non-regression tests; nearby depth-relative and nonlinear variants were tried without a clear gain. |
| Give later threads less reduction | Previously introduced and then simplified away; lacks a new causal trigger here. |
| Explicitly partition root moves among workers | Interferes with lazy SMP cooperation and each worker's search completeness; much larger implementation and validation scope. |
| Share networks or add cache-aware histories | Existing network replication/sharing and NUMA/cache-aware history allocation already address these themes. No duplicate implementation proposed. |
| Optimize the vote hash map | Runs once per move and has already had bucket/hash/PV-copy improvements. Lower expected leverage than correcting absent evidence. |

## Cost, failure modes, and validation

The patch adds two sentinel checks per worker in aggregation plus a selector check. It runs once after search, not at each node. Memory, synchronization, search work distribution, node speed, and atomic policies are unchanged. Branch overhead should be negligible but can be measured on large thread counts.

The main risk is that, in the rare states affected, the existing accidental headcount emphasis happens to choose the better move. Score-weighted voting is itself a heuristic. A mechanical consistency improvement therefore still needs game evidence before being described as an Elo gain.

Another risk is simply negligible incidence at standard controls. A synthetic example proves behavior but not importance. The first empirical step should count how many live selections contain any sentinel root score, how often the move or metadata changes, and the number of scored workers. Keep instrumentation out of the submitted patch.

Recommended validation:

1. Compile with unchanged search and run existing normal/Chess960, UCI, and multithread mate checks. Standard one-thread depth bench should remain unchanged.
2. Exercise the synthetic voting states directly in a small isolated diagnostic harness, including all-empty, same-move/one-ply-PV, exact loss, inexact loss, and a decisive win. These are meaningful tests of selection semantics, not statistical strength tests.
3. Measure live incidence at 1, 2, 8, and a higher available thread count. Use ordinary clocks and deliberately short node/time limits separately. Fixed-depth play bypasses best-thread selection at the caller and is unsuitable for judging this patch's chess effect.
4. Stress worker startup and interruption with rapid `go`/`stop` and multithread `go mate`; verify legal fallback moves, score flags, and complete mate PV handling. Any deliberately delayed-worker hook belongs only in a diagnostic build.
5. If incidence warrants strength testing, run paired-opening SMP Fishtest STC and LTC, then a high-thread or very-short-control test where the mechanism is more frequent. Label results by thread count and control; do not generalize a stress-case gain to ordinary engine strength.
6. Include at least one different scheduling environment if available—homogeneous x86 cores and a mixed-performance system are useful contrasts. No CPU-specific code was introduced, but incidence depends on scheduling.

If no affected cases occur in representative testing, this remains a small robustness proposal rather than a promising general Elo candidate. Do not spend a large gainer test budget on an event that has not been observed live.

## Overall assessment of this agent's four proposals

The strongest first Elo hypothesis remains 02: suppress negative correction learning from excluded-move fail-lows. Its effect occurs within ordinary search and has a clear mismatch between the learned target and the real position. Proposal 04 has an equally concrete geometric mechanism, but additional attack-query cost could erase any ordering gain. Proposal 08 is a clean abstention rule with concentrated short-search applicability and likely smaller general impact. Proposal 05 is an allocation experiment most relevant to increment-heavy controls and has substantial contrary evidence from the current clock-saving rule.

This ordering is a research judgment before reviewing the coordinator's game results. None of the four is an established Elo improvement from this agent's analysis alone.

## Sources

1. Stockfish developers. [Baseline thread.cpp](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/thread.cpp), worker lifecycle and final selection. Full local file inspected.
2. Stockfish developers. [Baseline types.h](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/types.h), sentinel and decisive-score definitions.
3. Stockfish developers. [Baseline search.cpp](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/search.cpp), startup, stopping, bound flags, restoration, and final-worker score retention.
4. Stockfish developers. [Baseline search.h](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/search.h), `RootMove` initialization and bound helpers.
5. Robert Nurnberg / Stockfish. [Simplify thread selection, PR 6935](https://github.com/official-stockfish/Stockfish/pull/6935), July 2026; accepted commit `9449162d588b2a185471501ad8ebea1ec8864f87`. [STC](https://tests.stockfishchess.org/tests/view/6a3158590d5d4b19d08055cd), [LTC](https://tests.stockfishchess.org/tests/view/6a377f3ba4f63d3271af0920), [author's account of failed depth-weighting experiments](https://github.com/official-stockfish/Stockfish/pull/6935#issuecomment-4840229141). Accepted diff read locally; PR/comments through GitHub API. Results attributed to primary reports, not independently reprocessed games.
6. Robert Nurnberg / Stockfish. [Simplify away completedDepth](https://github.com/official-stockfish/Stockfish/commit/7e754e17dd37491745b20970a7acce6bc27d4708), May 4, 2026. Accepted diff and 284,808-game SMP non-regression record inspected locally.
7. Robert Nurnberg / Stockfish. [Prevent unproven mated-in scores in game play](https://github.com/official-stockfish/Stockfish/commit/46ac9a7e6a656cece337bbfc226ab7caeb9fd72b), February 28, 2026. Local accepted diff inspected.
8. Robert Nurnberg / Stockfish. [Improve multi-threaded go-mate searches](https://github.com/official-stockfish/Stockfish/commit/67a2c247d45034509fbdd669751f3dabe11e797d), March 18, 2026; [MultiPV: protect mated-ins and allow thread selection](https://github.com/official-stockfish/Stockfish/commit/50e8ff1e23ad0f9c9f15f06cb5650b277129b744), April 26, 2026. Local accepted diffs inspected.
9. MARLIN-Tools / Stockfish. [Fix Depth 1 bug at very low time controls](https://github.com/official-stockfish/Stockfish/commit/3c04b5c4297c26b0dac9fa4ffc158c47a87a24cf), March 18, 2026. Time-budget clamp diff and specialized tests inspected locally.
10. Stefan Geschwentner / Stockfish. [Less reduction for later threads](https://github.com/official-stockfish/Stockfish/commit/39c077f15a88ff1e563971c396eb9a27b0ac6ac5), August 24, 2025; Shawn Xu / Stockfish. [Simplify SMP Reduction](https://github.com/official-stockfish/Stockfish/commit/f2da0ccf3f82c663daf958d05243d75247de6eb2), September 2, 2025. Accepted diffs and SMP test records inspected.
11. anematode / Stockfish. [Share correction history between threads](https://github.com/official-stockfish/Stockfish/commit/1a67ccc72ef2e3c06e9c905a793a14416d53643f), December 23, 2025. Earlier-wave source/history audit reused.
12. mstembera / Stockfish. [Improve thread voting inefficiencies](https://github.com/official-stockfish/Stockfish/commit/531747ee7889d9b61b9841a57bb6d582459999d6), February 11, 2024; [Avoid truncated PV in the threaded case](https://github.com/official-stockfish/Stockfish/commit/310928e985a6d87bdd73542e2109f93c31e2cc41), December 12, 2022. Local accepted diffs inspected.

## Exact read manifest

Complete files: `src/thread.cpp`, `src/thread.h`, `src/thread_native.h`.

Revisited relevant ranges: `src/search.cpp:192–263,269–451,452–570,1437–1530,2114–2147`; `src/search.h:134–168`; `src/types.h:116,152–187`. Earlier waves read the remaining root-time loop and all correction-history code relevant to shared-history scope. The coordinator separately read `numa.h` completely; this report does not claim an independent full read of that file.

Historical diffs/messages: `9449162d`, `fcbd160d`, `9db77822`, `46ac9a7e`, `531747ee`, `ad9fcbc4`, `d60f5de9`, `310928e9`, `39c077f1`, `f2da0ccf`, `7e754e17`, `50e8ff1e`, `3c04b5c4`, `67a2c247`. Primary online material includes PR 6935 and author comments, plus bounded issue/PR searches relating to voting and incomplete scores.
