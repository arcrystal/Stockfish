# Split the final NNUE dot-product dependency chain

**Subsequent lead-agent outcome:** the proposed patch preserved the bench signature and passed 80,000 scalar-reference checks, functional tests, and reproducibility checks. ARM and x86 VNNI wrapper assembly showed the intended independent chains. However, 20 interleaved whole-engine pairs on M1 Max estimated **−1.15% speedup**, approximate 95% interval **[−2.35%, +0.06%]**. No useful speedup was established, so this candidate is set aside. The research argument below is retained as the original hypothesis; see the [experiment ledger](../EXPERIMENTS.md) for complete evidence and limitations.

## Recommendation

Prototype two independent accumulators in the final `AffineTransform<128, 1>` layer on VNNI and NEON dot-product targets. At baseline `031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3`, earlier affine layers already split high-latency dot-product chains, but the single-output layer still accumulates every vector chunk into one register. This is a small exact-output speed candidate. It needs assembly inspection and reliable whole-engine timing before any claim of speed or Elo benefit.

The proposal adds no new evaluation approximation, model, cache, branch-dependent score, or neural-network training requirement. It addresses a remaining serial computation in the dense tail. The first experiment should keep the existing vector width and split into only two chains. No engine source was changed or compiled during this investigation.

## Complete inference map

The baseline uses one network, with HalfKAv2_hm piece-square, FullThreats, and PP_3Wide pawn-pair features. Its architecture has `L1=1024`, `L2=L3=32`, eight PSQT buckets, and eight dense layer stacks selected by `(pieceCount-1)/4`. Both perspectives are maintained in the accumulator. The transform clips and multiplies pairs of 16-bit accumulator values into a 1024-byte transformed input; the resulting input is bounded in `[0,127]`. Nonzero chunks are recorded while transforming. [1–3]

The first affine layer maps 1024 sparse inputs to 32 outputs. Squared and linear clipped activations concatenate to 64 inputs for the second affine layer, which produces another 32 outputs. Their squared and linear activations join the first activation pair, giving **128 inputs** to the final scalar affine layer. An additional forward skip is formed from the difference between the final two first-layer raw outputs. Output scaling uses a 64-bit intermediate. The proposed patch touches only the final 128-input sum before its bias and the existing skip/scaling steps. [1]

`Network::evaluate()` allocates aligned temporary transformed features and NNZ metadata, evaluates one material bucket, and returns PSQT and positional outputs. Search's outer evaluator then applies optimism, complexity, material, and rule-50 scaling. The NNUE load/save paths permute weights to match SIMD packing; hash and serialization functions are cold paths and should not be conflated with inference cost. [2,3]

## Existing conditional computation and memory boundaries

Accumulator updates are lazy. Pushing a move records dirty piece/threat/pawn-pair changes and resets computed flags; it does not eagerly update all feature sums. On evaluation, the stack finds usable computed states or refresh boundaries, updates both perspectives together along a common suffix when possible, and uses per-king-square Finny caches for HalfKA refreshes. Cache entries hold HalfKA sums and piece layouts, while active threat/pawn-pair features are added for a full refresh. A hybrid path for certain same-half king moves preserves the existing threat/pawn-pair contribution and replaces only the king-dependent HalfKA part. [4]

The large feature weights make accumulator work partly a memory-access problem. Incremental updates touch columns for changed features; these columns are prefetched while constructing change lists. The code tiles accumulation to fit vector registers. The smaller dense tail has very different constraints: first-layer sparse traversal and dependent dot products can dominate arithmetic scheduling even when their weights are cache-resident. A change that helps the dense tail does not necessarily help refresh-heavy positions.

Sparse traversal is architecture-specific. AVX-512 gathers nonzero indices, AVX2/NEON/LoongArch generally record bitsets for four-byte chunks, and RVV records individual nonzero indices. Existing sparse VNNI/NEON paths split accumulator dependencies into two or three chains. The multi-output dense layer also uses two chains on VNNI and NEON dot-product builds. Fused squared/linear activations and load-time weight permutations avoid repeated conversion/shuffle work on AVX2-family paths. [1,5,6]

The final single-output branch is different: it loops through all input vectors, repeatedly invoking `vec_add_dpbusd_32(sum0, inputVector[j], row0[j])`. In this architecture that is four 256-bit chunks on x86 and eight 128-bit chunks on NEON. All dot products depend on the preceding value of `sum0`; the final horizontal reduction waits for that chain. Two independent sums could overlap dot-product execution without changing the number of input/weight loads. Whether the processor and compiler actually benefit is an empirical question. [5,6]

## Exact candidate patch

Within `src/nnue/layers/affine_transform.h`, inside the `OutputDimensions == 1` branch, replace the loop at lines 356–360 with this code. Leave the existing declarations of `NumChunks`, `sum0`, and `row0`, and the final `output[0] = vec_hadd(sum0, biases[0]);` in place.

```cpp
            int j = 0;
    #if defined(USE_VNNI) || defined(USE_NEON_DOTPROD)
            // Shorten the final layer's dot-product dependency chain.
            vec_t sum1 = vec_setzero();
            for (; j + 1 < int(NumChunks); j += 2)
            {
                vec_add_dpbusd_32(sum0, inputVector[j], row0[j]);
                vec_add_dpbusd_32(sum1, inputVector[j + 1], row0[j + 1]);
            }
        #if defined(USE_NEON_DOTPROD)
            sum0 = vaddq_s32(sum0, sum1);
        #else
            sum0 = _mm256_add_epi32(sum0, sum1);
        #endif
    #endif
            for (; j < int(NumChunks); ++j)
                vec_add_dpbusd_32(sum0, inputVector[j], row0[j]);
```

The odd-chunk tail retains template generality. On non-VNNI/non-dot-product targets, preprocessing leaves the original computation. Supported VNNI builds in the inspected Makefile use the AVX2-width final layer even when earlier layers use AVX-512; consequently the x86 merge is `_mm256_add_epi32`. A future build configuration permitting `USE_VNNI` without `USE_AVX2` would need the merge width revisited. Avoid using the surrounding `vec_add_32` macro blindly: its earlier multi-output AVX-512 definition would have the wrong width here.

## Why the outputs should be identical

Both variants sum precisely the same products and apply the same bias once. Inputs are `[0,127]`, weights are signed bytes, and the current final dot product has only 128 inputs. Its absolute product-sum bound is `128 * 127 * 128 = 2,080,768`, safely within signed 32-bit range before the unchanged bias addition. No activation, rounding, saturation, or output scaling moves across the sum. VNNI uses non-saturating 32-bit accumulation here, and NEON's wrapper calls `vdotq_s32`; the Arm intrinsic reference identifies this as signed byte dot products accumulated into 32-bit lanes. [5,7]

Thus the numerical argument is stronger than for an evaluation-changing shortcut, but it is still a hypothesis until the candidate is compiled and compared. Template/preprocessor mistakes, register-type mistakes, unexpected input padding, compiler transformations, or a future architecture change could invalidate an implementation. Deterministic bench and direct layer comparisons should be exact.

## Prior work and novelty limits

| Primary experiment | Recorded evidence | Distinction from this proposal |
|---|---|---|
| [PR #6956, Split NEON dense affine accumulation two ways](https://github.com/official-stockfish/Stockfish/pull/6956), July 2026 | Commit records a local M3 Pro speedup around 0.56% and an STC pass; exact-output change | Changes the **multi-output** branch used by `fc_1`, not the scalar `fc_2` branch |
| [PR #6961, Split AVX-VNNI sparse affine accumulation two ways](https://github.com/official-stockfish/Stockfish/pull/6961), July 2026 | Commit records roughly 0.98% on Core Ultra 9 285H and an STC pass | Applies to sparse `fc_0` |
| [PR #6951, Split NEON sparse affine accumulation three ways](https://github.com/official-stockfish/Stockfish/pull/6951), July 2026 | Commit records roughly 1.21% locally on M3 Pro and an STC pass | Applies to sparse `fc_0`; its long sparse accumulation amortizes extra chains differently |
| [PR #6683, Split affine transform on VNNI](https://github.com/official-stockfish/Stockfish/pull/6683), April 2026 | Commit records roughly 0.31% speedup and an STC pass | Existing predecessor in the multi-output dense branch |

These percentages describe historical whole-engine measurements on their named hardware and commits. They are not forecasts for this proposal. The first PR was also opened on GitHub; the others were inspected through official local git history. Their Fishtest URLs are preserved in those commit records.

The single-output branch exists separately in part because [PR #4773](https://github.com/official-stockfish/Stockfish/pull/4773) fixed out-of-bounds accesses from using AVX-512 on an older 32-input last layer. That historical architecture differs from today's 128 inputs, but retaining the current width makes this experiment smaller and avoids reopening alignment/padding assumptions. Exact final-layer chain splitting was not found in the bounded local-history/web search. This does not rule out unmerged personal experiments.

## Alternatives considered and rejected for the first experiment

**Skipping part of the network when PSQT is decisive** changes evaluation. It can miss fortresses and other exceptions precisely where a cheap model looks confident. The former small network was removed in May 2026 despite recorded failing non-regression tests, with maintainability and weaker evaluation quality among the stated tradeoffs. That history is not evidence that arbitrary conditional inference is profitable. [8]

**Caching one NNUE result in each accumulator state** risks confusing side-to-move changes through null moves, and caching the outer evaluation also risks optimism/rule-50 context. A correctly keyed two-perspective cache would add state and invalidate work, while TT raw-evaluation reuse already removes many repeat computations. Measure duplicate inference first before adding another cache.

**Fusing two successive accumulator transitions** can remove intermediate stores and cancel feature changes, but it has direct prior art: the April 2025 double-incremental optimization was removed in April 2026 after the smaller L1 made bookkeeping relatively expensive. Different contributors measured opposite speed effects. Reintroducing it is not an obvious free optimization. [9]

**Hybrid king refresh and joint perspective updates** are already implemented, with recent successful tests. Re-proposing them would duplicate baseline work. The selected output-layer patch avoids the complexity of dirty-feature state, intermediate accumulator validity, and refreshed king buckets. [10]

## Costs, likely failures, and test protocol

The patch adds one vector accumulator, a zero initialization, and one vector addition. It does not reduce arithmetic count; it exposes instruction-level parallelism. It may lose if the compiler already unrolls/reassociates optimally, if the extra sum/merge costs more than the saved dependency delay, or if register pressure harms inlined surrounding code. The final layer is small, so even a large improvement to that micro-kernel can produce a negligible whole-engine improvement. A four-chain version should not be bundled into the first test.

First inspect generated assembly on the actual Apple-silicon build and one VNNI x86 target: confirm two independent dot-product chains, no spills, and expected merge width. Then compare scalar/reference and SIMD final-layer output across boundary and random legal-range inputs, verify full-network outputs on a broad position set, and require identical single-thread fixed-depth bench signatures. Include existing accumulator/reproducibility checks so unrelated compiler behavior is caught. No extra speed advantage should appear at fixed-node deterministic play if the patch is truly exact-output; benefit must come from time saved.

Next run repeated **interleaved** baseline/candidate whole-engine speed tests with the same profile-build method, CPU affinity, network, and idle-load conditions. Warm the binaries consistently; report uncertainty, compiler, hardware, and instruction set. Avoid contending with the other engine experiments while measuring tiny speed changes. Stop if whole-engine timing is inconclusive or worse. A kernel-only speedup does not establish a stronger chess engine.

For a reliably faster exact-output build, run Fishtest at equal wall-clock time, preserving matching nets/options. Use the current project's accepted speed-change test protocol and confirm the workers actually exercise the changed ISA path; an ordinary AVX2 worker receives no change from this proposal. A broad mixed-hardware pool can dilute a target-specific win. Report results by applicable hardware/time control, and do not turn a measured NPS percentage into a claimed Elo percentage. Independent game evidence is still required for an Elo claim.

## Sources and exact reading coverage

The following **15 files were read in full, totaling 4,714 lines at this baseline**. Output truncation in an initial combined read was repaired by subsequent complete reads of the affected common/header files. Feature implementations themselves were assigned to the orchestration agent and are not included in this coverage claim.

| File under `src/nnue/` | Lines | Main role |
|---|---:|---|
| `network.h` | 121 | Inference/loading interface and embedded architecture |
| `network.cpp` | 367 | Loading, tracing, inference, serialization, hashing |
| `nnue_accumulator.h` | 142 | Lazy stack and Finny-cache layout |
| `nnue_accumulator.cpp` | 953 | Incremental, paired, hybrid and refresh computation |
| `nnue_architecture.h` | 174 | Layer topology, activations, skips, output scale |
| `nnue_common.h` | 352 | Quantization types, SIMD widths, endian/LEB I/O |
| `nnue_feature_transformer.h` | 440 | Weight layout, clipping/products and sparse metadata |
| `nnue_misc.h` | 66 | Network metadata and tracing interface |
| `nnue_misc.cpp` | 100 | Trace formatting |
| `nnz_helper.h` | 171 | Architecture-specific nonzero metadata |
| `simd.h` | 532 | ISA wrappers and accumulator tiling |
| `layers/affine_transform.h` | 426 | Dense kernels, including proposed final-layer change |
| `layers/affine_transform_sparse_input.h` | 445 | Sparse kernels and dependency splitting |
| `layers/clipped_relu.h` | 178 | Linear clipped activations |
| `layers/sqr_clipped_relu.h` | 247 | Squared and paired activations |

1. [`nnue_architecture.h` at the exact baseline](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/nnue/nnue_architecture.h).
2. [`network.cpp` at the exact baseline](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/nnue/network.cpp); outer `src/evaluate.cpp` was read fully in wave 1.
3. [`nnue_feature_transformer.h` at the exact baseline](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/nnue/nnue_feature_transformer.h).
4. [`nnue_accumulator.cpp` at the exact baseline](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/nnue/nnue_accumulator.cpp).
5. [`layers/affine_transform.h` at the exact baseline](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/nnue/layers/affine_transform.h) and [`simd.h`](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/nnue/simd.h).
6. [`layers/affine_transform_sparse_input.h` at the exact baseline](https://github.com/official-stockfish/Stockfish/blob/031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3/src/nnue/layers/affine_transform_sparse_input.h), and `nnz_helper.h`; `src/Makefile` lines **781–814** also read for VNNI flags.
7. Arm, [Neon Intrinsics Reference, dot-product intrinsics](https://arm-software.github.io/acle/neon_intrinsics/advsimd.html#dot-product), accessed through the official Arm ACLE documentation. The documentation establishes instruction semantics, not a universal instruction latency or predicted speedup.
8. [`ab8f901d`, Remove small net](https://github.com/official-stockfish/Stockfish/commit/ab8f901d25def6c17f83b7a1b4b84eaec404c0f4), complete local message and statistics read; broad deletion diff not fully read.
9. [`fda269a2`, Introduce double incremental accumulator updates](https://github.com/official-stockfish/Stockfish/commit/fda269a2997033a01ed49d83337a2e0405cec805), and [`1a882efc`, Simplify out double_inc_update](https://github.com/official-stockfish/Stockfish/commit/1a882efc7fc22b3b16893a406e6060916022fcc4), full local messages and statistics, not complete historical diffs.
10. [`db98633b`, Hybrid king updates](https://github.com/official-stockfish/Stockfish/commit/db98633b1f8bbcad850bee892ec143ff8723ba80), and [`7b550409`, Joint perspective updates](https://github.com/official-stockfish/Stockfish/commit/7b5504097feb349a2262eec0702b2a18e426ccf6), full local messages/statistics; current implementation read fully.

Additional historical reading: complete `2d239de4` and `1461d861` messages/diffs; messages/statistics for `fb1d7772`, `2cbf39f8`, `8132dbcb`, `eca43a97`, and `1c384d3a`. No source edit, build, remote write, or Fishtest submission occurred. Confidence is high in the exact-output argument for the shipped architecture, moderate that generated instructions improve, and low in an Elo gain before measurement.
