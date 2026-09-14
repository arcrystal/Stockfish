# Increment-aware clock disadvantage

## Recommendation

Test a small allocation change that compares each side's remaining clock plus projected increment income over Stockfish's existing move horizon. The current clock-disadvantage multiplier compares only visible clocks, although the main time budget already includes future increments. This can sharply reduce thinking in increment-heavy games where both sides can sustain similar per-move spending despite different clock reserves.

This candidate has lower priority than the narrowly identified source-semantics candidates 02 and 04. Its resource-allocation rationale is coherent, but the existing rule was recently supported by substantial Fishtest evidence, and the proposal weakens that rule most late in games. No ordinary-Fishtest Elo benefit is established. The strongest expected use case is increment-heavy play.

Baseline: `031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3`. No engine code, build, branch, commit, remote content, or test submission was changed in this investigation.

## Exact candidate patch

Within the existing `if (!useNodesTime && limits.movestogo != 1)` block in `src/timeman.cpp`:

```diff
     if (!useNodesTime && limits.movestogo != 1)
     {
+        const double futureMoves = std::max(0, mtg - 1);
+        const double ourBudget = limits.time[us] + futureMoves * limits.inc[us];
+        const double theirBudget = limits.time[~us] + futureMoves * limits.inc[~us];
         double timeAdvantage =
-          (limits.time[us] - limits.time[~us]) / (1.0 + limits.time[us] + limits.time[~us]);
+          (ourBudget - theirBudget) / (1.0 + ourBudget + theirBudget);
         optScale *= 1 + 0.9 * std::min(timeAdvantage, 0.0);
     }
```

The new quantities are computed in floating point before multiplying increments, avoiding extra integer-overflow exposure. `max(0, mtg - 1)` matters because the existing sub-second horizon can fall to zero. The proposal adds no tuneable coefficient and uses the same `mtg - 1` future-increment convention as `timeLeft`.

Retain the current nodestime and `movestogo == 1` exclusions. Retain the absolute maximum-time cap, move overhead, root-level stability adjustments, and pondering behavior. The comment above the block should say the comparison concerns resources over the move horizon if the patch survives tests.

## Current time-management architecture

`TimeManagement::init()` computes a nominal optimum and maximum at the start of each move. It supports base time plus increment and cyclic moves-in-time controls. It also supports nodes-as-time accounting, including cyclic budget replenishment. The chosen horizon is at most 50 moves, reduced with a sub-second clock in non-cyclic controls. The baseline budget includes remaining clock plus future increments and subtracts an overhead allowance for the horizon. [1, 2]

For increment controls, `optScale` depends on game ply and logarithmic clock size. It is capped so healthy increment income cannot justify spending an excessive fraction of the actual current clock. `originalTimeAdjust` is initialized from the first time budget and retained through the game. `maximumTime` is bounded using both a multiplier of optimum time and a fraction of actual clock less overhead. [1]

The clock-disadvantage rule, added September 9, 2026, then multiplies `optScale` by:

```text
1 + 0.9 * min((ourClock - theirClock) / (1 + ourClock + theirClock), 0)
```

It can reduce optimum time toward approximately one tenth of the budget but never increases it above the pre-rule optimum. Because the maximum calculation also depends on optimum time, the effect can restrict recovery searches as well as routine stopping. [1, 3]

During iterative deepening, `search.cpp:578–620` further multiplies optimum time by score decline, best-move stability, recent best-move changes across threads, and the leading move's fraction of searched nodes. Completed-iteration time checks stop once elapsed time exceeds the smaller of this result and the maximum. `check_time()` also checks the hard maximum periodically during search. The proposed change modifies only the initial clock comparison. [4]

## Causal allocation hypothesis

Visible clocks measure accumulated reserve. In increment play they do not fully measure sustainable future thinking. Consider 2 seconds versus 20 seconds remaining with an equal 2-second increment. The reserve gap is real, but both sides receive nearly identical future income. The main budget acknowledges this income; the clock-disadvantage correction largely ignores it.

With the standard 50-move horizon, current and candidate multipliers in representative scenarios are:

| Current clocks | Increments | Horizon | Current multiplier | Candidate multiplier |
|---|---|---:|---:|---:|
| 2 s / 4 s | 0.1 s / 0.1 s | 50 | 0.700050 | 0.886083 |
| 2 s / 20 s | 2 s / 2 s | 50 | 0.263670 | 0.925688 |
| 2 s / 4 s | 0 / 0 | 50 | 0.700050 | 0.700050 |
| 0.2 s / 0.4 s | 0.1 s / 0.1 s | 10 | 0.700499 | 0.925031 |
| 2 s / 4 s | 1 s / 0.1 s | 50 | 0.700050 | 1.000000 |
| 10 s / 10 s | 0.1 s / 0.1 s | 50 | 1.000000 | 1.000000 |

These figures were computed directly from the two formulas using milliseconds, including the existing `+1` denominator term. They are allocation multipliers before root-level modifiers and clock caps, not predictions of actual move duration.

For equal increments, projected income cancels from the numerator and enlarges the denominator. Thus the candidate preserves the direction of the clock comparison while reducing its magnitude when incoming time dominates. With zero increments it is exactly unchanged. With unequal increments it also recognizes differences in future resources, which can reverse which player is behind over the horizon.

Future increments cannot be spent before they arrive. The candidate therefore leaves the current-clock cap intact. Its intention is to avoid unnecessary under-spending within that cap, not to allow borrowing beyond the live clock.

## Why existing root signals do not resolve this comparison

The best-move stability signal records when the root leader last changed. Recent change counts are aged by one half per main-thread iteration, summed across workers, and normalized by thread count. These signals estimate uncertainty in move selection; they do not represent future clock income. [4]

`RootMove::effort` accumulates nodes over the entire current move search and is reset when `ThreadPool::start_thinking()` constructs a new root-move list. The leading move's fraction of total nodes is used as another stopping multiplier. Since July 2026, effort also controls the weighting of root score averages. These histories are useful and already supported by tests, but changing them would alter aspiration windows and optimism as well as time allocation. [4, 5, 6]

`meanSquaredScore` should not be reused as ordinary statistical variance. The stored observation is `value * abs(value)`, and its averaging weight differs from that of `averageScore`. It is a signed second-magnitude statistic serving aspiration initialization, not an unbiased estimate of root-score uncertainty. A variance-based allocation patch would need new state or a deliberate redefinition with broader effects. [4, 6]

Root-depth stability also interacts with `searchAgainCounter`, failed-high reductions, and the recent fail-high recovery mechanism. Repeated iterations can revisit nearby effective depths, but that behavior is intentional and historically supports lazy SMP. Removing it or treating every repeated iteration as valueless would ignore tested design choices. [4, 7, 8]

## Prior evidence and contrary evidence

The September 2026 clock-disadvantage patch passed STC 10+0.1 after 127,360 games and LTC 60+0.6 after 191,328 games. It also passed non-regression tests at sudden death 15+0 and cyclic 40/10. These are significant evidence in favor of its current behavior. They are evidence against assuming the proposed normalization is automatically better. [3]

The primary PR discussion reports that much of the rule's effect occurs late in the game and that the disadvantaged-clock subset retained more time. The proposed income normalization weakens the adjustment specifically in this region. If those retained reserves rather than a comparison of total resources are the source of the Elo gain, this candidate may give it back. [3]

The same PR reports three 60,000-game matches with 10x time odds. The measured long-side Elo advantages were 195.80 for the baseline, 200.37 with the new rule, and 201.49 with a variant that remembered the initial clock ratio. The author summarized this as approximately 4–5 Elo lost by the short-clock side, with initial-ratio normalization failing to help. These matches are specialized comparisons, not direct Elo estimates for the candidate here. They show that natural-looking time-ratio normalization can fail empirically. [3]

Other time-management history reinforces time-control sensitivity. A 2024 extra-time compensation change passed STC and VLTC while returning a yellow LTC result. A 2024 sub-second horizon adjustment gained strongly in sudden death but was only non-regressing in ordinary increment tests. A September 2026 cyclic-horizon fix addressed actual timeout behavior at the control boundary. [9, 10, 11]

The candidate is not a restatement of the initial-clock-ratio experiment: it recomputes projected resources from current clocks and known increments, avoiding inference of initial time odds from a first `go` command. Nevertheless, no novelty claim is made. Available repository history, PR discussion, and issue searches did not reveal a matching accepted patch; failed or unindexed experiments may exist.

## Costs and failure modes

The computational cost is negligible: a few floating-point operations once per move. There is no added work per searched node, no new state, no neural change, and no cross-thread communication.

The dominant risks are allocation errors:

- A 50-move horizon may overvalue income in an endgame that will finish soon. It is inherited from the existing budget model, but its use in an opponent-relative correction is new.
- Equal projected resources do not imply equal survival margin: a 2-second clock has less protection against a difficult move or transmission delay than a 20-second clock.
- The effective maximum can rise because it includes an optimum-time multiplier. The absolute clock cap remains, but more expensive recovery searches can leave less reserve.
- Standard STC/LTC may lose strength even if increment-heavy games improve. An engine-wide gain cannot be claimed from a specialized control alone.
- Asymmetric increments can reverse the comparison. That is intentional mathematically, but time-odds games require explicit validation.

These risks make the proposal an experiment rather than a correctness fix.

## Validation that can actually measure the idea

Fixed-depth and fixed-node games cannot evaluate this time-management change. Pure `go movetime` tests without game clocks also bypass its intended behavior. The standard deterministic depth bench may remain unchanged; that is expected and says little about the patch. Nodestime is deliberately excluded, so it is unsuitable for estimating this candidate's Elo.

First validate formula cases and log actual clock inputs, optimum/maximum outputs, move durations, and flags in a temporary diagnostic build. Verify zero-increment identity and the retained nodestime/control-boundary guards. Exercise equal clocks, large reserve gaps, unequal increments, sub-second clocks, and `movestogo` values 1 and 2.

Then run real-clock paired-opening matches in separate groups:

1. Standard Fishtest STC 10+0.1, followed by LTC 60+0.6 if justified.
2. Increment-heavy controls such as 10+1 and 60+6, with results explicitly labeled by control.
3. Sudden-death and cyclic sanity checks, where zero-increment inputs should preserve the formula exactly.
4. Time-odds and unequal-increment tests, plus at least one multithread setting if it reaches promotion consideration.

Track time forfeits, reserve quantiles, and time spent per move along with paired win/draw/loss results. A small local sample can reject a major regression but cannot establish a small Elo improvement. Require a positive result on the target distribution and appropriate longer-control validation before promoting the candidate. If ordinary controls regress, either reject it or explicitly classify it as a specialized allocation option; do not silently generalize an increment-heavy gain to the main engine.

## Sources

1. Stockfish developers. [Baseline timeman.cpp](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/timeman.cpp). Full local file inspected.
2. Stockfish developers. [Baseline timeman.h](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/timeman.h). Full local file inspected.
3. Stefan Geschwentner / Stockfish. [Decrease time usage if engine has time disadvantage, PR 7113](https://github.com/official-stockfish/Stockfish/pull/7113), September 2026. PR and all available comments read through GitHub API; accepted commit `5ca4bfe72b9c0b1ba565c1da081d3531cce98a64` inspected locally. [STC](https://tests.stockfishchess.org/tests/view/6a8738495b1b38ebda864ed0), [LTC](https://tests.stockfishchess.org/tests/view/6a8ade7a08c0f6a39c9e79cc), [time-odds discussion and results](https://github.com/official-stockfish/Stockfish/pull/7113#issuecomment-5491953709). Figures are attributed to the primary PR/commit rather than independently reprocessed PGNs.
4. Stockfish developers. [Baseline search.cpp](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/search.cpp), iterative deepening, score averages, and periodic time checks.
5. Stockfish developers. [Baseline thread.cpp](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/thread.cpp), manager initialization and root-state reset.
6. Tony Congqian Wang / Stockfish. [Dynamic root score ema2](https://github.com/official-stockfish/Stockfish/commit/93ed4b53c4f602c4cc41dbdb67961a2a4712c60b), July 10, 2026. Local accepted diff and test summary inspected.
7. xoto10 / Stockfish. [Smarter time management near stop limit](https://github.com/official-stockfish/Stockfish/commit/69204f0720bba198952fb7a848ed4377430ef433), January 12, 2020. Local accepted diff and single/multithread test summaries inspected.
8. Joost VandeVondele / Stockfish. [Limit the researching at same depth](https://github.com/official-stockfish/Stockfish/commit/2e02dd79366e6f17df5b0599048937289fd5819e), July 9, 2022. Local accepted diff and test summaries inspected.
9. xoto10 / Stockfish. [Add compensation factor to adjust extra time according to time control](https://github.com/official-stockfish/Stockfish/commit/3c62ad7e077a5ed0ea7b55422e03e7316dcbce7e), May 29, 2024. Local accepted diff and STC/LTC/VLTC evidence inspected.
10. TierynnB / Stockfish. [Sudden Death—Improve TM](https://github.com/official-stockfish/Stockfish/commit/23493de08272226394fb69c4f31182b48b0e739e), March 14, 2024. Local accepted diff and control-specific evidence inspected.
11. Stockfish developers. [Avoid reducing move horizon in cyclic time controls](https://github.com/official-stockfish/Stockfish/commit/4d65257b), September 2026. Local accepted diff and timeout evidence inspected.
12. FauziAkram / Stockfish. [Implement smoother reduction in time management](https://github.com/official-stockfish/Stockfish/commit/fe7b9b14d22bb96a0f6b4dd5aa256e4d02bd84d0), May 25, 2025; [Simplify time management reduction logic](https://github.com/official-stockfish/Stockfish/commit/c787509663dface7637dc3985bab516070736678), April 26, 2026. Historical stability-function implementations inspected.

## Exact read manifest

Complete files: `src/timeman.cpp`, `src/timeman.h`.

Relevant sections: `src/search.cpp:180–637` (search startup, full iterative-deepening/time loop); `src/search.cpp:1443–1518` (root effort, score EMA, leader changes); `src/search.cpp:2114–2147` (periodic hard stopping); `src/search.h:133–192,267–306,370–390` (root/limits/manager/worker state); `src/thread.cpp:261–280,303–348` (game-level resets and root setup). Earlier waves read the main search and relevant history interfaces.

Historical diffs/messages: `5ca4bfe7`, `93ed4b53`, `c7875096`, `944bee71`, `c9538625`, `2e02dd79`, `4d65257b`, `23493de0`, `3c62ad7e`, `fe7b9b14`, `69204f07`. Live primary material: PR 7113 body and comments, plus bounded issue/PR searches for time-advantage/increment interactions.
