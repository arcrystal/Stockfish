# Preserve an available repetition draw at the quiescence horizon

## Runtime validation addendum

The later, separately authorized [runtime diagnostic](/Users/acrystal/Desktop/Coding/Games/Stockfish/research/results/repetition-diagnostic.md) **confirmed the proposed mechanism** in an isolated, instrumented baseline checkout. Original search return values and TT writes were preserved, and the default bench retained signature **1648567**. It recorded **3,841** existing upcoming-repetition detections, **103** surviving the initial window check, and **9 TT plus 16 ordinary final returns** below the remembered draw score. Of those 25 events, **2 were PV final returns and 23 were NonPV**.

The proposed history seed was also executed through normal UCI, using the first six moves and `go depth 1 searchmoves f8e8` to reach the target qsearch node. It observed **returned −351 versus detected repetition score −1**, at a non-check PV node one ply below the root. No custom qsearch harness or return-value change was used. This is targeted runtime evidence, not an Elo or speed result. Direct branch/edge-case harness checks and production-patch game testing remain incomplete in this agent's work.

The sections below preserve the original source-research phase and its proposal. Statements that the seed or patch had not been executed describe that original phase; the addendum and linked logs supersede them for the observational baseline seed. The production floor patch itself was not built or tested by this research agent.

## Candidate and status

At baseline `031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3`, retain the score of a detected upcoming repetition as a local floor for ordinary quiescence-search completion. When that score determines the return, do not write a new TT entry from this node. This is a small, falsifiable candidate for avoiding pessimistic horizon scores in repetitive positions. It requires no additional repetition scan, move generation, tablebase probe, network call, history table, or tuning constant.

The mechanism has a clearer chess justification than changing a generic endgame reduction. **Its tournament frequency, speed cost, and Elo effect are unknown.** At the original source-research stage, the case below had not been run through an instrumented engine; the later diagnostic above now supplies that observation. Implementation and game testing belong to the root task. This report does not establish a complete graph-history-interaction fix.

## What the existing implementation already solves

The complete Syzygy implementation supports WDL and DTZ files, lazy memory mapping, compressed-symbol decoding, material hashing, symmetry-based position indexing, and special treatment of captures, pawn moves, and en passant before accepting a compressed-table result. `probe_dtz()` searches the opposite side when the available table requires it. The code explicitly accounts for DTZ rounding: a returned distance may be one ply short, so the root ranking distinguishes a guaranteed `dtz + rule50 <= 99` from the boundary at 100. Its root ranking also takes earlier repetitions into account. This is not a simple exact-distance oracle that can be copied into every search node. [Baseline tbprobe.cpp](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/syzygy/tbprobe.cpp)

At the root, `root_probe()` explicitly scores a move that produces a repetition draw as drawn. It falls back to WDL ranking when DTZ is missing. With successful DTZ ranking, ordinary internal tablebase probing is disabled; with WDL alone it remains enabled only for winning roots. The root move order and allowed rank groups then constrain the search. Simple pawnless endings already receive DTZ ordering when DTZ is also DTM: `Position::dtz_is_dtm()` covers three-piece endings and four-piece minor-only endings. The historical [PR #6843](https://github.com/official-stockfish/Stockfish/pull/6843) specifically addressed this behavior. Reintroducing shortest-mate ordering for KRvK or KNBvK would duplicate existing work.

During main search, WDL probes require a zero halfmove clock, no castling rights, a suitable material count, and sufficient depth for the configured maximum cardinality. Outside this exact-data region, repetition remains important. `Position::is_repetition(ply)` distinguishes a repeated position inside the search from repetitions before the root. `upcoming_repetition(ply)` uses the cuckoo move table and historical keys to identify an available move that reaches a draw; its baseline contract says this matches testing all legal moves. Main search and qsearch already call it before TT use when alpha is negative. [Baseline search.cpp](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/search.cpp), [baseline position.cpp](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/position.cpp)

## Specific gap and mechanism

Qsearch at lines 1676–1682 recognizes an upcoming repetition by raising `alpha` to `value_draw(nodes)`, which is either −1 or +1 internal score units. It returns immediately if that closes the window. Otherwise it does not retain this draw as a candidate `bestValue`.

For an ordinary non-check qsearch node, `bestValue` subsequently starts at corrected static evaluation or a useful TT score. The move picker searches captures; the legal quiet move that draws by repetition is normally absent. Consequently, a PV window spanning the draw can recognize an available draw, search no better capture, and return a score below that draw. The final TT write stores that lower score as an upper bound. A return below alpha is normally legitimate fail-soft behavior; the special issue here is that alpha was raised by evidence from a legal drawing option that this restricted move set does not search.

Consider a source-level example: incoming PV window `(−600, 200)`, existing repetition detection returning −1, corrected evaluation −500, no legal captures, and no stalemate. Baseline raises alpha to −1 but completes with `bestValue = −500`; the proposed return is −1. These are internal units, not UCI centipawns. This inference follows the control flow; it is not an observed baseline log.

The largest affected class should be PV qsearch. At a non-PV zero-width window, an upcoming draw almost always closes the window immediately. The surviving corner is the `(-1, 0)` window when draw jitter yields −1. An already eligible TT upper cutoff can then also return below −1, so the patch clamps that return as well. A TT fail-high cannot be changed: if the initial repetition check did not return, `repetitionValue < beta`, whereas a fail-high TT value is at least beta.

Do not initialize `bestValue` to the draw before move generation. In-check qsearch uses a loss-range `bestValue` to keep evasions from being pruned. A late return floor preserves that existing move-search behavior. Actual draw/max-ply exits, stand-pat cutoffs, and the checkmate exit remain as they are. Therefore the proposal is a floor on ordinary completion and TT reuse, not a universal invariant covering every exceptional exit.

The return-path audit is explicit:

| Return path | Effect of the proposal |
|---|---|
| Upcoming repetition immediately closes the window | Identical existing return of the sampled −1/+1 draw score. |
| Step 2 actual draw | Identical return of zero; this can be below a previously sampled +1 floor. Terminal policy takes precedence. |
| Step 2 maximum ply | Identical non-check `evaluate(pos)` return, which can be below the stored floor; the emergency horizon policy is deliberately outside this proposal. In-check maximum ply still returns zero. |
| TT cutoff | Clamp only this return after existing `value_from_tt()` conversion and validity/bound checks. The normal decisive-score/rule50 conversion remains unchanged. No new TT write occurs on this path. |
| Stand pat | Unchanged: the return is at least beta, including its weighted smoothing, and surviving repetition detection guarantees the floor is below beta. |
| No-legal-move checkmate | Unchanged mate return. A correctly detected legal repetition move should make this combination unreachable, but the patch does not override mate handling if reached. |
| Ordinary final return | Apply the floor after fail-high smoothing. A smoothed fail-high remains at least beta and cannot be raised by the floor. Only a lower completion value triggers the new early return. |

This audit also avoids treating the randomized draw score as an exact mathematical lower bound on terminal zero. The intended claim is consistency with the already chosen repetition score during ordinary nonterminal qsearch, within the engine's existing draw policy.

## Exact proposed diff

Only change `Search::Worker::qsearch()` in `src/search.cpp`:

```diff
     // Check if we have an upcoming move that draws by repetition
+    Value repetitionValue = -VALUE_INFINITE;
     if (alpha < VALUE_DRAW && pos.upcoming_repetition(ss->ply))
     {
-        alpha = value_draw(nodes);
+        alpha = repetitionValue = value_draw(nodes);
         if (alpha >= beta)
             return alpha;
     }
@@
     if (!PvNode && ttData.depth >= DEPTH_QS && is_valid(ttData.value)
         && (ttData.bound & (ttData.value >= beta ? BOUND_LOWER : BOUND_UPPER)))
-        return ttData.value;
+        return std::max(ttData.value, repetitionValue);
@@
     if (!is_decisive(bestValue) && bestValue > beta)
         bestValue = (462 * bestValue + 562 * beta) / 1024;

+    // The drawing move may be quiet and absent from quiescence move generation.
+    // Keep its history-dependent value out of this node's TT write.
+    if (bestValue < repetitionValue)
+        return repetitionValue;
+
     // Step 10. Save gathered info in transposition table. The static evaluation
```

Keep the existing negative-alpha trigger and draw jitter. Do not widen repetition detection to every qsearch node in this candidate. Do not bundle a main-search change, qsearch rule-50 TT guard, or Syzygy option fix.

Skipping the final write when the return is raised prevents creating a new entry from this path-dependent floor and avoids saving the inconsistent below-floor upper value at this node. It is conservative admission behavior, not a proof that all other TT entries are history-independent. An earlier TT entry remains, and ancestors can still store results influenced by repetition. A full provenance scheme would be a much larger experiment.

## Prior work and novelty limits

* [PR #4742](https://github.com/official-stockfish/Stockfish/pull/4742), merged as `b7b7a3f3`, introduced upcoming-repetition detection in qsearch. The official record reports STC and LTC passes at 340,288 and 193,230 games. Its [LTC run](https://tests.stockfishchess.org/tests/view/64d5e1085b17f7c21c0e4ab5) tested detection and early cutoff, not this return-floor refinement. The patch already raised alpha without retaining a draw-valued `bestValue`.
* [PR #5432](https://github.com/official-stockfish/Stockfish/pull/5432), `6b782211`, removed the broader no-progress interpretation of `has_game_cycle()` and restored actual upcoming-repetition semantics. It reports non-regression STC/LTC results, with 63,584 and 464,574 games. This distinction matters: the proposal relies on an available drawing move, not merely a suspicious cycle. The original paper linked by the PR was attempted but could not be retrieved; its contents are not independently represented here.
* `440feecb` / [PR #4757](https://github.com/official-stockfish/Stockfish/pull/4757) added extra LMR for a repeated retreat-and-return move, with historical STC/LTC passes. `8e61d704` / [PR #5123](https://github.com/official-stockfish/Stockfish/pull/5123) later removed it with non-regression passes. This makes generic extra repetition reduction a weak novelty claim and cautions against assuming every repetition-related heuristic will remain useful.
* [PR #2453](https://github.com/official-stockfish/Stockfish/pull/2453), `bae019b5`, introduced the high-rule-50 main-search TT-cutoff workaround. Its description identifies the competing cost of fragmenting transpositions. Baseline now also hashes the halfmove clock in eight-ply buckets beginning at 14 and downgrades questionable decisive TT scores through `value_from_tt()`. The present candidate retains the existing hash and addresses a known legal option at the qsearch horizon.
* [PR #6271](https://github.com/official-stockfish/Stockfish/pull/6271), `75f07da9`, previously tested a shallow TT-cutoff guard for high-rule-50 zeroing moves, recording STC/LTC passes. Simply proposing that historical guard is not original. Its later evolution was not fully traced in this wave, so it is not recommended here.

Local history searches inspected changes involving upcoming repetition, draw returns, and `bestValue`/alpha assignments. Targeted web searches did not locate this exact retained-score/late-return combination. This is a bounded prior-art search; unmerged private variants and unindexed failed Fishtest runs could contain it. Historical results above are attributed to official commits/PRs; direct Fishtest result payloads were not independently obtained.

## Diagnostic and validation plan

1. Instrument baseline qsearch temporarily to count: detection hits; hits that do not close the window; final `bestValue < detectedDraw`; TT-cutoff values below the detected draw; material count; in-check/PV status; halfmove clock. Record a small sample with full move history, alpha/beta, static evaluation, returned value, and TT flags. A FEN alone loses the decisive repetition context. If the affected class is negligible, reject before an expensive test.
2. A proposed legal-history seed is `4k2q/8/8/8/8/8/8/R3K3 b - - 0 1` followed by `e8f8 e1f1 f8e8 f1e1 e8f8 e1f1 f8e8`. White can then repeat with `f1e1`; it has no capture in the displayed material arrangement. Use a temporary qsearch harness with a PV window spanning draw and a properly initialized stack, or reach the last node one ply below the search root. Confirm legal moves, repetition predicates, and actual NNUE values before treating it as a regression test. This seed was reasoned through but not executed. Repeat the same final board with no history to verify the new floor does not appear.
3. Cover both draw-jitter values, the surviving non-PV `(-1,0)` window, TT misses and upper/lower/exact hits, in-check repetition evasions, a capture better than the draw, genuine mate, stalemate, and max-ply handling. Confirm no false mate PVs and no illegal PV moves. The candidate does not insert the quiet drawing move into the displayed PV; do not advertise a complete explanatory draw line from this patch alone.
4. Compare material strata: three-to-five-piece sparse endings; six/seven-piece endings; rook/queen perpetual-check positions with more material; and ordinary middlegames. Within these, separate clock ranges 0–13, 14–79, 80–95, and 96–99. Include history-rich PGNs, not only independent FEN books. Use Syzygy disabled, WDL-only, and WDL+DTZ setups where available. Tablebase root results can mask the intended search effect, so report that stratum separately.
5. Run a small paired-opening local screen for legality/crashes/gross loss, then project-standard Fishtest STC and independent LTC if the diagnostic supports the mechanism. Include at least one longer control because sparse endings, repeated TT reuse, and horizon depth change with thinking time. Use identical base/candidate networks, compiler, architecture, hash, threads, and openings; publish all SHAs and results. A targeted endgame suite can establish the repaired behavior, but cannot establish general Elo.

Costs are one local integer, one comparison on ordinary qsearch completion, and a max on existing TT cutoffs. The larger possible cost is lost TT writes and changed parent search behavior. Fail-soft losing magnitudes may currently help ordering or pruning even after alpha has been raised; replacing them with the draw can reduce useful heuristic information. Pessimistic draw handling may also accidentally resist attractive but unproductive repetitions. The original repetition algorithm and its draw jitter are deliberate engine policies, not abstract exact minimax values. These are reasons to test, not reasons to claim a free gain.

## Exact read manifest

New full-file coverage in this wave:

* `src/syzygy/tbprobe.cpp`: **all 1–1968**, read in consecutive chunks 1–430, 431–860, 861–1300, 1301–1740, 1741–1968; 1620–1760 revisited.
* `src/syzygy/tbprobe.h`: **all 1–85**.

Relevant source read or revisited in this wave:

* `src/position.cpp`: **1450–1674**, including complete `is_draw`, `is_repetition`, `has_repeated`, and `upcoming_repetition` functions. The parent, not this agent, read the rest of the file.
* `src/position.h`: **300–360**, including key50, material queries, and complete `dtz_is_dtm`.
* `src/search.cpp`: **725–980, 1602–1905, 2120–2310**; complete qsearch and `syzygy_extend_pv` in these ranges. Earlier waves read **1–170 and 735–2015**, including `value_from_tt`.
* `src/types.h`: **145–200**, revisited score/sentinel definitions.

Historical complete messages and diffs read: `b7b7a3f3`, `6b782211`, `440feecb`, `8e61d704`, `5b068c96`, `75f07da9`, `bae019b5`, `d9ec82e7`, `808a4fe8`, `259bdaaa`. The last three were inspected as related-search candidates and do not establish prior implementation of this proposal. Log summaries covering recent Syzygy work and repetition/rule50 history were also inspected; unexpanded log entries are not counted as full-code reading.

No engine source edits, builds, branch changes, commits, remote writes, UI actions, or test submissions were performed during the original source-research wave. The later authorized diagnostic only edited and built an isolated detached checkout, as documented in the runtime addendum; it performed no match, commit, remote write, or production-source change.
