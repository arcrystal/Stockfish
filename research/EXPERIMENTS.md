# Stockfish experiment ledger

## Baseline

The immutable starting point is Stockfish commit `031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3` (13 September 2026), now available in the personal fork [arcrystal/Stockfish](https://github.com/arcrystal/Stockfish). The local research branch is `codex/elo-research`. Individual engine changes use separate worktrees and branches rooted directly at the baseline.

The baseline uses `nn-134a887f4c8f.nnue`, SHA-256 `134a887f4c8ff7bf7284177a3b3fc6ff9cef95ba89eb8db3079a8e507f7126af`. Baseline and candidates use `profile-build ARCH=apple-silicon COMP=clang`, with six parallel build jobs initially and two for later builds while the six-game local screen runs. Apple clang is version 21.0.0. Baseline bench is **1648567** nodes. The baseline binary's SHA-256 is `3bc6989c07a680e8478a997b5fcafb877724ac4909509341d1b0d373e7eb6083`.

The machine is an Apple M1 Max ARM64 Mac with ten logical/physical cores and 32 GiB memory. The build emits an existing SDK warning about the Makefile's macOS deployment target; compilation succeeds. Timing on this machine is not interchangeable with Fishtest's normalized time controls.

Baseline validation passed the repository signature check, all 20 search-reproducibility cases, and all 20 standard/Chess960 perft cases. An eight-game self-match completed to validate the runner. Its apparent rating difference is sampling noise between identical binaries and has no strength interpretation.

## Match method

Local screening uses [Fastchess](https://github.com/Disservin/fastchess), pinned at `60d7a7a26c6b0582a15c112fb29a1829bef2adb3`, and the official [UHO opening book](https://github.com/official-stockfish/books/blob/master/UHO_Lichess_4852_v1.epd.zip). The extracted EPD has 2,632,036 lines and SHA-256 `7a7f6470615a69c6cf23d565417701d38732876f480af90d67b42abade35644a`.

Each opening is played twice with colors reversed. Matches use one engine thread, 16 MiB hash, normal full strength, six concurrent games, and the Fishtest-style resignation/draw adjudication described in [Running Fastchess](https://github.com/official-stockfish/fishtest/wiki/Running-Fastchess). The runner emits pentanomial pair counts. Every invocation of `run_match.py` records the exact command, seed, input hashes, and timestamps before play, and preserves the game log and PGN. It refuses to overwrite an existing experiment record.

The first screening trial is fixed at **1,000 games, 1+0.01 seconds, seed 20260915**, declared before its results were inspected. It will run to completion unless a correctness or execution failure invalidates the match. Its purpose is to find gross regressions and check whether further testing is worthwhile. It cannot establish a small Elo gain. No parameter variants will be silently rerun until one looks positive; all completed experiments belong in this ledger.

Candidate selection is informed by causal reasoning, independent research, and local evidence. Selecting among several ideas creates selection bias. A claimed improvement requires independent games at meaningful time controls, with completed statistical evidence and exact test conditions. A smaller bench node count or faster single run is not an Elo result.

## Candidate 1: correction learning from excluded searches

Branch: `codex/correction-bound`. Candidate bench: **1283493**. The candidate passes all 20 existing search-reproducibility cases.

The candidate adds `&& (!excludedMove || bestMove)` to the final correction-history update in `src/search.cpp`. An excluded-move search evaluates alternatives after removing the presumed best move. Its fail-low result is not an upper bound on the complete position's value. The guard suppresses the resulting downward correction while retaining upward corrections supported by an alternative move. This is an experimental learning rule, not a maintainer-confirmed bug fix or a proven rating improvement.

The separate correction update after multi-cut, normal correction learning, NNUE weights, search constants, and transposition storage are unchanged. The main risk is that the old downward updates act as a useful bias in the empirically tuned search. Logical cleanliness alone does not establish strength.

Evidence files are in `results/correction-bound-*`. The agent report provides the detailed derivation and prior-art investigation.

The fixed local screen completed all 1,000 games: **265 wins, 261 losses, 474 draws; +1.39 Elo ±11.80**, pentanomial `[7,118,248,118,9]`. This is inconclusive. It completed without an engine failure. All 75 repository functional tests (seven suites) passed, as did all 20 search-reproducibility cases. Published candidate commit: `685e5a03696ea6f3fbd148b2346ad23de31e6bb7`.

## Fishtest plan and access

The first candidate was submitted successfully: [Fishtest run 6aa85960cb562be55c88e907](https://tests.stockfishchess.org/tests/view/6aa85960cb562be55c88e907). It has been approved by a maintainer and assigned workers. Settings: standard STC, 10+0.1, one thread, Hash=16 on both sides, normalized SPRT bounds [0,2], normal priority and throughput. This trial subsequently completed with a rejected gainer hypothesis; see the terminal record below. The public run snapshot is preserved in `results/fishtest-correction-bound.json`.

Use a source branch on the personal GitHub fork, exact baseline/candidate revisions, verified bench signatures, and the form's current standard STC settings. Let the standard sequential test reach a terminal result. If STC passes, perform independent LTC confirmation; search-scaling changes may additionally require the longer controls indicated by the source. The current [contribution/testing guide](https://github.com/official-stockfish/fishtest/wiki/Creating-my-first-test) and [statistical methodology](https://github.com/official-stockfish/fishtest/wiki/Fishtest-Mathematics) govern interpretation. Fishtest measures relative strength under its test conditions, not an absolute universal engine rating.

## Candidate 2: child transposition bound direction

Branch: `codex/tt-bound`, independently based on the same baseline.

Bench: **1485122**. All 20 reproducibility cases and all 75 functional tests passed.

The child TT score currently vetoes an otherwise eligible parent cutoff if its numeric value appears to disagree, even when its one-sided bound cannot establish that disagreement. The candidate retains vetoes only when the child carries the informative bound direction. No new constants or TT probes are introduced. This may save unnecessary search, but an inconclusive child bound could still be a useful empirical warning about stale parent data.

The second local screen is declared in advance as **1,000 games, 1+0.01, seed 20260916**, with the same runner/book/hash/thread settings. Candidate 1 and candidate 2 are tested separately. Their engine changes are not combined. See `agents/03-tt-semantics.md` for the derivation and historical experiments.

Completed result: **282 wins, 285 losses, 433 draws; −1.04 Elo ±11.21**, pentanomial `[5,116,262,111,6]`, without an engine failure. This is inconclusive. Commit `144dff77` is published on the personal fork.

## Candidate 3: queen escape occupancy

Branch: `codex/queen-escape`, independently based on the baseline.

This candidate removes the queen's origin from occupancy when validating an apparent escape from an enemy rook/bishop. The old square can hide the continuing attack on a retreating queen's destination. It removes a false escape bonus while preserving genuine escapes. The cost is a conditional slider attack query; improved geometric classification may still lose strength if its cost or search effects outweigh the benefit.

The third local screen is declared in advance as **1,000 games, 1+0.01, seed 20260917**, otherwise identical settings. See `agents/04-move-ordering.md`.

Bench: **1281886**. All 20 reproducibility cases and all 75 functional tests passed. Commit `442230b9` is published on the personal fork. The fixed local screen completed **267 wins, 262 losses, 471 draws; +1.74 Elo ±11.70**, pentanomial `[5,122,244,121,8]`, without an engine failure. This is inconclusive. Its point estimate does not meaningfully distinguish it from either of the other candidates.

## Candidate 4: independent final NNUE arithmetic chains

Branch: `codex/nnue-chains`, commit `4d8dd713`, independently based on the baseline and published on the personal fork. The single-output affine layer uses two dot-product accumulator chains on VNNI and NEON dot-product targets. The trained parameters and arithmetic sum remain the same.

The full-engine bench remains exactly **1648567**. Both baseline and candidate passed 80,000 standalone comparisons with a scalar reference across legal activation ranges, signed-byte weight extremes, and eight input dimensions including the shipped 128-input layer. The candidate also passed all 75 functional tests and all 20 search-reproducibility cases. `check_affine.cpp` uses the public parameter-loading and propagation interfaces; no private state is accessed.

Assembly from the isolated final-layer wrapper confirms eight serial ARM dot products become two four-instruction chains, with one merge and no spills. Cross-compiled x86 VNNI assembly confirms four serial dot products become two two-instruction chains, also without spills. The x86 binary was not run on this ARM host; cross-compilation checks instruction generation, not execution. These are wrapper-level observations; inlining into the full engine can change register pressure.

Timing is predeclared as **20 paired fixed-depth-15 benchmarks**, one warmup per variant, alternating AB/BA order, one thread and 16 MiB hash. `compare_speed.py` preserves every run, requires identical searched-node counts, and reports geometric speed ratios with approximate paired 95% intervals. Local matches and builds must finish before this experiment begins. No slow run will be silently discarded. One build per variant does not isolate PGO/layout variation, and this local ARM64 timing cannot establish x86 speed or Elo.

The timing experiment completed on 14 September 2026 at 21:01 UTC: **42 runs including two warmups**, all searching exactly **3,749,986 nodes**. Across the 20 measured pairs, the search-time geometric speedup was **−1.15%**, approximate 95% interval **[−2.35%, +0.06%]**. External wall timing agreed: **−1.07%**, interval **[−2.23%, +0.11%]**. Negative speedup means slower. This fails to establish a useful speedup on the M1 Max; the interval barely includes zero and is not a conclusive slowdown claim either. All our engine builds and matches had stopped, although normal desktop background activity remained. No CPU affinity was applied, and timing cannot isolate compiler/profile/layout effects from one build pair.

**Decision: set candidate 4 aside; do not promote it to Fishtest from this evidence.** The scheduling mechanism and exact outputs are verified, but the necessary whole-engine performance benefit is absent. An x86 performance claim would require separate hardware evidence. Full timings and every stdout/stderr transcript are in `results/nnue-timing/`; no runs were discarded or rerolled.

Reproduce the direct ARM check with `clang++ -std=c++17 -O3 -march=armv8.2-a+dotprod -DUSE_NEON=8 -DUSE_NEON_DOTPROD -DIS_64BIT -DUSE_POPCNT -I<checkout>/src research/check_affine.cpp -o <check-binary>`, then run the binary. Replace the input with `research/inspect_affine.cpp` and use `-S` for assembly. The x86 wrapper used `-arch x86_64 -mavx2 -mavxvnni -DUSE_SSE2 -DUSE_SSSE3 -DUSE_SSE41 -DUSE_AVX2 -DUSE_VNNI` in place of the ARM target flags. All outputs are under `results/affine-*`.

## Candidate 5: preserve a detected repetition through quiescence completion

Branch: `codex/repetition-floor`, independently based on the baseline. Quiescence already raises alpha when a legal repetition draw is available, but its restricted move set can omit the quiet drawing move and later return a lower score. The candidate retains the existing sampled draw in a local variable, clamps eligible TT cutoff returns to it, and returns it before the final TT write when ordinary completion falls below it. It does not change move generation, initial bestValue/pruning, draw jitter, terminal/max-ply/mate exits, or neural evaluation.

A separate logging-only baseline diagnostic preserved bench **1648567** and observed 3,841 repetition detections, 103 continuing nodes, 9 TT returns below the detected draw, and 16 ordinary completions below it. This confirms the source mechanism occurs in the standard benchmark; it does not measure frequency in real games or Elo. The diagnostic patch, runner, full command history and logs are retained under `results/repetition-diagnostic*` and excluded from the production engine patch.

The fourth local game screen is declared before play as **1,000 games, 1+0.01, seed 20260918**, with the same paired book, runner, threads, hash and concurrency as the earlier screens. It must follow successful functional and reproducibility checks. All 20 pairs of the NNUE speed experiment will run after this screen and every engine build have finished.

Bench: **1586754**, published commit `948232b7da3394fc02fd5ed60a7d4ce566d3f7d0`. All 75 functional tests and all 20 reproducibility cases passed. The production patch received a separate source review from the orchestration agent. A paired public-UCI probe with identical root boards and a forced root move gives baseline **cp 102** in both cases; the candidate gives **cp 0 with repetition history** and retains **cp 102 without history**. This is reported from Black's root perspective and uses UCI centipawns, unlike the internal −351 score in the diagnostic's White child. The histories, full output, and `repetition_probe.py` are preserved.

The fixed local screen completed **283 wins, 274 losses, 443 draws; +3.13 Elo ±11.93**, pentanomial `[8,116,244,123,9]`, without an engine failure. This is inconclusive. The causal reproduction and successful checks justify further testing independently of its small positive point estimate.

Submitted [Fishtest run 6aa85fe9cb562be55c88e90e](https://tests.stockfishchess.org/tests/view/6aa85fe9cb562be55c88e90e). It was approved and ran to a terminal rejection, recorded below. It uses the same pinned baseline and standard STC settings as candidate 1: 10+0.1, one thread, Hash=16, normalized SPRT [0,2], normal priority/throughput. The public API confirms the intended source revisions, signatures, network, fork, and settings. The saved snapshot is `results/fishtest-repetition-floor.json`.

At the 14 September 2026 23:39 UTC follow-up, the repetition trial had completed 2,080 games (527 wins, 514 losses, 1,039 draws), with SPRT LLR +0.123 and no terminal state. The correction-history trial had completed 9,216 games, with LLR −1.535 and no terminal state. Neither trial had crashes or time losses. Both remain within their declared stopping boundaries, so both are left running. These are progress snapshots, not completed Elo findings; no LTC trial or additional candidate is started at this stage.

## Terminal STC results and next trials — 16 September 2026

Both initial tests reached Fishtest's terminal `rejected` state without manual stopping. Neither advances to LTC or gets combined into another candidate. The API-reported Elo intervals below are 95% intervals under these STC conditions.

| Candidate | W / L / D | Games | Elo [95% interval] | LLR | Crashes / time losses |
|---|---|---:|---|---:|---|
| Correction bound | 8125 / 8333 / 15958 | 32,416 | −2.07 [−3.97, −0.15] | −2.9394 | 0 / 0 |
| Repetition floor | 21869 / 21991 / 42636 | 86,496 | −0.34 [−1.45, +0.80] | −2.9341 | 0 / 1 |

Pentanomials are `[49,3940,8432,3744,43]` and `[114,9104,24902,9046,82]`. Server completion timestamps are 15 September 07:33:43 UTC and 22:02:34 UTC. Fishtest reports rejection with overshoot accounting even though displayed LLRs are slightly above the nominal lower boundary; its terminal decision is retained. Correction shows a negative result in these conditions; repetition fails to establish a gain, without establishing a definitive loss. Full terminal API payloads are `results/fishtest-correction-bound-elo.json` and `results/fishtest-repetition-floor-elo.json`. Earlier run snapshots remain historical records.

The next already validated candidates were submitted separately against the original pinned baseline:

- **TT bound direction:** [6aaafaeddbd128aac8fd5081](https://tests.stockfishchess.org/tests/view/6aaafaeddbd128aac8fd5081), exact commit `144dff77ac0d96167a870b8e8c58dda5b6c87f30`, bench 1485122.
- **Queen escape occupancy:** [6aaafb0fdbd128aac8fd5083](https://tests.stockfishchess.org/tests/view/6aaafb0fdbd128aac8fd5083), exact commit `442230b916e2e17694ddbcd3d94ccc712cd2ba03`, bench 1281886.

Both await approval at submission. Each uses standard STC 10+0.1, one thread, Hash=16, normalized SPRT [0,2], normal priority and throughput, unchanged network and default UHO book. Public API snapshots verify source revisions, signatures and settings. These submissions use the two available slots; no further test will be added while both are active. Selection follows the documented causal investigations, not the inconclusive local point estimates. Standard stopping and independent LTC confirmation after an STC pass remain required.

## Second pair terminal results — 17 September 2026

Both independent trials completed with Fishtest SPRT `rejected`, without manual stopping. Neither establishes an improvement or advances to LTC.

| Candidate | W / L / D | Games | Elo [95% interval] | LLR | Crashes / time losses |
|---|---|---:|---|---:|---|
| TT bound direction | 11941 / 12126 / 23613 | 47,680 | −1.18 [−2.75, +0.40] | −2.9430 | 0 / 1 |
| Queen escape occupancy | 13676 / 13850 / 26522 | 54,048 | −0.96 [−2.43, +0.53] | −2.9276 | 0 / 0 |

Pentanomials: `[54,5693,12546,5478,69]` and `[70,6365,14335,6177,77]`. Server completion timestamps: 17 September 09:50:21 UTC and 12:39:06 UTC. Full terminal payloads: `results/fishtest-tt-bound-elo.json` and `results/fishtest-queen-escape-elo.json`. Both intervals include zero; the appropriate decision is failure to establish the intended gain, not a definitive regression claim. Fishtest's terminal decision includes overshoot accounting.

There are now zero active Fishtest experiments. All four previously validated search candidates have rejected STC results, and the exact-output NNUE candidate lacked a demonstrated speed benefit. None is combined or rerolled. The orchestration agent is assigned the next ranked hypothesis from report 01: a logging-only baseline diagnostic for correction-direction conflict and its potential effect on rounded quiet-move reductions. This must establish practical incidence and support the mechanism before a production prototype and its functional checks/local screen can justify another submission. No new rating test is authorized by diagnostic counts alone.

## Second-pass rethink — 20 September 2026

The user requested a fundamental rethink after four negative STC estimates (220,640 games total). The new orchestration report `agents/second-pass-synthesis.md` supersedes the initial candidate ranking. The remaining old hypotheses are not automatically promoted. All failed source branches remain separate and preserved.

New baseline observations preserve bench 1648567 and all iteration score/node/PV and final bestmove outputs on 64 fixed-seed UHO positions, depth 13, one thread, Hash=16. LMR verification outcomes do not justify an outcome-dependent continuation bonus or a new reliability gate. Retaining the exact singularity-refuting quiet also failed its opportunity test: current histories already put 615 of 724 observed candidates first; the 23 later successful cutoff witnesses had only 231 preceding quiet nodes total across 1,704,360 searched nodes. That is a descriptive opportunity count, not guaranteed savings. Pawn-history residuals were small and exploratory, with no reduced fail-low audit; no new reduction term is justified yet. Raw evidence is in `results/lmr-observation/`, `results/lmr-pawn-observation/`, and `results/singular-witness-observation/`.

### Candidate 6: reuse an already passed qsearch SEE threshold

Branch `codex/qsearch-see-reuse`, independently based on 031dfeb4. When qsearch's first `see_ge(move, alpha-futilityBase)` passes at a threshold >= -74, a move-local boolean skips the later `see_ge(move,-74)`. The same board/move and monotone threshold evaluator imply that answer. First-call failure handling remains unchanged. No heuristic coefficient, pruning rule, search depth, history update or neural parameter changes.

This is selected for one cheap performance falsification, **not** as an established strong upgrade. The observational 64-position corpus found 15,219 reusable calls, of which only 4,190 entered attack generation and 5,578 exchange-loop iterations were potentially avoided; there were zero implication violations. The potential whole-engine benefit is small and may be erased by added branch/state overhead. See the independent proof audit and source report.

Before seeing candidate speed results, declare exactly the existing 20-pair `compare_speed.py` procedure: one warmup per engine, fixed depth 15, one thread, Hash=16, alternating AB/BA, all timings retained, identical nodes required, no simultaneous builds/games. Use the same Apple-clang PGO configuration. A production bench mismatch stops promotion. Functional/reproducibility checks and a useful measured whole-engine speed benefit must precede Fishtest. No timing rerolls or combined SEE variants will be used to chase a favorable estimate. ARM timing alone does not establish x86 speed or Elo.

Candidate 6 is published as `5e16e3f3` on `codex/qsearch-see-reuse`. It retained bench **1648567**, passed all 75 functional tests and 20 reproducibility cases, and passed the SEE monotonicity/implication harness over **70 positions, 2,172 legal moves, 17,795,196 threshold queries and 143,554 reuse implications**. All four move types were exercised. The first standalone-harness link failed because LTO's embedded-network relative path was resolved from the repository root; rerunning the same link from the candidate src directory fixed it. Both linker logs and the successful command are retained; this was a harness working-directory issue, not an engine test failure.

The predeclared 20 timing pairs completed, with both warmups and every measured run retained. All 42 runs searched **3,749,986 nodes**. Search-time geometric speedup: **+0.100%**, approximate paired 95% interval **[−0.176%, +0.376%]**. External wall speedup: **−0.019%**, interval **[−0.270%, +0.232%]**. This does not establish a useful whole-engine speed gain. **Set candidate 6 aside; no Fishtest submission.** These are local ARM results from one PGO build pair, with normal OS background activity and no CPU affinity; they neither prove a slowdown nor establish x86 performance. Full evidence: `results/qsearch-see-reuse-timing/` and associated build/functional/repro/property logs.

The next bounded diagnostic measures the missing labels directly: reduced fail-lows. An unchanged baseline observer will collect a fresh 64-position UHO corpus (seed 20260921, excluding the previous64), select at most one positive-pawn and one nonpositive-pawn candidate per root, and replay the identical deterministic root prefix with exactly one scout changed from d to d+1. Restrict to quiet, non-PV, non-check, non-excluded events at parent depth >=6, actual reduction >=2 and nonpositive current statScore. Entry identities must match, ss->reduction must reflect the tested depth, and normal downstream verification stays intact. Cap at128 intervention replays and retain every result. No pawn-history coefficient or production policy is chosen from survival correlations alone.


### Completed causal pawn-LMR audit — 23 September 2026 UTC

The frozen fresh corpus (seed 20260921) matched the baseline's complete iteration traces on all **64/64** roots at depth 13, Threads=1, Hash=16. Standard bench remained **1648567**. All roots supplied a common matching bucket, producing exactly **128 targets** selected before treatment. Selection SHA256: `5932cf589f772e3562b5bbe7a2c898e7b143becccf04e41c4ce3dd091392195a`. The diagnostic binary SHA256 is `f6b301ee1b2a5f62c8d9162d5dd75f55a2dc43cd03db4ac1385d4fdf14749840`; its source patch, protocol and runner are preserved.

All 128 single-event replays passed the recorded identity and prefix checks, with no invalid/aborted results. Each changed only one selected scout from d to d+1 while keeping the reduction field and normal downstream policy consistent. **Both pawn-history groups remained fail-low in all 64/64 cases.** There were zero verification-supported recoveries, zero exposed illusions and zero accepted-without-verification threshold crossings. No event was replaced or rerolled.

| Outcome | Positive pawn history | Nonpositive pawn history |
|---|---:|---:|
| Valid treatments | 64 | 64 |
| Verification-supported recoveries | 0 | 0 |
| Unchanged local move-node count | 52 | 55 |
| Sum of local move-node deltas | +135 | +23 |
| Unchanged whole-root node count | 47 | 54 |
| Sum of whole-root node deltas | +35,007 | −55,782 |
| Changed final best move | 6 | 2 |

The nominal depth intervention frequently caused no measured additional local work. Existing TT reuse, pruning and child-depth adjustments can absorb a nominal ply; the audit does not isolate which mechanism explains each case. Changed root nodes or best moves do not establish better chess. Zero recoveries in this small, restricted sample are insufficient to estimate targeting advantage or reject every broader pawn-context policy. In particular, a zero-width empirical bootstrap interval would be misleading. This result provides **no support for selecting a production reduction coefficient or submitting this hypothesis to Fishtest**.

Full evidence is in `results/pawn-lmr-audit/`. Large raw logs/JSON are losslessly gzip-compressed for publication; the compression manifest records original and compressed SHA256 hashes, with decompressed equality checked before replacement. Restore them before using the frozen runners. No observations are discarded.

**Research-pass disposition:** six isolated implementation branches are preserved; four STC candidates rejected and two exact-output performance candidates lacked established speed gains. The second-pass witness, LMR reliability and pawn-context screens support no new production candidate. Cost-aware ordering remains an unexecuted diagnostic design, not a tested or exhausted hypothesis. There is no supported winning engine to build, no active Fishtest run, and no basis for LTC. An attempt to pause the recorded test follow-up returned that the automation no longer exists in the app (possibly deleted by the user); it was not recreated. No further submission is scheduled by this work. This closes the measured candidate set, not the broader question of improving Stockfish.
