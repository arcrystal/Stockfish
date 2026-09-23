# Independent review: exact reuse of a qsearch SEE result

Baseline: `031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3`. This is the independent source audit of the minimal candidate subsequently implemented as `5e16e3f3`. Its functional, reproducibility and threshold-property checks passed, but the completed 20-pair whole-engine timing did not establish a useful speed benefit. The candidate is set aside without Fishtest; the proof below establishes the intended equivalence mechanism, not a performance claim.

## Exact reviewed change

In the qsearch move loop, initialize one local boolean to false for each move. In the existing first SEE block, retain the exact threshold expression and all failure handling. Only after that call succeeds, set the boolean when its threshold is at least the second call's existing `-74` threshold. Short-circuit the second call when the boolean is true:

```cpp
bool seeAlreadyPassed = false;
// ... original conditions before first SEE ...
const Value seeThreshold = alpha - futilityBase;
if (!pos.see_ge(move, seeThreshold))
{
    bestValue = std::max(bestValue, std::min(alpha, futilityBase));
    continue;
}
seeAlreadyPassed = seeThreshold >= -74;
// ... original end of block and non-capture continue ...
if (!seeAlreadyPassed && !pos.see_ge(move, -74))
    continue;
```

The reviewed source diff changed only this path. The first-call failure update to `bestValue` is essential and must stay exactly where it is. A combined call at the maximum threshold is not equivalent because first- and second-call failures have different score side effects. Do not modify `see_ge`, the move picker, pruning thresholds, search depths, NNUE, or histories.

Checks, recaptures and promotions bypassing the first block keep `seeAlreadyPassed == false` and execute the original second call. In-check paths where the first block is ineligible likewise retain the original handling. No new numerical tuning parameter is introduced.

## Proof obligation and implementation audit

The desired implication is purely local:

`see_ge(move, T) && T >= -74` implies `see_ge(move, -74)`.

This does not require SEE to predict the true legal chess minimax material outcome. It requires monotonicity of the **same** deterministic threshold evaluator on the **same** board and move.

The first and second calls are separated only by local control flow and a capture classification check. No move is made or undone, no occupancy changes, and no history changes alter SEE's inputs. `Position::see_ge` is const and does not use history or TT state. Alpha and futilityBase also remain unchanged in this interval.

The implementation in `position.cpp:1389–1490` has these relevant properties:

- Non-normal moves return `VALUE_ZERO >= threshold`, which is monotone directly. A non-normal move that passed a threshold at least -74 therefore also passes -74. The first caller already excludes promotions; en passant, if it reaches this path, is covered by this rule.
- The first arithmetic exit compares captured piece value against the threshold. Decreasing the threshold cannot change a passing material lower bound into failure.
- The next arithmetic exit compares the moving piece against the threshold-adjusted capture gain. Its early success becomes no harder when the threshold decreases.
- Beyond those exits, the least-valuable-attacker sequence, occupied squares, x-ray additions and pin masks are determined by board state and the exchange prefix. Threshold arithmetic decides when that deterministic exchange decision has enough information to return, rather than choosing a different attacker. This is a null-window exchange evaluation with alternating stop/capture choices; lowering the requested bound cannot make its decided exchange value fail that bound.
- Pin handling removes attackers using blockers/pinners and occupied pieces. It is independent of the requested threshold. It can make SEE an approximation of legal chess because the exchange model is limited, but does not invalidate the threshold implication within that model.
- The terminal king branch determines whether an opposing attacker remains after the proposed king recapture. That legality test depends on the same occupancy/attacker prefix, not the threshold. The earlier null-window exits may reach a decision before it, but they do not change the underlying exchange sequence.

The arithmetic here is comfortably within `int` for the finite engine scores and piece values used by this caller; the proposal neither extends the range nor introduces new arithmetic operations beyond retaining the original threshold expression. This audit supports the implication, but is not a machine-checked proof of every implementation path. The diagnostic must execute both original calls and count/assert **zero implication violations** over all eligible events. Broader legal-position SEE differential checks should deliberately include pins, king recaptures, en passant and promotions before relying on this as an optimization invariant.

## Why this is a better-defined experiment

This intervention tries to perform exactly the same search with less repeated computation. Unlike the rejected search-policy candidates, its intended causal benefit does not depend on a more logically accurate heuristic changing allocation favorably. The known risks are a bug in the implication/transport or a net runtime loss from the added boolean/branch/register lifetime and changed code layout. Both are measurable before rating games.

Counts are only the first gate. Many `see_ge` calls return after cheap material arithmetic. The diagnostic must distinguish avoided attack generation and exchange-loop work from cheap early exits. If it proceeds, require baseline bench and corpus iteration score/node/PV identity, functional/reproducibility checks, and a predeclared alternating paired whole-engine fixed-work speed test with builds/games stopped. Retain every timing and control for existing background-load limitations. A faster wrapper or fewer calls is not a whole-engine speed claim. A whole-engine speedup on this ARM machine is not an x86 speed claim or a measured Elo increase; standard independent strength testing remains necessary before describing the engine as stronger.
