# Baseline LMR verification observations, 20 September 2026

This is an observational diagnostic of unchanged baseline `031dfeb4`, not a candidate or a rating measurement. It helps reject an attractive but unsupported idea: reducing the reward or search investment for moves whose reduced fail-high is refuted by deeper search.

## Method and behavioral equivalence

`research/lmr_observe.py` selected 64 unique line indices from the published UHO book using fixed seed 20260920 before looking at results. Each position runs in a fresh process at depth 13, one thread, Hash=16. The unchanged PGO baseline and the diagnostic build are both run. Every iteration's depth, score, node count and PV, plus the final best move, must match; only time and NPS fields are ignored. All 64 comparisons passed. The default diagnostic bench also preserved signature **1648567**.

`corpus.json` records exact FENs, indices, timestamps and SHA-256 hashes for both binaries and the book. `instrumentation.patch` records the complete logging-only source change. Build command: `make -C .research-tools/lmr-observation/src -j6 build ARCH=apple-silicon COMP=clang`; compiler output is in `../lmr-observation-build.log`. The diagnostic is deliberately not PGO and logging adds overhead: these runs cannot measure speed. No engine policy, score, history update, TT write, or depth is changed. Counters are single-worker only; this instrument must not be used as written for SMP.

Each `LMR` record occurs only when an existing reduced fail-high actually triggers a deeper null-window verification. Columns after the prefix are: parent depth; scout depth d; pre-adjustment newDepth; verification depth; moveCount; pre-scout statScore; PV flag; cut-node flag; capture-stage flag; gives-check flag; ttPv; alpha; beta; bestValue; eval; reduced result; verified result; scout inclusive nodes; verifier inclusive nodes. `LMR_TOTAL` counts all LMR calls, reduced fail-highs and actual verifications. Recursive node costs overlap: their sums are not disjoint work or savings estimates.

## Observations

| Existing verification group | Events | Still above alpha after verification | Fraction |
|---|---:|---:|---:|
| All | 26,746 | 21,631 | 80.88% |
| Quiet | 23,496 | 18,862 | 80.28% |
| Quiet, current rule requests an extra ply | 10,205 | 8,793 | 86.16% |
| Other quiet verifications | 13,291 | 10,069 | 75.76% |
| Quiet, positive pre-scout statScore | 11,673 | 9,876 | 84.61% |
| Quiet, nonpositive pre-scout statScore | 11,823 | 8,986 | 76.00% |

Raw observations and the analysis script are retained. These are descriptive fractions, not independent Bernoulli trials or causal estimates: events are correlated within roots and recursive searches. The extra-ply group differs in depth, score margin and histories. Its higher survival does not prove the extra ply causes better play. History already distinguishes survival, so adding another correlated table needs evidence of incremental value.

## Decision and limits

**Do not change continuation rewards or add a verification-reliability gate from this evidence.** Current allocation is already concentrating work in promising groups. A refutation may be precisely the valuable information supplied by the extra search; preventing it could preserve a tactical illusion. Official prior changes `2ce47573` and `0dabf4f3` also removed verification-outcome-conditioned continuation updates, with recorded STC/LTC nonregression passes.

This corpus consists of opening positions at modest depth. It does not establish late-game or longer-control behavior. The observations exclude reduced fail-lows, which ordinarily receive no deeper verification; therefore they say nothing about the rate of missed strong moves. The logged `quiet` group includes all non-capture-stage moves across node types, not solely the narrower eligibility proposed by the separate reliability-table report. There is no counterfactual comparison from restored identical internal states. No confidence interval or Elo claim is inferred from these counts.
