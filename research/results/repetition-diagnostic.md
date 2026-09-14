# Runtime diagnostic: qsearch returns below a detected repetition draw

The suspected behavior is **observed**, including a one-node reproduction through normal UCI commands. This diagnostic applied no production patch and ran no Elo test. The lead's separate production validation is tracked in the [experiment ledger](../EXPERIMENTS.md).

The isolated diagnostic checkout is `/Users/acrystal/Desktop/Coding/Games/Stockfish/.research-tools/repetition-diagnostic`, detached at baseline `031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3`. Only this checkout's `src/search.cpp` was instrumented. All original search return expressions and TT writes remain intact. The default bench completed with the required **1,648,567-node signature**. This is the available check that instrumentation preserved deterministic baseline behavior; it does not certify every possible multithreaded or time-limited execution.

## Direct reproduction

Starting with `4k2q/8/8/8/8/8/8/R3K3 b - - 0 1`, the UCI position command supplied six legal moves:

```text
e8f8 e1f1 f8e8 f1e1 e8f8 e1f1
```

This leaves Black to move with its king on f8 and White's king on f1. The command `go depth 1 searchmoves f8e8` reaches the intended White-to-move qsearch node one ply below the root. White can play the quiet `f1e1`, reaching the starting board for a third occurrence across the supplied history. The engine accepted the position and move sequence, displayed the expected root FEN, and searched exactly one node. No direct qsearch harness or forced evaluation was needed.

The diagnostic captured:

```text
QREP_EVENT route=final pv=1 check=0 ply=1 pieces=4 rule50=7 alpha_in=-32001 beta_in=32001 alpha_now=-1 returned=-351 floor=-1 fen="4k2q/8/8/8/8/8/8/R4K2 w - - 7 5" path="f8e8 "
QREP_TOTAL detected=1 continued=1 tt_below=0 final_below=1 logged=1
```

Thus the existing repetition check set alpha to −1, the window remained open, and ordinary PV qsearch completion returned −351. The final ordinary TT write still executed with its original semantics. At the root the engine displayed `score cp 102 nodes 1` and `bestmove f8e8`. The root centipawn display and the internal −351 score are different scales; do not subtract them as if they shared units.

This demonstrates that the proposed floor would change this return to −1 and that the behavior is reachable with the standard UCI history/stack initialization. It does not show the patched engine's actual output, its choice among unrestricted root moves, or a changed game result. The first-six-moves setup and root `searchmoves` restriction were suggested by the orchestration agent to ensure the target position occurs at qsearch depth.

## Default bench observations

| Observation | Count |
|---|---:|
| Existing qsearch upcoming-repetition detections | 3,841 |
| Detections that did not close the window | 103 |
| Eligible TT returns below the remembered draw score | 9 |
| Ordinary final returns below the remembered draw score | 16 |
| Logged below-score events | 25 |

All 25 detailed events were retained; the configured cap was 64 per process. Two were PV final returns: −10 versus a sampled +1 in bench position 3, and −156 versus +1 in bench position 45. The other 23 events were NonPV, all with incoming window `(-1, 0)` and sampled draw −1. This is the exact draw-jitter corner predicted by the source analysis.

The events occurred in bench positions 3 and 45, with 6 and 19 events respectively. Four events were in check and 21 were outside check. By remaining piece count, the sample contains two events with two pieces, five with five pieces, sixteen with six pieces, and two with eight pieces. The benchmark mixes ordinary and artificial positions; this is evidence of reachability across its search tree, not an estimate of tournament frequency. In particular, the two bare-king events should not be used to infer chess strength or material-stratified Elo.

The earliest PV example at [bench log line 54](/Users/acrystal/Desktop/Coding/Games/Stockfish/research/results/repetition-diagnostic-bench.log:54) has input window `(-75, 48)`, current alpha +1, and final return −10. The second PV example at [line 813](/Users/acrystal/Desktop/Coding/Games/Stockfish/research/results/repetition-diagnostic-bench.log:813) has input window `(-137, 185)`, current alpha +1, and final return −156. Every event records the root-to-node move path; its preceding `Position:` line provides the benchmark root FEN. The JSON summary preserves those associations explicitly.

## Instrumentation and limits

The instrumentation calls no additional repetition probe. It records the already sampled `value_draw(nodes)` only when the original qsearch condition fires. It then observes eligible TT-cutoff returns and ordinary final returns. A counter records each event; detailed output stops after 64 events. Counter updates use atomics, but both authorized engine runs used one thread. Logging uses stderr. Move paths are read from the initialized search stack and rendered as UCI moves.

The TT observation occurs after baseline `value_from_tt()` conversion and existing validity/bound checks. It records the returned score, not the raw pre-conversion TT field or its individual bound flags. The final observation occurs after baseline fail-high smoothing and before the unchanged TT write. It does not count terminal draw, maximum-ply, stand-pat, or mate exits. Therefore the diagnostic matches the proposed ordinary-completion scope and does not establish a universal floor across terminal policy.

The additional logging and counters have overhead, and this was a non-PGO `make build` binary. Bench timing and NPS are not speed evidence and must not be compared with a production binary. The diagnostic did not modify alpha beyond the original repetition assignment, change scores, skip TT writes, change move ordering, or patch the production candidate. The exact diff is saved for inspection. The build succeeded; it emitted repeated Apple SDK/libc++ platform-support warnings, recorded in the build log. No compile failure occurred.

The evidence justifies implementing and locally checking the small candidate from `research/agents/07-repetition-endgames.md`. It provides no measured Elo improvement. The retained draw floor could still reduce useful fail-soft information or TT reuse. Existing entries and ancestors remain subject to graph-history interaction. Paired game testing, and longer-control verification if promising, remain necessary.

## Commands and artifacts

The bounded procedure was:

```sh
git worktree add --detach .research-tools/repetition-diagnostic 031dfeb437fa6b06cdbdf4ef89dfb82f6b83c4d3
```

The existing `src/nn-134a887f4c8f.nnue` file was copied into the detached checkout's `src` directory. The diagnostic diff was applied only there. From that `src` directory:

```sh
make -j2 build ARCH=apple-silicon COMP=clang
```

From the primary workspace:

```sh
python3 research/results/repetition-diagnostic-run.py
```

The saved runner executes the binary with the single argument `bench`, requires the exact signature, then performs the one depth-1 UCI seed search and quits. It uses timeouts of 60 seconds for bench, 15 seconds for UCI response stages, and 5 seconds for shutdown. The seed explicitly sets Threads 1, Hash 16, and SyzygyProbeLimit 0. Bench uses its defaults with the checkout's copied network.

Recorded SHA-256 identifiers:

| Artifact | SHA-256 |
|---|---|
| Instrumentation patch | `4feee0e7f5cfd32547e6ce81dbec865e48ed201b88500938aa8acf8c5faeec4d` |
| Bounded runner | `4f64e25fb6468047ca0f3c6d67fad6c5c289c8b224f003ae90eab808ef8d09f9` |
| Instrumented `src/stockfish` executable | `d642760d8728b709f52456a63f879ec83639bc033533a075c4e15e8074fa9378` |

The checkout's final `git status --short` reports only `M src/search.cpp`; its HEAD remains the pinned baseline. The source edit is uncommitted.

Artifacts in this directory:

* `repetition-diagnostic.patch`: exact observational source diff.
* `repetition-diagnostic-build.log`: complete compile output.
* `repetition-diagnostic-run.py`: reproducible bounded driver with exact arguments and UCI sequencing.
* `repetition-diagnostic-bench.log`: complete default bench output and diagnostic events.
* `repetition-diagnostic-seed.commands`: exact seed UCI commands.
* `repetition-diagnostic-seed.stdout.log` and `repetition-diagnostic-seed.stderr.log`: seed engine output and diagnostic record.
* `repetition-diagnostic-summary.json`: aggregate counts and all 25 benchmark events with root-position association.

CPU work ended immediately after the one bench and one seed search; the orchestration agent was notified before further report work. No match, remote write, branch modification, commit, production-source edit, extra engine run, or prolonged suite was performed.
