# Third discriminator: reuse answered questions before adding search heuristics

20 September 2026, baseline `031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3`. Historical candidate design followed by completed diagnostics. The root subsequently implemented the narrow exact-output candidate `5e16e3f3`; it passed functional/property checks but failed to establish a useful whole-engine speed gain and was set aside without Fishtest. This follows the no-go decision for the [LMR reliability proposal](second-pass-lmr-feedback.md).

## Shortlist and selection

1. **Reuse an already established static-exchange threshold result.** Quiescence can call `see_ge` twice for the same capture, on the same unchanged board. Sometimes the first call has already proved the second answer. Removing that duplicate work should preserve the entire searched tree; the open question is useful whole-engine speed, not whether a superficially cleaner heuristic makes better choices. Select this for the next cheap discriminator.
2. **Use pawn-structure history only if it predicts residual LMR error.** Pawn history participates in ordering and shallow pruning, but the final quiet `statScore` combines main history and continuation histories 0/1 only. A structural move-quality signal can plausibly remain after that blend. However, it has already influenced which moves reach the LMR decision and their move index; omission from `statScore` does not imply omission from the allocator. First condition on current history, move count, depth, reduction, node type and TT role, and audit reduced fail-lows. Adding it to `statScore` also changes downstream training, so any eventual intervention should alter reduction separately. No coefficient is proposed without that evidence.

The pawn-history introduction [b0658f09](https://github.com/official-stockfish/Stockfish/commit/b0658f09b93185e2b43d4b2d6f0daa30c36ebcc2) records gainer STC/LTC passes and explicitly uses structural context in ordering and pruning. Conversely, [3b4ddf4a](https://github.com/official-stockfish/Stockfish/commit/3b4ddf4ae6362ddef063cc644d1466754015482e) removed an additional continuation term from `statScore` with simplification passes: a useful history in one role need not improve every role. These are local official commit records, not newly rerun tests.

## Exact duplicate in qsearch

At `search.cpp:1800–1835`, after giving-check, recapture and promotion exclusions, qsearch asks:

```cpp
pos.see_ge(move, alpha - futilityBase)
```

If false, it updates `bestValue` and skips the move. If true, after the non-capture guard it asks:

```cpp
pos.see_ge(move, -74)
```

The board has not changed between these calls. If the first threshold `T = alpha - futilityBase` is at least -74 and that call passed, the result at -74 is already known to pass. The intervening code neither changes occupancy nor the threshold input. The exact candidate would retain a move-local “second threshold already proved” flag, false by default, and set it only after the first call passes with `T >= -74`. Gate only the second call on that flag. Checks, recaptures, promotions, in-check cases, skipped first calls, and all first-call failure score updates retain their current behavior.

There is no new chess/search constant: -74 is the existing second threshold. This does not assume that Stockfish's SEE equals legal minimax material gain. It uses the weaker property that this same deterministic threshold algorithm is monotone in its threshold. Its existing implementation (`position.cpp:1389–1490`) is a null-window exchange decision with early exits. Verify this property against actual legal-move samples, especially pins, king recaptures and non-normal moves, before relying on it as an implementation invariant.

**Do not replace both calls with one call at `max(T,-74)` without preserving the failure path.** Failure at the stronger threshold can require different `bestValue` handling from failure at the weaker threshold. The exact proposal only skips a call whose answer is already true.

The immediate adversary is performance, not a tactical pattern: `see_ge` often returns after two material arithmetic comparisons, so skipping a call can save almost nothing while introducing another condition and carrying state through a hot loop. PGO and code layout may dominate. This is why a count of apparently duplicate calls is not enough.

## Cheap measurement that can reject it immediately

Use a logging-only baseline diagnostic over the same fixed corpus and standard bench. Keep both calls and all behavior. Count total qsearch nodes, first SEE calls, first-call passes, passes with `T >= -74`, and eligible final calls. For those eligible final calls separately count returns before attack generation versus entries into the exchange loop and its iterations. Assert the existing second call passes whenever the flag would skip it. Report these as call/work counts, never Elo.

No per-node wall clock timing belongs in this hot diagnostic; it would dwarf the work. A production prototype is justified only if meaningful expensive duplicate work exists. It must retain benchmark signature, all corpus iteration PV/score/node outputs, and differential SEE results. Then compare fixed-work speed with alternating paired order and all results retained, separately from builds/games. If speed does not improve beyond noise, discard it before Fishtest. Exact tree identity does not prove exact-output code is faster.

Related primary prior art: [2a1ab11a](https://github.com/official-stockfish/Stockfish/commit/2a1ab11ab019ce588f4f4f4b175ddd6e60d1df36) removed a redundant SEE condition as a no-functional-change optimization. [aff1f679](https://github.com/official-stockfish/Stockfish/commit/aff1f67997cd2584ea7c82d967ac7bfd4cc77861) simplified qsearch's first threshold formula, with recorded STC/LTC simplification passes. Neither establishes the speed of the present proposal. Bounded history searches found no exact duplicate-query reuse implementation, which is not proof of global novelty.

### Completed discriminator: set the narrow qsearch candidate aside

The orchestration agent subsequently authorized this diagnostic, implemented in the isolated, ignored baseline worktree `.research-tools/see-observation`. The original two calls remain; counters never feed a search decision. Counters use single-worker global state and are unsuitable for multithreaded tests. It builds with `profile-build ARCH=apple-silicon COMP=clang`, two build jobs. Diagnostic binary SHA-256 is `29c66881eebb6cc6fb7921ba495a1e98f5c631004ca147ed65982a17329049d8`. Default bench preserved **1648567** nodes with zero implication violations.

The exact [instrumentation patch](../results/see-observation/instrumentation.patch), [runner](../see_observe.py), [manifest](../results/see-observation/manifest.json), [summary](../results/see-observation/summary.json), build log, and all stdout/stderr are retained. The runner checks the saved baseline binary hash and source-corpus hash. All 64 positions use the same seed-20260920 UHO corpus, depth 13, one thread and 16 MiB hash as the LMR observation. Every iteration score, PV, node count and best move matched its saved baseline output exactly.

| Count over 64 positions | Result |
|---|---:|
| Qsearch calls | 481,863 |
| First threshold SEE calls / passes | 140,035 / 49,519 |
| Final -74 SEE calls | 213,141 |
| Implication-eligible final calls | 15,219 (7.14% of final calls) |
| Implication violations | 0 |
| Eligible calls reaching attack generation | 4,190 |
| All SEE calls reaching attack generation | 1,714,568 |
| Eligible exchange-loop iterations | 5,578 |
| All SEE exchange-loop iterations | 2,542,087 |

Of the calls that could be skipped, **72.47% return before attack generation**. Eligible calls represent only **0.244% of all SEE attack-generation entries** and **0.219% of exchange-loop iterations**. The standard bench independently showed the same small scale: 17,013 eligible calls, 5,266 reaching attack generation, or 0.407% of all such entries.

These are work-incidence counts, not time fractions or rigorous speed upper bounds. Nevertheless the removable expensive work is a tiny part of SEE, itself one part of engine computation; hot-loop flag/branch costs could consume the savings. **Decision: do not prioritize a production build or Fishtest for this narrow duplicate.** It is a verified exact-work opportunity whose expected scale does not meet the user's request for a strong improving direction. No speed measurement or Elo claim was made. The larger picker-to-main-search reuse is not tested by these numbers and must earn separate evidence if pursued.

## Larger same-mechanism opportunity, kept separate

The main move picker tests each non-TT candidate capture at `Tpicker = -storedCaptureScore / 18` to choose its good/bad capture stage. Main search may later call SEE on the same unchanged position at `Tsearch = -margin`. A known pass with `Tpicker >= Tsearch`, or a known fail with `Tpicker <= Tsearch`, answers that later call exactly. This could have wider coverage than the qsearch pair.

It needs explicit picker provenance and the *stored* threshold, because capture histories can change during intervening sibling searches. Do not reconstruct the original threshold from current history. TT moves and evasions have no such proof. The larger version introduces API/state overhead and more edge cases; first measure incidence and expensive-call share separately. Do not bundle it with the narrow qsearch optimization and then lose attribution.

## Why probability/cost move ordering is not selected first

For two independent cutoff candidates with probabilities `pA,pB` and costs `cA,cB`, trying A first minimizes expected work when `pA/cA >= pB/cB`. Existing histories learn cutoff propensity but do not explicitly estimate per-move search cost, so a shadow cost model is a defensible separate research direction.

The actual search violates the fixed-cost assumptions: depth/reduction depends on move index and history, earlier searches warm TT and change histories, and only the moves attempted before a cutoff have observed outcomes. Later cutoffs and costs are censored. Expensive tactical lines can also be the valuable lines worth examining first. Reordering recorded attempted moves while freezing their old costs is not a counterfactual engine experiment.

A future diagnostic can freeze a shadow cost predictor and ask whether it predicts held-out, depth-conditioned cost beyond current history/reduction/TT/capture class at non-PV cut nodes. Root-position splits and explicit censoring are necessary. It should not invent a cost penalty now or attach another broad history table to search merely because the probability/cost formula is elegant. Exact duplicate-work reuse has a much cleaner and cheaper initial discriminator.


## Final runtime gate

The root completed the one predeclared 20-pair depth-15 PGO timing experiment after all task builds and matches stopped. All 42 runs including warmups searched exactly 3,749,986 nodes. Search-time geometric speedup was +0.100%, approximate 95% interval [−0.176%, +0.376%]; wall-time speedup was −0.019%, interval [−0.270%, +0.232%]. No useful speed gain was established. The narrow SEE candidate is set aside, with no Fishtest submission or timing reroll. Broader SEE reuse was not implemented or tested in this pass.
